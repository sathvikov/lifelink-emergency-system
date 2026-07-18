import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from uuid import uuid4

import bcrypt
from bson import ObjectId
from faker import Faker
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from app.core.config import get_settings  # noqa: E402
from app.db.mongo import connect_to_mongo, close_mongo_connection  # noqa: E402
from app.db.models import (  # noqa: E402
    Document,
    GovAmbulance,
    GovDecisionEvent,
    GovDisasterEvent,
    GovEmergency,
    GovHospital,
    GovPolicyAction,
    GovPrediction,
    GovSimulationSession,
    GovUser,
    GovVerificationRequest,
)
from app.services.collections import (  # noqa: E402
    ALERTS,
    AMBULANCES,
    AMBULANCE_ASSIGNMENTS,
    ANALYTICS_EVENTS,
    BED_ALLOCATIONS,
    BILLING_INVOICES,
    DEPARTMENT_LOGS,
    DONATIONS,
    EQUIPMENT_INVENTORY,
    EMERGENCY_EVENTS,
    FAMILY_MEMBERS,
    FINANCE_EXPENSES,
    GOVERNMENT_COMPLIANCE,
    GOVERNMENT_REPORTS,
    HEALTH_RECORDS,
    HOSPITAL_BENCHMARKS,
    HOSPITALS,
    HOSPITAL_DEPARTMENTS,
    HOSPITAL_MESSAGES,
    HOSPITAL_NETWORK_AGREEMENTS,
    HOSPITAL_REPORTS,
    HOSPITAL_STAFF,
    ICU_ALERTS,
    ICU_PATIENTS,
    INSURANCE_CLAIMS,
    MODULE_ALERTS,
    MODULE_AUTOMATIONS,
    MODULE_ITEMS,
    OPD_APPOINTMENTS,
    OPD_CONSULTATIONS,
    OPD_DOCTORS,
    OPD_QUEUE,
    OT_ALLOCATIONS,
    OT_SURGERIES,
    PATIENTS,
    PREDICTIONS,
    RADIOLOGY_REPORTS,
    RADIOLOGY_REQUESTS,
    RESOURCE_REQUESTS,
    RESOURCES,
    USERS,
    VENDOR_LEAD_TIMES,
)

faker = Faker("en_US")

DEMO_PASSWORD = "Demo@2026!"
DEMO_PASSWORD_HASH = None

COUNTS = {
    "gov_hospitals": 1000,
    "gov_ambulances": 1000,
    "gov_emergencies": 1000,
    "gov_users": 1000,
    "gov_disasters": 1000,
    "gov_predictions": 1000,
    "gov_policy_actions": 1000,
    "gov_verifications": 1000,
    "gov_simulations": 1000,
    "documents_alerts": 1000,
    "documents_donations": 1000,
    "documents_emergencies": 1000,
    "documents_reports": 1000,
    "documents_compliance": 1000,
    "documents_analytics": 1000,
    "documents_hospitals": 1000,
    "documents_ambulances": 1000,
}

ROLE_COUNTS = {
    "public": 100,
    "government": 100,
    "hospital": 100,
    "ambulance": 100,
}

GOV_SUBROLES = ["national_admin", "state_admin", "district_admin", "supervisory_authority"]
HOSPITAL_SUBROLES = ["ceo", "finance", "emergency", "opd", "icu", "radiology", "ot"]
AMBULANCE_SUBROLES = ["crew", "dispatcher"]

CENTER_LAT = 12.9716
CENTER_LNG = 77.5946

PUBLIC_DOCS_PER_USER = 4
HOSPITAL_DOCS_PER_COLLECTION = 3
AMBULANCE_DOCS_PER_USER = 4
GOV_MODULE_ITEMS_PER_USER = 3

DEMO_ACCOUNT_OVERRIDES = {
    "public.001@lifelink.demo": {"sub_role": None, "verified": True},
    "government.001@lifelink.demo": {"sub_role": "national_admin", "verified": True},
    "hospital.002@lifelink.demo": {"sub_role": "finance", "verified": True},
    "ambulance.002@lifelink.demo": {"sub_role": "dispatcher", "verified": True},
}

DEMO_EMAIL_DOMAIN = "@lifelink.demo"


