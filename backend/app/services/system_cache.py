from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.cache_store import CacheStore


class SystemCache:
    def __init__(self) -> None:
        settings = get_settings()
        self._store = CacheStore(settings.redis_url, namespace="system")

    def get_hospital_availability(self, hospital_id: str) -> dict[str, Any] | None:
        return self._store.get(f"hospital_availability:{hospital_id}")

    def set_hospital_availability(self, hospital_id: str, payload: dict[str, Any], ttl: int = 45) -> None:
        self._store.set(f"hospital_availability:{hospital_id}", payload, ttl=ttl)

    def get_nearest_ambulance(self, key: str) -> dict[str, Any] | None:
        return self._store.get(f"nearest_ambulance:{key}")

    def set_nearest_ambulance(self, key: str, payload: dict[str, Any], ttl: int = 45) -> None:
        self._store.set(f"nearest_ambulance:{key}", payload, ttl=ttl)

    def get_prediction(self, key: str) -> dict[str, Any] | None:
        return self._store.get(f"prediction:{key}")

    def set_prediction(self, key: str, payload: dict[str, Any], ttl: int = 60) -> None:
        self._store.set(f"prediction:{key}", payload, ttl=ttl)
