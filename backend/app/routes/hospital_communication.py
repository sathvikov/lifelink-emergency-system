from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import HOSPITAL_MESSAGES, HOSPITAL_NETWORK_AGREEMENTS, HOSPITALS, USERS
from app.services.repository import MongoRepository

router = APIRouter(tags=["hospital-communication"])


class SendMessageRequest(BaseModel):
    fromHospitalId: str
    toHospitalId: str
    messageType: str
    subject: str
    details: str
    requestDetails: dict | None = None
    urgencyLevel: str | None = "medium"


class UpdateMessageRequest(BaseModel):
    status: str
    response: dict | None = None
    responseMessage: str | None = None


class ReplyMessageRequest(BaseModel):
    status: str | None = "approved"
    responseMessage: str


class AgreementCreate(BaseModel):
    hospitalId: str
    partnerHospitalId: str
    dataTypes: list[str] | None = None
    status: str | None = "active"


class MutualAidRequest(BaseModel):
    hospitalId: str
    resourceType: str
    requiredUnits: int
    urgency: str | None = "medium"


def _try_object_id(value: str | ObjectId) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _normalize_id(value: str | ObjectId) -> ObjectId | str:
    oid = _try_object_id(value)
    return oid if oid is not None else str(value)


async def _resolve_hospital_doc(db, value: str, auto_create: bool = True) -> dict | None:
    hospital_repo = MongoRepository(db, HOSPITALS)

    by_id = None
    oid = _try_object_id(value)
    if oid is not None:
        by_id = await hospital_repo.find_one({"_id": oid})
    if not by_id:
        by_id = await hospital_repo.find_one({"_id": value})

    if by_id:
        return by_id

    user_candidates = []
    if oid is not None:
        user_candidates.append(oid)
    user_candidates.append(value)
    if len(user_candidates) == 1:
        by_user = await hospital_repo.find_one({"user": user_candidates[0]})
    else:
        by_user = await hospital_repo.find_one({"user": {"$in": user_candidates}})
    if by_user:
        return by_user

    if not auto_create:
        return None

    created = await hospital_repo.insert_one(
        {
            "user": oid if oid is not None else value,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
        }
    )
    return created


def _format_location(hospital_doc: dict | None) -> str | None:
    if not hospital_doc:
        return None
    location = hospital_doc.get("location") if isinstance(hospital_doc.get("location"), dict) else {}
    city = location.get("city") or location.get("address")
    state = location.get("state")
    if city and state:
        return f"{city}, {state}"
    return city or None


def _get_user_display(user_doc: dict | None, hospital_doc: dict | None) -> dict:
    user_doc = user_doc or {}
    hp = user_doc.get("hospitalProfile", {}) if isinstance(user_doc, dict) else {}
    return {
        "name": hp.get("hospitalName") or user_doc.get("name") or (hospital_doc or {}).get("name") or "Unnamed Hospital",
        "location": hp.get("jurisdiction") or user_doc.get("location") or _format_location(hospital_doc) or "Unknown",
        "email": user_doc.get("email") or (hospital_doc or {}).get("email") or "",
        "phone": hp.get("contactNumber") or user_doc.get("phone") or (hospital_doc or {}).get("phone") or "",
    }


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/debug/status")
async def debug_status():
    db = get_db()
    hospital_repo = MongoRepository(db, HOSPITALS)
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)

    hospitals = await hospital_repo.find_many({}, projection={"user": 1})
    messages = await message_repo.find_many({}, projection={"_id": 1})

    return {
        "status": "ok",
        "hospitalCount": len(hospitals),
        "messageCount": len(messages),
        "hospitals": hospitals,
    }


