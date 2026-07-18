from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from bson import ObjectId

from app.core.rbac import AuthContext, ensure_roles, ensure_scopes, resolve_scopes
from app.core.security import decode_access_token
from app.db.mongo import get_db
from app.services.collections import USERS
from app.services.repository import MongoRepository


def _extract_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()


async def get_optional_user(authorization: str | None = Header(default=None)) -> AuthContext | None:
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()

    try:
        payload = decode_access_token(token)
    except Exception as exc:
        return None

    user_id = payload.get("id") or payload.get("sub")
    role = payload.get("role") or payload.get("portal") or payload.get("portalRole")
    sub_role = payload.get("sub_role") or payload.get("subRole")

    if not user_id or not role:
        return None

    db = get_db()
    user_repo = MongoRepository(db, USERS)
    try:
        lookup_id = ObjectId(str(user_id))
    except Exception:
        lookup_id = user_id
    user = await user_repo.find_one({"_id": lookup_id})
    if not user:
        return None

    scopes = resolve_scopes(role, sub_role)
    return AuthContext(user_id=str(user_id), role=role, sub_role=sub_role, scopes=scopes)


async def get_current_user(authorization: str | None = Header(default=None)) -> AuthContext:
    token = _extract_token(authorization)
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = payload.get("id") or payload.get("sub")
    role = payload.get("role") or payload.get("portal") or payload.get("portalRole")
    sub_role = payload.get("sub_role") or payload.get("subRole")

    if not user_id or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    db = get_db()
    user_repo = MongoRepository(db, USERS)
    try:
        lookup_id = ObjectId(str(user_id))
    except Exception:
        lookup_id = user_id
    user = await user_repo.find_one({"_id": lookup_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    scopes = resolve_scopes(role, sub_role)
    return AuthContext(user_id=str(user_id), role=role, sub_role=sub_role, scopes=scopes)


def require_roles(*roles: str):
    def _dependency(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        ensure_roles(ctx.role, roles)
        return ctx

    return _dependency


def require_scopes(*scopes: str):
    def _dependency(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        ensure_scopes(ctx.scopes, scopes)
        return ctx

    return _dependency
