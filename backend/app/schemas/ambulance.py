from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import MongoDocument


class LocationPoint(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    timestamp: datetime | None = None


class ETAPrediction(BaseModel):
    estimatedMinutes: int | None = None
    confidenceLevel: Literal["High", "Medium", "Low"] = "Medium"
    trafficFactor: float | None = None
    weatherCondition: str | None = None
    lastUpdated: datetime | None = None


class RouteInfo(BaseModel):
    startLocation: LocationPoint | None = None
    destinationLocation: LocationPoint | None = None
    routePath: list[LocationPoint] | None = None
    distanceKm: float | None = None
    estimatedTimeMinutes: int | None = None
    startTime: datetime | None = None
    estimatedArrivalTime: datetime | None = None
    actualArrivalTime: datetime | None = None


class DriverInfo(BaseModel):
    name: str | None = None
    licenseNumber: str | None = None
    phone: str | None = None
    availability: bool = True


class AmbulanceMetrics(BaseModel):
    averageResponseTime: float | None = None
    onTimeDeliveryRate: float | None = None
    totalTripsToday: int = 0
    totalDistanceTodayKm: float = 0


class AmbulanceDocument(MongoDocument):
    ambulanceId: str
    registrationNumber: str
    hospital: str
    status: Literal["available", "en_route", "at_location", "returning", "maintenance"] = "available"
    currentLocation: LocationPoint | None = None
    activeRoute: RouteInfo | None = None
    etaPrediction: ETAPrediction | None = None
    driver: DriverInfo | None = None
    currentEmergency: str | None = None
    patientCount: int = 0
    emergencyType: str | None = None
    priorityLevel: Literal["Low", "Medium", "High", "Critical"] | None = None
    metrics: AmbulanceMetrics | None = None
    lastLocationUpdate: datetime | None = None
