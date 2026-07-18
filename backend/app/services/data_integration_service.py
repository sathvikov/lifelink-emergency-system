from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.cache_store import CacheStore
from app.services.routing_service import RoutingService
from app.services.weather_service import WeatherService


class DataIntegrationService:
    def __init__(
        self,
        routing_service: RoutingService | None = None,
        weather_service: WeatherService | None = None,
        cache: CacheStore | None = None,
    ) -> None:
        settings = get_settings()
        self._cache = cache or CacheStore(settings.redis_url, namespace="integrations")
        self._routing = routing_service or RoutingService()
        self._weather = weather_service or WeatherService()

    async def _get_json(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _parse_coords(value: str) -> tuple[float, float]:
        parts = [p.strip() for p in value.split(",")]
        if len(parts) != 2:
            raise ValueError("Invalid coordinate format")
        return float(parts[0]), float(parts[1])

    async def geocode(self, query: str) -> dict[str, Any]:
        key = f"geocode:{query.lower()}"
        cached = self._cache.get(key)
        if cached:
            return cached

        headers = {"User-Agent": "LifeLink/1.0"}
        data = await self._get_json(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers=headers,
        )
        if not data:
            result = {"status": "not_found", "query": query}
        else:
            result = {
                "status": "ok",
                "query": query,
                "provider": "nominatim",
                "location": {
                    "lat": float(data[0]["lat"]),
                    "lng": float(data[0]["lon"]),
                    "display": data[0].get("display_name"),
                },
            }

        self._cache.set(key, result, ttl=3600)
        return result

    async def route(self, origin: str, destination: str, provider: str = "auto") -> dict[str, Any]:
        try:
            lat1, lon1 = self._parse_coords(origin)
            lat2, lon2 = self._parse_coords(destination)
        except ValueError:
            origin_geo = await self.geocode(origin)
            dest_geo = await self.geocode(destination)
            if origin_geo.get("status") != "ok" or dest_geo.get("status") != "ok":
                result = {
                    "status": "error",
                    "provider": "osrm",
                    "message": "Unable to geocode origin or destination",
                }
                return result
            lat1 = origin_geo["location"]["lat"]
            lon1 = origin_geo["location"]["lng"]
            lat2 = dest_geo["location"]["lat"]
            lon2 = dest_geo["location"]["lng"]
        return await self._routing.route(lat1, lon1, lat2, lon2, include_geometry=False)

    async def weather(self, lat: float, lng: float) -> dict[str, Any]:
        return await self._weather.current(lat, lng)

    async def traffic(self, origin: str, destination: str) -> dict[str, Any]:
        key = f"traffic:{origin}:{destination}"
        cached = self._cache.get(key)
        if cached:
            return cached
        try:
            lat1, lon1 = self._parse_coords(origin)
            lat2, lon2 = self._parse_coords(destination)
        except ValueError:
            origin_geo = await self.geocode(origin)
            dest_geo = await self.geocode(destination)
            if origin_geo.get("status") != "ok" or dest_geo.get("status") != "ok":
                result = {
                    "status": "error",
                    "provider": "simulation",
                    "message": "Unable to geocode origin or destination",
                }
                self._cache.set(key, result, ttl=120)
                return result
            lat1 = origin_geo["location"]["lat"]
            lon1 = origin_geo["location"]["lng"]
            lat2 = dest_geo["location"]["lat"]
            lon2 = dest_geo["location"]["lng"]

        route = await self._routing.route(lat1, lon1, lat2, lon2, include_geometry=False)
        if route.get("status") != "ok":
            result = {
                "status": "error",
                "provider": "simulation",
                "message": "Route not available",
            }
            self._cache.set(key, result, ttl=120)
            return result

        base_duration = int(route.get("duration_seconds") or 0)
        midpoint_lat = (lat1 + lat2) / 2
        midpoint_lng = (lon1 + lon2) / 2
        weather = await self._weather.current(midpoint_lat, midpoint_lng)
        time_factor = self._time_factor(datetime.now().hour)
        weather_factor = self._weather_factor(weather)
        adjusted = int(base_duration * time_factor * weather_factor)

        result = {
            "status": "ok",
            "provider": "simulation",
            "base_duration_seconds": base_duration,
            "adjusted_duration_seconds": adjusted,
            "factors": {
                "time": time_factor,
                "weather": weather_factor,
            },
            "weather": weather,
        }
        self._cache.set(key, result, ttl=180)
        return result

    @staticmethod
    def _time_factor(hour: int) -> float:
        if 7 <= hour <= 10:
            return 1.25
        if 17 <= hour <= 20:
            return 1.2
        if 12 <= hour <= 14:
            return 1.1
        return 1.0

    @staticmethod
    def _weather_factor(weather: dict[str, Any]) -> float:
        precipitation = weather.get("precipitation_mm") or 0
        wind_kph = weather.get("wind_kph") or 0
        factor = 1.0
        if precipitation >= 0.5:
            factor *= 1.15
        if wind_kph >= 40:
            factor *= 1.1
        return factor
