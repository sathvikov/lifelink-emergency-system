import bcrypt
from bson import ObjectId
from fastapi import APIRouter, HTTPException

from app.db.mongo import get_db
from app.services.collections import (
    ALERTS,
    ANALYTICS_EVENTS,
    DONATIONS,
    HEALTH_RECORDS,
    HOSPITAL_MESSAGES,
    PATIENTS,
    PREDICTIONS,
    RESOURCES,
    RESOURCE_REQUESTS,
    USERS,
)
from app.services.repository import MongoRepository

router = APIRouter(tags=["dashboard"])


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


@router.get("/public/{user_id}/full")
async def public_full_dashboard(user_id: str):
    db = get_db()
    user_repo = MongoRepository(db, USERS)
    alert_repo = MongoRepository(db, ALERTS)
    request_repo = MongoRepository(db, RESOURCE_REQUESTS)
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)
    donation_repo = MongoRepository(db, DONATIONS)
    prediction_repo = MongoRepository(db, PREDICTIONS)
    health_repo = MongoRepository(db, HEALTH_RECORDS)
    activity_repo = MongoRepository(db, ANALYTICS_EVENTS)

    oid = _as_object_id(user_id)

    alerts = await alert_repo.find_many({"user": oid}, sort=[("createdAt", -1)])
    requests = await request_repo.find_many({"requester": oid}, sort=[("createdAt", -1)])
    donations = await donation_repo.find_many({"userId": str(oid)}, sort=[("donationDate", -1)])
    if not donations:
        donations = await donation_repo.find_many({"user": oid}, sort=[("donationDate", -1)])

    hospital_messages = await message_repo.find_many(
        {"toHospital": user_id, "status": {"$ne": "resolved"}},
        sort=[("createdAt", -1)],
    )

    user = await user_repo.find_one({"_id": oid})
    health_records = (
        (user or {}).get("publicProfile", {}).get("healthRecords", {})
        if user
        else {}
    )
    hospital_profile = (user or {}).get("hospitalProfile", {}) if user else {}

    risk_history = await prediction_repo.find_many(
        {"user": oid, "prediction_type": "health_risk"},
        sort=[("createdAt", -1)],
        limit=20,
    )
    risk_timeline = [
        {
            "date": item.get("createdAt"),
            "risk_score": item.get("risk_score"),
            "risk_level": item.get("risk_level"),
        }
        for item in reversed(risk_history)
    ]

    latest_vitals = await health_repo.find_many(
        {"user": oid, "record_type": "vitals"},
        sort=[("createdAt", -1)],
        limit=1,
    )
    vitals_payload = latest_vitals[0] if latest_vitals else None

    activity_history = await activity_repo.find_many(
        {"$or": [{"user": oid}, {"user": str(oid)}]},
        sort=[("createdAt", -1)],
        limit=20,
    )

    anomalies = []
    if vitals_payload:
        metrics = vitals_payload.get("metrics") or {}
        hr = metrics.get("heart_rate")
        bp = metrics.get("blood_pressure")
        oxygen = metrics.get("oxygen")
        if hr and hr > 110:
            anomalies.append("Elevated heart rate detected")
        if bp and isinstance(bp, (int, float)) and bp >= 140:
            anomalies.append("High blood pressure trend")
        if oxygen and oxygen < 92:
            anomalies.append("Low oxygen saturation")

    return {
        "alerts": alerts,
        "resourceRequests": requests,
        "donationHistory": donations,
        "hospitalMessages": hospital_messages,
        "healthRecords": health_records,
        "hospitalProfile": hospital_profile,
        "riskTimeline": risk_timeline,
        "anomalies": anomalies,
        "latestVitals": vitals_payload,
        "activityHistory": activity_history,
    }


