from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from faker import Faker
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.auth import get_optional_user, require_roles, require_scopes
from app.core.dependencies import get_hospital_service, get_routing_service
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.services.collections import ANALYTICS_EVENTS, HOSPITALS, HOSPITAL_WAIT_TIMES, RESOURCES
from app.services.hospital_service import HospitalService
from app.services.repository import MongoRepository
from app.services.routing_service import RoutingService

router = APIRouter(tags=["hospital"])


class WaitTimeReport(BaseModel):
    hospital_id: str
    wait_time_minutes: int
    reported_by: str | None = None


def _parse_float(value: float, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}") from exc


def _extract_coords(doc: dict[str, Any]) -> tuple[float, float] | None:
    for key_pair in (("lat", "lng"), ("latitude", "longitude")):
        if key_pair[0] in doc and key_pair[1] in doc:
            try:
                return float(doc[key_pair[0]]), float(doc[key_pair[1]])
            except (TypeError, ValueError):
                return None
    location = doc.get("location") or {}
    if isinstance(location, dict) and "lat" in location and "lng" in location:
        try:
            return float(location["lat"]), float(location["lng"])
        except (TypeError, ValueError):
            return None
    return None


async def _ensure_hospital_locations(db, center_lat: float, center_lng: float) -> int:
    repo = MongoRepository(db, HOSPITALS)
    existing = await repo.collection.find_one(
        {"$or": [{"lat": {"$exists": True}}, {"location.lat": {"$exists": True}}, {"latitude": {"$exists": True}}]}
    )
    if existing:
        return 0

    docs = await repo.collection.find({}).to_list(length=500)
    if not docs:
        return 0

    faker = Faker()
    updates = 0
    for doc in docs:
        if _extract_coords(doc):
            continue
        lat_offset = random.uniform(-0.25, 0.25)
        lng_offset = random.uniform(-0.25, 0.25)
        lat = center_lat + lat_offset
        lng = center_lng + lng_offset
        location = {
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "address": faker.street_address(),
            "city": faker.city(),
            "state": faker.state(),
        }
        await repo.collection.update_one({"_id": doc["_id"]}, {"$set": {"location": location}})
        updates += 1
    return updates


async def _seed_hospitals(db, center_lat: float, center_lng: float, count: int = 25) -> int:
    repo = MongoRepository(db, HOSPITALS)
    faker = Faker()
    inserted = 0
    for _ in range(count):
        lat_offset = random.uniform(-0.35, 0.35)
        lng_offset = random.uniform(-0.35, 0.35)
        lat = center_lat + lat_offset
        lng = center_lng + lng_offset
        beds_total = random.randint(80, 220)
        beds_available = random.randint(10, max(15, int(beds_total * 0.4)))
        doc = {
            "name": f"{faker.city()} Medical Center",
            "location": {
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "address": faker.street_address(),
                "city": faker.city(),
                "state": faker.state(),
            },
            "beds_total": beds_total,
            "beds_available": beds_available,
            "rating": round(random.uniform(3.6, 4.9), 1),
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
        }
        await repo.insert_one(doc)
        inserted += 1
    return inserted


async def _log_activity(db, user_id: str, metadata: dict) -> None:
    repo = MongoRepository(db, ANALYTICS_EVENTS)
    await repo.insert_one(
        {
            "user": user_id,
            "module": "hospital_finder",
            "action": "nearby_search",
            "metadata": metadata,
            "createdAt": datetime.utcnow(),
        }
    )


def _stable_random(value: str, seed_offset: int = 0) -> float:
    seed = abs(hash(f"{value}:{seed_offset}")) % 1000
    return (seed % 100) / 100


def _estimate_bed_availability(doc: dict[str, Any]) -> tuple[int, int]:
    total = doc.get("beds_total") or doc.get("totalBeds") or 120
    try:
        total = int(total)
    except (TypeError, ValueError):
        total = 120
    occupied = doc.get("beds_occupied") or doc.get("occupiedBeds")
    if occupied is None:
        ratio = 0.55 + _stable_random(str(doc.get("_id")), 2) * 0.35
        occupied = int(total * ratio)
    try:
        occupied = int(occupied)
    except (TypeError, ValueError):
        occupied = int(total * 0.65)
    available = max(0, total - occupied)
    return available, total


@router.get("/overview")
async def overview(ctx: AuthContext = Depends(require_roles("hospital"))) -> dict:
    return {
        "message": "Hospital service ready",
        "hospitalId": ctx.user_id,
        "subRole": ctx.sub_role,
    }


@router.post("/triage")
async def triage(payload: dict, ctx: AuthContext = Depends(require_scopes("patients:read"))) -> dict:
    return {
        "status": "received",
        "triage": payload,
        "handledBy": ctx.sub_role or "general",
    }


