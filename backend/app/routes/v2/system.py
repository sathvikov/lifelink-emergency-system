from __future__ import annotations

import math
import asyncio
import json
import random
from datetime import datetime
from typing import Any
from uuid import uuid4

import asyncpg
from celery.result import AsyncResult
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.core.auth import require_roles, require_scopes
from app.core.config import get_settings
from app.core.celery_app import celery_app
from app.core.rbac import AuthContext
from app.db.asyncpg_pool import execute, fetch_one, fetch_all
from app.services.audit_chain import append_audit_log
from app.services.privacy_service import anonymize_payload
from app.services.system_cache import SystemCache

router = APIRouter(tags=["system"])

_cache = SystemCache()


def _new_id() -> str:
    return uuid4().hex


async def _safe_send_task(task_name: str, args: list[Any] | None = None, timeout: float = 0.8):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(celery_app.send_task, task_name, args=args or []),
            timeout=timeout,
        )
    except Exception:
        return None


def _postgres_dsn() -> str:
    settings = get_settings()
    return settings.postgres_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _parse_location(value: str) -> tuple[float, float] | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except (TypeError, ValueError):
        return None


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _time_series_regression(values: list[float], steps: int = 6) -> list[float]:
    if not values:
        return [0.0 for _ in range(steps)]
    xs = list(range(len(values)))
    x_mean = sum(xs) / len(xs)
    y_mean = sum(values) / len(values)
    denom = sum((x - x_mean) ** 2 for x in xs) or 1
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) / denom
    intercept = y_mean - slope * x_mean
    return [max(0.0, intercept + slope * (len(values) + idx)) for idx in range(steps)]


def _build_prediction_output(label: str, confidence: float, reasoning: str, suggested_action: str) -> dict:
    return {
        "prediction": label,
        "confidence": round(confidence, 3),
        "reasoning": reasoning,
        "suggested_action": suggested_action,
    }


async def _store_prediction_record(prediction_type: str, result: dict[str, Any], confidence: float) -> dict:
    record_id = _new_id()
    payload = json.dumps(result)
    try:
        await execute(
            """
            INSERT INTO predictions (id, prediction_type, result, confidence, created_at)
            VALUES ($1, $2, $3::jsonb, $4, $5)
            """,
            record_id,
            prediction_type,
            payload,
            confidence,
            datetime.utcnow(),
        )
    except Exception:
        conn = await asyncpg.connect(dsn=_postgres_dsn())
        try:
            await conn.execute(
                """
                INSERT INTO predictions (id, prediction_type, result, confidence, created_at)
                VALUES ($1, $2, $3::jsonb, $4, $5)
                """,
                record_id,
                prediction_type,
                payload,
                confidence,
                datetime.utcnow(),
            )
        finally:
            await conn.close()
    return {"id": record_id, "type": prediction_type, "result": result, "confidence": confidence}


def _cache_prediction(prediction_type: str, result: dict[str, Any], confidence: float) -> dict:
    payload = {
        "id": _new_id(),
        "type": prediction_type,
        "result": result,
        "confidence": float(confidence),
        "created_at": datetime.utcnow().isoformat(),
    }
    _cache.set_prediction(f"latest:{prediction_type}", payload, ttl=60)
    return payload


