from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_roles, require_scopes
from app.core.dependencies import get_government_service
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.services.government_service import GovernmentService
from app.services.collections import USERS
from app.services.repository import MongoRepository

router = APIRouter(tags=["government"])


@router.get("/overview")
async def overview(ctx: AuthContext = Depends(require_roles("government"))) -> dict:
    return {
        "message": "Government service ready",
        "authorityId": ctx.user_id,
        "level": ctx.sub_role,
    }


@router.post("/policy/simulate")
async def policy_simulation(payload: dict, ctx: AuthContext = Depends(require_scopes("policy:write"))) -> dict:
    return {
        "status": "simulated",
        "input": payload,
        "requestedBy": ctx.user_id,
    }


@router.get("/ambulance/pending")
async def pending_ambulances(ctx: AuthContext = Depends(require_roles("government"))) -> list[dict]:
    db = get_db()
    repo = MongoRepository(db, USERS)
    return await repo.find_many({"role": "ambulance", "isVerified": False})


@router.put("/ambulance/verify/{user_id}")
async def verify_ambulance(user_id: str, ctx: AuthContext = Depends(require_roles("government"))) -> dict:
    db = get_db()
    repo = MongoRepository(db, USERS)
    try:
        oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ambulance id") from exc

    updated = await repo.update_one({"_id": oid}, {"$set": {"isVerified": True}}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Ambulance user not found")

    return {"message": "Ambulance verified", "id": user_id}


@router.get("/modules")
async def list_modules(
    ctx: AuthContext = Depends(require_roles("government")),
    service: GovernmentService = Depends(get_government_service),
) -> dict:
    return service.list_modules(ctx.sub_role)


@router.get("/modules/{module_key}")
async def get_module(
    module_key: str,
    ctx: AuthContext = Depends(require_roles("government")),
    service: GovernmentService = Depends(get_government_service),
) -> dict:
    return service.get_module(ctx.sub_role, module_key)
