from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_scopes
from app.core.dependencies import get_realtime_service
from app.db.mongo import get_db
from app.services.collections import MODULE_ALERTS, MODULE_AUTOMATIONS, MODULE_ITEMS
from app.services.realtime_service import RealtimeService
from app.services.repository import MongoRepository

router = APIRouter(tags=["modules"])


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


def _channel(module_key: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", module_key).strip("-").lower()
    return f"module-{slug}"


def _build_search_fields(search: str | None, fields: list[str]) -> dict[str, Any] | None:
    if not search:
        return None
    text = search.strip()
    if not text:
        return None
    escaped = re.escape(text)
    return {"$or": [{field: {"$regex": escaped, "$options": "i"}} for field in fields]}


def _build_search(search: str | None) -> dict[str, Any] | None:
    return _build_search_fields(search, ["title", "summary", "description"])


def _build_sort(sort_by: str | None, sort_dir: str | None, allowed: set[str], fallback: str) -> list[tuple[str, int]]:
    field = sort_by if sort_by in allowed else fallback
    direction = 1 if (sort_dir or "").lower() == "asc" else -1
    return [(field, direction)]


def _emit(realtime: RealtimeService, module_key: str, entity: str, action: str, record: dict) -> None:
    event = {
        "type": "module_update",
        "moduleKey": module_key,
        "entity": entity,
        "action": action,
        "record": record,
        "timestamp": datetime.utcnow().isoformat(),
    }
    channel = _channel(module_key)
    # Fire-and-forget; no await in sync helper
    return realtime.manager.broadcast(channel, {"channel": channel, "payload": event})


@router.get("/{module_key}/items")
async def list_items(
    module_key: str,
    search: str | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    owner_id: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, MODULE_ITEMS)

    query: dict[str, Any] = {"moduleKey": module_key}
    search_query = _build_search(search)
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if owner_id:
        query["ownerId"] = owner_id

    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "priority", "status", "title"}, "createdAt")
    items = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(items), "data": items}