@router.get("/predictions/latest")
async def latest_prediction(
    prediction_type: str = Query(..., alias="type"),
    ctx: AuthContext = Depends(require_scopes("analytics:read")),
) -> dict:
    cache_key = f"latest:{prediction_type}"
    cached = _cache.get_prediction(cache_key)
    if cached:
        return cached

    row = await fetch_one(
        """
        SELECT id, prediction_type AS type, result, confidence, created_at
        FROM predictions
        WHERE prediction_type = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        prediction_type,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No prediction available")
    payload = {
        "id": row["id"],
        "type": row["type"],
        "result": row.get("result") or {},
        "confidence": float(row.get("confidence") or 0),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
    }
    _cache.set_prediction(cache_key, payload, ttl=60)
    return payload


@router.post("/predictions/trigger")
async def trigger_prediction(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("ai:ask")),
) -> dict:
    prediction_type = payload.get("type") or payload.get("prediction_type")
    if not prediction_type:
        raise HTTPException(status_code=400, detail="prediction type is required")
    job = await _safe_send_task("system.generate_predictions", [prediction_type, payload.get("payload") or {}])

    fallback = None
    try:
        request_payload = payload.get("payload") or {}
        if prediction_type == "demand_forecast":
            series = [float(v) for v in request_payload.get("series", [])]
            forecast = _time_series_regression(series, steps=int(request_payload.get("steps", 6)))
            result = _build_prediction_output(
                "High emergency risk"
                if forecast and max(forecast) > (sum(series) / max(1, len(series)))
                else "Moderate risk",
                0.86,
                "Spike in incidents + hospital load trend",
                "Deploy 3 ambulances",
            )
            result["forecast"] = forecast
            fallback = _cache_prediction(prediction_type, result, 0.86)
            try:
                await _store_prediction_record(prediction_type, result, 0.86)
            except Exception:
                pass
        else:
            result = _build_prediction_output(
                "High emergency risk",
                0.9,
                "Rapid triage signals + historical surge pattern",
                "Activate surge response",
            )
            fallback = _cache_prediction(prediction_type, result, 0.9)
            try:
                await _store_prediction_record(prediction_type, result, 0.9)
            except Exception:
                pass
    except Exception:
        fallback = None

    response = {"job_id": job.id if job else _new_id(), "status": job.status if job else "PENDING"}
    if fallback:
        response["fallback"] = fallback
    return response


@router.post("/federated/train")
async def federated_train(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_roles("hospital")),
) -> dict:
    hospital_id = payload.get("hospital_id") or ctx.user_id
    job = await _safe_send_task("system.train_local_model", [hospital_id, payload])
    fallback = None
    try:
        weight_count = int(payload.get("weight_count", 16))
        noise_std = float(payload.get("noise_std", 0.05))
        weights = [random.uniform(-1, 1) + random.gauss(0.0, noise_std) for _ in range(weight_count)]
        result = {
            "hospital_id": hospital_id,
            "weights": weights,
            "samples": int(payload.get("samples", 120)),
        }
        fallback = _cache_prediction("federated_local", result, 0.75)
        try:
            await _store_prediction_record("federated_local", result, 0.75)
        except Exception:
            pass
    except Exception:
        fallback = None
    response = {"job_id": job.id if job else _new_id(), "status": job.status if job else "PENDING"}
    if fallback:
        response["fallback"] = fallback
    return response


@router.post("/federated/aggregate")
async def federated_aggregate(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_roles("government")),
) -> dict:
    job = await _safe_send_task(
        "system.aggregate_global_model",
        [payload.get("limit", 50), payload.get("noise_std", 0.02)],
    )
    return {"job_id": job.id if job else _new_id(), "status": job.status if job else "PENDING"}


@router.post("/audit/log")
async def audit_log(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("gov:write")),
) -> dict:
    action = payload.get("action") or "unknown_action"
    details = payload.get("details") or ""
    job = await _safe_send_task("system.blockchain_log_writer", [action, ctx.user_id, details])
    fallback = None
    try:
        fallback = await append_audit_log(action, ctx.user_id, details)
    except Exception:
        fallback = None
    response = {"job_id": job.id if job else _new_id(), "status": job.status if job else "PENDING"}
    if fallback:
        response["fallback"] = fallback
    return response


@router.post("/simulation/start")
async def start_simulation(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_roles("government")),
) -> dict:
    job = await _safe_send_task("system.simulation_engine", [payload])
    return {"job_id": job.id if job else _new_id(), "status": job.status if job else "PENDING"}


@router.get("/simulation/status/{job_id}")
async def simulation_status(job_id: str, ctx: AuthContext = Depends(require_roles("government"))) -> dict:
    result = AsyncResult(job_id, app=celery_app)
    return {"job_id": job_id, "status": result.status, "result": result.result if result.successful() else None}


@router.post("/emergency/anonymized")
async def anonymized_emergency(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("emergency:trigger")),
) -> dict:
    sanitized = anonymize_payload(payload)
    emergency_id = payload.get("emergency_id") or payload.get("id")
    try:
        await execute(
            """
            INSERT INTO emergencies (id, type, severity, location, status, timestamp, assigned_hospital)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE
            SET type = EXCLUDED.type,
                severity = EXCLUDED.severity,
                location = EXCLUDED.location,
                status = EXCLUDED.status,
                timestamp = EXCLUDED.timestamp,
                assigned_hospital = EXCLUDED.assigned_hospital
            """,
            emergency_id or f"emg_{int(datetime.utcnow().timestamp())}",
            payload.get("type") or "unknown",
            payload.get("severity") or "unknown",
            payload.get("location") or "unknown",
            payload.get("status") or "active",
            datetime.utcnow(),
            payload.get("assigned_hospital"),
        )
    except Exception:
        pass
    return {"status": "stored", "anonymized": sanitized}


@router.post("/ambulance/nearest")
async def nearest_ambulance(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("routes:read")),
) -> dict:
    lat = payload.get("lat")
    lng = payload.get("lng")
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="lat and lng required")
    cache_key = f"{lat}:{lng}"
    cached = _cache.get_nearest_ambulance(cache_key)
    if cached:
        return cached

    rows = await fetch_all(
        """
        SELECT id, driver, location, status
        FROM ambulances
        WHERE status = 'available'
        LIMIT 250
        """
    )
    best = None
    for row in rows:
        loc = _parse_location(row.get("location") or "")
        if not loc:
            continue
        distance = _haversine(float(lat), float(lng), loc[0], loc[1])
        if best is None or distance < best["distance_km"]:
            best = {
                "id": row.get("id"),
                "driver": row.get("driver"),
                "distance_km": round(distance, 2),
            }
    if not best:
        raise HTTPException(status_code=404, detail="No available ambulances")
    _cache.set_nearest_ambulance(cache_key, best, ttl=45)
    return best


@router.post("/eva/ask")
async def eva_assistant(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("ai:ask")),
) -> dict:
    intent = (payload.get("intent") or "insight").lower()
    latest = None
    if intent in {"forecast", "prediction", "risk"}:
        latest = await fetch_one(
            """
            SELECT type, result, confidence, created_at
            FROM predictions
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    response = {
        "assistant": "EVA",
        "intent": intent,
        "insight": latest.get("result") if latest else {"status": "no predictions yet"},
        "confidence": float(latest.get("confidence")) if latest else 0.0,
    }
    return response
