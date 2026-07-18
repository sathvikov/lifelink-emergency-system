from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db.mongo import get_db
from app.services.collections import MODEL_REGISTRY
from app.services.repository import MongoRepository


class ModelRegistry:
    def __init__(self) -> None:
        self._db = get_db()
        self._repo = MongoRepository(self._db, MODEL_REGISTRY)

    async def register(self, name: str, version: str, metadata: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "name": name,
            "version": version,
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat(),
            "status": metadata.get("status", "active"),
        }
        return await self._repo.insert_one(payload)

    async def list(self, name: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if name:
            query["name"] = name
        return await self._repo.find_many(query, sort=[("created_at", -1)], limit=limit)

    async def get_latest(self, name: str) -> dict[str, Any] | None:
        records = await self._repo.find_many({"name": name}, sort=[("created_at", -1)], limit=1)
        return records[0] if records else None
