from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b\+?\d{10,13}\b")


def _collect_texts(value: Any, texts: list[str]) -> None:
    if isinstance(value, str):
        texts.append(value)
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_texts(item, texts)
        return
    if isinstance(value, list):
        for item in value:
            _collect_texts(item, texts)



def redact_text(value: str) -> str:
    value = EMAIL_RE.sub("[redacted-email]", value)
    value = PHONE_RE.sub("[redacted-phone]", value)
    return value


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, val in payload.items():
        if isinstance(val, str):
            redacted[key] = redact_text(val)
        elif isinstance(val, dict):
            redacted[key] = redact_payload(val)
        elif isinstance(val, list):
            redacted[key] = [redact_payload(v) if isinstance(v, dict) else redact_text(v) if isinstance(v, str) else v for v in val]
        else:
            redacted[key] = val
    return redacted


def scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    texts: list[str] = []
    _collect_texts(payload, texts)
    emails: list[str] = []
    phones: list[str] = []
    for text in texts:
        emails.extend(EMAIL_RE.findall(text))
        phones.extend(PHONE_RE.findall(text))

    unique_emails = sorted(set(emails))
    unique_phones = sorted(set(phones))
    return {
        "pii_found": bool(unique_emails or unique_phones),
        "emails": unique_emails,
        "phones": unique_phones,
    }
