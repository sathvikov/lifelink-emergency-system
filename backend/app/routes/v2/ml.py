from datetime import datetime

from bson import ObjectId
from celery.result import AsyncResult
from fastapi import APIRouter, Body, Depends, HTTPException

import json

from app.core.auth import require_roles, require_scopes
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.dependencies import get_routing_service, get_weather_service
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.services.cache_store import CacheStore
from app.services.collections import ANALYTICS_EVENTS, PREDICTIONS
from app.services.prediction_store import get_latest_prediction
from app.services.routing_service import RoutingService
from app.services.weather_service import WeatherService
from app.services.repository import MongoRepository

router = APIRouter(tags=["ml"])


def _numeric(value, fallback: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _fast_health_risk(payload: dict) -> dict:
    score = 0
    drivers: list[str] = []
    age = _numeric(payload.get("age"))
    bmi = _numeric(payload.get("bmi"))
    bp = _numeric(payload.get("blood_pressure"))
    hr = _numeric(payload.get("heart_rate"))
    oxygen = _numeric(payload.get("oxygen"))

    if age >= 60:
        score += 15
        drivers.append("Age 60+")
    if bmi >= 30:
        score += 10
        drivers.append("BMI over 30")
    if bp >= 140:
        score += 20
        drivers.append("High blood pressure")
    if hr >= 100:
        score += 15
        drivers.append("High resting heart rate")
    if oxygen and oxygen < 92:
        score += 15
        drivers.append("Low oxygen saturation")
    if payload.get("has_condition") in {"1", 1, True}:
        score += 15
        drivers.append("Existing condition")

    score = min(100, max(10, score))
    risk_level = "High" if score >= 70 else "Moderate" if score >= 45 else "Low"
    explanation = "Fast heuristic scoring based on vitals and reported conditions."

    return {
        "risk_level": risk_level,
        "risk_score": score,
        "drivers": drivers,
        "explanation": explanation,
        "meta": {
            "command": "predict_risk_fast",
            "confidence": 0.58,
            "reasoning": ["Quick rule-based scoring used for faster response."],
            "references": [
                {"title": "Model", "detail": "ml/ai_ml.py::predict_health_risk"},
            ],
        },
    }


def _fast_severity_from_message(message: str) -> dict:
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


def _fallback_eta_minutes(distance_km: float) -> int:
    speed_kmh = 45
    return max(2, int(round((distance_km / speed_kmh) * 60)))


async def _run(command: str, payload):
    celery_app.send_task("system.generate_predictions", args=[command, payload])
    cached = await get_latest_prediction(command)
    if cached and isinstance(cached.get("result"), dict):
        return cached["result"]
    if command == "predict_risk":
        return _fast_health_risk(payload)
    if command == "predict_eta":
        distance_km = _numeric(payload.get("distance_km"), 1.0)
        return {
            "eta_minutes": _fallback_eta_minutes(distance_km),
            "distance_km": distance_km,
            "meta": {
                "confidence": 0.4,
                "reasoning": ["Fallback ETA until async model completes."],
                "references": [{"title": "Task", "detail": f"system.generate_predictions::{command}"}],
            },
        }
    if command == "predict_sos_severity":
        return _fast_severity_from_message(payload.get("message", ""))
    return {
        "status": "queued",
        "meta": {
            "confidence": 0.0,
            "reasoning": ["Prediction queued for background processing."],
            "references": [{"title": "Task", "detail": f"system.generate_predictions::{command}"}],
        },
    }


@router.post("/health-risk")
async def health_risk(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("public", "hospital", "ambulance", "government"))):
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="ml")
    fast_mode = bool(payload.get("fast") or payload.get("mode") == "fast")
    cache_key = f"health-risk:{hash(json.dumps(payload, sort_keys=True))}:{'fast' if fast_mode else 'full'}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result = None
    if fast_mode:
        result = _fast_health_risk(payload)
    else:
        result = await _run("predict_risk", payload)
    if not isinstance(result, dict):
        result = {}

    risk_level = result.get("risk_level") or ("High" if result.get("risk_score", 0) >= 70 else "Low")
    risk_score = result.get("risk_score") or (78 if risk_level == "High" else 35)

    drivers = result.get("drivers") or []
    if not drivers:
        if payload.get("age") and int(payload.get("age")) >= 60:
            drivers.append("Age 60+")
        if payload.get("bmi") and float(payload.get("bmi")) >= 30:
            drivers.append("BMI over 30")
        if payload.get("blood_pressure") and float(payload.get("blood_pressure")) >= 140:
            drivers.append("High blood pressure")
        if payload.get("heart_rate") and float(payload.get("heart_rate")) >= 100:
            drivers.append("High resting heart rate")
        if payload.get("has_condition") in {"1", 1, True}:
            drivers.append("Existing condition")

    explanation = result.get("explanation") or "Risk score estimated from recent vitals and reported conditions."

    enriched = {
        **result,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "drivers": drivers,
        "explanation": explanation,
    }

    cache.set(cache_key, enriched, ttl=300)

    user_id = payload.get("user_id")
    if user_id:
        try:
            oid = ObjectId(user_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid user_id") from exc
        stored_payload = {key: value for key, value in payload.items() if key not in {"fast", "mode"}}
        db = get_db()
        repo = MongoRepository(db, PREDICTIONS)
        await repo.insert_one(
            {
                "user": oid,
                "prediction_type": "health_risk",
                "risk_level": risk_level,
                "risk_score": risk_score,
                "drivers": drivers,
                "explanation": explanation,
                "payload": stored_payload,
                "createdAt": datetime.utcnow(),
            }
        )
        await MongoRepository(db, ANALYTICS_EVENTS).insert_one(
            {
                "user": oid,
                "module": "health_risk",
                "action": "predicted",
                "metadata": {
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                },
                "createdAt": datetime.utcnow(),
            }
        )

    return enriched


@router.post("/health-risk/async")
async def health_risk_async(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("public", "hospital", "ambulance", "government"))):
    job = celery_app.send_task("ml.run_model", args=["predict_risk", payload])
    return {"job_id": job.id, "status": job.status}


