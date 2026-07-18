from __future__ import annotations

import math
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.cache_store import CacheStore


class RoutingService:
    def __init__(self, cache: CacheStore | None = None) -> None:
        settings = get_settings()
        self._cache = cache or CacheStore(settings.redis_url, namespace="routing")

    async def route(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        include_geometry: bool = False,
    ) -> dict[str, Any]:
        key = f"{start_lat:.5f},{start_lng:.5f}:{end_lat:.5f},{end_lng:.5f}:{include_geometry}"
        cached = self._cache.get(key)
        if cached:
            return cached

        coords = f"{start_lng},{start_lat};{end_lng},{end_lat}"
        params = {"overview": "simplified" if include_geometry else "false"}
        if include_geometry:
            params["geometries"] = "geojson"
        url = f"http://router.project-osrm.org/route/v1/driving/{coords}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if not data.get("routes"):
            result = {
                "status": "error",
                "provider": "osrm",
                "message": "Route not available",
            }
            self._cache.set(key, result, ttl=120)
            return result

        route = data["routes"][0]
        result = {
            "status": "ok",
            "provider": "osrm",
            "distance_meters": route.get("distance"),
            "duration_seconds": route.get("duration"),
        }
        if include_geometry:
            result["geometry"] = route.get("geometry")
        self._cache.set(key, result, ttl=300)
        return result

    @staticmethod
    def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        radius_km = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)
        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius_km * c
