from __future__ import annotations

import json
import time
from typing import Any

import redis


class EventStream:
    def __init__(self, redis_url: str, namespace: str = "lifelink:ai") -> None:
        self._namespace = namespace
        self._redis = self._init_redis(redis_url)
        self._fallback: dict[str, list[dict[str, Any]]] = {}

    @staticmethod
    def _init_redis(redis_url: str):
        try:
            client = redis.Redis.from_url(redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

    def _stream_key(self, stream: str) -> str:
        return f"{self._namespace}:{stream}"

    def publish(self, stream: str, payload: dict[str, Any], maxlen: int = 2000) -> dict[str, Any]:
        record = {
            "ts": time.time(),
            "payload": payload,
        }
        key = self._stream_key(stream)
        if self._redis:
            try:
                event_id = self._redis.xadd(key, {"data": json.dumps(record)}, maxlen=maxlen)
                return {"status": "ok", "event_id": event_id}
            except Exception:
                pass

        self._fallback.setdefault(key, []).append(record)
        return {"status": "fallback", "event_id": str(len(self._fallback[key]))}

    def read(self, stream: str, count: int = 50) -> list[dict[str, Any]]:
        key = self._stream_key(stream)
        if self._redis:
            try:
                rows = self._redis.xrevrange(key, count=count)
                results = []
                for _, data in rows:
                    raw = data.get("data")
                    try:
                        results.append(json.loads(raw) if raw else {})
                    except Exception:
                        results.append({"payload": raw})
                return results
            except Exception:
                pass

        return list(reversed(self._fallback.get(key, [])[-count:]))
