from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg

from app.core.config import get_settings


def _hash_chain(data: str, prev_hash: str | None) -> str:
    base = f"{data}:{prev_hash or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


async def append_audit_log(action: str, actor: str, details: str) -> dict:
    settings = get_settings()
    dsn = settings.postgres_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn=dsn)
    try:
        last = await conn.fetchrow("SELECT hash FROM audit_logs ORDER BY timestamp DESC LIMIT 1")
        prev_hash = last.get("hash") if last else None
    finally:
        await conn.close()
    timestamp = datetime.now(timezone.utc)
    record_id = uuid4().hex
    hash_value = _hash_chain(f"{action}|{actor}|{details}|{timestamp.isoformat()}", prev_hash)

    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            """
            INSERT INTO audit_logs (id, action, actor, timestamp, hash, prev_hash)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            record_id,
            action,
            actor,
            timestamp,
            hash_value,
            prev_hash,
        )
    finally:
        await conn.close()

    return {
        "id": record_id,
        "action": action,
        "actor": actor,
        "timestamp": timestamp.isoformat(),
        "hash": hash_value,
        "prev_hash": prev_hash,
    }
