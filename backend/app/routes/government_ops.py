import re
from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import (
    ALERTS,
    AMBULANCES,
    GOVERNMENT_COMPLIANCE,
    GOVERNMENT_REPORTS,
    HOSPITALS,
    USERS,
)
from app.services.repository import MongoRepository

router = APIRouter(tags=["government-ops"])


class GovernmentReportCreate(BaseModel):
    title: str
    scope: str
    summary: str | None = None


class GovernmentComplianceCreate(BaseModel):
    hospitalId: str
    status: str
    findings: str | None = None
    owner: str | None = None


class GovernmentComplianceUpdate(BaseModel):
    status: str | None = None
    findings: str | None = None
    owner: str | None = None


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


def _format_location(hospital_doc: dict | None) -> str | None:
    if not hospital_doc:
        return None
    location = hospital_doc.get("location") if isinstance(hospital_doc.get("location"), dict) else {}
    city = location.get("city") or location.get("address")
    state = location.get("state")
    if city and state:
        return f"{city}, {state}"
    return city or None


def _build_search(search: str | None, fields: list[str]) -> dict[str, Any] | None:
    if not search:
        return None
    text = search.strip()
    if not text:
        return None
    escaped = re.escape(text)
    return {"$or": [{field: {"$regex": escaped, "$options": "i"}} for field in fields]}


def _build_sort(sort_by: str | None, sort_dir: str | None, allowed: set[str], fallback: str) -> list[tuple[str, int]]:
    field = sort_by if sort_by in allowed else fallback
    direction = 1 if (sort_dir or "").lower() == "asc" else -1
    return [(field, direction)]


def _get_user_display(user_doc: dict | None, hospital_doc: dict | None) -> dict:
    user_doc = user_doc or {}
    hp = user_doc.get("hospitalProfile", {}) if isinstance(user_doc, dict) else {}
    return {
        "name": hp.get("hospitalName") or user_doc.get("name") or (hospital_doc or {}).get("name") or "Unnamed Hospital",
        "location": hp.get("jurisdiction") or user_doc.get("location") or _format_location(hospital_doc) or "Unknown",
        "email": user_doc.get("email") or (hospital_doc or {}).get("email") or "",
        "phone": hp.get("contactNumber") or user_doc.get("phone") or (hospital_doc or {}).get("phone") or "",
    }


@router.get("/hospitals")
async def list_hospitals(
    search: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    hospital_repo = MongoRepository(db, HOSPITALS)
    user_repo = MongoRepository(db, USERS)

    hospitals = await hospital_repo.find_many({}, projection={"user": 1, "beds": 1, "location": 1})
    user_ids = []
    for h in hospitals:
        if h.get("user"):
            try:
                user_ids.append(_as_object_id(h.get("user")))
            except HTTPException:
                continue

    users = await user_repo.find_many({"_id": {"$in": user_ids}}) if user_ids else []
    user_map = {u.get("_id"): u for u in users}

    mapped = []
    for h in hospitals:
        user_doc = user_map.get(h.get("user"))
        disp = _get_user_display(user_doc, h)
        beds = h.get("beds") or {"totalBeds": 0, "occupiedBeds": 0, "availableBeds": 0}
        mapped.append(
            {
                "id": h.get("_id"),
                "name": disp["name"],
                "location": disp["location"],
                "email": disp["email"],
                "phone": disp["phone"],
                "beds": beds,
                "updatedAt": h.get("updatedAt"),
            }
        )

    if search:
        term = search.lower().strip()
        mapped = [
            item for item in mapped
            if term in str(item.get("name") or "").lower() or term in str(item.get("location") or "").lower()
        ]

    sort_fields = {"name", "location", "updatedAt", "availableBeds", "totalBeds"}
    if sort_by in sort_fields:
        reverse = (sort_dir or "").lower() != "asc"
        if sort_by == "availableBeds":
            mapped = sorted(mapped, key=lambda item: (item.get("beds") or {}).get("availableBeds", 0), reverse=reverse)
        elif sort_by == "totalBeds":
            mapped = sorted(mapped, key=lambda item: (item.get("beds") or {}).get("totalBeds", 0), reverse=reverse)
        else:
            mapped = sorted(mapped, key=lambda item: item.get(sort_by) or "", reverse=reverse)

    return {"count": len(mapped), "data": mapped}


@router.get("/emergencies")
async def list_emergencies(
    search: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    repo = MongoRepository(db, ALERTS)
    query: dict[str, Any] = {"status": {"$ne": "Resolved"}}
    search_query = _build_search(search, ["message", "locationDetails"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if severity:
        query["emergencyType"] = severity
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "emergencyType", "status"}, "createdAt")
    alerts = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(alerts), "data": alerts}


@router.get("/ambulances")
async def list_ambulances(
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    repo = MongoRepository(db, AMBULANCES)
    query: dict[str, Any] = {}
    search_query = _build_search(search, ["ambulanceId", "registrationNumber"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "ambulanceId", "status"}, "createdAt")
    docs = await repo.find_many(
        query,
        projection={
            "ambulanceId": 1,
            "registrationNumber": 1,
            "status": 1,
            "currentLocation": 1,
            "metrics": 1,
            "activeRoute": 1,
        },
        sort=sort,
    )
    return {"count": len(docs), "data": docs}


@router.get("/reports")
async def list_reports(
    search: str | None = Query(None),
    scope: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    repo = MongoRepository(db, GOVERNMENT_REPORTS)
    query: dict[str, Any] = {}
    search_query = _build_search(search, ["title", "summary"])
    if search_query:
        query.update(search_query)
    if scope:
        query["scope"] = scope
    if status:
        query["status"] = status
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "title", "status"}, "createdAt")
    reports = await repo.find_many(query, sort=sort, limit=100)
    return {"count": len(reports), "data": reports}


@router.post("/reports", status_code=201)
async def create_report(payload: GovernmentReportCreate):
    db = get_db()
    repo = MongoRepository(db, GOVERNMENT_REPORTS)

    doc = {
        "title": payload.title,
        "scope": payload.scope,
        "summary": payload.summary or "Automated report generated.",
        "status": "Ready",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    return created


@router.get("/compliance")
async def list_compliance(
    search: str | None = Query(None),
    status: str | None = Query(None),
    owner: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    repo = MongoRepository(db, GOVERNMENT_COMPLIANCE)
    query: dict[str, Any] = {}
    search_query = _build_search(search, ["hospitalId", "findings", "owner"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if owner:
        query["owner"] = owner
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "status", "hospitalId"}, "createdAt")
    items = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(items), "data": items}


@router.post("/compliance", status_code=201)
async def create_compliance(payload: GovernmentComplianceCreate):
    db = get_db()
    repo = MongoRepository(db, GOVERNMENT_COMPLIANCE)

    doc = {
        "hospitalId": payload.hospitalId,
        "status": payload.status,
        "findings": payload.findings,
        "owner": payload.owner,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    return created


@router.patch("/compliance/{item_id}")
async def update_compliance(item_id: str, payload: GovernmentComplianceUpdate):
    db = get_db()
    repo = MongoRepository(db, GOVERNMENT_COMPLIANCE)

    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    update_data["updatedAt"] = datetime.utcnow()

    updated = await repo.update_one({"_id": _as_object_id(item_id)}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Compliance item not found")
    return updated