@router.get("/list/{current_hospital_id}")
async def list_hospitals(current_hospital_id: str):
    db = get_db()
    hospital_repo = MongoRepository(db, HOSPITALS)
    user_repo = MongoRepository(db, USERS)

    current = await _resolve_hospital_doc(db, current_hospital_id, auto_create=True)
    if not current:
        raise HTTPException(status_code=400, detail="Hospital ID is required")

    others = await hospital_repo.find_many(
        {"_id": {"$ne": current["_id"]}},
        projection={"user": 1, "beds": 1, "doctors": 1, "resources": 1},
    )

    user_ids = [h.get("user") for h in others if h.get("user")]
    oid_list = []
    for uid in user_ids:
        try:
            oid_list.append(_normalize_id(uid))
        except Exception:
            continue

    users = await user_repo.find_many({"_id": {"$in": oid_list}}) if oid_list else []
    user_map = {u.get("_id"): u for u in users}

    mapped = []
    for h in others:
        u = user_map.get(h.get("user"))
        disp = _get_user_display(u, h)
        mapped.append(
            {
                "_id": h.get("_id"),
                "userId": h.get("user"),
                "name": disp["name"],
                "location": disp["location"],
                "email": disp["email"],
                "phone": disp["phone"],
                "beds": h.get("beds") or {"totalBeds": 0, "occupiedBeds": 0, "availableBeds": 0},
                "doctors": h.get("doctors") or [],
                "resources": h.get("resources") or [],
            }
        )

    return {"data": mapped}


@router.get("/details/{hospital_id}")
async def hospital_details(hospital_id: str):
    db = get_db()
    user_repo = MongoRepository(db, USERS)

    hospital = await _resolve_hospital_doc(db, hospital_id, auto_create=False)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    user = None
    if hospital.get("user"):
        try:
            user = await user_repo.find_one({"_id": _normalize_id(hospital.get("user"))})
        except Exception:
            user = None

    disp = _get_user_display(user, hospital)
    return {
        "_id": hospital.get("_id"),
        "name": disp["name"],
        "location": disp["location"],
        "email": disp["email"],
        "phone": disp["phone"],
        "beds": hospital.get("beds") or {"totalBeds": 0, "occupiedBeds": 0, "availableBeds": 0},
        "doctors": hospital.get("doctors") or [],
        "resources": hospital.get("resources") or [],
    }


@router.post("/send-message", status_code=201)
async def send_message(payload: SendMessageRequest):
    db = get_db()
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)

    from_h = await _resolve_hospital_doc(db, payload.fromHospitalId, auto_create=True)
    to_h = await _resolve_hospital_doc(db, payload.toHospitalId, auto_create=True)
    if not from_h or not to_h:
        raise HTTPException(status_code=400, detail="Invalid hospital ids")

    doc = {
        "fromHospital": _normalize_id(from_h["_id"]),
        "toHospital": _normalize_id(to_h["_id"]),
        "messageType": payload.messageType,
        "subject": payload.subject,
        "details": payload.details,
        "requestDetails": {
            **(payload.requestDetails or {}),
            "urgencyLevel": payload.urgencyLevel or "medium",
        },
        "status": "pending",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await message_repo.insert_one(doc)
    return {"message": "Message sent successfully", "data": created}


@router.get("/messages/{hospital_id}")
async def messages_received(hospital_id: str):
    db = get_db()
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)
    hospital_repo = MongoRepository(db, HOSPITALS)
    user_repo = MongoRepository(db, USERS)

    hospital = await _resolve_hospital_doc(db, hospital_id, auto_create=True)
    if not hospital:
        return []

    msgs = await message_repo.find_many(
        {"toHospital": _normalize_id(hospital["_id"])},
        sort=[("createdAt", -1)],
    )

    from_h_ids = [m.get("fromHospital") for m in msgs if m.get("fromHospital")]
    from_h_oid = []
    for hid in from_h_ids:
        try:
            from_h_oid.append(_normalize_id(hid))
        except Exception:
            continue

    from_hospitals = await hospital_repo.find_many({"_id": {"$in": from_h_oid}}) if from_h_oid else []
    hospital_map = {h.get("_id"): h for h in from_hospitals}

    user_ids = []
    for h in from_hospitals:
        if h.get("user"):
            try:
                user_ids.append(_normalize_id(h.get("user")))
            except Exception:
                continue

    users = await user_repo.find_many({"_id": {"$in": user_ids}}) if user_ids else []
    user_map = {u.get("_id"): u for u in users}

    normalized = []
    for m in msgs:
        from_h = hospital_map.get(m.get("fromHospital"), {})
        from_u = user_map.get(from_h.get("user"), {})
        disp = _get_user_display(from_u, from_h)
        normalized.append(
            {
                **m,
                "fromHospital": {
                    "_id": from_h.get("_id"),
                    "name": disp["name"],
                    "location": disp["location"],
                    "email": disp["email"],
                    "phone": disp["phone"],
                },
            }
        )

    return normalized