@router.post("/{module_key}/items", status_code=201)
async def create_item(
    module_key: str,
    payload: dict,
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    title = payload.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    db = get_db()
    repo = MongoRepository(db, MODULE_ITEMS)

    doc = {
        "moduleKey": module_key,
        "title": title,
        "summary": payload.get("summary") or "",
        "description": payload.get("description") or "",
        "status": payload.get("status") or "Open",
        "priority": payload.get("priority") or "Medium",
        "ownerId": payload.get("ownerId"),
        "tags": payload.get("tags") or [],
        "metrics": payload.get("metrics") or {},
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    realtime = get_realtime_service()
    await realtime.broadcast(_channel(module_key), {"channel": _channel(module_key), "payload": {
        "type": "module_update",
        "moduleKey": module_key,
        "entity": "items",
        "action": "create",
        "record": created,
        "timestamp": datetime.utcnow().isoformat(),
    }})
    return created


@router.patch("/{module_key}/items/{item_id}")
async def update_item(
    module_key: str,
    item_id: str,
    payload: dict,
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, MODULE_ITEMS)

    update_data = {k: v for k, v in payload.items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    update_data["updatedAt"] = datetime.utcnow()

    updated = await repo.update_one({"_id": _as_object_id(item_id), "moduleKey": module_key}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Item not found")

    realtime = get_realtime_service()
    await realtime.broadcast(_channel(module_key), {"channel": _channel(module_key), "payload": {
        "type": "module_update",
        "moduleKey": module_key,
        "entity": "items",
        "action": "update",
        "record": updated,
        "timestamp": datetime.utcnow().isoformat(),
    }})
    return updated


@router.delete("/{module_key}/items/{item_id}")
async def delete_item(
    module_key: str,
    item_id: str,
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, MODULE_ITEMS)

    deleted = await repo.delete_by_id(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")

    realtime = get_realtime_service()
    await realtime.broadcast(_channel(module_key), {"channel": _channel(module_key), "payload": {
        "type": "module_update",
        "moduleKey": module_key,
        "entity": "items",
        "action": "delete",
        "record": {"_id": item_id},
        "timestamp": datetime.utcnow().isoformat(),
    }})
    return {"status": "deleted"}


@router.get("/{module_key}/alerts")
async def list_alerts(
    module_key: str,
    search: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, MODULE_ALERTS)
    query: dict[str, Any] = {"moduleKey": module_key}
    search_query = _build_search_fields(search, ["message"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "severity", "status"}, "createdAt")
    alerts = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(alerts), "data": alerts}


@router.post("/{module_key}/alerts", status_code=201)
async def create_alert(
    module_key: str,
    payload: dict,
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    if not payload.get("message"):
        raise HTTPException(status_code=400, detail="message is required")

    db = get_db()
    repo = MongoRepository(db, MODULE_ALERTS)

    doc = {
        "moduleKey": module_key,
        "message": payload.get("message"),
        "severity": payload.get("severity") or "Medium",
        "status": payload.get("status") or "Open",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    realtime = get_realtime_service()
    await realtime.broadcast(_channel(module_key), {"channel": _channel(module_key), "payload": {
        "type": "module_update",
        "moduleKey": module_key,
        "entity": "alerts",
        "action": "create",
        "record": created,
        "timestamp": datetime.utcnow().isoformat(),
    }})
    return created


@router.patch("/{module_key}/alerts/{alert_id}")
async def update_alert(
    module_key: str,
    alert_id: str,
    payload: dict,
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, MODULE_ALERTS)

    update_data = {k: v for k, v in payload.items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    update_data["updatedAt"] = datetime.utcnow()

    updated = await repo.update_one({"_id": _as_object_id(alert_id), "moduleKey": module_key}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")

    realtime = get_realtime_service()
    await realtime.broadcast(_channel(module_key), {"channel": _channel(module_key), "payload": {
        "type": "module_update",
        "moduleKey": module_key,
        "entity": "alerts",
        "action": "update",
        "record": updated,
        "timestamp": datetime.utcnow().isoformat(),
    }})
    return updated


@router.get("/{module_key}/automations")
async def list_automations(
    module_key: str,
    search: str | None = Query(None),
    enabled: bool | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, MODULE_AUTOMATIONS)
    query: dict[str, Any] = {"moduleKey": module_key}
    search_query = _build_search_fields(search, ["name", "trigger", "action"])
    if search_query:
        query.update(search_query)
    if enabled is not None:
        query["enabled"] = enabled
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "name", "enabled"}, "createdAt")
    automations = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(automations), "data": automations}


@router.post("/{module_key}/automations", status_code=201)
async def create_automation(
    module_key: str,
    payload: dict,
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    db = get_db()
    repo = MongoRepository(db, MODULE_AUTOMATIONS)

    doc = {
        "moduleKey": module_key,
        "name": name,
        "trigger": payload.get("trigger") or "On Update",
        "action": payload.get("action") or "Notify Team",
        "enabled": payload.get("enabled", True),
        "lastRun": None,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    realtime = get_realtime_service()
    await realtime.broadcast(_channel(module_key), {"channel": _channel(module_key), "payload": {
        "type": "module_update",
        "moduleKey": module_key,
        "entity": "automations",
        "action": "create",
        "record": created,
        "timestamp": datetime.utcnow().isoformat(),
    }})
    return created


@router.patch("/{module_key}/automations/{automation_id}")
async def update_automation(
    module_key: str,
    automation_id: str,
    payload: dict,
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, MODULE_AUTOMATIONS)

    update_data = {k: v for k, v in payload.items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    update_data["updatedAt"] = datetime.utcnow()

    updated = await repo.update_one({"_id": _as_object_id(automation_id), "moduleKey": module_key}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Automation not found")

    realtime = get_realtime_service()
    await realtime.broadcast(_channel(module_key), {"channel": _channel(module_key), "payload": {
        "type": "module_update",
        "moduleKey": module_key,
        "entity": "automations",
        "action": "update",
        "record": updated,
        "timestamp": datetime.utcnow().isoformat(),
    }})
    return updated


@router.get("/{module_key}/analytics")
async def analytics(
    module_key: str,
    ctx=Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, MODULE_ITEMS)

    items = await repo.find_many({"moduleKey": module_key}, limit=500)

    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for item in items:
        status = item.get("status") or "Open"
        priority = item.get("priority") or "Medium"
        by_status[status] = by_status.get(status, 0) + 1
        by_priority[priority] = by_priority.get(priority, 0) + 1

    today = datetime.utcnow().date()
    timeline = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = 0
        for item in items:
            created_at = item.get("createdAt")
            if not created_at:
                continue
            try:
                created_date = datetime.fromisoformat(str(created_at)).date()
            except ValueError:
                continue
            if created_date == day:
                count += 1
        timeline.append({"label": day.isoformat(), "value": count})

    return {
        "summary": {
            "total": len(items),
            "open": by_status.get("Open", 0),
            "critical": by_priority.get("Critical", 0),
        },
        "series": {
            "byStatus": [{"label": k, "value": v} for k, v in by_status.items()],
            "byPriority": [{"label": k, "value": v} for k, v in by_priority.items()],
            "timeline": timeline,
        },
    }


@router.post("/{module_key}/ai")
async def ai_insights(
    module_key: str,
    payload: dict,
    ctx=Depends(require_scopes("ai:ask")),
) -> dict:
    text = " ".join(
        str(payload.get(k) or "")
        for k in ("title", "summary", "description", "text")
    ).lower()

    severity = "Low"
    confidence = 0.62
    if any(term in text for term in ["critical", "cardiac", "collapse", "bleeding", "stroke"]):
        severity = "Critical"
        confidence = 0.92
    elif any(term in text for term in ["severe", "accident", "trauma", "emergency"]):
        severity = "High"
        confidence = 0.86
    elif any(term in text for term in ["moderate", "delay", "overdue"]):
        severity = "Medium"
        confidence = 0.74

    recommendation = "Monitor and continue standard operations."
    if severity == "Critical":
        recommendation = "Trigger escalation workflow and notify leadership."
    elif severity == "High":
        recommendation = "Prioritize this case and allocate resources."

    meta = {
        "confidence": confidence,
        "reasoning": [
            "Classification derived from keyword cues in submitted text.",
            "Confidence reflects heuristic weighting for critical terms.",
        ],
        "references": [
            {"title": "Heuristic", "detail": "Rule-based classifier in modules.ai_insights"},
        ],
    }

    return {
        "moduleKey": module_key,
        "classification": severity,
        "confidence": confidence,
        "recommendation": recommendation,
        "anomaly_score": round((1 - confidence) * 100, 2),
        "actions": [
            "Notify on-call team",
            "Update dashboard priority",
            "Log audit entry",
        ],
        "meta": meta,
    }
