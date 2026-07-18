from __future__ import annotations

from app.core.rbac import AuthContext


class UserService:
    def me(self, ctx: AuthContext) -> dict:
        return {
            "id": ctx.user_id,
            "role": ctx.role,
            "subRole": ctx.sub_role,
            "scopes": sorted(ctx.scopes),
        }

    def permissions(self, ctx: AuthContext) -> dict:
        return {
            "role": ctx.role,
            "subRole": ctx.sub_role,
            "scopes": sorted(ctx.scopes),
        }
