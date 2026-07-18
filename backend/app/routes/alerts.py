import math
import re
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import ALERTS, HEALTH_RECORDS, HOSPITALS, NOTIFICATIONS
from app.core.celery_app import celery_app
from app.services.repository import MongoRepository

router = APIRouter(tags=["alerts"])


class AlertCreateRequest(BaseModel):
    userId: str
    locationDetails: str
    message: str
    latitude: float | None = None
    longitude: float | None = None
    vitals: dict | None = None


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


def _predict_severity(message: str) -> dict:
    msg = (message or "").lower()
    if any(k in msg for k in ["unconscious", "not breathing", "cardiac arrest", "stroke"]):
        return {
            "severity_level": "Critical",
            "severity_score": 95,
            "ai_confidence": 0.92,
            "ambulance_type": "ICU Ambulance",
            "hospital_type": "Trauma & Critical Care Center",
            "response_time": "Immediate",
        }
    if any(k in msg for k in ["chest pain", "severe", "bleeding", "accident"]):
        return {
            "severity_level": "High",
            "severity_score": 82,
            "ai_confidence": 0.86,
            "ambulance_type": "Advanced Life Support",
            "hospital_type": "Emergency Department - Central",
            "response_time": "Fast",
        }
    if any(k in msg for k in ["fever", "dizzy", "pain", "injury"]):
        return {
            "severity_level": "Medium",
            "severity_score": 64,
            "ai_confidence": 0.8,
            "ambulance_type": "Standard Ambulance",
            "hospital_type": "Urgent Care Center",
            "response_time": "Normal",
        }
    return {
        "severity_level": "Low",
        "severity_score": 45,
        "ai_confidence": 0.74,
        "ambulance_type": "Standard Ambulance",
        "hospital_type": "Walk-in Clinic",
        "response_time": "Standard",
    }


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def _parse_coords_from_text(location_text: str) -> tuple[float, float] | None:
    if not location_text:
        return None
    match = re.search(r"lat\s*[:=]\s*([\d.-]+)\s*,?\s*lng\s*[:=]\s*([\d.-]+)", location_text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return None


async def _nearest_hospital(db, lat: float, lng: float) -> dict | None:
    repo = MongoRepository(db, HOSPITALS)
    hospitals = await repo.find_many({})
    closest = None
    closest_distance = None
    for hospital in hospitals:
        location = hospital.get("location") if isinstance(hospital.get("location"), dict) else {}
        try:
            h_lat = float(location.get("lat"))
            h_lng = float(location.get("lng"))
        except (TypeError, ValueError):
            continue
        distance = _haversine_km(lat, lng, h_lat, h_lng)
        if closest_distance is None or distance < closest_distance:
            closest_distance = distance
            closest = {
                "id": str(hospital.get("_id")),
                "name": hospital.get("name") or hospital.get("hospital_name") or "Central City General",
                "distance_km": round(distance, 2),
            }
    return closest


@router.post("/alerts", status_code=201)
async def create_alert(payload: AlertCreateRequest):
    db = get_db()
    alert_repo = MongoRepository(db, ALERTS)
    notification_repo = MongoRepository(db, NOTIFICATIONS)
    health_repo = MongoRepository(db, HEALTH_RECORDS)

    severity_result = _predict_severity(payload.message)
    celery_app.send_task(
        "system.generate_predictions",
        args=["predict_sos_severity", {"message": payload.message, "vitals": payload.vitals, "location": payload.locationDetails}],
    )

    severity_meta = None
    if isinstance(severity_result, dict):
        severity_meta = severity_result.get("meta")
    if not isinstance(severity_meta, dict):
        severity_meta = {
            "confidence": float(severity_result.get("ai_confidence") or 0.7),
            "reasoning": [
                "Severity derived from SOS message keywords and vitals when available.",
                "Heuristic rules applied when model output is unavailable.",
            ],
            "references": [
                {"title": "Dataset", "detail": "ml/emergency_severity_data.csv"},
                {"title": "Model", "detail": "ml/emergency_severity_model.joblib"},
            ],
        }

    ml_severity = severity_result.get("severity_level", "Medium")
    priority_map = {
        "Critical": "High",
        "High": "High",
        "Medium": "Medium",
        "Low": "Low",
    }
    normalized_priority = priority_map.get(ml_severity, "High")

    coords = None
    if payload.latitude is not None and payload.longitude is not None:
        coords = (payload.latitude, payload.longitude)
    if coords is None:
        coords = _parse_coords_from_text(payload.locationDetails)

    vitals = payload.vitals
    if vitals is None:
        latest = await health_repo.find_many(
            {"user": _as_object_id(payload.userId), "record_type": "vitals"},
            sort=[("createdAt", -1)],
            limit=1,
        )
        if latest:
            vitals = latest[0].get("metrics")

    new_doc = {
        "user": _as_object_id(payload.userId),
        "locationDetails": payload.locationDetails,
        "location": {"lat": coords[0], "lng": coords[1]} if coords else None,
        "message": payload.message,
        "emergencyType": ml_severity,
        "priority": normalized_priority,
        "severity_score": severity_result.get("severity_score", 50),
        "ai_confidence": severity_result.get("ai_confidence", 0),
        "severity_meta": severity_meta,
        "ambulance_type": severity_result.get("ambulance_type", "Standard Ambulance"),
        "recommended_hospital": severity_result.get("hospital_type", "Emergency Department"),
        "vitals": vitals,
        "status": "pending",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await alert_repo.insert_one(new_doc)

    selected_hospital = "Central City General"
    eta_minutes = None
    if coords:
        nearest = await _nearest_hospital(db, coords[0], coords[1])
        if nearest:
            selected_hospital = nearest.get("name", selected_hospital)
            speed_kmh = 60 if ml_severity == "Critical" else 45 if ml_severity == "High" else 35
            eta_minutes = max(2, int(round((nearest.get("distance_km", 1) / speed_kmh) * 60)))
    if eta_minutes is None:
        eta_map = {
            "Critical": 2,
            "High": 7,
            "Medium": 15,
            "Low": 25,
        }
        eta_minutes = eta_map.get(ml_severity, 10)

    await notification_repo.insert_one(
        {
            "user": _as_object_id(payload.userId),
            "type": "sos_alert",
            "title": "Emergency SOS Alert",
            "message": payload.message,
            "severity": ml_severity,
            "createdAt": datetime.utcnow(),
            "read": False,
            "metadata": {
                "alert_id": created.get("_id"),
                "hospital": selected_hospital,
                "eta_minutes": eta_minutes,
            },
        }
    )

    return {
        "message": "Alert Sent Successfully!",
        "severity_level": ml_severity,
        "severity_score": severity_result.get("severity_score"),
        "ai_confidence": severity_result.get("ai_confidence"),
        "recommendation": {
            "hospital_name": selected_hospital,
            "eta": eta_minutes,
            "ambulance_type": severity_result.get("ambulance_type"),
            "response_time": severity_result.get("response_time"),
        },
        "alert_id": created.get("_id"),
        "vitals": vitals,
        "meta": severity_meta,
    }


@router.get("/notifications/{user_id}")
async def get_notifications(user_id: str):
    db = get_db()
    alert_repo = MongoRepository(db, ALERTS)
    notification_repo = MongoRepository(db, NOTIFICATIONS)

    oid = _as_object_id(user_id)

    alerts = await alert_repo.find_many({"user": oid}, sort=[("createdAt", -1)], limit=20)
    notifications = await notification_repo.find_many({"user": oid}, sort=[("createdAt", -1)], limit=20)

    one_day_ago = datetime.utcnow() - timedelta(hours=24)
    critical_recent = await alert_repo.find_many(
        {
            "user": oid,
            "createdAt": {"$gte": one_day_ago},
            "emergencyType": {"$in": ["Critical", "High"]},
        },
    )

    total = await alert_repo.find_many({"user": oid})

    mapped = []
    for alert in alerts:
        emergency_type = alert.get("emergencyType")
        mapped.append(
            {
                "id": alert.get("_id"),
                "message": alert.get("message"),
                "severity": emergency_type or alert.get("priority"),
                "severity_score": alert.get("severity_score") if alert.get("severity_score") is not None else "N/A",
                "ambulance_type": alert.get("ambulance_type", "Standard"),
                "timestamp": alert.get("createdAt"),
                "icon": "fa-exclamation-circle" if emergency_type == "Critical" else "fa-alert",
                "source": "alerts",
            }
        )

    for note in notifications:
        mapped.append(
            {
                "id": note.get("_id"),
                "message": note.get("message") or note.get("title"),
                "severity": note.get("severity") or "Info",
                "severity_score": note.get("severity_score", "N/A"),
                "ambulance_type": note.get("metadata", {}).get("ambulance_type", "Standard"),
                "timestamp": note.get("createdAt"),
                "icon": "fa-bell",
                "source": "notifications",
            }
        )

    def _sort_key(item: dict) -> datetime:
        ts = item.get("timestamp")
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return datetime.utcnow()
        return datetime.utcnow()

    mapped.sort(key=_sort_key, reverse=True)
    mapped = mapped[:10]

    return {
        "notifications": mapped,
        "stats": {
            "recent_critical_alerts": len(critical_recent),
            "total_sos_calls": len(total),
            "last_alert": alerts[0].get("createdAt") if alerts else None,
        },
    }
