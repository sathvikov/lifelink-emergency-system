from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict

_MEMORY_LOCK = threading.Lock()
_MEMORY: Dict[str, Dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def create_session(initial_state: dict | None = None) -> dict:
    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "createdAt": _now(),
        "updatedAt": _now(),
        "state": initial_state or {},
        "log": [],
    }
    with _MEMORY_LOCK:
        _MEMORY[session_id] = session
    return session.copy()


def ensure_session(session_id: str, initial_state: dict | None = None) -> dict:
    with _MEMORY_LOCK:
        existing = _MEMORY.get(session_id)
        if existing:
            return existing.copy()
        session = {
            "id": session_id,
            "createdAt": _now(),
            "updatedAt": _now(),
            "state": initial_state or {},
            "log": [],
        }
        _MEMORY[session_id] = session
        return session.copy()


def get_session(session_id: str) -> dict | None:
    with _MEMORY_LOCK:
        session = _MEMORY.get(session_id)
        return session.copy() if session else None


def update_session(session_id: str, state: dict) -> dict | None:
    with _MEMORY_LOCK:
        session = _MEMORY.get(session_id)
        if not session:
            return None
        session["state"] = state
        session["updatedAt"] = _now()
        return session.copy()


def append_log(session_id: str, entry: dict) -> dict | None:
    with _MEMORY_LOCK:
        session = _MEMORY.get(session_id)
        if not session:
            return None
        session["log"].append(entry)
        session["updatedAt"] = _now()
        return session.copy()
