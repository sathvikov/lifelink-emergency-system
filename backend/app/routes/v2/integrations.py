from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_scopes
from app.core.dependencies import get_data_integration_service
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.services.collections import EMERGENCY_EVENTS, HEALTH_RECORDS, HOSPITALS
from app.services.data_integration_service import DataIntegrationService
from app.services.repository import MongoRepository

router = APIRouter(tags=["integrations"])


def _parse_float(value: str, label: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}") from exc


@router.get("/maps/geocode")
async def geocode(
    query: str = Query(..., min_length=2),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
    service: DataIntegrationService = Depends(get_data_integration_service),
) -> dict:
    return await service.geocode(query)


@router.get("/maps/route")
async def route(
    origin: str,
    destination: str,
    provider: str = "auto",
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
    service: DataIntegrationService = Depends(get_data_integration_service),
) -> dict:
    return await service.route(origin, destination, provider)


@router.get("/traffic")
async def traffic(
    origin: str,
    destination: str,
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
    service: DataIntegrationService = Depends(get_data_integration_service),
) -> dict:
    return await service.traffic(origin, destination)


@router.get("/weather")
async def weather(
    lat: str,
    lng: str,
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
    service: DataIntegrationService = Depends(get_data_integration_service),
) -> dict:
    latitude = _parse_float(lat, "lat")
    longitude = _parse_float(lng, "lng")
    return await service.weather(latitude, longitude)


@router.get("/health/summary")
async def health_summary(
    ctx: AuthContext = Depends(require_scopes("analytics:read")),
) -> dict:
    db = get_db()
    health_repo = MongoRepository(db, HEALTH_RECORDS)
    emergency_repo = MongoRepository(db, EMERGENCY_EVENTS)
    health_count = await health_repo.collection.count_documents({})
    emergency_count = await emergency_repo.collection.count_documents({})
    return {
        "status": "ok",
        "health_records": health_count,
        "emergency_events": emergency_count,
    }


@router.get("/hospitals/summary")
async def hospital_summary(
    ctx: AuthContext = Depends(require_scopes("analytics:read")),
) -> dict:
    db = get_db()
    hospital_repo = MongoRepository(db, HOSPITALS)
    total = await hospital_repo.collection.count_documents({})
    sample = await hospital_repo.find_many({}, limit=5)
    return {
        "status": "ok",
        "total_hospitals": total,
        "sample": sample,
    }
