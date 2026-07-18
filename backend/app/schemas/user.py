from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import MongoDocument


class HealthRecords(BaseModel):
    age: int | None = None
    gender: str | None = None
    bloodGroup: str | None = None
    conditions: list[str] | None = None
    location: str | None = None
    contact: str | None = None


class PublicProfile(BaseModel):
    healthRecords: HealthRecords | None = None


class HospitalProfile(BaseModel):
    regNumber: str | None = None
    type: str = "General"
    totalBeds: int = 0
    ambulances: int = 0
    specialties: list[str] | None = None
    website: str | None = None
    isVerified: bool | None = None
    departmentRole: str | None = None


class GovernmentProfile(BaseModel):
    level: str | None = None


class AmbulanceProfile(BaseModel):
    base: str | None = None
    vehicleId: str | None = None


class UserDocument(MongoDocument):
    name: str
    email: str
    password: str
    role: Literal["public", "hospital", "ambulance", "government"]
    subRole: str | None = None
    isVerified: bool = False
    location: str | None = None
    phone: str | None = None
    publicProfile: PublicProfile | None = None
    hospitalProfile: HospitalProfile | None = None
    governmentProfile: GovernmentProfile | None = None
    ambulanceProfile: AmbulanceProfile | None = None
    createdAt: datetime | None = None


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str
    location: str | None = None
    phone: str | None = None
    regNumber: str | None = None
    hospitalType: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str
    role: str | None = None
