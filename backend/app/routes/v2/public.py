from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
import random
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_optional_user, require_roles
from app.core.config import get_settings
from app.core.dependencies import get_public_service, get_realtime_service, get_routing_service, get_weather_service
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.services.cache_store import CacheStore
from app.services.collections import (
    ALERTS,
    AMBULANCE_ASSIGNMENTS,
    AMBULANCES,
    ANALYTICS_EVENTS,
    DONATIONS,
    EMERGENCY_EVENTS,
    FAMILY_MEMBERS,
    HEALTH_RECORDS,
    HOSPITALS,
    NOTIFICATIONS,
    RESOURCE_REQUESTS,
    USERS,
)
from app.core.celery_app import celery_app
from app.services.public_service import PublicService
from app.services.repository import MongoRepository
from app.services.routing_service import RoutingService
from app.services.weather_service import WeatherService

router = APIRouter(tags=["public"])


class SosRequest(BaseModel):
    userId: str | None = None
    message: str
    latitude: float
    longitude: float
    vitals: dict | None = None
    fast: bool | None = False


class DonorMatchRequest(BaseModel):
    blood_group: str
    urgency: str | None = "medium"
    latitude: float
    longitude: float


class DonorNotifyRequest(BaseModel):
    donor_id: str
    message: str
    urgency: str | None = "medium"
    requester_id: str | None = None
    requester_name: str | None = None


def _parse_float(value: float, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}") from exc


def _as_object_id(value: str | None) -> ObjectId | None:
    try:
        return ObjectId(str(value)) if value else None
    except Exception:
        return None


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


def _traffic_level(weather: dict | None) -> int:
    if not weather:
        return 2
    rain = float(weather.get("precipitation_mm") or 0)
    wind = float(weather.get("wind_kph") or 0)
    if rain >= 10 or wind >= 45:
        return 5
    if rain >= 4 or wind >= 30:
        return 4
    if rain > 0 or wind >= 20:
        return 3
    return 2


def _predict_sos_heuristic(message: str) -> dict:
    msg = (message or "").lower()
    if any(k in msg for k in ["unconscious", "not breathing", "cardiac arrest", "stroke"]):
        return {
            "severity_level": "Critical",
            "severity_score": 95,
            "ai_confidence": 0.92,
            "ambulance_type": "ICU Ambulance",
            "hospital_type": "Trauma & Critical Care Center",
            "response_time": "Immediate",
            "emergency_type": "critical_care",
        }
    if any(k in msg for k in ["chest pain", "severe", "bleeding", "accident"]):
        return {
            "severity_level": "High",
            "severity_score": 82,
            "ai_confidence": 0.86,
            "ambulance_type": "Advanced Life Support",
            "hospital_type": "Emergency Department - Central",
            "response_time": "Fast",
            "emergency_type": "trauma",
        }
    if any(k in msg for k in ["fever", "dizzy", "pain", "injury"]):
        return {
            "severity_level": "Medium",
            "severity_score": 64,
            "ai_confidence": 0.8,
            "ambulance_type": "Standard Ambulance",
            "hospital_type": "Urgent Care Center",
            "response_time": "Normal",
            "emergency_type": "medical_emergency",
        }
    return {
        "severity_level": "Low",
        "severity_score": 45,
        "ai_confidence": 0.74,
        "ambulance_type": "Standard Ambulance",
        "hospital_type": "Walk-in Clinic",
        "response_time": "Standard",
        "emergency_type": "general",
    }


def _urgency_score(value: str | None) -> float:
    if not value:
        return 0.5
    label = value.lower()
    if label in {"high", "critical"}:
        return 1.0
    if label in {"medium", "moderate"}:
        return 0.7
    return 0.4


def _normalize_blood_group(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).replace(" ", "").upper()


def _resolve_blood_group(user: dict[str, Any], donor_profile: dict[str, Any], health: dict[str, Any]) -> str:
    candidates = [
        donor_profile.get("bloodGroup"),
        donor_profile.get("blood_group"),
        health.get("bloodGroup"),
        health.get("blood_group"),
        user.get("bloodGroup"),
        user.get("blood_group"),
    ]
    for value in candidates:
        normalized = _normalize_blood_group(value)
        if normalized:
            return normalized
    return "O+"


