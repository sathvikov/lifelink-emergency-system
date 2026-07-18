from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import RESOURCE_REQUESTS, USERS
from app.services.repository import MongoRepository

router = APIRouter(tags=["donors"])


def _normalize_blood_group(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).replace(" ", "").upper()


def _resolve_blood_group(donor: dict, donor_profile: dict, health: dict) -> str:
    candidates = [
        donor_profile.get("bloodGroup"),
        donor_profile.get("blood_group"),
        health.get("bloodGroup"),
        health.get("blood_group"),
        donor.get("bloodGroup"),
        donor.get("blood_group"),
    ]
    for value in candidates:
        normalized = _normalize_blood_group(value)
        if normalized:
            return normalized
    return "O+"


class DonorAvailabilityUpdate(BaseModel):
    userId: str
    availability: str
    organTypes: list[str] | None = None
    lastDonation: str | None = None


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


@router.get("/donors")
async def get_donors():
    db = get_db()
    user_repo = MongoRepository(db, USERS)

    donors = await user_repo.find_many(
        {"role": "public"},
        projection={"name": 1, "location": 1, "phone": 1, "publicProfile": 1},
    )

    results = []
    for donor in donors:
        health = (donor.get("publicProfile") or {}).get("healthRecords") or {}
        donor_profile = (donor.get("publicProfile") or {}).get("donorProfile") or {}
        blood_group = _resolve_blood_group(donor, donor_profile, health)
        results.append(
            {
                "user_id": donor.get("_id"),
                "name": donor.get("name"),
                "location": donor.get("location") or health.get("location") or "Unknown",
            "blood_group": blood_group,
                "phone": donor.get("phone") or "Not available",
                "age": health.get("age"),
                "gender": health.get("gender"),
                "availability": donor_profile.get("availability") or "Available",
                "lastDonation": donor_profile.get("lastDonation") or health.get("lastDonation") or "2026-01-01",
                "organTypes": donor_profile.get("organTypes") or ["Blood"],
            }
        )

    return results


@router.patch("/donors/availability")
async def update_availability(payload: DonorAvailabilityUpdate):
    db = get_db()
    user_repo = MongoRepository(db, USERS)
    oid = _as_object_id(payload.userId)

    update_data = {
        "publicProfile.donorProfile.availability": payload.availability,
        "publicProfile.donorProfile.updatedAt": datetime.utcnow().isoformat(),
    }
    if payload.organTypes is not None:
        update_data["publicProfile.donorProfile.organTypes"] = payload.organTypes
    if payload.lastDonation is not None:
        update_data["publicProfile.donorProfile.lastDonation"] = payload.lastDonation

    updated = await user_repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Donor not found")
    return {"status": "ok", "availability": payload.availability}


@router.get("/donors/forecast")
async def donor_forecast(blood_group: str | None = None):
    db = get_db()
    user_repo = MongoRepository(db, USERS)
    request_repo = MongoRepository(db, RESOURCE_REQUESTS)

    donors = await user_repo.find_many({"role": "public"}, projection={"publicProfile": 1})
    requests = await request_repo.find_many({"requestType": {"$in": ["blood", "Blood", "plasma"]}})

    supply = 0
    for donor in donors:
        health = (donor.get("publicProfile") or {}).get("healthRecords") or {}
        donor_profile = (donor.get("publicProfile") or {}).get("donorProfile") or {}
        donor_group = _resolve_blood_group(donor, donor_profile, health)
        availability = donor_profile.get("availability") or "Available"
        if blood_group and donor_group != blood_group:
            continue
        if availability in {"Available", "On Call"}:
            supply += 1

    demand = len(requests)
    availability_score = max(10, min(95, int((supply + 1) / max(1, demand) * 50)))
    demand_index = max(1, demand - supply)

    meta = {
        "confidence": 0.6,
        "reasoning": [
            "Availability derived from active donor count and recent blood/plasma requests.",
            "Scores are heuristic estimates when ML forecasts are unavailable.",
        ],
        "references": [
            {"title": "Dataset", "detail": "ml/donor_availability_data.csv"},
            {"title": "Model", "detail": "ml/donor_availability_model.joblib"},
        ],
    }

    return {
        "blood_group": blood_group or "All",
        "supply": supply,
        "demand": demand,
        "availability_score": availability_score,
        "demand_index": demand_index,
        "forecast_days": max(1, 10 - min(9, supply)),
        "meta": meta,
    }