def _uuid() -> str:
    return uuid4().hex


def _object_id() -> str:
    return str(ObjectId())


def _ascii(value: str) -> str:
    return (value or "").encode("ascii", "ignore").decode("ascii")


def _coords(scale: float = 0.6) -> tuple[float, float]:
    return (
        CENTER_LAT + random.uniform(-scale, scale),
        CENTER_LNG + random.uniform(-scale, scale),
    )


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _doc(id_value: str, collection: str, payload: dict, created_at: datetime) -> Document:
    return Document(
        id=id_value,
        collection=collection,
        data=payload,
        created_at=created_at,
        updated_at=created_at,
    )


async def _bulk_insert(session, rows, batch_size=300):
    for idx in range(0, len(rows), batch_size):
        session.add_all(rows[idx : idx + batch_size])
        await session.commit()
        session.expunge_all()


async def _cleanup_demo_documents(session) -> list[str]:
    stmt = (
        select(Document.id)
        .where(Document.collection == USERS)
        .where(func.jsonb_extract_path_text(Document.data, "email").ilike(f"%{DEMO_EMAIL_DOMAIN}"))
    )
    result = await session.execute(stmt)
    user_ids = [row[0] for row in result.fetchall() if row and row[0]]
    if not user_ids:
        return []

    await session.execute(delete(Document).where(Document.id.in_(user_ids)))

    fields = [
        "user",
        "userId",
        "requester",
        "requester_id",
        "hospitalId",
        "ambulanceId",
        "ownerId",
        "assignedTo",
        "createdBy",
        "requestedBy",
    ]
    clauses = [func.jsonb_extract_path_text(Document.data, field).in_(user_ids) for field in fields]
    await session.execute(delete(Document).where(or_(*clauses)))
    await session.commit()
    return user_ids


