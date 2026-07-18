from __future__ import annotations

from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.setdefault(channel, set()).add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        if channel in self.active:
            self.active[channel].discard(websocket)
            if not self.active[channel]:
                del self.active[channel]

    async def broadcast(self, channel: str, message: dict) -> None:
        for ws in list(self.active.get(channel, [])):
            await ws.send_json(message)
