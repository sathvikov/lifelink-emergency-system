from __future__ import annotations

import asyncio
import random
from datetime import datetime
from uuid import uuid4

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.db.mongo import get_db
from app.db.models import GovEmergency
from app.services.cache_store import CacheStore


def _uuid() -> str:
    return uuid4().hex


async def _simulate_emergencies(count: int, center_lat: float, center_lng: float) -> int:
    db = get_db()
    async with db() as session:
        for _ in range(count):
            lat = center_lat + random.uniform(-0.4, 0.4)
            lng = center_lng + random.uniform(-0.4, 0.4)
            session.add(
                GovEmergency(
                    id=_uuid(),
                    emergency_type=random.choice(["road_accident", "cardiac", "trauma", "fire", "flood"]),
                    severity=random.choice(["Low", "Medium", "High", "Critical"]),
                    latitude=lat,
                    longitude=lng,
                    status="active",
                    hospital_id=None,
                    ambulance_id=None,
                    occurred_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
            )
        await session.commit()
    return count


async def _refresh_metrics() -> dict:
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="gov")
    cache.set("last_refresh", {"value": datetime.utcnow().isoformat()}, ttl=300)
    return {"status": "ok"}


@celery_app.task(name="government.simulate")
def simulate_task(count: int = 50, center_lat: float = 12.9716, center_lng: float = 77.5946) -> dict:
    return {"generated": asyncio.run(_simulate_emergencies(count, center_lat, center_lng))}


@celery_app.task(name="government.refresh_metrics")
def refresh_metrics_task() -> dict:
    return asyncio.run(_refresh_metrics())
