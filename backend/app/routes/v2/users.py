from fastapi import APIRouter, Depends

from app.core.auth import get_current_user, require_scopes
from app.core.dependencies import get_user_service
from app.core.rbac import AuthContext
from app.services.user_service import UserService

router = APIRouter(tags=["users"])


@router.get("/me")
async def me(
    ctx: AuthContext = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> dict:
    return service.me(ctx)


@router.get("/permissions")
async def permissions(
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
    service: UserService = Depends(get_user_service),
) -> dict:
    return service.permissions(ctx)
