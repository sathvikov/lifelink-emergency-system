from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_scopes
from app.core.dependencies import get_routing_service, get_weather_service
from app.core.rbac import AuthContext
from app.services.routing_service import RoutingService
from app.services.weather_service import WeatherService

router = APIRouter(tags=["routing"])


def _parse_float(value: float, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}") from exc


@router.get("/route")
async def route(
    start_lat: float = Query(...),
    start_lng: float = Query(...),
    end_lat: float = Query(...),
    end_lng: float = Query(...),
    include_geometry: bool = Query(False),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
    service: RoutingService = Depends(get_routing_service),
) -> dict:
    return await service.route(
        _parse_float(start_lat, "start_lat"),
        _parse_float(start_lng, "start_lng"),
        _parse_float(end_lat, "end_lat"),
        _parse_float(end_lng, "end_lng"),
        include_geometry=include_geometry,
    )


@router.get("/weather")
async def weather(
    lat: float = Query(...),
    lng: float = Query(...),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
    service: WeatherService = Depends(get_weather_service),
) -> dict:
    return await service.current(_parse_float(lat, "lat"), _parse_float(lng, "lng"))
