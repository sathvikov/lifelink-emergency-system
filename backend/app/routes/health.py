from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import HEALTH_RECORDS, PREDICTIONS
from app.services.repository import MongoRepository

router = APIRouter(tags=["health"])


class VitalsIngestRequest(BaseModel):
    userId: str
    source: str | None = "manual"
    heart_rate: int | None = None
    blood_pressure: int | None = None
    oxygen: int | None = None
    temperature: float | None = None
    steps: int | None = None
    note: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class VitalsSample(BaseModel):
    source: str | None = "wearable"
    heart_rate: int | None = None
    blood_pressure: int | None = None
    oxygen: int | None = None
    temperature: float | None = None
    steps: int | None = None
    note: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class WearableIngestRequest(BaseModel):
    userId: str
    payloads: list[VitalsSample]


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


@router.get("/")
async def root() -> dict:
    return {
        "status": "ok",
        "service": "lifelink-fastapi",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "lifelink-fastapi"}


@router.post("/health/vitals", status_code=201)
async def ingest_vitals(payload: VitalsIngestRequest):
    db = get_db()
    repo = MongoRepository(db, HEALTH_RECORDS)

    doc = {
        "user": _as_object_id(payload.userId),
        "record_type": "vitals",
        "source": payload.source or "manual",
        "metrics": {
            "heart_rate": payload.heart_rate,
            "blood_pressure": payload.blood_pressure,
            "oxygen": payload.oxygen,
            "temperature": payload.temperature,
            "steps": payload.steps,
        },
        "note": payload.note,
        "location": {"lat": payload.latitude, "lng": payload.longitude}
        if payload.latitude is not None and payload.longitude is not None
        else None,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    return created


@router.post("/health/wearables/ingest", status_code=201)
async def ingest_wearables(payload: WearableIngestRequest):
    db = get_db()
    repo = MongoRepository(db, HEALTH_RECORDS)

    inserted = 0
    for entry in payload.payloads:
        doc = {
            "user": _as_object_id(payload.userId),
            "record_type": "vitals",
            "source": entry.source or "wearable",
            "metrics": {
                "heart_rate": entry.heart_rate,
                "blood_pressure": entry.blood_pressure,
                "oxygen": entry.oxygen,
                "temperature": entry.temperature,
                "steps": entry.steps,
            },
            "note": entry.note,
            "location": {"lat": entry.latitude, "lng": entry.longitude}
            if entry.latitude is not None and entry.longitude is not None
            else None,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
        }
        await repo.insert_one(doc)
        inserted += 1

    return {"status": "ok", "inserted": inserted}


@router.get("/health/vitals/latest/{user_id}")
async def latest_vitals(user_id: str):
    db = get_db()
    repo = MongoRepository(db, HEALTH_RECORDS)
    oid = _as_object_id(user_id)
    latest = await repo.find_many({"user": oid, "record_type": "vitals"}, sort=[("createdAt", -1)], limit=1)
    return latest[0] if latest else {}


@router.get("/health/risk/history/{user_id}")
async def risk_history(user_id: str):
    db = get_db()
    repo = MongoRepository(db, PREDICTIONS)
    oid = _as_object_id(user_id)
    records = await repo.find_many({"user": oid, "prediction_type": "health_risk"}, sort=[("createdAt", -1)], limit=12)
    return {"count": len(records), "data": records}


@router.get("/health/records/{user_id}")
async def health_records(user_id: str):
    db = get_db()
    repo = MongoRepository(db, HEALTH_RECORDS)
    oid = _as_object_id(user_id)
    records = await repo.find_many({"user": oid, "record_type": {"$in": ["medical_record", "report_analysis"]}}, sort=[("createdAt", -1)], limit=50)
    return {"count": len(records), "data": records}
