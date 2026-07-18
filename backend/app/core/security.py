from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


def create_access_token(subject: str, expires_minutes: int = 60, claims: dict | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
