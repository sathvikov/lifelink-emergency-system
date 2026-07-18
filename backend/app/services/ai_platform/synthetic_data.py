from __future__ import annotations

from datetime import datetime
from typing import Any

from faker import Faker

from app.db.mongo import get_db
from app.services.collections import SYNTHETIC_EVENTS
from app.services.repository import MongoRepository

faker = Faker()


class SyntheticDataService:
    def __init__(self) -> None:
        self._db = get_db()
        self._repo = MongoRepository(self._db, SYNTHETIC_EVENTS)

    async def bootstrap(self, role: str, module_key: str, count: int = 25) -> dict[str, Any]:
        events = []
        for _ in range(count):
            events.append({
                "role": role,
                "module_key": module_key,
                "created_at": datetime.utcnow().isoformat(),
                "summary": faker.sentence(nb_words=8),
                "severity": faker.random_element(["Low", "Medium", "High", "Critical"]),
                "location": faker.city(),
                "metrics": {
                    "score": faker.random_int(40, 95),
                    "confidence": faker.random_int(60, 99),
                },
            })

        inserted = []
        for event in events:
            inserted.append(await self._repo.insert_one(event))

        return {
            "count": len(inserted),
            "items": inserted,
        }
