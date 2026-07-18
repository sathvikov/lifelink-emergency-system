from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db.mongo import get_db
from app.services.collections import FEATURE_STORE
from app.services.repository import MongoRepository


class FeatureStore:
    def __init__(self) -> None:
        self._db = get_db()
        self._repo = MongoRepository(self._db, FEATURE_STORE)

    async def upsert(self, entity_type: str, entity_id: str, features: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "features": features,
            "updated_at": datetime.utcnow().isoformat(),
        }
        existing = await self._repo.find_one({"entity_type": entity_type, "entity_id": entity_id})
        if existing:
            await self._repo.update_one(
                {"entity_type": entity_type, "entity_id": entity_id},
                {"$set": payload},
            )
            return payload
        return await self._repo.insert_one(payload)

    async def get(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        return await self._repo.find_one({"entity_type": entity_type, "entity_id": entity_id})

    async def list(self, entity_type: str, limit: int = 200) -> list[dict[str, Any]]:
        return await self._repo.find_many({"entity_type": entity_type}, limit=limit)
