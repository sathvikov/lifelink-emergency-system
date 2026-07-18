from datetime import datetime
from typing import Literal

from app.schemas.common import MongoDocument


class PatientDocument(MongoDocument):
    hospitalId: str
    name: str
    age: int
    gender: str
    contact: str | None = None
    dept: str
    room: str
    condition: str
    severity: Literal["Critical", "High", "Moderate", "Stable"] = "Stable"
    status: str = "Admitted"
    oxygen: int = 98
    heartRate: int = 80
    bp: str = "120/80"
    admitDate: datetime | None = None
