from fastapi import APIRouter, Body, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.auth import require_scopes
from app.core.rbac import AuthContext
from app.core.dependencies import get_realtime_service
from app.services.realtime_service import RealtimeService

router = APIRouter(tags=["realtime"])
_service: RealtimeService = get_realtime_service()


class PublishEvent(BaseModel):
    channel: str
    event: dict


@router.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    await _service.connect(channel, websocket)
    try:
        while True:
            payload = await websocket.receive_json()
            await _service.broadcast(channel, {"channel": channel, "payload": payload})
    except WebSocketDisconnect:
        _service.disconnect(channel, websocket)


@router.post("/publish")
async def publish(
    payload: PublishEvent,
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    await _service.broadcast(payload.channel, {"channel": payload.channel, "payload": payload.event})
    return {"status": "ok", "channel": payload.channel}


@router.post("/ambulance-update")
async def ambulance_update(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("ambulance:write")),
) -> dict:
    await _service.broadcast("ambulance", {"type": "ambulance_update", "payload": payload})
    return {"status": "ok"}


@router.post("/hospital-update")
async def hospital_update(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("hospital:write")),
) -> dict:
    await _service.broadcast("hospital", {"type": "hospital_update", "payload": payload})
    return {"status": "ok"}


@router.post("/alert")
async def alert_event(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("emergency:trigger")),
) -> dict:
    await _service.broadcast("alerts", {"type": "alert", "payload": payload})
    return {"status": "ok"}


@router.post("/government-update")
async def government_update(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("gov:write")),
) -> dict:
    await _service.broadcast("government", {"type": "government_update", "payload": payload})
    return {"status": "ok"}