@router.get("/sent-messages/{hospital_id}")
async def messages_sent(hospital_id: str):
    db = get_db()
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)
    hospital_repo = MongoRepository(db, HOSPITALS)
    user_repo = MongoRepository(db, USERS)

    hospital = await _resolve_hospital_doc(db, hospital_id, auto_create=True)
    if not hospital:
        return []

    msgs = await message_repo.find_many(
        {"fromHospital": _normalize_id(hospital["_id"])},
        sort=[("createdAt", -1)],
    )

    to_h_ids = [m.get("toHospital") for m in msgs if m.get("toHospital")]
    to_h_oid = []
    for hid in to_h_ids:
        try:
            to_h_oid.append(_normalize_id(hid))
        except Exception:
            continue

    to_hospitals = await hospital_repo.find_many({"_id": {"$in": to_h_oid}}) if to_h_oid else []
    hospital_map = {h.get("_id"): h for h in to_hospitals}

    user_ids = []
    for h in to_hospitals:
        if h.get("user"):
            try:
                user_ids.append(_normalize_id(h.get("user")))
            except Exception:
                continue

    users = await user_repo.find_many({"_id": {"$in": user_ids}}) if user_ids else []
    user_map = {u.get("_id"): u for u in users}

    normalized = []
    for m in msgs:
        to_h = hospital_map.get(m.get("toHospital"), {})
        to_u = user_map.get(to_h.get("user"), {})
        disp = _get_user_display(to_u, to_h)
        normalized.append(
            {
                **m,
                "toHospital": {
                    "_id": to_h.get("_id"),
                    "name": disp["name"],
                    "location": disp["location"],
                    "email": disp["email"],
                    "phone": disp["phone"],
                },
            }
        )

    return normalized


@router.patch("/message/{message_id}")
async def update_message(message_id: str, payload: UpdateMessageRequest):
    db = get_db()
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)

    oid = _normalize_id(message_id)

    update_data = {
        "status": payload.status,
        "updatedAt": datetime.utcnow(),
    }
    if payload.response is not None:
        update_data["response"] = {
            "message": payload.responseMessage or "",
            "responseDate": datetime.utcnow(),
            "respondedBy": payload.response.get("respondedBy") if isinstance(payload.response, dict) else None,
        }

    updated = await message_repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found")

    return {"message": "Message updated successfully", "data": updated}


@router.post("/message/{message_id}/reply")
async def reply_message(message_id: str, payload: ReplyMessageRequest):
    db = get_db()
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)

    if not payload.responseMessage:
        raise HTTPException(status_code=400, detail="Reply message is required")

    oid = _normalize_id(message_id)
    update_data = {
        "status": payload.status or "approved",
        "response": {
            "message": payload.responseMessage,
            "responseDate": datetime.utcnow(),
        },
        "updatedAt": datetime.utcnow(),
    }

    updated = await message_repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found")

    return {"message": "Reply sent successfully", "data": updated}


