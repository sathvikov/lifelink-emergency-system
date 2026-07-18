from __future__ import annotations

import hashlib
from typing import Any

from app.core.config import get_settings


_PII_FIELDS = {"name", "full_name", "phone", "address", "email"}


def _hash_value(value: str, salt: str) -> str:
    digest = hashlib.sha256(f"{value}:{salt}".encode("utf-8")).hexdigest()
    return digest


def anonymize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    cleaned: dict[str, Any] = {}
    for key, value in (payload or {}).items():
        lower_key = key.lower()
        if lower_key in _PII_FIELDS:
            continue
        if lower_key in {"id", "user_id", "patient_id"}:
            if value is not None:
                cleaned["hashed_id"] = _hash_value(str(value), settings.privacy_salt)
            continue
        cleaned[key] = value
    return cleaned
