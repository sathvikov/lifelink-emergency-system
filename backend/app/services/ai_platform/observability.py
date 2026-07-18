from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.db.mongo import get_db
from app.services.collections import INFERENCE_LOGS
from app.services.repository import MongoRepository


class ObservabilityService:
    def __init__(self) -> None:
        self._db = get_db()
        self._repo = MongoRepository(self._db, INFERENCE_LOGS)

    async def log_inference(
        self,
        role: str,
        module_key: str,
        model_name: str,
        model_version: str | None,
        latency_ms: float,
        status: str,
        payload: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        quality_score: float | None = None,
        drift_score: float | None = None,
        data_freshness_hours: float | None = None,
        explanation_quality: float | None = None,
    ) -> dict[str, Any]:
        record = {
            "role": role,
            "module_key": module_key,
            "model_name": model_name,
            "model_version": model_version,
            "latency_ms": latency_ms,
            "status": status,
            "payload": payload or {},
            "response": response or {},
            "quality_score": quality_score,
            "drift_score": drift_score,
            "data_freshness_hours": data_freshness_hours,
            "explanation_quality": explanation_quality,
            "created_at": datetime.utcnow().isoformat(),
        }
        return await self._repo.insert_one(record)

    async def summary(self, hours: int = 24) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(hours=hours)
        records = await self._repo.find_many(
            {"created_at": {"$gte": since.isoformat()}},
            limit=500,
        )
        total = len(records)
        errors = [r for r in records if r.get("status") != "ok"]
        latency = [r.get("latency_ms", 0) for r in records if r.get("latency_ms") is not None]
        drift = [r.get("drift_score") for r in records if r.get("drift_score") is not None]
        quality = [r.get("quality_score") for r in records if r.get("quality_score") is not None]
        freshness = [r.get("data_freshness_hours") for r in records if r.get("data_freshness_hours") is not None]
        avg_latency = round(sum(latency) / len(latency), 2) if latency else 0
        sorted_latency = sorted(latency)
        p95_latency = sorted_latency[int(len(sorted_latency) * 0.95) - 1] if sorted_latency else 0
        avg_drift = round(sum(drift) / len(drift), 3) if drift else 0
        avg_quality = round(sum(quality) / len(quality), 3) if quality else 0
        avg_freshness = round(sum(freshness) / len(freshness), 2) if freshness else 0
        return {
            "window_hours": hours,
            "total_requests": total,
            "error_rate": round(len(errors) / total, 3) if total else 0,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "avg_drift_score": avg_drift,
            "avg_quality_score": avg_quality,
            "avg_data_freshness_hours": avg_freshness,
            "recent_modules": list({r.get("module_key") for r in records if r.get("module_key")} )[:12],
        }
