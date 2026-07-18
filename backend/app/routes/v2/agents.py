from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user, get_optional_user, require_scopes
from app.core.rbac import AuthContext
from app.core.dependencies import get_ai_chat_service, get_routing_service, get_weather_service
from app.db.mongo import get_db
from app.services.agents.orchestrator import run_decision_workflow
from app.services.agents.memory_store import append_log, create_session, ensure_session, get_session, update_session
from app.services.ai_chat_service import AiChatService
from app.services.collections import ALERTS, DONATIONS, HOSPITALS, RESOURCE_REQUESTS, USERS
from app.services.rag.vector_store import search
from app.services.agents.llm_client import generate_text
from app.core.celery_app import celery_app
from app.services.repository import MongoRepository
from app.services.routing_service import RoutingService
from app.services.weather_service import WeatherService

router = APIRouter(tags=["agents"])


class AgentEvent(BaseModel):
    event: dict
    memoryId: str | None = None
    execute: bool | None = True


class AskRequest(BaseModel):
    query: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    memoryId: str | None = None
    supervised: bool | None = True
    mode: str | None = None
    module: str | None = None
    web_search: bool | None = None
    regenerate: bool | None = None
    attachments: list[dict] | None = None


class ChatSessionCreate(BaseModel):
    title: str | None = None
    module: str | None = None
    mode: str | None = None


def _hospital_intent(query: str) -> bool:
    text = query.lower()
    return any(keyword in text for keyword in ["hospital", "emergency", "icu", "ambulance", "cardiac"])


def _donor_intent(query: str) -> bool:
    text = query.lower()
    return any(keyword in text for keyword in ["donor", "donors", "blood", "donation", "plasma"])


def _extract_coords(doc: dict) -> tuple[float, float] | None:
    location = doc.get("location") or {}
    for key_pair in (("lat", "lng"), ("latitude", "longitude")):
        if key_pair[0] in doc and key_pair[1] in doc:
            try:
                return float(doc[key_pair[0]]), float(doc[key_pair[1]])
            except (TypeError, ValueError):
                return None
    if isinstance(location, dict) and "lat" in location and "lng" in location:
        try:
            return float(location["lat"]), float(location["lng"])
        except (TypeError, ValueError):
            return None
    return None


def _extract_coords(doc: dict) -> tuple[float, float] | None:
    location = doc.get("location") or {}
    for key_pair in (("lat", "lng"), ("latitude", "longitude")):
        if key_pair[0] in doc and key_pair[1] in doc:
            try:
                return float(doc[key_pair[0]]), float(doc[key_pair[1]])
            except (TypeError, ValueError):
                return None
    if isinstance(location, dict) and "lat" in location and "lng" in location:
        try:
            return float(location["lat"]), float(location["lng"])
        except (TypeError, ValueError):
            return None
    return None


def _needs_clarification(query: str) -> bool:
    tokens = [token for token in query.strip().split() if token]
    if len(tokens) <= 2:
        return True
    if len(query.strip()) < 8:
        return True
    return False


def _build_attachment_context(attachments: list[dict]) -> tuple[str, list[dict]]:
    if not attachments:
        return "", []

    summaries = []
    cleaned = []
    total_text = 0
    for attachment in attachments:
        name = str(attachment.get("name") or "attachment")
        content_type = str(attachment.get("type") or "application/octet-stream")
        size = int(attachment.get("size") or 0)
        text = attachment.get("text")
        snippet = ""
        if isinstance(text, str) and text.strip():
            snippet = text.strip()[:2000]
            total_text += len(snippet)
        summaries.append(
            {
                "name": name,
                "type": content_type,
                "size": size,
                "has_text": bool(snippet),
            }
        )
        cleaned.append(
            {
                "name": name,
                "type": content_type,
                "size": size,
                "text": snippet,
            }
        )
        if total_text >= 6000:
            break

    lines = ["Attachments:"]
    for item in cleaned:
        lines.append(f"- {item['name']} ({item['type']}, {item['size']} bytes)")
        if item.get("text"):
            lines.append(f"  Content snippet: {item['text']}")
    return "\n".join(lines), summaries


class _DDGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict] = []
        self._capture = False
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attr_map = dict(attrs)
        if "result__a" in (attr_map.get("class") or ""):
            self._capture = True
            self._href = attr_map.get("href")
            self._text = []

    def handle_data(self, data):
        if self._capture:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._capture:
            title = "".join(self._text).strip()
            if title and self._href:
                self.results.append({"title": title, "url": self._href})
            self._capture = False
            self._href = None
            self._text = []