def _make_user_docs() -> tuple[
    list[Document],
    list[Document],
    list[GovVerificationRequest],
    list[dict],
    dict[str, list[dict]],
]:
    user_docs: list[Document] = []
    hospital_docs: list[Document] = []
    verification_rows: list[GovVerificationRequest] = []
    credentials: list[dict] = []
    users_by_role: dict[str, list[dict]] = {"public": [], "government": [], "hospital": [], "ambulance": []}

    created_at = datetime.utcnow()

    for role, total in ROLE_COUNTS.items():
        for idx in range(total):
            user_id = _object_id()
            name = _ascii(faker.name())
            email = f"{role}.{idx+1:03d}@lifelink.demo"
            sub_role = None
            if role == "government":
                sub_role = GOV_SUBROLES[idx % len(GOV_SUBROLES)]
            if role == "hospital":
                sub_role = HOSPITAL_SUBROLES[idx % len(HOSPITAL_SUBROLES)]
            if role == "ambulance":
                sub_role = AMBULANCE_SUBROLES[idx % len(AMBULANCE_SUBROLES)]

            verified = True
            if role in {"hospital", "ambulance"} and idx % 3 == 0:
                verified = False

            override = DEMO_ACCOUNT_OVERRIDES.get(email)
            if override:
                sub_role = override.get("sub_role")
                verified = bool(override.get("verified", verified))

            user_payload: dict = {
                "_id": user_id,
                "name": name,
                "email": email,
                "password": DEMO_PASSWORD_HASH,
                "role": role,
                "subRole": sub_role,
                "location": _ascii(faker.city()),
                "phone": _ascii(faker.phone_number()),
                "isVerified": verified,
                "createdAt": created_at.isoformat(),
            }

            if role == "hospital":
                user_payload["hospitalProfile"] = {
                    "regNumber": f"HOSP-{idx+1000}",
                    "type": random.choice(["General", "Specialty", "Trauma"]),
                    "departmentRole": sub_role,
                }
            if role == "government":
                user_payload["governmentProfile"] = {
                    "level": sub_role,
                }
            if role == "ambulance":
                user_payload["ambulanceProfile"] = {
                    "base": _ascii(faker.city()),
                    "vehicleId": f"AMB-{idx+2000}",
                }

            user_docs.append(_doc(user_id, USERS, user_payload, created_at))

            if role == "hospital":
                hospital_doc_id = _uuid()
                hospital_docs.append(
                    _doc(
                        hospital_doc_id,
                        HOSPITALS,
                        {
                            "user": user_id,
                            "name": _ascii(f"{faker.company()} Hospital"),
                            "location": _ascii(faker.city()),
                            "beds": {
                                "totalBeds": random.randint(80, 250),
                                "availableBeds": random.randint(10, 120),
                            },
                            "createdAt": created_at.isoformat(),
                            "updatedAt": created_at.isoformat(),
                        },
                        created_at,
                    )
                )

            if role in {"hospital", "ambulance"} and not verified:
                verification_rows.append(
                    GovVerificationRequest(
                        id=_uuid(),
                        entity_type=role,
                        entity_id=user_id,
                        status="pending",
                        notes=f"{role.title()} signup pending verification",
                        requested_by=user_id,
                        reviewed_by=None,
                        reviewed_at=None,
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )

            credentials.append(
                {
                    "role": role,
                    "sub_role": sub_role or "",
                    "email": email,
                    "password": DEMO_PASSWORD,
                    "verified": str(verified).lower(),
                }
            )

            users_by_role[role].append(
                {
                    "id": user_id,
                    "email": email,
                    "sub_role": sub_role,
                    "verified": verified,
                }
            )

    return user_docs, hospital_docs, verification_rows, credentials, users_by_role


def _random_choice(items: list[str], fallback: str) -> str:
    return random.choice(items) if items else fallback


def _seed_public_docs(user: dict, now: datetime) -> list[Document]:
    docs: list[Document] = []
    user_id = user["id"]
    for _ in range(PUBLIC_DOCS_PER_USER):
        docs.append(
            _doc(
                _uuid(),
                ALERTS,
                {
                    "userId": user_id,
                    "user": user_id,
                    "status": random.choice(["pending", "dispatched", "resolved"]),
                    "message": _ascii(faker.sentence(nb_words=8)),
                    "locationDetails": _ascii(faker.city()),
                    "severity": random.choice(["Low", "Medium", "High", "Critical"]),
                    "createdAt": now.isoformat(),
                },
                now,
            )
        )
        docs.append(
            _doc(
                _uuid(),
                DONATIONS,
                {
                    "userId": user_id,
                    "donorName": _ascii(faker.name()),
                    "bloodGroup": random.choice(["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]),
                    "city": _ascii(faker.city()),
                    "status": random.choice(["available", "pending", "on_hold"]),
                    "createdAt": now.isoformat(),
                },
                now,
            )
        )
        docs.append(
            _doc(
                _uuid(),
                RESOURCE_REQUESTS,
                {
                    "requester_id": user_id,
                    "requester": user_id,
                    "requestType": random.choice(["blood", "organ"]),
                    "details": _ascii(faker.sentence(nb_words=6)),
                    "urgency": random.choice(["low", "medium", "high"]),
                    "status": random.choice(["pending", "matched", "fulfilled"]),
                    "createdAt": now.isoformat(),
                },
                now,
            )
        )
        docs.append(
            _doc(
                _uuid(),
                PREDICTIONS,
                {
                    "userId": user_id,
                    "type": "health_risk",
                    "score": round(random.uniform(0.2, 0.92), 2),
                    "createdAt": now.isoformat(),
                },
                now,
            )
        )
        docs.append(
            _doc(
                _uuid(),
                HEALTH_RECORDS,
                {
                    "patientId": user_id,
                    "summary": _ascii(faker.sentence(nb_words=10)),
                    "status": random.choice(["Stable", "Moderate", "Critical"]),
                    "createdAt": now.isoformat(),
                },
                now,
            )
        )
        docs.append(
            _doc(
                _uuid(),
                FAMILY_MEMBERS,
                {
                    "userId": user_id,
                    "name": _ascii(faker.name()),
                    "relation": random.choice(["Parent", "Sibling", "Spouse"]),
                    "age": random.randint(18, 72),
                    "createdAt": now.isoformat(),
                },
                now,
            )
        )
    return docs


def _seed_ambulance_docs(user: dict, hospital_ids: list[str], now: datetime) -> list[Document]:
    docs: list[Document] = []
    user_id = user["id"]
    for _ in range(AMBULANCE_DOCS_PER_USER):
        docs.append(
            _doc(
                _uuid(),
                AMBULANCES,
                {
                    "ambulanceId": user_id,
                    "status": random.choice(["available", "busy", "offline"]),
                    "currentLocation": {
                        "latitude": _coords(0.7)[0],
                        "longitude": _coords(0.7)[1],
                    },
                    "createdAt": now.isoformat(),
                },
                now,
            )
        )
        docs.append(
            _doc(
                _uuid(),
                AMBULANCE_ASSIGNMENTS,
                {
                    "ambulanceId": user_id,
                    "hospital": _random_choice(hospital_ids, ""),
                    "status": random.choice(["assigned", "enroute", "completed"]),
                    "patientName": _ascii(faker.name()),
                    "destination": _ascii(faker.city()),
                    "createdAt": now.isoformat(),
                },
                now,
            )
        )
    return docs


def _seed_hospital_docs(user: dict, hospital_ids: list[str], now: datetime) -> list[Document]:
    docs: list[Document] = []
    hospital_id = user["id"]
    partner_id = _random_choice([hid for hid in hospital_ids if hid != hospital_id], hospital_id)

    for _ in range(HOSPITAL_DOCS_PER_COLLECTION):
        docs.extend(
            [
                _doc(
                    _uuid(),
                    ALERTS,
                    {
                        "hospitalId": hospital_id,
                        "status": random.choice(["open", "monitoring", "resolved"]),
                        "message": _ascii(faker.sentence(nb_words=7)),
                        "severity": random.choice(["Low", "Medium", "High"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    HOSPITAL_STAFF,
                    {
                        "hospitalId": hospital_id,
                        "name": _ascii(faker.name()),
                        "role": random.choice(["Nurse", "Doctor", "Surgeon", "Admin"]),
                        "status": random.choice(["Active", "On Call", "Off Duty"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    HOSPITAL_DEPARTMENTS,
                    {
                        "hospitalId": hospital_id,
                        "name": random.choice(["ER", "ICU", "Cardiology", "Radiology"]),
                        "status": "Active",
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    DEPARTMENT_LOGS,
                    {
                        "hospitalId": hospital_id,
                        "department": random.choice(["ER", "ICU", "Radiology"]),
                        "message": _ascii(faker.sentence(nb_words=8)),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    BED_ALLOCATIONS,
                    {
                        "hospitalId": hospital_id,
                        "patientName": _ascii(faker.name()),
                        "status": random.choice(["Allocated", "Pending", "Released"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    RESOURCES,
                    {
                        "hospitalId": hospital_id,
                        "name": _ascii(faker.word()),
                        "category": random.choice(["Medicine", "Blood", "Organ", "Equipment"]),
                        "quantity": random.randint(10, 300),
                        "unit": "units",
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    EQUIPMENT_INVENTORY,
                    {
                        "hospitalId": hospital_id,
                        "name": _ascii(faker.word()),
                        "category": random.choice(["Imaging", "Monitoring", "Surgical"]),
                        "status": random.choice(["Operational", "Maintenance"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    VENDOR_LEAD_TIMES,
                    {
                        "hospitalId": hospital_id,
                        "vendor": _ascii(faker.company()),
                        "leadDays": random.randint(3, 15),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    BILLING_INVOICES,
                    {
                        "hospitalId": hospital_id,
                        "amount": round(random.uniform(500, 9000), 2),
                        "status": random.choice(["Issued", "Paid", "Overdue"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    FINANCE_EXPENSES,
                    {
                        "hospitalId": hospital_id,
                        "category": random.choice(["Supplies", "Staff", "Maintenance"]),
                        "amount": round(random.uniform(200, 6000), 2),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    INSURANCE_CLAIMS,
                    {
                        "hospitalId": hospital_id,
                        "payer": random.choice(["Aetna", "Cigna", "United"]),
                        "status": random.choice(["Submitted", "Approved", "Rejected"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    HOSPITAL_REPORTS,
                    {
                        "hospitalId": hospital_id,
                        "title": _ascii(faker.catch_phrase()),
                        "summary": _ascii(faker.sentence(nb_words=10)),
                        "status": "Ready",
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    HOSPITAL_MESSAGES,
                    {
                        "fromHospital": hospital_id,
                        "toHospital": partner_id,
                        "message": _ascii(faker.sentence(nb_words=12)),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    HOSPITAL_NETWORK_AGREEMENTS,
                    {
                        "hospital": hospital_id,
                        "partner": partner_id,
                        "status": random.choice(["Active", "Pending"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    EMERGENCY_EVENTS,
                    {
                        "hospitalId": hospital_id,
                        "type": random.choice(["accident", "cardiac", "trauma"]),
                        "severity": random.choice(["Low", "Medium", "High", "Critical"]),
                        "status": "active",
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    PATIENTS,
                    {
                        "hospitalId": hospital_id,
                        "name": _ascii(faker.name()),
                        "age": random.randint(18, 80),
                        "dept": random.choice(["ER", "ICU", "Cardiology"]),
                        "room": f"R-{random.randint(100, 520)}",
                        "condition": _ascii(faker.word()),
                        "severity": random.choice(["Critical", "High", "Moderate", "Stable"]),
                        "status": random.choice(["Admitted", "Discharged", "Intake"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    PREDICTIONS,
                    {
                        "hospitalId": hospital_id,
                        "prediction_type": "capacity",
                        "result": {"score": round(random.uniform(0.2, 0.9), 2)},
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    OPD_APPOINTMENTS,
                    {
                        "hospitalId": hospital_id,
                        "patientName": _ascii(faker.name()),
                        "doctorName": _ascii(faker.name()),
                        "status": random.choice(["Scheduled", "Completed", "Cancelled"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    OPD_DOCTORS,
                    {
                        "hospitalId": hospital_id,
                        "name": _ascii(faker.name()),
                        "speciality": random.choice(["Cardiology", "Ortho", "Neuro"]),
                        "status": "Active",
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    OPD_QUEUE,
                    {
                        "hospitalId": hospital_id,
                        "token": f"Q-{random.randint(1, 120)}",
                        "status": random.choice(["Waiting", "In Consultation", "Completed"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    OPD_CONSULTATIONS,
                    {
                        "hospitalId": hospital_id,
                        "patientName": _ascii(faker.name()),
                        "notes": _ascii(faker.sentence(nb_words=10)),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    ICU_PATIENTS,
                    {
                        "hospitalId": hospital_id,
                        "name": _ascii(faker.name()),
                        "status": random.choice(["Stable", "Critical"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    ICU_ALERTS,
                    {
                        "hospitalId": hospital_id,
                        "message": _ascii(faker.sentence(nb_words=7)),
                        "severity": random.choice(["Medium", "High"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    RADIOLOGY_REQUESTS,
                    {
                        "hospitalId": hospital_id,
                        "patientName": _ascii(faker.name()),
                        "scanType": random.choice(["CT", "MRI", "X-Ray"]),
                        "status": random.choice(["Queued", "In Progress", "Done"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    RADIOLOGY_REPORTS,
                    {
                        "hospitalId": hospital_id,
                        "patientName": _ascii(faker.name()),
                        "summary": _ascii(faker.sentence(nb_words=9)),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    OT_SURGERIES,
                    {
                        "hospitalId": hospital_id,
                        "patientName": _ascii(faker.name()),
                        "procedure": _ascii(faker.word()),
                        "status": random.choice(["Scheduled", "Completed"]),
                        "scheduledAt": (now + timedelta(hours=random.randint(2, 48))).isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    OT_ALLOCATIONS,
                    {
                        "hospitalId": hospital_id,
                        "room": f"OT-{random.randint(1, 6)}",
                        "status": random.choice(["Allocated", "Available"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
                _doc(
                    _uuid(),
                    ANALYTICS_EVENTS,
                    {
                        "hospitalId": hospital_id,
                        "module": "hospital-dashboard",
                        "action": "seeded",
                        "metadata": {"source": "seed"},
                        "createdAt": now.isoformat(),
                    },
                    now,
                ),
            ]
        )
    return docs


def _seed_government_docs(user: dict, now: datetime) -> list[Document]:
    docs: list[Document] = []
    user_id = user["id"]
    modules = ["command-center", "disaster-management", "verification-center"]
    for _ in range(GOV_MODULE_ITEMS_PER_USER):
        module_key = random.choice(modules)
        docs.append(
            _doc(
                _uuid(),
                MODULE_ITEMS,
                {
                    "moduleKey": module_key,
                    "title": _ascii(faker.catch_phrase()),
                    "summary": _ascii(faker.sentence(nb_words=10)),
                    "status": random.choice(["Open", "In Progress", "Closed"]),
                    "priority": random.choice(["Low", "Medium", "High"]),
                    "ownerId": user_id,
                    "createdAt": now.isoformat(),
                    "updatedAt": now.isoformat(),
                },
                now,
            )
        )
        docs.append(
            _doc(
                _uuid(),
                MODULE_ALERTS,
                {
                    "moduleKey": module_key,
                    "message": _ascii(faker.sentence(nb_words=8)),
                    "severity": random.choice(["Low", "Medium", "High"]),
                    "status": "Open",
                    "createdAt": now.isoformat(),
                    "updatedAt": now.isoformat(),
                },
                now,
            )
        )
        docs.append(
            _doc(
                _uuid(),
                MODULE_AUTOMATIONS,
                {
                    "moduleKey": module_key,
                    "name": _ascii(faker.word()),
                    "status": random.choice(["Active", "Paused"]),
                    "createdAt": now.isoformat(),
                    "updatedAt": now.isoformat(),
                },
                now,
            )
        )
    return docs


async def _seed_account_data(session, users_by_role: dict[str, list[dict]], now: datetime) -> None:
    docs: list[Document] = []

    hospital_ids = [item["id"] for item in users_by_role.get("hospital", [])]

    for user in users_by_role.get("public", []):
        docs.extend(_seed_public_docs(user, now))

    for user in users_by_role.get("ambulance", []):
        docs.extend(_seed_ambulance_docs(user, hospital_ids, now))

    for user in users_by_role.get("hospital", []):
        docs.extend(_seed_hospital_docs(user, hospital_ids, now))

    for user in users_by_role.get("government", []):
        docs.extend(_seed_government_docs(user, now))

    if docs:
        await _bulk_insert(session, docs)


async def seed():
    global DEMO_PASSWORD_HASH
    if DEMO_PASSWORD_HASH is None:
        DEMO_PASSWORD_HASH = _hash_password(DEMO_PASSWORD)
    await connect_to_mongo()
    settings = get_settings()
    engine = create_async_engine(settings.postgres_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    now = datetime.utcnow()

    async with session_factory() as session:
        await _cleanup_demo_documents(session)

        hospitals = []
        for idx in range(COUNTS["gov_hospitals"]):
            lat, lng = _coords(0.8)
            beds_total = random.randint(80, 240)
            beds_available = random.randint(10, max(12, int(beds_total * 0.45)))
            hospitals.append(
                GovHospital(
                    id=_uuid(),
                    name=f"{faker.city()} Medical Center",
                    city=faker.city(),
                    state=faker.state(),
                    latitude=lat,
                    longitude=lng,
                    status="active",
                    verified=random.choice([True, False]),
                    beds_total=beds_total,
                    beds_available=beds_available,
                    load_score=round(1 - (beds_available / max(1, beds_total)), 2),
                    rating=round(random.uniform(3.6, 4.9), 1),
                    created_at=now,
                    updated_at=now,
                )
            )
        await _bulk_insert(session, hospitals)

        ambulances = []
        for idx in range(COUNTS["gov_ambulances"]):
            lat, lng = _coords(0.7)
            ambulances.append(
                GovAmbulance(
                    id=_uuid(),
                    code=f"AMB-{3000 + idx}",
                    driver=faker.name(),
                    latitude=lat,
                    longitude=lng,
                    status=random.choice(["available", "assigned", "offline"]),
                    verified=random.choice([True, False]),
                    created_at=now,
                    updated_at=now,
                )
            )
        await _bulk_insert(session, ambulances)

        emergencies = []
        for _ in range(COUNTS["gov_emergencies"]):
            lat, lng = _coords(0.6)
            emergencies.append(
                GovEmergency(
                    id=_uuid(),
                    emergency_type=random.choice(["road_accident", "cardiac", "trauma", "fire", "flood"]),
                    severity=random.choice(["Low", "Medium", "High", "Critical"]),
                    latitude=lat,
                    longitude=lng,
                    status="active",
                    hospital_id=None,
                    ambulance_id=None,
                    occurred_at=now - timedelta(minutes=random.randint(1, 600)),
                    created_at=now,
                )
            )
        await _bulk_insert(session, emergencies)

        gov_users = []
        for _ in range(COUNTS["gov_users"]):
            lat, lng = _coords(1.0)
            gov_users.append(
                GovUser(
                    id=_uuid(),
                    role=random.choice(["public", "hospital", "ambulance"]),
                    sub_role=None,
                    latitude=lat,
                    longitude=lng,
                    created_at=now,
                )
            )
        await _bulk_insert(session, gov_users)

        disasters = []
        for _ in range(COUNTS["gov_disasters"]):
            lat, lng = _coords(1.2)
            disasters.append(
                GovDisasterEvent(
                    id=_uuid(),
                    disaster_type=random.choice(["flood", "fire", "storm", "earthquake", "cluster"]),
                    status=random.choice(["active", "monitoring", "resolved"]),
                    zone=f"Zone {random.choice(['A', 'B', 'C', 'D'])}",
                    severity=random.choice(["Low", "Medium", "High", "Critical"]),
                    started_at=now - timedelta(hours=random.randint(1, 96)),
                    peak_at=None,
                    resolved_at=None,
                    timeline={"events": ["detected"]},
                    meta={"lat": lat, "lng": lng, "impact": faker.word()},
                    created_at=now,
                )
            )
        await _bulk_insert(session, disasters)

        decisions = []
        for _ in range(COUNTS["gov_policy_actions"]):
            decisions.append(
                GovDecisionEvent(
                    id=_uuid(),
                    event="Resource Shift",
                    location=f"Zone {random.choice(['A', 'B', 'C'])}",
                    reason=faker.sentence(nb_words=8),
                    confidence=round(random.uniform(0.6, 0.95), 2),
                    suggested_action=faker.sentence(nb_words=6),
                    impact=random.choice(["Low", "Medium", "High"]),
                    affected_entities={"items": [faker.word() for _ in range(3)]},
                    created_at=now,
                )
            )
        await _bulk_insert(session, decisions)

        predictions = []
        for _ in range(COUNTS["gov_predictions"]):
            predictions.append(
                GovPrediction(
                    id=_uuid(),
                    prediction_type=random.choice(["emergency_anomaly", "capacity", "surge"]),
                    result={"score": random.random()},
                    confidence=round(random.uniform(0.6, 0.95), 2),
                    created_at=now,
                )
            )
        await _bulk_insert(session, predictions)

        policies = []
        for _ in range(COUNTS["gov_policy_actions"]):
            policies.append(
                GovPolicyAction(
                    id=_uuid(),
                    title=faker.catch_phrase(),
                    action=faker.sentence(nb_words=7),
                    status=random.choice(["Draft", "In Review", "Approved"]),
                    impact=random.choice(["Low", "Medium", "High"]),
                    decision_event_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        await _bulk_insert(session, policies)

        verifications = []
        for _ in range(COUNTS["gov_verifications"]):
            verifications.append(
                GovVerificationRequest(
                    id=_uuid(),
                    entity_type=random.choice(["hospital", "ambulance"]),
                    entity_id=_uuid(),
                    status=random.choice(["pending", "approved", "rejected"]),
                    notes=faker.sentence(nb_words=6),
                    requested_by=_uuid(),
                    reviewed_by=_uuid(),
                    reviewed_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        await _bulk_insert(session, verifications)

        simulations = []
        for _ in range(COUNTS["gov_simulations"]):
            simulations.append(
                GovSimulationSession(
                    id=_uuid(),
                    status=random.choice(["completed", "stopped", "recovery"]),
                    intensity=random.choice(["low", "medium", "high"]),
                    started_at=now - timedelta(hours=random.randint(1, 72)),
                    ended_at=now,
                    meta={"note": faker.sentence(nb_words=6)},
                )
            )
        await _bulk_insert(session, simulations)

        user_docs, hospital_docs, verification_rows, credentials, users_by_role = _make_user_docs()
        await _bulk_insert(session, user_docs)
        await _bulk_insert(session, hospital_docs)
        await _bulk_insert(session, verification_rows)

        documents = []
        for _ in range(COUNTS["documents_alerts"]):
            documents.append(
                _doc(
                    _uuid(),
                    ALERTS,
                    {
                        "status": random.choice(["pending", "dispatched", "resolved"]),
                        "message": faker.sentence(nb_words=8),
                        "locationDetails": faker.city(),
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
            )
        for _ in range(COUNTS["documents_donations"]):
            documents.append(
                _doc(
                    _uuid(),
                    DONATIONS,
                    {
                        "donorName": faker.name(),
                        "bloodGroup": random.choice(["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]),
                        "city": faker.city(),
                        "status": random.choice(["available", "pending", "on_hold"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
            )
        for _ in range(COUNTS["documents_emergencies"]):
            documents.append(
                _doc(
                    _uuid(),
                    EMERGENCY_EVENTS,
                    {
                        "type": random.choice(["accident", "cardiac", "trauma"]),
                        "severity": random.choice(["Low", "Medium", "High", "Critical"]),
                        "status": "active",
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
            )
        for _ in range(COUNTS["documents_reports"]):
            documents.append(
                _doc(
                    _uuid(),
                    GOVERNMENT_REPORTS,
                    {
                        "title": faker.catch_phrase(),
                        "scope": random.choice(["National", "State", "District"]),
                        "summary": faker.sentence(nb_words=10),
                        "status": "Ready",
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
            )
        for _ in range(COUNTS["documents_compliance"]):
            documents.append(
                _doc(
                    _uuid(),
                    GOVERNMENT_COMPLIANCE,
                    {
                        "hospitalId": f"HOSP-{random.randint(1000, 2000)}",
                        "status": random.choice(["Open", "Resolved", "Pending"]),
                        "findings": faker.sentence(nb_words=6),
                        "owner": faker.name(),
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
            )
        for _ in range(COUNTS["documents_analytics"]):
            documents.append(
                _doc(
                    _uuid(),
                    ANALYTICS_EVENTS,
                    {
                        "type": random.choice(["sos", "donor_match", "route_assigned", "hospital_lookup"]),
                        "status": "completed",
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
            )
        for _ in range(COUNTS["documents_hospitals"]):
            documents.append(
                _doc(
                    _uuid(),
                    HOSPITALS,
                    {
                        "name": f"{faker.company()} Hospital",
                        "location": faker.city(),
                        "beds": {
                            "totalBeds": random.randint(80, 220),
                            "availableBeds": random.randint(10, 110),
                        },
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
            )
        for _ in range(COUNTS["documents_ambulances"]):
            documents.append(
                _doc(
                    _uuid(),
                    AMBULANCES,
                    {
                        "ambulanceId": f"AMB-{random.randint(4000, 7000)}",
                        "currentLocation": {"latitude": _coords(0.8)[0], "longitude": _coords(0.8)[1]},
                        "status": random.choice(["available", "busy", "offline"]),
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
            )

        await _bulk_insert(session, documents)

        await _bulk_insert(
            session,
            [
                _doc(
                    _uuid(),
                    HOSPITAL_BENCHMARKS,
                    {
                        "name": _ascii(faker.company()),
                        "metric": "avg_wait_time",
                        "value": random.randint(10, 45),
                        "createdAt": now.isoformat(),
                    },
                    now,
                )
                for _ in range(40)
            ],
        )

        await _seed_account_data(session, users_by_role, now)

    credentials_path = os.path.join(os.path.dirname(__file__), "demo_credentials.csv")
    with open(credentials_path, "w", encoding="utf-8", newline="") as f:
        f.write("role,sub_role,email,password,verified\n")
        for row in credentials:
            f.write(
                f"{row['role']},{row['sub_role']},{row['email']},{row['password']},{row['verified']}\n"
            )

    await engine.dispose()
    await close_mongo_connection()
    print("Seed complete. Credentials saved to", credentials_path)


if __name__ == "__main__":
    asyncio.run(seed())
