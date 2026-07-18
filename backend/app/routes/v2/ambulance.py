from fastapi import APIRouter, Depends

from app.core.auth import require_roles, require_scopes
from app.core.dependencies import get_ambulance_service
from app.core.rbac import AuthContext
from app.services.ambulance_service import AmbulanceService

router = APIRouter(tags=["ambulance"])


@router.get("/status")
async def status(ctx: AuthContext = Depends(require_roles("ambulance"))) -> dict:
    return {
        "ambulanceId": ctx.user_id,
        "subRole": ctx.sub_role,
        "status": "available",
    }


@router.post("/assignment")
async def assignment(payload: dict, ctx: AuthContext = Depends(require_scopes("ambulance:write"))) -> dict:
    return {
        "status": "queued",
        "assignment": payload,
        "assignedTo": ctx.user_id,
    }


@router.get("/modules")
async def list_modules(
    ctx: AuthContext = Depends(require_roles("ambulance")),
    service: AmbulanceService = Depends(get_ambulance_service),
) -> dict:
    return service.list_modules()


@router.get("/modules/{module_key}")
async def get_module(
    module_key: str,
    ctx: AuthContext = Depends(require_roles("ambulance")),
    service: AmbulanceService = Depends(get_ambulance_service),
) -> dict:
    return service.get_module(module_key)