def _web_search(query: str, limit: int = 5) -> list[dict]:
    if not query:
        return []
    try:
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=6) as response:
            html = response.read().decode("utf-8", "ignore")
        parser = _DDGParser()
        parser.feed(html)
        return parser.results[:limit]
    except Exception:
        return []


def _compute_confidence(context_len: int, web_count: int, attachment_count: int, regenerated: bool) -> float:
    score = 0.58
    if context_len:
        score += min(0.18, (context_len / 2000) * 0.18)
    if web_count:
        score += min(0.12, web_count * 0.03)
    if attachment_count:
        score += 0.05
    if regenerated:
        score += 0.03
    return round(min(0.95, max(0.2, score)), 2)


@router.post("/decision")
async def decision(payload: AgentEvent, ctx: AuthContext = Depends(require_scopes("emergency:trigger"))) -> dict:
    session = None
    if payload.memoryId:
        session = get_session(payload.memoryId)
    if not session:
        session = create_session({"createdBy": ctx.user_id})

    event_payload = {**payload.event, "execute": payload.execute}
    result = run_decision_workflow(event_payload, memory_id=session["id"])
    update_session(session["id"], result)
    append_log(session["id"], {"type": "decision", "by": ctx.user_id})
    return {"requestedBy": ctx.user_id, "memoryId": session["id"], "result": result}


@router.post("/workflow")
async def workflow(payload: AgentEvent, ctx: AuthContext = Depends(require_scopes("emergency:trigger"))) -> dict:
    session = None
    if payload.memoryId:
        session = get_session(payload.memoryId)
    if not session:
        session = create_session({"createdBy": ctx.user_id})

    event_payload = {**payload.event, "execute": payload.execute}
    result = run_decision_workflow(event_payload, memory_id=session["id"])
    update_session(session["id"], result)
    append_log(session["id"], {"type": "workflow", "by": ctx.user_id})
    return {"requestedBy": ctx.user_id, "memoryId": session["id"], "result": result}


@router.get("/memory/{memory_id}")
async def memory(memory_id: str, ctx: AuthContext = Depends(require_scopes("emergency:trigger"))) -> dict:
    session = get_session(memory_id)
    if not session:
        raise HTTPException(status_code=404, detail="Memory session not found")
    return {"memory": session}


@router.get("/chat/sessions")
async def list_chat_sessions(
    ctx: AuthContext = Depends(get_current_user),
    chat_service: AiChatService = Depends(get_ai_chat_service),
) -> dict:
    sessions = await chat_service.list_sessions(ctx.user_id)
    return {"sessions": sessions}


@router.post("/chat/sessions")
async def create_chat_session(
    payload: ChatSessionCreate,
    ctx: AuthContext = Depends(get_current_user),
    chat_service: AiChatService = Depends(get_ai_chat_service),
) -> dict:
    title = (payload.title or "New chat").strip() or "New chat"
    session = await chat_service.create_session(
        ctx.user_id,
        title=title,
        module=(payload.module or "general").lower(),
        mode=(payload.mode or "chat").lower(),
    )
    ensure_session(session["id"], {"createdBy": ctx.user_id})
    return {"session": session}


@router.get("/chat/sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    ctx: AuthContext = Depends(get_current_user),
    chat_service: AiChatService = Depends(get_ai_chat_service),
) -> dict:
    session = await chat_service.get_session_with_messages(ctx.user_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"session": session}


