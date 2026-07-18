from datetime import date, datetime
from decimal import Decimal
from typing import Any

from bson import ObjectId


def to_serializable(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [to_serializable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_serializable(v) for k, v in value.items()}
    return value


def normalize_mongo_doc(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    return to_serializable(doc)
