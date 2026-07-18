from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.dependencies import get_auth_service
from app.core.rbac import AuthContext
from app.schemas.portal_auth import PortalLoginRequest, PortalSignupRequest
from app.services.auth_service import AuthService

router = APIRouter(tags=["auth"])


@router.get("/portals")
async def list_portals(service: AuthService = Depends(get_auth_service)) -> dict:
    return service.list_portals()


@router.post("/signup", status_code=201)
async def signup(
    payload: PortalSignupRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    return await service.signup(payload)


@router.post("/login")
async def login(
    payload: PortalLoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    return await service.login(payload)


@router.post("/select-role")
async def select_role(
    payload: dict,
    ctx: AuthContext = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    sub_role = payload.get("subRole")
    if not sub_role:
        raise HTTPException(status_code=400, detail="subRole is required")
    return await service.select_role(sub_role, ctx)
