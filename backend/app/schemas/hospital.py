from pydantic import BaseModel

from app.schemas.common import MongoDocument


class BedInfo(BaseModel):
    totalBeds: int = 0
    occupiedBeds: int = 0
    availableBeds: int = 0


class DoctorInfo(BaseModel):
    name: str
    department: str
    availability: bool = True
    specialization: str | None = None
    phone: str | None = None
    email: str | None = None


class ResourceInfo(BaseModel):
    name: str
    category: str
    totalUnits: int = 0
    availableUnits: int = 0
    unit: str = "units"
    description: str | None = None


class HospitalDocument(MongoDocument):
    user: str
    beds: BedInfo | None = None
    doctors: list[DoctorInfo] | None = None
    resources: list[ResourceInfo] | None = None
