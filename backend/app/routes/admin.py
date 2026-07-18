from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import USERS
from app.services.repository import MongoRepository

router = APIRouter(tags=["admin"])


class VerifyHospitalRequest(BaseModel):
    hospitalUserId: str


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


@router.post("/users/verify")
async def verify_hospital(payload: VerifyHospitalRequest):
    db = get_db()
    user_repo = MongoRepository(db, USERS)

    oid = _as_object_id(payload.hospitalUserId)
    updated = await user_repo.update_one(
        {"_id": oid},
        {"$set": {"isVerified": True}},
        return_new=True,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Hospital user not found")

    return {"message": "Hospital Verified Successfully"}
