from datetime import datetime
from typing import Literal

from app.schemas.common import MongoDocument


class ResourceDocument(MongoDocument):
    hospitalId: str
    name: str
    category: Literal["Medicine", "Blood", "Organ", "Equipment"]
    quantity: int
    unit: str = "units"
    minThreshold: int = 10
    expiryDate: datetime | None = None
    lastUpdated: datetime | None = None
