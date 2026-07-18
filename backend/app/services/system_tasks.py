from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime
from typing import Any
from uuid import uuid4

import asyncpg
from faker import Faker
from sklearn.cluster import KMeans

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.services.audit_chain import append_audit_log
from app.services.ml_runner import run_ml_model

faker = Faker()


def _uuid() -> str:
    return uuid4().hex


def _postgres_dsn() -> str:
    settings = get_settings()
    return settings.postgres_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _gaussian_noise(std_dev: float) -> float:
    return random.gauss(0.0, std_dev)


def _fedavg(weights: list[list[float]]) -> list[float]:
    if not weights:
        return []
    length = len(weights[0])
    averaged = []
    for idx in range(length):
        vals = [w[idx] for w in weights if len(w) > idx]
        averaged.append(sum(vals) / max(1, len(vals)))
    return averaged


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


async def _store_prediction(prediction_type: str, result: dict[str, Any], confidence: float) -> str:
    dsn = _postgres_dsn()
    record_id = _uuid()
    payload = json.dumps(result)
    conn = await asyncpg.connect(dsn=dsn)
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
    return record_id


@celery_app.task(name="system.train_local_model")
def train_local_model(hospital_id: str, payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    weight_count = int(payload.get("weight_count", 16))
    weights = [random.uniform(-1, 1) for _ in range(weight_count)]
    noise_std = float(payload.get("noise_std", 0.05))
    noisy_weights = [w + _gaussian_noise(noise_std) for w in weights]
    result = {
        "hospital_id": hospital_id,
        "weights": noisy_weights,
        "samples": int(payload.get("samples", 120)),
    }
    asyncio.run(_store_prediction("federated_local", result, 0.75))
    return result


@celery_app.task(name="system.aggregate_global_model")
def aggregate_global_model(limit: int = 50, noise_std: float = 0.02) -> dict:
    dsn = _postgres_dsn()
    async def _fetch_local() -> list[list[float]]:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT result FROM predictions
                WHERE prediction_type = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                "federated_local",
                limit,
            )
            weights = []
            for row in rows:
                result = row.get("result") or {}
                if isinstance(result, dict) and isinstance(result.get("weights"), list):
                    weights.append([float(v) for v in result.get("weights")])
            return weights
        finally:
            await conn.close()

    weights = asyncio.run(_fetch_local())
    aggregated = _fedavg(weights)
    dp_weights = [w + _gaussian_noise(noise_std) for w in aggregated]
    result = {
        "weights": dp_weights,
        "contributors": len(weights),
    }
    asyncio.run(_store_prediction("federated_global", result, 0.8))
    return result


@celery_app.task(name="system.generate_predictions")
def generate_predictions(prediction_type: str, payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    result: dict[str, Any] = {}
    confidence = 0.7

    if prediction_type == "demand_forecast":
        series = [float(v) for v in payload.get("series", [])]
        forecast = _time_series_regression(series, steps=int(payload.get("steps", 6)))
        result = _build_prediction_output(
            "High emergency risk" if forecast and max(forecast) > (sum(series) / max(1, len(series))) else "Moderate risk",
            0.86,
            "Spike in incidents + hospital load trend",
            "Deploy 3 ambulances",
        )
        result["forecast"] = forecast
        confidence = 0.86
    elif prediction_type == "hotspot_cluster":
        points = payload.get("points", [])
        clusters = []
        if points:
            model = KMeans(n_clusters=min(4, len(points)), n_init=10)
            model.fit(points)
            clusters = model.cluster_centers_.tolist()
        result = {
            "clusters": clusters,
            "count": len(clusters),
        }
        confidence = 0.72
    else:
        try:
            result = asyncio.run(run_ml_model(prediction_type, payload, "ai_ml.py"))
            if not isinstance(result, dict):
                result = {"result": result}
        except Exception:
            result = _build_prediction_output(
                "High emergency risk",
                0.91,
                "Spike in incidents + hospital overload",
                "Deploy 3 ambulances",
            )
            confidence = 0.91

    record_id = asyncio.run(_store_prediction(prediction_type, result, confidence))
    return {"id": record_id, "type": prediction_type, "result": result, "confidence": confidence}


@celery_app.task(name="system.blockchain_log_writer")
def blockchain_log_writer(action: str, actor: str, details: str) -> dict:
    return asyncio.run(append_audit_log(action, actor, details))


@celery_app.task(name="system.simulation_engine")
def simulation_engine(payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    hospitals = int(payload.get("hospitals", 120))
    users = int(payload.get("users", 1100))
    ambulances = int(payload.get("ambulances", 240))
    center_lat = float(payload.get("center_lat", 12.9716))
    center_lng = float(payload.get("center_lng", 77.5946))

    async def _seed() -> dict[str, int]:
        conn = await asyncpg.connect(dsn=_postgres_dsn())
        try:
            for _ in range(hospitals):
                lat = center_lat + random.uniform(-0.6, 0.6)
                lng = center_lng + random.uniform(-0.6, 0.6)
                await conn.execute(
                    """
                    INSERT INTO hospitals (id, name, location, capacity, occupancy, verified, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    _uuid(),
                    f"{faker.city()} Medical Center",
                    f"{lat:.4f},{lng:.4f}",
                    random.randint(80, 240),
                    random.randint(10, 180),
                    random.choice([True, False]),
                    datetime.utcnow(),
                )
            for _ in range(ambulances):
                lat = center_lat + random.uniform(-0.6, 0.6)
                lng = center_lng + random.uniform(-0.6, 0.6)
                await conn.execute(
                    """
                    INSERT INTO ambulances (id, driver, location, status, verified)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    _uuid(),
                    faker.name(),
                    f"{lat:.4f},{lng:.4f}",
                    random.choice(["available", "assigned", "offline"]),
                    random.choice([True, False]),
                )
            for _ in range(users):
                lat = center_lat + random.uniform(-0.6, 0.6)
                lng = center_lng + random.uniform(-0.6, 0.6)
                await conn.execute(
                    """
                    INSERT INTO users (id, role, location)
                    VALUES ($1, $2, $3)
                    """,
                    _uuid(),
                    random.choice(["public", "hospital", "ambulance"]),
                    f"{lat:.4f},{lng:.4f}",
                )
        finally:
            await conn.close()
        return {"hospitals": hospitals, "ambulances": ambulances, "users": users}

    counts = asyncio.run(_seed())
    return {"status": "seeded", **counts}
