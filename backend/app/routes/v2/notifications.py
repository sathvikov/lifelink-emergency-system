from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_scopes
from app.core.dependencies import get_notification_service
from app.core.rbac import AuthContext
from app.services.notification_service import NotificationService

router = APIRouter(tags=["notifications"])


class EmailNotification(BaseModel):
    to_email: str
    subject: str
    html: str


@router.post("/email")
async def send_email_notification(
    payload: EmailNotification,
    ctx: AuthContext = Depends(require_scopes("alerts:read")),
    service: NotificationService = Depends(get_notification_service),
) -> dict:
    result = service.send_email(payload.to_email, payload.subject, payload.html)
    return {"requestedBy": ctx.user_id, **result}
