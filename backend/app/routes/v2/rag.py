from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_scopes
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.services.collections import ALERTS, HEALTH_RECORDS, HOSPITALS, PATIENTS
from app.services.rag.vector_store import reset_index, search as rag_search, upsert_documents
from app.services.repository import MongoRepository

router = APIRouter(tags=["rag"])


class RagIngestRequest(BaseModel):
    sources: list[str] | None = None
    limit_per_source: int | None = 200
    reset: bool | None = False


class RagSearchRequest(BaseModel):
    query: str
    top_k: int | None = None
    role: str | None = None
    user_id: str | None = None


def _hospital_content(doc: dict[str, Any]) -> str:
    location = doc.get("location") or {}
    parts = [
        f"Hospital {doc.get('name') or doc.get('hospital_name') or 'Unknown'}.",
        f"City: {location.get('city') or doc.get('city') or 'Unknown'}.",
        f"State: {location.get('state') or doc.get('state') or 'Unknown'}.",
    ]
    if location.get("address"):
        parts.append(f"Address: {location.get('address')}.")
    if doc.get("beds_total") is not None:
        parts.append(f"Total beds: {doc.get('beds_total')}.")
    return " ".join(parts)


def _patient_content(doc: dict[str, Any]) -> str:
    profile = doc.get("publicProfile") or {}
    health = profile.get("healthRecords") or {}
    parts = [
        f"Patient {doc.get('name') or 'Unknown'}.",
        f"Age: {health.get('age') or profile.get('age') or 'Unknown'}.",
        f"Blood group: {health.get('bloodGroup') or 'Unknown'}.",
    ]
    if health.get("conditions"):
        parts.append(f"Conditions: {health.get('conditions')}.")
    if health.get("allergies"):
        parts.append(f"Allergies: {health.get('allergies')}.")
    return " ".join(parts)


def _alert_content(doc: dict[str, Any]) -> str:
    parts = [
        f"Alert: {doc.get('message') or 'Unknown'}.",
        f"Severity: {doc.get('severity') or doc.get('priority') or 'Unknown'}.",
    ]
    if doc.get("location"):
        parts.append(f"Location: {doc.get('location')}.")
    return " ".join(parts)


def _health_record_content(doc: dict[str, Any]) -> str:
    parts = [
        f"Health record for patient {doc.get('patient_name') or doc.get('patientId') or 'Unknown'}.",
    ]
    if doc.get("diagnosis"):
        parts.append(f"Diagnosis: {doc.get('diagnosis')}.")
    if doc.get("notes"):
        parts.append(f"Notes: {doc.get('notes')}.")
    return " ".join(parts)


@router.post("/ingest")
async def ingest(payload: RagIngestRequest, ctx: AuthContext = Depends(require_scopes("ai:ask"))) -> dict:
    sources = payload.sources or ["hospitals", "patients", "alerts"]
    limit = payload.limit_per_source or 200

    if payload.reset:
        reset_index()

    db = get_db()
    docs: list[dict[str, Any]] = []

    if "hospitals" in sources:
        repo = MongoRepository(db, HOSPITALS)
        hospitals = await repo.find_many({}, limit=limit)
        for doc in hospitals:
            docs.append({
                "content": _hospital_content(doc),
                "metadata": {
                    "source": "hospitals",
                    "id": doc.get("_id"),
                    "title": doc.get("name") or doc.get("hospital_name") or "Hospital",
                    "roles": ["public", "hospital", "government", "ambulance"],
                },
            })

    if "patients" in sources:
        repo = MongoRepository(db, PATIENTS)
        patients = await repo.find_many({}, limit=limit)
        for doc in patients:
            docs.append({
                "content": _patient_content(doc),
                "metadata": {
                    "source": "patients",
                    "id": doc.get("_id"),
                    "title": doc.get("name") or "Patient",
                    "roles": ["hospital", "government"],
                },
            })

    if "alerts" in sources:
        repo = MongoRepository(db, ALERTS)
        alerts = await repo.find_many({}, limit=limit)
        for doc in alerts:
            docs.append({
                "content": _alert_content(doc),
                "metadata": {
                    "source": "alerts",
                    "id": doc.get("_id"),
                    "title": "Emergency alert",
                    "roles": ["public"],
                    "user_id": str(doc.get("user")) if doc.get("user") else None,
                },
            })

    if "health_records" in sources:
        repo = MongoRepository(db, HEALTH_RECORDS)
        records = await repo.find_many({}, limit=limit)
        for doc in records:
            docs.append({
                "content": _health_record_content(doc),
                "metadata": {
                    "source": "health_records",
                    "id": doc.get("_id"),
                    "title": doc.get("primary_category") or doc.get("diagnosis") or "Health record",
                    "roles": ["public"],
                    "user_id": str(doc.get("user")) if doc.get("user") else None,
                },
            })

    if not docs:
        raise HTTPException(status_code=400, detail="No documents found to ingest")

    result = upsert_documents(docs)
    return {"status": "ok", "result": result, "count": len(docs)}


@router.post("/search")
async def search(payload: RagSearchRequest, ctx: AuthContext = Depends(require_scopes("ai:ask"))) -> dict:
    term = payload.query.strip()
    if not term:
        raise HTTPException(status_code=400, detail="query is required")
    filters = {}
    if payload.role:
        filters["roles"] = [payload.role]
    if payload.user_id:
        filters["user_id"] = payload.user_id

    results = rag_search(term, top_k=payload.top_k, filters=filters)
    for item in results:
        metadata = item.get("metadata") or {}
        item["citation"] = {
            "source": metadata.get("source"),
            "id": str(metadata.get("id")) if metadata.get("id") else None,
            "title": metadata.get("title") or metadata.get("source"),
            "snippet": (item.get("content") or "")[:180],
        }
    return {"query": term, "results": results}
