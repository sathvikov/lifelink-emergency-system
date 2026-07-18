from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_scopes
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.services.collections import ALERTS, AMBULANCES, HOSPITALS, USERS
from app.services.repository import MongoRepository

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    query: str


@router.post("/search")
async def search(payload: SearchRequest, ctx: AuthContext = Depends(require_scopes("dashboard:read"))) -> dict:
    term = payload.query.strip()
    if not term:
        return {"query": term, "results": {}}

    lowered = term.lower()

    db = get_db()
    user_repo = MongoRepository(db, USERS)
    alert_repo = MongoRepository(db, ALERTS)
    ambulance_repo = MongoRepository(db, AMBULANCES)
    hospital_repo = MongoRepository(db, HOSPITALS)

    regex = {"$regex": term, "$options": "i"}

    users = await user_repo.find_many(
        {
            "$or": [
                {"name": regex},
                {"email": regex},
                {"hospitalProfile.regNumber": regex},
                {"location": regex},
            ]
        },
        limit=5,
    )

    alerts = await alert_repo.find_many(
        {"message": regex},
        limit=5,
    )

    ambulances = await ambulance_repo.find_many(
        {
            "$or": [
                {"ambulanceId": regex},
                {"registrationNumber": regex},
                {"driverName": regex},
            ]
        },
        limit=5,
    )

    hospitals = await hospital_repo.find_many(
        {
            "$or": [
                {"name": regex},
                {"hospital_name": regex},
                {"location.city": regex},
                {"location.state": regex},
                {"location.address": regex},
            ]
        },
        limit=5,
    )

    if not hospitals and any(keyword in lowered for keyword in ["hospital", "nearest", "nearby", "clinic"]):
        hospitals = await hospital_repo.find_many({}, sort=[("beds_available", -1), ("rating", -1)], limit=5)

    return {
        "query": term,
        "results": {
            "users": users,
            "alerts": alerts,
            "ambulances": ambulances,
            "hospitals": hospitals,
        },
    }
