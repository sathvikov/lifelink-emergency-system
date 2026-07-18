from fastapi import APIRouter, Depends

from app.core.auth import require_scopes
from app.core.rbac import AuthContext

router = APIRouter(tags=["analytics"])


@router.get("/summary")
async def summary(ctx: AuthContext = Depends(require_scopes("analytics:read"))) -> dict:
    return {
        "status": "ok",
        "requestedBy": ctx.user_id,
        "metrics": {
            "active_alerts": 0,
            "available_beds": 0,
            "ambulances_available": 0,
        },
    }
