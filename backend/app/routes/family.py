from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import ALERTS, FAMILY_MEMBERS, NOTIFICATIONS
from app.services.repository import MongoRepository

router = APIRouter(tags=["family"])


class FamilyMemberCreate(BaseModel):
    userId: str
    name: str
    relation: str
    phone: str | None = None
    location: str | None = None


class FamilyMemberUpdate(BaseModel):
    name: str | None = None
    relation: str | None = None
    phone: str | None = None
    location: str | None = None
    status: str | None = None
    lastCheckIn: str | None = None


class FamilyLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    label: str | None = None


class FamilyVitalsUpdate(BaseModel):
    heart_rate: int | None = None
    oxygen: int | None = None
    blood_pressure: str | None = None
    temperature: float | None = None


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


@router.get("/members/{user_id}")
async def list_members(user_id: str):
    db = get_db()
    repo = MongoRepository(db, FAMILY_MEMBERS)
    members = await repo.find_many({"user": _as_object_id(user_id)}, sort=[("createdAt", -1)])
    return {"count": len(members), "data": members}


@router.post("/members", status_code=201)
async def create_member(payload: FamilyMemberCreate):
    db = get_db()
    repo = MongoRepository(db, FAMILY_MEMBERS)

    doc = {
        "user": _as_object_id(payload.userId),
        "name": payload.name,
        "relation": payload.relation,
        "phone": payload.phone,
        "location": payload.location,
        "status": "Safe",
        "lastCheckIn": datetime.utcnow().isoformat(),
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    return created


@router.patch("/members/{member_id}")
async def update_member(member_id: str, payload: FamilyMemberUpdate):
    db = get_db()
    repo = MongoRepository(db, FAMILY_MEMBERS)
    alert_repo = MongoRepository(db, ALERTS)
    notification_repo = MongoRepository(db, NOTIFICATIONS)

    existing = await repo.find_one({"_id": _as_object_id(member_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Family member not found")

    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    update_data["updatedAt"] = datetime.utcnow()
    updated = await repo.update_one({"_id": _as_object_id(member_id)}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Family member not found")

    if payload.status and payload.status.lower() == "needs help":
        user_id = existing.get("user")
        message = f"Family member {existing.get('name')} requested help."
        created_alert = await alert_repo.insert_one(
            {
                "user": user_id,
                "message": message,
                "emergencyType": "High",
                "priority": "High",
                "status": "pending",
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
        )
        await notification_repo.insert_one(
            {
                "user": user_id,
                "type": "family_alert",
                "title": "Family Alert",
                "message": message,
                "severity": "High",
                "createdAt": datetime.utcnow(),
                "read": False,
                "metadata": {"member_id": member_id, "alert_id": created_alert.get("_id")},
            }
        )

    return updated


@router.patch("/members/{member_id}/location")
async def update_member_location(member_id: str, payload: FamilyLocationUpdate):
    db = get_db()
    repo = MongoRepository(db, FAMILY_MEMBERS)

    update_data = {
        "lastLocation": {
            "lat": payload.latitude,
            "lng": payload.longitude,
            "label": payload.label or "Live location",
            "updatedAt": datetime.utcnow().isoformat(),
        },
        "updatedAt": datetime.utcnow(),
    }

    updated = await repo.update_one({"_id": _as_object_id(member_id)}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Family member not found")
    return updated


@router.post("/members/{member_id}/vitals")
async def update_member_vitals(member_id: str, payload: FamilyVitalsUpdate):
    db = get_db()
    repo = MongoRepository(db, FAMILY_MEMBERS)

    update_data = {
        "lastVitals": {
            "heart_rate": payload.heart_rate,
            "oxygen": payload.oxygen,
            "blood_pressure": payload.blood_pressure,
            "temperature": payload.temperature,
            "updatedAt": datetime.utcnow().isoformat(),
        },
        "lastCheckIn": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow(),
    }

    updated = await repo.update_one({"_id": _as_object_id(member_id)}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Family member not found")
    return updated


@router.get("/insights/{user_id}")
async def family_insights(user_id: str):
    db = get_db()
    repo = MongoRepository(db, FAMILY_MEMBERS)
    members = await repo.find_many({"user": _as_object_id(user_id)})

    at_risk = []
    trend_summary = []
    for member in members:
        vitals = member.get("lastVitals") or {}
        oxygen = vitals.get("oxygen")
        heart_rate = vitals.get("heart_rate")
        risk = "Low"
        if oxygen is not None and oxygen < 92:
            risk = "High"
        if heart_rate is not None and heart_rate > 110:
            risk = "High"
        if member.get("status") == "Needs Help":
            risk = "High"

        trend_summary.append(
            {
                "member_id": member.get("_id"),
                "name": member.get("name"),
                "risk": risk,
                "lastCheckIn": member.get("lastCheckIn"),
            }
        )
        if risk == "High":
            at_risk.append(member.get("name"))

    return {
        "count": len(members),
        "at_risk": at_risk,
        "summary": trend_summary,
    }
