from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import MongoDocument


class RequestDetails(BaseModel):
    staffCount: int = 0
    specialization: str | None = None
    resourceName: str | None = None
    resourceQuantity: int | None = None
    urgencyLevel: Literal["low", "medium", "high", "critical"] = "medium"
    preferredDate: datetime | None = None
    duration: str | None = None


class ResponseDetails(BaseModel):
    message: str | None = None
    responseDate: datetime | None = None
    respondedBy: str | None = None


class HospitalMessageDocument(MongoDocument):
    fromHospital: str
    toHospital: str
    messageType: Literal["staff", "doctor", "resource"]
    subject: str
    details: str
    requestDetails: RequestDetails | None = None
    status: Literal["pending", "approved", "rejected", "resolved"] = "pending"
    response: ResponseDetails | None = None