@router.post("/ask")
async def ask(
    payload: AskRequest,
    ctx: AuthContext | None = Depends(get_optional_user),
    chat_service: AiChatService = Depends(get_ai_chat_service),
    routing: RoutingService = Depends(get_routing_service),
    weather: WeatherService = Depends(get_weather_service),
) -> dict:
    question = (payload.query or "").strip()
    attachments = payload.attachments or []
    mode = (payload.mode or ("agent" if payload.supervised else "chat")).lower()
    is_agent_mode = mode == "agent"
    module = (payload.module or "general").lower()
    web_search = bool(payload.web_search)
    regenerate = bool(payload.regenerate)
    attachments_context, attachment_summaries = _build_attachment_context(attachments)
    if not question and not attachments_context:
        raise HTTPException(status_code=400, detail="query is required")

    requester_id = ctx.user_id if ctx else "guest"
    role = ctx.role if ctx else "public"

    memory_id = payload.memoryId
    session = get_session(memory_id) if memory_id else None

    if not session:
        if memory_id:
            session = ensure_session(memory_id, {"createdBy": requester_id})
        else:
            session = create_session({"createdBy": requester_id})
            memory_id = session["id"]

    persisted_session = None
    if ctx and memory_id:
        persisted_session = await chat_service.get_session_summary(ctx.user_id, memory_id)
        if not persisted_session:
            persisted_session = await chat_service.create_session(
                ctx.user_id,
                title="New chat",
                module=module,
                mode=mode,
                session_id=memory_id,
            )

    history_context = "No prior context."
    if ctx and memory_id:
        recent_messages = await chat_service.get_recent_messages(ctx.user_id, memory_id, limit=6)
        recent_turns = []
        for entry in recent_messages:
            role_name = "Assistant" if entry.get("role") == "assistant" else "User"
            recent_turns.append(f"{role_name}: {entry.get('content')}")
        if recent_turns:
            history_context = "\n".join(recent_turns)
    else:
        history = session.get("log") or []
        recent_turns = []
        for entry in history[-6:]:
            if entry.get("type") == "ask":
                recent_turns.append(f"User: {entry.get('query')}")
                recent_turns.append(f"Assistant: {entry.get('answer')}")
        history_context = "\n".join(recent_turns) if recent_turns else "No prior context."

    regen_count = len([entry for entry in (session.get("log") or []) if entry.get("type") == "regenerate"])
    learning_note = f"Regenerated {regen_count} time(s) based on user feedback." if regen_count else "No recent corrections."
    if regenerate:
        append_log(session["id"], {"type": "regenerate", "by": requester_id, "query": question})

    actions = []
    answer = None

    if _needs_clarification(question) and not attachments_context and not _donor_intent(question) and not _hospital_intent(question):
        clarifying = [
            "What specific information or outcome do you need?",
            "Which location, timeframe, or entity should I focus on?",
            "Do you want a summary, report, or chart?",
        ]
        append_log(session["id"], {"type": "clarify", "by": requester_id, "query": question})
        if ctx and memory_id:
            await chat_service.add_message(
                ctx.user_id,
                memory_id,
                role="user",
                content=question,
                payload={"attachments": attachment_summaries, "module": module, "mode": mode},
            )
            await chat_service.add_message(
                ctx.user_id,
                memory_id,
                role="assistant",
                content="I can help, but I need a bit more detail to proceed.",
                payload={"clarifying": clarifying, "needsClarification": True},
            )
            if persisted_session and persisted_session.get("title") == "New chat":
                await chat_service.update_title(ctx.user_id, memory_id, question[:32])
            persisted_session = await chat_service.get_session_summary(ctx.user_id, memory_id)
        return {
            "requestedBy": requester_id,
            "memoryId": memory_id,
            "answer": "I can help, but I need a bit more detail to proceed.",
            "needs_clarification": True,
            "clarifying_questions": clarifying,
            "actions": [],
            "metadata": {},
            "generatedAt": datetime.utcnow().isoformat(),
            "session": persisted_session,
        }

    if not question:
        question = "Analyze the provided attachments and return key insights."

    if ctx and memory_id:
        await chat_service.add_message(
            ctx.user_id,
            memory_id,
            role="user",
            content=question,
            payload={"attachments": attachment_summaries, "module": module, "mode": mode},
        )
        if persisted_session and persisted_session.get("title") == "New chat":
            await chat_service.update_title(ctx.user_id, memory_id, question[:32])

    if _hospital_intent(question) and payload.latitude is not None and payload.longitude is not None:
        db = get_db()
        repo = MongoRepository(db, HOSPITALS)
        hospitals = await repo.find_many({}, limit=200)
        candidates = []
        for doc in hospitals:
            coords = _extract_coords(doc)
            if not coords:
                continue
            distance_km = routing.haversine_km(payload.latitude, payload.longitude, coords[0], coords[1])
            if distance_km > 60:
                continue
            rating = float(doc.get("rating") or 4.2)
            candidates.append({
                "emergency_type": "medical_emergency",
                "distance_km": round(distance_km, 2),
                "traffic_level": 3,
                "hospital_rating": rating,
                "name": doc.get("name") or doc.get("hospital_name") or "Hospital",
                "id": doc.get("_id"),
            })

        celery_app.send_task("system.generate_predictions", args=["predict_recommend", candidates])
        ranked = sorted(candidates, key=lambda item: item.get("distance_km") or 9999) if candidates else []
        best = ranked[0] if ranked else None
        if best:
            answer = f"Best nearby hospital: {best.get('name')} (~{best.get('distance_km')} km)."
            actions.append({"type": "hospital_rank", "best": best, "ranked": ranked[:5]})

    if answer is None and _donor_intent(question):
        db = get_db()
        user_repo = MongoRepository(db, USERS)
        donors = await user_repo.find_many(
            {"role": "public"},
            projection={"name": 1, "location": 1, "phone": 1, "publicProfile": 1},
            limit=120,
        )
        candidates = []
        for donor in donors:
            health = (donor.get("publicProfile") or {}).get("healthRecords") or {}
            donor_profile = (donor.get("publicProfile") or {}).get("donorProfile") or {}
            coords = _extract_coords(donor) or _extract_coords(health)
            distance_km = None
            if coords and payload.latitude is not None and payload.longitude is not None:
                distance_km = routing.haversine_km(payload.latitude, payload.longitude, coords[0], coords[1])
            candidates.append({
                "id": donor.get("_id"),
                "name": donor.get("name"),
                "location": donor.get("location") or health.get("location") or "Unknown",
                "blood_group": donor_profile.get("bloodGroup") or health.get("bloodGroup"),
                "availability": donor_profile.get("availability") or "Available",
                "phone": donor.get("phone") or "Not available",
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
            })
        if payload.latitude is not None and payload.longitude is not None:
            candidates = sorted(candidates, key=lambda item: item.get("distance_km") or 9999)
        top = candidates[:6]
        if top:
            header = (
                "Here are the top matching donors from the registry:"
                if payload.latitude is not None
                else "Here are donors from the registry:"
            )
            lines = [header]
            for idx, donor in enumerate(top, start=1):
                distance = f"{donor['distance_km']} km" if donor.get("distance_km") is not None else "distance unknown"
                group = donor.get("blood_group") or "Unknown"
                lines.append(
                    f"{idx}. {donor.get('name') or 'Donor'} ({group}) - {donor.get('location') or 'Unknown'} ({distance})"
                )
            answer = "\n".join(lines)
            actions.append({"type": "donor_list", "count": len(top), "donors": top})

    contexts = []
    context_text = "No additional context found."
    if ctx:
        role_filter = [role] if role else []
        contexts = search(question or "overview", filters={"roles": role_filter, "user_id": ctx.user_id, "module": module})
        context_text = "\n".join(item.get("content", "") for item in contexts) or "No additional context found."

    web_results = _web_search(question, limit=5) if web_search else []
    web_context = "\n".join([f"{item['title']} - {item['url']}" for item in web_results])
    if not web_context:
        web_context = "No web results." if web_search else "Web search disabled."

    db = get_db()
    user_repo = MongoRepository(db, USERS)
    hospital_repo = MongoRepository(db, HOSPITALS)
    alert_repo = MongoRepository(db, ALERTS)
    request_repo = MongoRepository(db, RESOURCE_REQUESTS)
    donation_repo = MongoRepository(db, DONATIONS)
    users_total = await user_repo.collection.count_documents({})
    users_by_role = {}
    for role_name in ("public", "hospital", "ambulance", "government"):
        users_by_role[role_name] = await user_repo.collection.count_documents({"role": role_name})
    metadata = {
        "users_total": users_total,
        "users_by_role": users_by_role,
        "hospitals_total": await hospital_repo.collection.count_documents({}),
        "alerts_total": await alert_repo.collection.count_documents({}),
        "requests_total": await request_repo.collection.count_documents({}),
        "donations_total": await donation_repo.collection.count_documents({}),
    }

    metadata_summary = (
        f"Users total: {metadata['users_total']}, hospitals: {metadata['hospitals_total']}, "
        f"alerts: {metadata['alerts_total']}, requests: {metadata['requests_total']}, donations: {metadata['donations_total']}."
    )

    if answer is None:
        try:
            answer = generate_text(
                prompt=(
                    f"Question: {question}\n"
                    f"Module focus: {module}\n"
                    f"Conversation history:\n{history_context}\n"
                    f"{attachments_context}\n"
                    f"Context:\n{context_text}\n"
                    f"Metadata overview: {metadata_summary}\n"
                    f"Web results:\n{web_context}\n"
                    "Instructions: Answer the user's question clearly and directly. "
                    "Begin with a concise, plain-language response that directly addresses the request. "
                    "Then, if helpful, add a brief list of 2-3 recommended next steps or actions. "
                    "Do not open with raw statistics, web-result dumps, or platform summaries. "
                    "Use metadata and web sources only when they actually support the answer. "
                    "If you mention a web source, use a descriptive site name or domain and do not print the long raw URL in the answer body. "
                    "If the question is ambiguous, ask one clarifying question after providing your best guidance."
                ),
                system_prompt=(
                    "You are LifeLink Assist, a high-quality healthcare operations assistant. "
                    "Write in a natural, conversational style similar to modern AI assistants. "
                    "Use LifeLink context and public sources to make the answer useful, but keep the user's question front and center. "
                    "Avoid generic fallback language and do not return raw metadata as the main answer."
                ),
            )
        except Exception as exc:
            error_text = str(exc)
            context_lines = [line.strip() for line in (context_text or '').splitlines() if line.strip()]
            context_preview = " ".join(context_lines[:2]) if context_lines else "No stored context found."
            attachment_note = "Attachments received." if attachments else "No attachments provided."
            web_note = f"Web results: {len(web_results)} source(s)." if web_results else "Web search disabled or unavailable."
            if "not configured" in error_text.lower() or "api key" in error_text.lower():
                answer = (
                    "The AI assistant cannot generate responses because the backend LLM provider is not configured correctly. "
                    "Please verify your OPENAI_API_KEY or GROQ_API_KEY and LLM_PROVIDER settings, then retry."
                )
            else:
                answer = (
                    "I could not generate a complete answer right now. "
                    f"Context: {context_preview} "
                    f"{attachment_note} "
                    f"{web_note} "
                    f"Metadata: {metadata_summary}. "
                    "Please try again or ask a more specific question."
                )

    wants_visuals = any(token in (question or "").lower() for token in ["report", "summary", "analysis", "trend", "chart", "graph", "dashboard"]) or bool(attachments)
    charts = []
    report = None
    if wants_visuals:
        charts.append(
            {
                "title": "Users by role",
                "type": "bar",
                "data": [{"label": key, "value": value} for key, value in users_by_role.items()],
            }
        )
        report = {
            "title": "LifeLink AI Report",
            "summary": answer,
            "highlights": [
                f"Users: {metadata['users_total']}",
                f"Hospitals: {metadata['hospitals_total']}",
                f"Alerts: {metadata['alerts_total']}",
                f"Requests: {metadata['requests_total']}",
                f"Donations: {metadata['donations_total']}",
            ],
        }

    orchestration = None
    if is_agent_mode:
        event_payload = {
            "query": question,
            "attachments": attachment_summaries,
            "execute": False,
        }
        workflow = run_decision_workflow(event_payload, memory_id=session["id"])
        orchestration = {
            "mode": "supervised",
            "notes": workflow.get("notes", []),
            "actions": workflow.get("actions", []),
            "requires_confirmation": True,
        }

    reasoning = []
    if context_text and context_text != "No additional context found.":
        reasoning.append("Used indexed LifeLink context relevant to the query.")
    if web_results:
        reasoning.append("Referenced available public web sources for additional evidence.")
    if not reasoning:
        reasoning.append("Answered using available LifeLink context and metadata.")

    references = [
        {"title": "Internal metadata", "detail": "Aggregated LifeLink metadata and operational context."},
        {"title": "Knowledge base", "detail": "Context retrieved from indexed summaries."},
    ]
    if web_results:
        references.extend(
            {
                "title": item.get("title") or "Web source",
                "detail": item.get("url") or item.get("title") or "Unknown source",
                "url": item.get("url"),
            }
            for item in web_results
        )

    confidence = _compute_confidence(len(context_text), len(web_results), len(attachments), regenerate)
    follow_up = "If you want more detail or a related insight, ask me another question."

    append_log(session["id"], {"type": "ask", "by": requester_id, "query": question, "answer": answer})
    update_session(session["id"], {"last_query": question, "last_answer": answer})

    if ctx and memory_id:
        await chat_service.add_message(
            ctx.user_id,
            memory_id,
            role="assistant",
            content=answer,
            payload={
                "sourceQuery": question,
                "confidence": confidence,
                "webResults": web_results,
                "report": report,
                "charts": charts,
                "references": references,
                "reasoning": reasoning,
                "clarifying": [],
                "orchestration": orchestration,
                "metadata": metadata,
                "module": module,
                "mode": mode,
                "followUp": follow_up,
            },
        )
        persisted_session = await chat_service.get_session_summary(ctx.user_id, memory_id)

    return {
        "requestedBy": requester_id,
        "memoryId": memory_id,
        "answer": answer,
        "contextUsed": contexts,
        "web_results": web_results,
        "actions": actions,
        "metadata": metadata,
        "report": report,
        "charts": charts,
        "reasoning": reasoning,
        "references": references,
        "orchestration": orchestration,
        "confidence": confidence,
        "followUp": follow_up,
        "mode": mode,
        "generatedAt": datetime.utcnow().isoformat(),
        "session": persisted_session,
    }
