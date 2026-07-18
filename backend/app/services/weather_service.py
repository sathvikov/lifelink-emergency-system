from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.services.cache_store import CacheStore


class WeatherService:
    def __init__(self, cache: CacheStore | None = None) -> None:
        settings = get_settings()
        self._cache = cache or CacheStore(settings.redis_url, namespace="weather")

    async def current(self, lat: float, lng: float) -> dict[str, Any]:
        key = f"{lat:.4f}:{lng:.4f}"
        cached = self._cache.get(key)
        if cached:
            return cached

        params = {
            "latitude": lat,
            "longitude": lng,
            "current": "temperature_2m,precipitation,wind_speed_10m",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
            response.raise_for_status()
            data = response.json()

        current = data.get("current", {})
        result = {
            "status": "ok",
            "provider": "open-meteo",
            "temperature_c": current.get("temperature_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_kph": current.get("wind_speed_10m"),
            "is_raining": (current.get("precipitation") or 0) > 0,
        }
        self._cache.set(key, result, ttl=600)
        return result
