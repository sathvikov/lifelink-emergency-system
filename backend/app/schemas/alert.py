from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import MongoDocument


class Coordinates(BaseModel):
    lat: float | None = None
    lng: float | None = None


class AlertDocument(MongoDocument):
    user: str
    locationDetails: str
    coordinates: Coordinates | None = None
    message: str
    emergencyType: str = "Unclassified"
    priority: Literal["High", "Medium", "Low"] = "High"
    status: Literal["pending", "dispatched", "resolved", "cancelled"] = "pending"
    severity_score: float | None = None
    ai_confidence: float | None = None
    ambulance_type: str = "Standard"
    recommended_hospital: str | None = None
    dispatchedHospital: str | None = None
    createdAt: datetime | None = None
