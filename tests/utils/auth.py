from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import jwt


def _resolve_secret() -> str:
    for key in ("LIFELINK_JWT_SECRET", "JWT_SECRET", "APP_JWT_SECRET", "JWT_SIGNING_SECRET"):
        value = os.getenv(key)
        if value:
            return value
    env_path = Path(__file__).resolve().parents[2] / "backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("JWT_SECRET="):
                return line.split("=", 1)[1].strip()
            if line.startswith("LIFELINK_JWT_SECRET="):
                return line.split("=", 1)[1].strip()
    return "change_me"


def build_token(role: str, sub_role: str | None = None) -> str:
    secret = _resolve_secret()
    payload = {
        "id": f"test-{role}",
        "role": role,
        "sub_role": sub_role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=2),
    }
    return jwt.encode(payload, secret, algorithm="HS256")
