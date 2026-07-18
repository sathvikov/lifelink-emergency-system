from __future__ import annotations

from app.db.asyncpg_pool import fetch_one


async def get_latest_prediction(prediction_type: str) -> dict | None:
    row = await fetch_one(
        """
        SELECT id, prediction_type AS type, result, confidence, created_at
        FROM predictions
        WHERE prediction_type = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        prediction_type,
    )
    if not row:
        return None
    return {
        "id": row.get("id"),
        "type": row.get("type"),
        "result": row.get("result") or {},
        "confidence": float(row.get("confidence") or 0.0),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
    }
