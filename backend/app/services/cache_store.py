from __future__ import annotations

import json
import time
from typing import Any

import redis


class CacheStore:
    def __init__(self, redis_url: str, namespace: str) -> None:
        self._namespace = namespace
        self._memory_cache: dict[str, dict[str, Any]] = {}
        self._redis = self._init_redis(redis_url)

    @staticmethod
    def _init_redis(redis_url: str):
        try:
            client = redis.Redis.from_url(redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def get(self, key: str) -> dict[str, Any] | None:
        namespaced = self._key(key)
        if self._redis:
            try:
                cached = self._redis.get(namespaced)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        entry = self._memory_cache.get(namespaced)
        if not entry:
            return None
        if entry["expires_at"] <= time.time():
            self._memory_cache.pop(namespaced, None)
            return None
        return entry["value"]

    def set(self, key: str, value: dict[str, Any], ttl: int = 300) -> None:
        namespaced = self._key(key)
        if self._redis:
            try:
                self._redis.setex(namespaced, ttl, json.dumps(value))
                return
            except Exception:
                pass
        self._memory_cache[namespaced] = {"value": value, "expires_at": time.time() + ttl}
