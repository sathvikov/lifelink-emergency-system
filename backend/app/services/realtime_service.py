from __future__ import annotations

from app.services.realtime.manager import ConnectionManager


class RealtimeService:
    def __init__(self) -> None:
        self.manager = ConnectionManager()

    async def connect(self, channel: str, websocket) -> None:
        await self.manager.connect(channel, websocket)

    def disconnect(self, channel: str, websocket) -> None:
        self.manager.disconnect(channel, websocket)

    async def broadcast(self, channel: str, message: dict) -> None:
        await self.manager.broadcast(channel, message)
