from datetime import datetime
from typing import Literal

from app.schemas.common import MongoDocument


class DonationDocument(MongoDocument):
    donor: str
    donationType: Literal["blood", "organ"]
    donationDate: datetime | None = None
    hospital: str
    details: str | None = None