@router.get("/modules")
async def list_modules(
    ctx: AuthContext = Depends(require_roles("hospital")),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    return service.list_modules(ctx.sub_role)


@router.get("/modules/{module_key}")
async def get_module(
    module_key: str,
    ctx: AuthContext = Depends(require_roles("hospital")),
    service: HospitalService = Depends(get_hospital_service),
) -> dict:
    return service.get_module(ctx.sub_role, module_key)


@router.get("/nearby")
async def nearby_hospitals(
    lat: float = Query(...),
    lng: float = Query(...),
    limit: int = Query(5, ge=1, le=25),
    radius_km: float = Query(25.0, ge=1, le=200),
    include_eta: bool = Query(True),
    ctx: AuthContext | None = Depends(get_optional_user),
    routing: RoutingService = Depends(get_routing_service),
) -> dict:
    latitude = _parse_float(lat, "lat")
    longitude = _parse_float(lng, "lng")
    db = get_db()
    await _ensure_hospital_locations(db, latitude, longitude)
    repo = MongoRepository(db, HOSPITALS)
    docs = await repo.collection.find({}).to_list(length=500)
    if not docs:
        await _seed_hospitals(db, latitude, longitude)
        docs = await repo.collection.find({}).to_list(length=500)

    candidates: list[dict[str, Any]] = []
    for doc in docs:
        coords = _extract_coords(doc)
        if not coords:
            continue
        distance_km = routing.haversine_km(latitude, longitude, coords[0], coords[1])
        if distance_km <= radius_km:
            candidates.append({
                "doc": doc,
                "distance_km": round(distance_km, 2),
                "lat": coords[0],
                "lng": coords[1],
            })

    candidates.sort(key=lambda item: item["distance_km"])
    selected = candidates[:limit]

    if include_eta:
        for item in selected:
            route = await routing.route(
                latitude,
                longitude,
                item["lat"],
                item["lng"],
                include_geometry=False,
            )
            item["eta_seconds"] = route.get("duration_seconds")

    hospitals = []
    for item in selected:
        doc = item["doc"]
        available_beds, total_beds = _estimate_bed_availability(doc)
        wait_time_minutes = None
        wait_repo = MongoRepository(db, HOSPITAL_WAIT_TIMES)
        latest_wait = await wait_repo.find_many({"hospital_id": str(doc.get("_id"))}, sort=[("createdAt", -1)], limit=1)
        if latest_wait:
            wait_time_minutes = latest_wait[0].get("wait_time_minutes")
        if wait_time_minutes is None:
            wait_time_minutes = max(5, int(available_beds * -0.6 + 45))
        safety_score = max(40, min(98, int(95 - (item["distance_km"] * 1.8) - (wait_time_minutes * 0.2))))

        location_payload = {
            "lat": item["lat"],
            "lng": item["lng"],
        }
        doc_location = doc.get("location") if isinstance(doc.get("location"), dict) else {}
        if doc_location:
            for key in ("address", "city", "state"):
                if doc_location.get(key):
                    location_payload[key] = doc_location.get(key)
        name = doc.get("name") or doc.get("hospital_name")
        if not name:
            if doc_location.get("city"):
                name = f"{doc_location['city']} General Hospital"
            elif doc.get("regNumber"):
                name = f"Hospital {doc.get('regNumber')}"
            else:
                name = f"Hospital {doc.get('hospital_id', 'N/A')}"
        hospitals.append(
            {
                "id": str(doc.get("_id")),
                "name": name,
                "distance_km": item["distance_km"],
                "eta_seconds": item.get("eta_seconds"),
                "location": location_payload,
                "beds_available": available_beds,
                "beds_total": total_beds,
                "wait_time_minutes": wait_time_minutes,
                "safety_score": safety_score,
            }
        )

    if ctx:
        await _log_activity(
            db,
            ctx.user_id,
            {
                "count": len(hospitals),
                "radius_km": radius_km,
                "lat": latitude,
                "lng": longitude,
            },
        )

    return {
        "status": "ok",
        "count": len(hospitals),
        "hospitals": hospitals,
    }


@router.post("/wait-time", status_code=201)
async def report_wait_time(
    payload: WaitTimeReport,
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_WAIT_TIMES)
    doc = {
        "hospital_id": payload.hospital_id,
        "wait_time_minutes": payload.wait_time_minutes,
        "reported_by": payload.reported_by or ctx.user_id,
        "createdAt": datetime.utcnow(),
    }
    await repo.insert_one(doc)
    return {"status": "ok"}


@router.get("/beds/availability")
async def bed_availability(
    hospital_id: int | None = Query(None),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    db = get_db()
    repo = MongoRepository(db, RESOURCES)
    query: dict[str, Any] = {}
    if hospital_id is not None:
        query["hospital_id"] = hospital_id
    records = await repo.find_many(query, limit=200)

    availability = []
    for record in records:
        occupancy = record.get("current_bed_occupancy")
        try:
            occupancy_pct = float(occupancy)
        except (TypeError, ValueError):
            occupancy_pct = 0.0
        capacity = 100
        available = max(0, int(round(capacity * (1 - occupancy_pct / 100))))
        availability.append(
            {
                "hospital_id": record.get("hospital_id"),
                "available_beds": available,
                "occupancy_pct": occupancy_pct,
                "next_week_demand": record.get("next_week_bed_demand"),
                "capacity_assumed": capacity,
            }
        )

    return {
        "status": "ok",
        "count": len(availability),
        "availability": availability,
    }