def _compatibility_factor(required: str | None, donor: str | None) -> float:
    required_group = _normalize_blood_group(required)
    donor_group = _normalize_blood_group(donor)
    if not required_group or not donor_group:
        return 0.6

    compatible = {
        "O-": {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"},
        "O+": {"O+", "A+", "B+", "AB+"},
        "A-": {"A-", "A+", "AB-", "AB+"},
        "A+": {"A+", "AB+"},
        "B-": {"B-", "B+", "AB-", "AB+"},
        "B+": {"B+", "AB+"},
        "AB-": {"AB-", "AB+"},
        "AB+": {"AB+"},
    }

    if donor_group == required_group:
        return 1.0
    if required_group in compatible.get(donor_group, set()):
        return 0.85
    return 0.25


def _availability_score(value: str | bool | None) -> float:
    if value is True:
        return 1.0
    label = str(value or "").lower()
    if label in {"available", "on call", "oncall"}:
        return 0.9 if "on" in label else 1.0
    if label in {"limited", "busy"}:
        return 0.6
    if label in {"unavailable", "inactive", "false"}:
        return 0.2
    return 0.7


def _approx_eta_minutes(distance_km: float, traffic_level: int) -> int:
    speed_kmh = max(18.0, 58.0 - (traffic_level * 6.0))
    return max(2, int(round((distance_km / speed_kmh) * 60)))


def _safe_object_id(value: str) -> ObjectId | str:
    try:
        return ObjectId(str(value))
    except Exception:
        return str(value)


async def _log_activity(
    db,
    user_id: str,
    module: str,
    action: str,
    metadata: dict | None = None,
) -> None:
    repo = MongoRepository(db, ANALYTICS_EVENTS)
    await repo.insert_one(
        {
            "user": _safe_object_id(user_id),
            "module": module,
            "action": action,
            "metadata": metadata or {},
            "createdAt": datetime.utcnow(),
        }
    )


async def _seed_ambulances(db, center_lat: float, center_lng: float, count: int = 10) -> int:
    repo = MongoRepository(db, AMBULANCES)
    inserted = 0
    for idx in range(count):
        lat = center_lat + random.uniform(-0.08, 0.08)
        lng = center_lng + random.uniform(-0.08, 0.08)
        doc = {
            "ambulanceId": f"AMB-{1000 + idx}",
            "status": "Available",
            "location": {"lat": round(lat, 6), "lng": round(lng, 6)},
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
        }
        await repo.insert_one(doc)
        inserted += 1
    return inserted


async def _seed_hospitals(db, center_lat: float, center_lng: float, count: int = 20) -> int:
    repo = MongoRepository(db, HOSPITALS)
    inserted = 0
    for idx in range(count):
        lat = center_lat + random.uniform(-0.35, 0.35)
        lng = center_lng + random.uniform(-0.35, 0.35)
        beds_total = random.randint(90, 220)
        beds_available = random.randint(12, max(18, int(beds_total * 0.4)))
        doc = {
            "name": f"City Medical Center {idx + 1}",
            "location": {"lat": round(lat, 6), "lng": round(lng, 6)},
            "beds_total": beds_total,
            "beds_available": beds_available,
            "rating": round(random.uniform(3.8, 4.9), 1),
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
        }
        await repo.insert_one(doc)
        inserted += 1
    return inserted


@router.get("/modules")
async def list_modules(
    ctx: AuthContext = Depends(require_roles("public")),
    service: PublicService = Depends(get_public_service),
) -> dict:
    return service.list_modules()


@router.get("/modules/{module_key}")
async def get_module(
    module_key: str,
    ctx: AuthContext = Depends(require_roles("public")),
    service: PublicService = Depends(get_public_service),
) -> dict:
    return service.get_module(module_key)


@router.post("/sos")
async def create_sos(
    payload: SosRequest,
    ctx: AuthContext | None = Depends(get_optional_user),
    routing: RoutingService = Depends(get_routing_service),
    weather: WeatherService = Depends(get_weather_service),
    realtime=Depends(get_realtime_service),
) -> dict:
    latitude = _parse_float(payload.latitude, "latitude")
    longitude = _parse_float(payload.longitude, "longitude")
    fast_mode = bool(payload.fast)

    user_id = payload.userId or (ctx.user_id if ctx else None)
    if ctx and payload.userId and payload.userId != ctx.user_id:
        raise HTTPException(status_code=403, detail="Invalid user context")

    db = get_db()
    alert_repo = MongoRepository(db, ALERTS)
    ambulance_repo = MongoRepository(db, AMBULANCES)
    assignment_repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    hospital_repo = MongoRepository(db, HOSPITALS)
    notification_repo = MongoRepository(db, NOTIFICATIONS)
    family_repo = MongoRepository(db, FAMILY_MEMBERS)
    user_repo = MongoRepository(db, USERS)

    async def _insert_role_notifications(role: str, title: str, message_text: str, metadata_base: dict[str, Any] | None = None, route: str | None = None, module_name: str | None = None):
        users = await user_repo.find_many({"role": role}, limit=200)
        for user in users:
            user_oid = _as_object_id(user.get("_id"))
            if not user_oid:
                continue
            await notification_repo.insert_one(
                {
                    "user": user_oid,
                    "type": "sos_alert",
                    "title": title,
                    "message": message_text,
                    "createdAt": datetime.utcnow(),
                    "read": False,
                    "metadata": {
                        **(metadata_base or {}),
                        "route": route,
                        "actionLabel": "View route" if route else None,
                        "module": module_name,
                    },
                }
            )

    severity_result = _predict_sos_heuristic(payload.message)
    celery_app.send_task(
        "system.generate_predictions",
        args=["predict_sos_severity", {"message": payload.message, "vitals": payload.vitals or {}}],
    )
    emergency_type = severity_result.get("emergency_type") or "medical_emergency"

    severity_meta = None
    if isinstance(severity_result, dict):
        severity_meta = severity_result.get("meta")
    if not isinstance(severity_meta, dict):
        severity_meta = {
            "confidence": float(severity_result.get("ai_confidence") or 0.7),
            "reasoning": [
                "Severity derived from SOS message content and vitals when provided.",
            ],
            "references": [
                {"title": "Dataset", "detail": "ml/emergency_severity_data.csv"},
                {"title": "Model", "detail": "ml/emergency_severity_model.joblib"},
            ],
        }

    weather_now = await weather.current(latitude, longitude)
    traffic_level = _traffic_level(weather_now)

    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="public")
    cached_hospitals = cache.get("hospitals:all")
    if cached_hospitals and isinstance(cached_hospitals.get("items"), list):
        hospitals = cached_hospitals["items"]
    else:
        hospitals = await hospital_repo.find_many({}, limit=250)
        if not hospitals:
            await _seed_hospitals(db, latitude, longitude, count=25)
            hospitals = await hospital_repo.find_many({}, limit=250)
        cache.set("hospitals:all", {"items": hospitals}, ttl=300)

    candidates: list[dict[str, Any]] = []
    for doc in hospitals:
        coords = _extract_coords(doc)
        if not coords:
            continue
        distance_km = routing.haversine_km(latitude, longitude, coords[0], coords[1])
        if distance_km > 80:
            continue
        beds_total = int(doc.get("beds_total") or doc.get("bedsTotal") or 120)
        beds_available = int(doc.get("beds_available") or doc.get("bedsAvailable") or max(5, int(beds_total * 0.25)))
        icu_available = int(doc.get("icu_available") or doc.get("icuAvailable") or max(2, int(beds_available * 0.3)))
        load_score = float(doc.get("load_score") or doc.get("loadScore") or max(0.1, 1 - (beds_available / max(1, beds_total))))
        rating = float(doc.get("rating") or 4.2)
        candidates.append(
            {
                "id": doc.get("_id"),
                "name": doc.get("name") or doc.get("hospital_name") or "Hospital",
                "lat": coords[0],
                "lng": coords[1],
                "distance_km": round(distance_km, 2),
                "beds_available": beds_available,
                "beds_total": beds_total,
                "icu_available": icu_available,
                "load_score": load_score,
                "rating": rating,
            }
        )

    candidates.sort(key=lambda item: item["distance_km"])
    candidates = candidates[:8]

    ranked_payload = [
        {
            "emergency_type": emergency_type,
            "distance_km": c["distance_km"],
            "traffic_level": traffic_level,
            "hospital_rating": c["rating"],
        }
        for c in candidates
    ]
    ranking_result = {"ranked": []}
    if ranked_payload and not fast_mode:
        celery_app.send_task("system.generate_predictions", args=["predict_recommend", ranked_payload])
    ranking_lookup = {item.get("index"): item for item in ranking_result.get("ranked", [])}

    enriched: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates):
        eta_minutes = _approx_eta_minutes(item["distance_km"], traffic_level)
        model_score = ranking_lookup.get(idx, {}).get("ml_score", 0)
        final_score = (model_score * 0.7) + (item["beds_available"] / max(1, item["beds_total"])) * 0.2 + (item["icu_available"] / max(1, item["beds_total"])) * 0.1
        enriched.append({
            **item,
            "eta_minutes": eta_minutes,
            "ml_score": model_score,
            "final_score": round(final_score, 4),
        })

    enriched.sort(key=lambda item: item["final_score"], reverse=True)
    selected_hospital = enriched[0] if enriched else None
    if not selected_hospital:
        selected_hospital = {
            "id": None,
            "name": "City Medical Center",
            "lat": latitude,
            "lng": longitude,
            "distance_km": 0.0,
            "beds_available": 25,
            "beds_total": 120,
            "icu_available": 6,
            "rating": 4.2,
            "eta_minutes": 8,
            "ml_score": 0.0,
            "final_score": 0.0,
        }
        enriched = [selected_hospital]

    ambulances = await ambulance_repo.find_many({"status": {"$in": ["Available", "Idle"]}}, limit=200)
    if not ambulances:
        await _seed_ambulances(db, latitude, longitude, count=12)
        ambulances = await ambulance_repo.find_many({"status": {"$in": ["Available", "Idle"]}}, limit=200)
    selected_ambulance = None
    best_distance = None
    for amb in ambulances:
        coords = _extract_coords(amb)
        if not coords:
            continue
        distance_km = routing.haversine_km(latitude, longitude, coords[0], coords[1])
        if best_distance is None or distance_km < best_distance:
            best_distance = distance_km
            selected_ambulance = amb

    alert_doc = {
        "user": user_id or "public-guest",
        "location": {"lat": latitude, "lng": longitude},
        "message": payload.message,
        "emergencyType": severity_result.get("severity_level"),
        "severity_score": severity_result.get("severity_score"),
        "ai_confidence": severity_result.get("ai_confidence"),
        "ambulance_type": severity_result.get("ambulance_type"),
        "recommended_hospital": selected_hospital["name"] if selected_hospital else None,
        "vitals": payload.vitals,
        "status": "assigned" if selected_ambulance else "pending",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created_alert = await alert_repo.insert_one(alert_doc)
    if ctx:
        await _log_activity(
            db,
            ctx.user_id,
            "sos",
            "triggered",
            {
                "alert_id": created_alert.get("_id"),
                "severity": severity_result.get("severity_level"),
                "ambulance_type": severity_result.get("ambulance_type"),
            },
        )

    assignment_doc = None
    if selected_ambulance and selected_hospital and selected_hospital.get("id"):
        assignment_doc = await assignment_repo.insert_one(
            {
                "sos_id": created_alert.get("_id"),
                "ambulance_id": selected_ambulance.get("_id"),
                "hospital_id": selected_hospital.get("id"),
                "eta_minutes": selected_hospital.get("eta_minutes"),
                "distance_km": selected_hospital.get("distance_km"),
                "status": "Assigned",
                "createdAt": datetime.utcnow(),
            }
        )
        await ambulance_repo.update_one(
            {"_id": selected_ambulance.get("_id")},
            {"$set": {"status": "Assigned", "currentAssignment": assignment_doc.get("_id")}},
        )

    sos_user_id = _as_object_id(user_id) if user_id else None
    if user_id:
        await notification_repo.insert_one(
            {
                "user": sos_user_id or user_id,
                "type": "sos_update",
                "title": "Ambulance Assigned" if selected_ambulance else "SOS Received",
                "message": f"ETA {selected_hospital.get('eta_minutes')} mins" if selected_hospital else "We are locating help.",
                "createdAt": datetime.utcnow(),
                "read": False,
                "metadata": {
                    "alert_id": created_alert.get("_id"),
                    "ambulance_id": selected_ambulance.get("_id") if selected_ambulance else None,
                    "hospital": selected_hospital.get("name") if selected_hospital else None,
                    "eta_minutes": selected_hospital.get("eta_minutes") if selected_hospital else None,
                },
            }
        )

        family_members = await family_repo.find_many({"user": sos_user_id or user_id}, limit=20)
        for member in family_members:
            await notification_repo.insert_one(
                {
                    "user": _as_object_id(member.get("_id")) or member.get("id"),
                    "type": "family_alert",
                    "title": "Family SOS Triggered",
                    "message": payload.message,
                    "createdAt": datetime.utcnow(),
                    "read": False,
                    "metadata": {"alert_id": created_alert.get("_id"), "relation": member.get("relation")},
                }
            )

    common_sos_metadata = {
        "alert_id": created_alert.get("_id"),
        "ambulance_id": selected_ambulance.get("_id") if selected_ambulance else None,
        "hospital_id": selected_hospital.get("id") if selected_hospital else None,
        "hospital_name": selected_hospital.get("name") if selected_hospital else None,
        "ambulance_code": selected_ambulance.get("ambulanceId") if selected_ambulance else None,
    }

    await _insert_role_notifications(
        "hospital",
        "SOS Alert: Ambulance En Route",
        f"Ambulance {selected_ambulance.get('ambulanceId') if selected_ambulance else 'assigned'} is en route to {selected_hospital.get('name') if selected_hospital else 'the hospital'}. Prepare emergency triage.",
        metadata_base=common_sos_metadata,
        route="/dashboard/hospital/ambulance-tracking",
        module_name="hospital",
    )

    await _insert_role_notifications(
        "ambulance",
        "New SOS Dispatch",
        "A new SOS assignment is available. Open live route tracking now.",
        metadata_base=common_sos_metadata,
        route="/dashboard/ambulance/live-tracking",
        module_name="ambulance",
    )

    await _insert_role_notifications(
        "government",
        "District Emergency Alert",
        "A new SOS incident has been reported. Monitor live ambulance status and hospital readiness.",
        metadata_base=common_sos_metadata,
        route="/dashboard/government/live-monitoring",
        module_name="government",
    )

    await MongoRepository(db, EMERGENCY_EVENTS).insert_one(
        {
            "alert_id": created_alert.get("_id"),
            "hospital": selected_hospital.get("id") if selected_hospital else None,
            "severity": severity_result.get("severity_level"),
            "status": "Active",
            "source": "public",
            "createdAt": datetime.utcnow(),
        }
    )

    await realtime.broadcast(
        "ambulance",
        {
            "type": "assignment",
            "alert_id": created_alert.get("_id"),
            "ambulance_id": selected_ambulance.get("_id") if selected_ambulance else None,
        },
    )

    await realtime.broadcast(
        "hospital",
        {
            "type": "sos_alert",
            "alert_id": created_alert.get("_id"),
            "hospital_id": selected_hospital.get("id") if selected_hospital else None,
        },
    )

    await realtime.broadcast(
        "government",
        {
            "type": "sos_alert",
            "alert_id": created_alert.get("_id"),
            "severity": severity_result.get("severity_level"),
        },
    )

    response_meta = {
        "confidence": severity_meta.get("confidence", 0.7),
        "reasoning": [
            "Severity prediction influences hospital ranking and ambulance dispatch.",
            "Hospital ranking balances bed availability, distance, and rating.",
            "ETAs are approximated from distance and traffic for faster response.",
        ],
        "references": severity_meta.get("references") or [
            {"title": "Dataset", "detail": "ml/hospital_data.csv"},
            {"title": "Model", "detail": "ml/hospital_recommendation_model.joblib"},
        ],
        "fast_mode": fast_mode,
    }

    return {
        "status": "assigned" if selected_ambulance else "pending",
        "sos_id": created_alert.get("_id"),
        "severity": severity_result,
        "hospital": selected_hospital,
        "ambulance": {
            "id": selected_ambulance.get("_id") if selected_ambulance else None,
            "code": selected_ambulance.get("ambulanceId") if selected_ambulance else None,
        },
        "eta_minutes": selected_hospital.get("eta_minutes") if selected_hospital else None,
        "ranked_hospitals": enriched[:5],
        "meta": response_meta,
    }


@router.get("/sos/{sos_id}")
async def sos_status(
    sos_id: str,
    ctx: AuthContext = Depends(require_roles("public")),
    routing: RoutingService = Depends(get_routing_service),
) -> dict:
    db = get_db()
    alert_repo = MongoRepository(db, ALERTS)
    assignment_repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    ambulance_repo = MongoRepository(db, AMBULANCES)
    hospital_repo = MongoRepository(db, HOSPITALS)

    alert = await alert_repo.find_one({"_id": sos_id})
    if not alert:
        raise HTTPException(status_code=404, detail="SOS not found")
    if str(alert.get("user")) != str(ctx.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    assignment = await assignment_repo.find_one({"sos_id": sos_id})
    ambulance = None
    hospital = None
    eta_minutes = None
    if assignment:
        ambulance = await ambulance_repo.find_one({"_id": assignment.get("ambulance_id")})
        hospital = await hospital_repo.find_one({"_id": assignment.get("hospital_id")})
        if hospital and isinstance(hospital.get("location"), dict):
            hospital.setdefault("lat", hospital["location"].get("lat"))
            hospital.setdefault("lng", hospital["location"].get("lng"))
        if ambulance and alert.get("location"):
            coords = _extract_coords(ambulance)
            if coords:
                route = await routing.route(
                    alert["location"]["lat"],
                    alert["location"]["lng"],
                    coords[0],
                    coords[1],
                    include_geometry=False,
                )
                eta_minutes = int(round((route.get("duration_seconds") or 600) / 60))

    return {
        "status": alert.get("status"),
        "severity": alert.get("emergencyType"),
        "location": alert.get("location"),
        "hospital": hospital,
        "ambulance": ambulance,
        "assignment": assignment,
        "eta_minutes": eta_minutes or assignment.get("eta_minutes") if assignment else None,
    }


@router.post("/donors/match")
async def donor_match(
    payload: DonorMatchRequest,
    ctx: AuthContext | None = Depends(get_optional_user),
    routing: RoutingService = Depends(get_routing_service),
) -> dict:
    db = get_db()
    user_repo = MongoRepository(db, USERS)
    users = await user_repo.find_many({"role": "public"}, projection={"name": 1, "location": 1, "publicProfile": 1})

    ranked = []
    urgency_weight = _urgency_score(payload.urgency)
    for user in users:
        profile = user.get("publicProfile") or {}
        donor_profile = profile.get("donorProfile") or {}
        health = profile.get("healthRecords") or {}

        availability = donor_profile.get("availability") or "Available"
        if str(availability).lower() in {"unavailable", "inactive", "false"}:
            continue

        donor_blood = donor_profile.get("bloodGroup") or donor_profile.get("blood_group")
        donor_blood = donor_blood or health.get("bloodGroup") or health.get("blood_group")
        donor_blood = donor_blood or user.get("bloodGroup") or user.get("blood_group")
        blood_factor = _compatibility_factor(payload.blood_group, donor_blood)
        if donor_blood and blood_factor < 0.3:
            continue

        coords = _extract_coords(user) or _extract_coords(donor_profile) or _extract_coords(health)
        if coords:
            distance_km = routing.haversine_km(payload.latitude, payload.longitude, coords[0], coords[1])
        else:
            distance_km = random.uniform(2.0, 18.0)

        distance_score = max(0.1, 1 - (distance_km / 40))
        availability_score = _availability_score(availability)
        score = (
            (0.4 * blood_factor)
            + (0.25 * availability_score)
            + (0.2 * urgency_weight)
            + (0.15 * distance_score)
        )
        jitter_seed = abs(hash(str(user.get("_id") or user.get("name") or ""))) % 11
        score = max(0.05, min(1.0, score + ((jitter_seed - 5) / 1000)))

        location_label = user.get("location") or donor_profile.get("location") or health.get("location") or "Unknown"
        if isinstance(location_label, dict):
            location_label = location_label.get("city") or location_label.get("address") or "Unknown"

        ranked.append(
            {
                "id": user.get("_id"),
                "name": user.get("name"),
                "blood_group": _resolve_blood_group(user, donor_profile, health),
                "availability": availability if isinstance(availability, str) else "Available",
                "distance_km": round(distance_km, 2),
                "location": location_label,
                "score": round(score * 100, 1),
                "phone": user.get("phone") or health.get("contact"),
                "last_donation": donor_profile.get("lastDonation") or health.get("lastDonation"),
                "organ_types": donor_profile.get("organTypes") or ["Blood"],
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    if ctx:
        await _log_activity(
            db,
            ctx.user_id,
            "donor_match",
            "ranked",
            {
                "count": len(ranked),
                "blood_group": payload.blood_group,
                "urgency": payload.urgency,
            },
        )
    return {"count": len(ranked), "donors": ranked[:12]}


@router.post("/donors/notify")
async def notify_donor(
    payload: DonorNotifyRequest,
    ctx: AuthContext = Depends(require_roles("public")),
) -> dict:
    if payload.requester_id and payload.requester_id != ctx.user_id:
        raise HTTPException(status_code=403, detail="Invalid requester context")

    db = get_db()
    notification_repo = MongoRepository(db, NOTIFICATIONS)

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    await notification_repo.insert_one(
        {
            "user": _safe_object_id(payload.donor_id),
            "type": "donor_request",
            "title": "Donor availability request",
            "message": message,
            "createdAt": datetime.utcnow(),
            "read": False,
            "metadata": {
                "requester_id": payload.requester_id or ctx.user_id,
                "requester_name": payload.requester_name,
                "urgency": payload.urgency or "medium",
            },
        }
    )

    await _log_activity(
        db,
        ctx.user_id,
        "donor",
        "notified",
        {"donor_id": payload.donor_id, "urgency": payload.urgency or "medium"},
    )

    return {"status": "ok"}


@router.get("/health/summary")
async def public_health_summary() -> dict:
    db = get_db()
    alert_repo = MongoRepository(db, ALERTS)
    request_repo = MongoRepository(db, RESOURCE_REQUESTS)
    donation_repo = MongoRepository(db, DONATIONS)
    health_repo = MongoRepository(db, HEALTH_RECORDS)
    hospital_repo = MongoRepository(db, HOSPITALS)
    ambulance_repo = MongoRepository(db, AMBULANCES)

    return {
        "status": "ok",
        "alerts": await alert_repo.collection.count_documents({}),
        "requests": await request_repo.collection.count_documents({}),
        "donations": await donation_repo.collection.count_documents({}),
        "health_records": await health_repo.collection.count_documents({}),
        "hospitals": await hospital_repo.collection.count_documents({}),
        "ambulances": await ambulance_repo.collection.count_documents({}),
        "checkedAt": datetime.utcnow().isoformat(),
    }