@router.delete("/message/{message_id}")
async def delete_message(message_id: str):
    db = get_db()
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)

    deleted = await message_repo.delete_by_id(message_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")

    return {"message": "Message deleted successfully"}


@router.get("/my-hospital/{user_id}")
async def my_hospital(user_id: str):
    db = get_db()
    user_repo = MongoRepository(db, USERS)

    user = await user_repo.find_one({"_id": _normalize_id(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail=f"No user found with ID: {user_id}")

    hospital = await _resolve_hospital_doc(db, user_id, auto_create=True)
    if not hospital:
        raise HTTPException(status_code=500, detail="Failed to resolve hospital")

    return hospital


@router.put("/my-hospital/{user_id}")
async def update_my_hospital(user_id: str, payload: dict):
    db = get_db()
    user_repo = MongoRepository(db, USERS)
    hospital_repo = MongoRepository(db, HOSPITALS)

    user = await user_repo.find_one({"_id": _normalize_id(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail=f"No user found with ID: {user_id}")

    hospital = await _resolve_hospital_doc(db, user_id, auto_create=True)
    if not hospital:
        raise HTTPException(status_code=500, detail="Failed to resolve hospital")

    updates = {"updatedAt": datetime.utcnow()}
    if "beds" in payload:
        updates["beds"] = payload.get("beds")
    if "doctors" in payload:
        updates["doctors"] = payload.get("doctors")
    if "resources" in payload:
        updates["resources"] = payload.get("resources")

    updated = await hospital_repo.update_one(
        {"_id": _normalize_id(hospital["_id"])},
        {"$set": updates},
        return_new=True,
    )

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update hospital")

    return updated


@router.post("/agreements", status_code=201)
async def create_agreement(payload: AgreementCreate):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_NETWORK_AGREEMENTS)

    hospital = await _resolve_hospital_doc(db, payload.hospitalId, auto_create=False)
    partner = await _resolve_hospital_doc(db, payload.partnerHospitalId, auto_create=False)
    if not hospital or not partner:
        raise HTTPException(status_code=400, detail="Hospital not found")

    doc = {
        "hospital": _normalize_id(hospital.get("_id")),
        "partner": _normalize_id(partner.get("_id")),
        "dataTypes": payload.dataTypes or ["beds", "resources", "staff"],
        "status": payload.status or "active",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.get("/agreements/{hospital_id}")
async def list_agreements(hospital_id: str):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_NETWORK_AGREEMENTS)

    hospital = await _resolve_hospital_doc(db, hospital_id, auto_create=False)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    oid = _normalize_id(hospital.get("_id"))
    agreements = await repo.find_many({"$or": [{"hospital": oid}, {"partner": oid}]}, sort=[("createdAt", -1)])
    return {"count": len(agreements), "data": agreements}


@router.post("/mutual-aid/recommendations")
async def mutual_aid_recommendations(payload: MutualAidRequest):
    db = get_db()
    hospital_repo = MongoRepository(db, HOSPITALS)
    agreement_repo = MongoRepository(db, HOSPITAL_NETWORK_AGREEMENTS)

    hospital = await _resolve_hospital_doc(db, payload.hospitalId, auto_create=True)
    if not hospital:
        raise HTTPException(status_code=400, detail="Hospital not found")

    agreements = await agreement_repo.find_many({"hospital": hospital.get("_id"), "status": "active"})
    partner_ids = [a.get("partner") for a in agreements if a.get("partner")]
    partners = await hospital_repo.find_many({"_id": {"$in": partner_ids}}) if partner_ids else []

    recommendations = []
    for partner in partners:
        beds = partner.get("beds") or {}
        available = beds.get("availableBeds") or max(0, (beds.get("totalBeds") or 0) - (beds.get("occupiedBeds") or 0))
        recommendations.append({
            "hospitalId": partner.get("_id"),
            "name": partner.get("name") or "Partner Hospital",
            "availableBeds": available,
            "matchScore": min(100, available * 5),
        })

    recommendations.sort(key=lambda item: item.get("matchScore", 0), reverse=True)
    return {"count": len(recommendations), "data": recommendations[:5]}


@router.post("/transfer/request", status_code=201)
async def transfer_request(payload: MutualAidRequest):
    db = get_db()
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)
    hospital_repo = MongoRepository(db, HOSPITALS)

    from_h = await _resolve_hospital_doc(db, payload.hospitalId, auto_create=True)
    if not from_h:
        raise HTTPException(status_code=400, detail="Hospital not found")

    candidates = await hospital_repo.find_many({}, limit=50)
    target = None
    best_score = -1
    for candidate in candidates:
        if str(candidate.get("_id")) == str(from_h.get("_id")):
            continue
        beds = candidate.get("beds") or {}
        available = beds.get("availableBeds") or max(0, (beds.get("totalBeds") or 0) - (beds.get("occupiedBeds") or 0))
        score = available
        if score > best_score:
            best_score = score
            target = candidate

    if not target:
        raise HTTPException(status_code=404, detail="No partner hospital available")

    doc = {
        "fromHospital": _normalize_id(from_h.get("_id")),
        "toHospital": _normalize_id(target.get("_id")),
        "messageType": "transfer",
        "subject": f"Transfer request for {payload.resourceType}",
        "details": f"Need {payload.requiredUnits} units. Urgency: {payload.urgency}",
        "requestDetails": {
            "resourceType": payload.resourceType,
            "requiredUnits": payload.requiredUnits,
            "urgencyLevel": payload.urgency or "medium",
        },
        "status": "pending",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await message_repo.insert_one(doc)
    return {"message": "Transfer request sent", "data": created}
