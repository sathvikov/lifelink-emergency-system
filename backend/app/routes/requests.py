from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import RESOURCE_REQUESTS
from app.services.repository import MongoRepository

router = APIRouter(tags=["requests"])


class ResourceRequestCreate(BaseModel):
    requester_id: str
    request_type: str
    details: str | None = None
    urgency: str


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


@router.post("/requests", status_code=201)
async def create_request(payload: ResourceRequestCreate):
    db = get_db()
    repo = MongoRepository(db, RESOURCE_REQUESTS)

    doc = {
        "requester": _as_object_id(payload.requester_id),
        "requestType": payload.request_type,
        "details": payload.details,
        "urgency": payload.urgency,
        "status": "pending",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    await repo.insert_one(doc)
    return {"message": "Request created successfully"}
