from typing import Literal

from app.schemas.common import MongoDocument


class ResourceRequestDocument(MongoDocument):
    requester: str
    requestType: Literal["blood", "organ"]
    details: str | None = None
    urgency: Literal["low", "medium", "high"]
    status: Literal["pending", "matched", "fulfilled", "cancelled"] = "pending"