@router.post("/emergency-detection")
async def emergency_detection(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_scopes("emergency:trigger"))):
    if not payload.get("message"):
        raise HTTPException(status_code=400, detail="message is required")
    return await _run("predict_sos_severity", payload)


@router.post("/eta")
async def eta_prediction(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("routes:read")),
    routing: RoutingService = Depends(get_routing_service),
    weather: WeatherService = Depends(get_weather_service),
):
    distance_km = payload.get("distance_km")
    if distance_km is None and all(key in payload for key in ("start_lat", "start_lng", "end_lat", "end_lng")):
        route = await routing.route(
            float(payload["start_lat"]),
            float(payload["start_lng"]),
            float(payload["end_lat"]),
            float(payload["end_lng"]),
            include_geometry=False,
        )
        distance_km = (route.get("distance_meters") or 0) / 1000
    weather_now = None
    if payload.get("start_lat") is not None and payload.get("start_lng") is not None:
        weather_now = await weather.current(float(payload["start_lat"]), float(payload["start_lng"]))
    enriched_payload = {
        "distance_km": distance_km or 1.0,
        "precipitation_mm": (weather_now or {}).get("precipitation_mm"),
        "wind_kph": (weather_now or {}).get("wind_kph"),
        "hour": datetime.utcnow().hour,
    }
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="ml")
    cache_key = f"eta:{hash(json.dumps(enriched_payload, sort_keys=True))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result = await _run("predict_eta", enriched_payload)
    if not isinstance(result, dict):
        result = {}
    result["distance_km"] = distance_km
    cache.set(cache_key, result, ttl=300)
    return result


@router.post("/eta/async")
async def eta_prediction_async(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("routes:read")),
    routing: RoutingService = Depends(get_routing_service),
    weather: WeatherService = Depends(get_weather_service),
):
    distance_km = payload.get("distance_km")
    if distance_km is None and all(key in payload for key in ("start_lat", "start_lng", "end_lat", "end_lng")):
        route = await routing.route(
            float(payload["start_lat"]),
            float(payload["start_lng"]),
            float(payload["end_lat"]),
            float(payload["end_lng"]),
            include_geometry=False,
        )
        distance_km = (route.get("distance_meters") or 0) / 1000
    weather_now = None
    if payload.get("start_lat") is not None and payload.get("start_lng") is not None:
        weather_now = await weather.current(float(payload["start_lat"]), float(payload["start_lng"]))
    enriched_payload = {
        "distance_km": distance_km or 1.0,
        "precipitation_mm": (weather_now or {}).get("precipitation_mm"),
        "wind_kph": (weather_now or {}).get("wind_kph"),
        "hour": datetime.utcnow().hour,
    }
    job = celery_app.send_task("ml.run_model", args=["predict_eta", enriched_payload])
    return {"job_id": job.id, "status": job.status, "distance_km": distance_km}


@router.post("/hospital-load")
async def hospital_load(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_scopes("resources:read"))):
    return await _run("predict_bed_forecast", payload)


@router.post("/heatmap")
async def heatmap(payload: list = Body(default_factory=list), ctx: AuthContext = Depends(require_scopes("analytics:read"))):
    if not payload:
        raise HTTPException(status_code=400, detail="payload must be a non-empty list")
    return await _run("predict_hotspot", payload)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, ctx: AuthContext = Depends(require_scopes("ai:ask"))):
    result = AsyncResult(job_id, app=celery_app)
    if result.failed():
        return {"status": result.status, "error": str(result.result)}
    if result.ready():
        return {"status": result.status, "result": result.result}
    return {"status": result.status}