@router.put("/profile/{user_id}")
async def update_profile(user_id: str, payload: dict):
    db = get_db()
    user_repo = MongoRepository(db, USERS)

    oid = _as_object_id(user_id)

    name = payload.get("name")
    email = payload.get("email")
    phone = payload.get("phone")
    location = payload.get("location")
    password = payload.get("password")
    age = payload.get("age")
    blood_group = payload.get("bloodGroup")
    medical_history = payload.get("medicalHistory")
    reg_number = payload.get("regNumber")
    total_beds = payload.get("totalBeds")
    ambulances = payload.get("ambulances")
    specialties = payload.get("specialties")
    hospital_type = payload.get("type")
    website = payload.get("website")

    set_data: dict = {}

    if name is not None:
        set_data["name"] = name
    if email is not None:
        set_data["email"] = email
    if phone is not None:
        set_data["phone"] = phone
    if location is not None:
        set_data["location"] = location
    if password is not None:
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        set_data["password"] = hashed_password

    if age is not None:
        set_data["publicProfile.healthRecords.age"] = age
    if blood_group is not None:
        set_data["publicProfile.healthRecords.bloodGroup"] = blood_group
    if phone is not None:
        set_data["publicProfile.healthRecords.contact"] = phone
    if medical_history is not None:
        if isinstance(medical_history, str):
            conditions = [s.strip() for s in medical_history.split(",") if s.strip()]
        else:
            conditions = medical_history
        set_data["publicProfile.healthRecords.conditions"] = conditions

    if reg_number is not None:
        set_data["hospitalProfile.regNumber"] = reg_number
    if total_beds is not None:
        set_data["hospitalProfile.totalBeds"] = total_beds
    if ambulances is not None:
        set_data["hospitalProfile.ambulances"] = ambulances
    if hospital_type is not None:
        set_data["hospitalProfile.type"] = hospital_type
    if website is not None:
        set_data["hospitalProfile.website"] = website

    if specialties is not None:
        if isinstance(specialties, list):
            spec_array = specialties
        else:
            spec_array = [s.strip() for s in str(specialties).split(",") if s.strip()]
        set_data["hospitalProfile.specialties"] = spec_array

    if not set_data:
        raise HTTPException(status_code=400, detail="No valid fields provided for update")

    updated = await user_repo.update_one({"_id": oid}, {"$set": set_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    updated.pop("password", None)
    return {"message": "Profile Updated", "user": updated}


@router.get("/hospital/stats")
async def hospital_stats():
    # Preserve existing backend behavior: static aggregate sample payload.
    return {
        "totalPatients": 142,
        "availableBeds": 38,
        "criticalCases": 9,
        "activeAmbulances": 5,
        "caseDistribution": [
            {"name": "Cardiac", "value": 30},
            {"name": "Trauma", "value": 40},
            {"name": "Viral", "value": 20},
            {"name": "Other", "value": 10},
        ],
        "patientFlow": [
            {"time": "08:00", "admitted": 10, "discharged": 5},
            {"time": "12:00", "admitted": 20, "discharged": 15},
            {"time": "16:00", "admitted": 15, "discharged": 10},
            {"time": "20:00", "admitted": 25, "discharged": 20},
        ],
    }


@router.get("/hospital/alerts")
async def hospital_alerts():
    db = get_db()
    alert_repo = MongoRepository(db, ALERTS)
    alerts = await alert_repo.find_many({"status": {"$ne": "Resolved"}}, sort=[("createdAt", -1)])
    return alerts


@router.put("/hospital/alert/{alert_id}")
async def update_hospital_alert(alert_id: str, payload: dict):
    db = get_db()
    alert_repo = MongoRepository(db, ALERTS)
    oid = _as_object_id(alert_id)

    status = payload.get("status")
    if status is None:
        raise HTTPException(status_code=400, detail="status is required")

    updated = await alert_repo.update_one({"_id": oid}, {"$set": {"status": status}}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return updated


@router.get("/admin/pending-hospitals")
async def admin_pending_hospitals():
    db = get_db()
    user_repo = MongoRepository(db, USERS)
    pending = await user_repo.find_many({"role": "hospital", "isVerified": False})
    return pending


@router.put("/admin/verify/{user_id}")
async def admin_verify_hospital(user_id: str):
    db = get_db()
    user_repo = MongoRepository(db, USERS)
    oid = _as_object_id(user_id)

    updated = await user_repo.update_one({"_id": oid}, {"$set": {"isVerified": True}}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Hospital user not found")

    return {"message": "Hospital Verified Successfully"}


@router.post("/hospital/patient/admit", status_code=201)
async def hospital_admit_patient(payload: dict):
    db = get_db()
    patient_repo = MongoRepository(db, PATIENTS)

    hospital_id = payload.get("hospitalId")
    if not hospital_id:
        raise HTTPException(status_code=400, detail="hospitalId is required")

    doc = {
        "hospitalId": _as_object_id(str(hospital_id)),
        "name": payload.get("name"),
        "age": payload.get("age"),
        "gender": payload.get("gender"),
        "dept": payload.get("dept"),
        "room": payload.get("room"),
        "condition": payload.get("condition"),
        "severity": payload.get("severity", "Stable"),
        "oxygen": payload.get("oxygen", 98),
        "heartRate": payload.get("heartRate", 80),
        "bp": payload.get("bp", "120/80"),
        "status": payload.get("status", "Admitted"),
        "admitDate": payload.get("admitDate"),
    }

    created = await patient_repo.insert_one(doc)
    # Mongoose responses include version key by default; preserve contract parity.
    created["__v"] = 0
    return created


@router.get("/hospital/patients/{hospital_id}")
async def hospital_patients(hospital_id: str):
    db = get_db()
    patient_repo = MongoRepository(db, PATIENTS)
    oid = _as_object_id(hospital_id)
    patients = await patient_repo.find_many({"hospitalId": oid}, sort=[("admitDate", -1)])
    return patients


@router.post("/hospital/resource/add", status_code=201)
async def hospital_add_resource(payload: dict):
    db = get_db()
    resource_repo = MongoRepository(db, RESOURCES)

    hospital_id = payload.get("hospitalId")
    if not hospital_id:
        raise HTTPException(status_code=400, detail="hospitalId is required")

    doc = {
        "hospitalId": _as_object_id(str(hospital_id)),
        "name": payload.get("name"),
        "category": payload.get("category"),
        "quantity": payload.get("quantity"),
        "unit": payload.get("unit", "units"),
        "minThreshold": payload.get("minThreshold", 10),
        "expiryDate": payload.get("expiryDate"),
        "lastUpdated": payload.get("lastUpdated"),
    }

    created = await resource_repo.insert_one(doc)
    created["__v"] = 0
    return created


@router.get("/hospital/resources/{hospital_id}")
async def hospital_resources(hospital_id: str):
    db = get_db()
    resource_repo = MongoRepository(db, RESOURCES)
    oid = _as_object_id(hospital_id)
    resources = await resource_repo.find_many({"hospitalId": oid}, sort=[("category", 1)])
    return resources


@router.delete("/notification/{item_type}/{item_id}")
async def delete_notification_item(item_type: str, item_id: str):
    db = get_db()
    oid = _as_object_id(item_id)

    if item_type == "alert":
        await MongoRepository(db, ALERTS).delete_by_id(str(oid))
        return {"message": "Alert deleted"}

    if item_type == "request":
        await MongoRepository(db, RESOURCE_REQUESTS).delete_by_id(str(oid))
        return {"message": "Request deleted"}

    if item_type == "message":
        await MongoRepository(db, HOSPITAL_MESSAGES).delete_by_id(str(oid))
        return {"message": "Hospital message deleted"}

    raise HTTPException(status_code=400, detail="Unknown notification type")
