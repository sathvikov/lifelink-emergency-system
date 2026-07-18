from __future__ import annotations

import argparse
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import bcrypt
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri


SEED_TAG = "demo"

EXTRA_HOSPITALS = [
    {
        "reg_number": "y-002",
        "password": "y",
        "email": "admin.oakridge@lifelink.local",
        "name": "Oakridge Multi-Specialty Hospital",
        "sub_role": "ceo",
        "location": "Mysuru, Karnataka",
        "phone": "0821-2412200",
        "city": "Mysuru",
        "state": "Karnataka",
        "address": "27 Chamundi Road",
        "lat": 12.2958,
        "lng": 76.6394,
    },
    {
        "reg_number": "y-003",
        "password": "y",
        "email": "admin.sunrise@lifelink.local",
        "name": "Sunrise Heart Institute",
        "sub_role": "ceo",
        "location": "Mangaluru, Karnataka",
        "phone": "0824-2444590",
        "city": "Mangaluru",
        "state": "Karnataka",
        "address": "18 Marina Avenue",
        "lat": 12.9141,
        "lng": 74.8560,
    },
    {
        "reg_number": "y-004",
        "password": "y",
        "email": "admin.riverdale@lifelink.local",
        "name": "Riverdale Regional Medical Center",
        "sub_role": "ceo",
        "location": "Hubballi, Karnataka",
        "phone": "0836-2373348",
        "city": "Hubballi",
        "state": "Karnataka",
        "address": "42 Station Road",
        "lat": 15.3647,
        "lng": 75.1240,
    },
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _get_mongo_uri() -> str:
    return os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/lifelink_db")


def _get_db_name(mongo_uri: str) -> str:
    try:
        parsed = parse_uri(mongo_uri)
        db_name = parsed.get("database")
    except Exception:
        db_name = None
    return db_name or os.getenv("MONGO_DB") or "lifelink_db"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo hospital account and module data.")
    parser.add_argument("--reg-number", type=str, default="y", help="Hospital registration ID")
    parser.add_argument("--password", type=str, default="y", help="Hospital login password")
    parser.add_argument("--email", type=str, default="demo.hospital@lifelink.local", help="Hospital admin email")
    parser.add_argument("--name", type=str, default="Y Central Hospital", help="Hospital display name")
    parser.add_argument("--sub-role", type=str, default="ceo", help="Hospital sub-role")
    parser.add_argument("--location", type=str, default="Bengaluru, Karnataka", help="User location string")
    parser.add_argument("--phone", type=str, default="080-45678910", help="Hospital contact number")
    parser.add_argument("--city", type=str, default="Bengaluru", help="Hospital city")
    parser.add_argument("--state", type=str, default="Karnataka", help="Hospital state")
    parser.add_argument("--address", type=str, default="12 MG Road", help="Hospital address")
    parser.add_argument("--lat", type=float, default=12.9716, help="Hospital latitude")
    parser.add_argument("--lng", type=float, default=77.5946, help="Hospital longitude")
    parser.add_argument("--wipe-demo", action="store_true", help="Remove existing demo seed records first")
    parser.add_argument("--skip-extras", action="store_true", help="Skip creating extra demo hospitals")
    return parser.parse_args()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _now() -> datetime:
    return datetime.utcnow()


def _ensure_object_id(value: Any) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    return ObjectId(str(value))


def _format_location(city: str, state: str) -> str:
    if city and state:
        return f"{city}, {state}"
    return city or state or "Unknown"


def _delete_demo_docs(db, seed_owner: str) -> None:
    for name in [
        "alerts",
        "ambulances",
        "ambulance_assignments",
        "billing_invoices",
        "insurance_claims",
        "finance_expenses",
        "hospital_staff",
        "equipment_inventory",
        "resources",
        "emergency_events",
        "opd_queue",
        "opd_appointments",
        "opd_doctors",
        "opd_consultations",
        "icu_patients",
        "icu_alerts",
        "radiology_requests",
        "radiology_reports",
        "ot_surgeries",
        "ot_allocations",
        "bed_allocations",
        "department_logs",
        "analytics_events",
        "government_reports",
        "government_compliance",
        "hospital_reports",
        "hospital_network_agreements",
        "audit_logs",
        "hospitalmessages",
        "patients",
        "health_records",
        "donations",
        "resourcerequests",
        "family_members",
        "predictions",
    ]:
        db[name].delete_many({"seedTag": SEED_TAG, "seedOwner": seed_owner})


def _upsert_hospital_user(db, args: argparse.Namespace) -> dict[str, Any]:
    users = db["users"]
    existing = users.find_one({"hospitalProfile.regNumber": args.reg_number})
    if not existing and args.email:
        existing = users.find_one({"email": args.email})

    profile = {
        "regNumber": args.reg_number,
        "type": "Multi-Specialty",
        "totalBeds": 420,
        "ambulances": 8,
        "specialties": [
            "Emergency",
            "Cardiology",
            "Orthopedics",
            "ICU",
            "Radiology",
            "Surgery",
        ],
        "website": "https://y-central-hospital.example",
        "isVerified": True,
        "departmentRole": args.sub_role,
        "hospitalName": args.name,
        "jurisdiction": _format_location(args.city, args.state),
        "contactNumber": args.phone,
    }

    now = _now()
    if existing:
        updates = {
            "name": args.name,
            "email": args.email,
            "phone": args.phone,
            "location": args.location,
            "role": "hospital",
            "subRole": args.sub_role,
            "isVerified": True,
            "hospitalProfile": profile,
            "updatedAt": now,
        }
        if args.password:
            updates["password"] = _hash_password(args.password)
        users.update_one({"_id": existing["_id"]}, {"$set": updates})
        existing.update(updates)
        return existing

    user_doc = {
        "name": args.name,
        "email": args.email,
        "password": _hash_password(args.password),
        "role": "hospital",
        "subRole": args.sub_role,
        "location": args.location,
        "phone": args.phone,
        "isVerified": True,
        "hospitalProfile": profile,
        "createdAt": now,
    }
    created = users.insert_one(user_doc)
    user_doc["_id"] = created.inserted_id
    return user_doc


def _upsert_hospital_doc(db, user_doc: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    hospitals = db["hospitals"]
    existing = hospitals.find_one({"user": user_doc["_id"]})
    if not existing:
        existing = hospitals.find_one({"regNumber": args.reg_number})

    now = _now()
    hospital_doc = {
        "user": user_doc["_id"],
        "hospital_id": f"DEMO-{args.reg_number.upper()}",
        "name": args.name,
        "regNumber": args.reg_number,
        "type": "Multi-Specialty",
        "phone": args.phone,
        "email": args.email,
        "location": {
            "lat": round(args.lat, 6),
            "lng": round(args.lng, 6),
            "address": args.address,
            "city": args.city,
            "state": args.state,
        },
        "specialties": ["Emergency", "Cardiology", "Orthopedics", "ICU", "Radiology", "Surgery"],
        "beds": {
            "totalBeds": 420,
            "occupiedBeds": 298,
            "availableBeds": 122,
            "icuBeds": 84,
            "icuOccupied": 62,
            "emergencyBeds": 64,
            "emergencyOccupied": 42,
        },
        "ambulances": 8,
        "rating": 4.6,
        "establishedYear": 1999,
        "doctors": [
            {"name": "Dr. Asha Raman", "department": "Emergency", "availability": True, "role": "Doctor"},
            {"name": "Dr. Kiran Shah", "department": "Cardiology", "availability": True, "role": "Doctor"},
            {"name": "Dr. Meera Nair", "department": "Orthopedics", "availability": True, "role": "Doctor"},
        ],
        "resources": [],
        "updatedAt": now,
    }

    if existing:
        hospitals.update_one({"_id": existing["_id"]}, {"$set": hospital_doc})
        existing.update(hospital_doc)
        return existing

    hospital_doc["createdAt"] = now
    created = hospitals.insert_one(hospital_doc)
    hospital_doc["_id"] = created.inserted_id
    return hospital_doc


def _backfill_hospital_names(db) -> int:
    hospitals = db["hospitals"]
    updates = 0
    cursor = hospitals.find({})
    for index, doc in enumerate(cursor, start=1):
        name = doc.get("name")
        if name and not name.lower().startswith("hospital ") and name != "Unnamed Hospital":
            continue
        location = doc.get("location") if isinstance(doc.get("location"), dict) else {}
        city = location.get("city")
        reg_number = doc.get("regNumber") or doc.get("hospital_id")
        if city:
            name = f"{city} Community Hospital"
        elif reg_number:
            name = f"Regional Hospital {reg_number}"
        else:
            name = f"Regional Hospital {index:02d}"
        hospitals.update_one({"_id": doc["_id"]}, {"$set": {"name": name}})
        updates += 1
    return updates


def _seed_collection(db, name: str, docs: list[dict[str, Any]], seed_owner: str) -> int:
    if not docs:
        return 0
    db[name].delete_many({"seedTag": SEED_TAG, "seedOwner": seed_owner})
    db[name].insert_many(docs)
    return len(docs)


def main() -> None:
    args = _parse_args()
    load_dotenv(_repo_root() / "backend" / ".env")

    random.seed(42)
    mongo_uri = _get_mongo_uri()
    db_name = _get_db_name(mongo_uri)
    client = MongoClient(mongo_uri)
    db = client[db_name]

    if args.wipe_demo:
        _delete_demo_docs(db, args.reg_number)
        db["users"].delete_many({"hospitalProfile.regNumber": args.reg_number})
        db["hospitals"].delete_many({"regNumber": args.reg_number})

    user_doc = _upsert_hospital_user(db, args)
    hospital_doc = _upsert_hospital_doc(db, user_doc, args)
    hospital_oid = _ensure_object_id(hospital_doc["_id"])
    hospital_scope_id = _ensure_object_id(user_doc["_id"])

    now = _now()
    seed_owner = args.reg_number

    if not args.skip_extras:
        extra_docs = []
        for extra in EXTRA_HOSPITALS:
            merged = {
                **vars(args),
                **extra,
            }
            extra_args = SimpleNamespace(**merged)
            extra_user = _upsert_hospital_user(db, extra_args)
            extra_doc = _upsert_hospital_doc(db, extra_user, extra_args)
            extra_docs.append(extra_doc)

    _backfill_hospital_names(db)

    agreement_rows = []
    if not args.skip_extras:
        partner_regs = [extra.get("reg_number") for extra in EXTRA_HOSPITALS if extra.get("reg_number")]
        reg_numbers = [args.reg_number, *partner_regs]
        hospital_docs = list(db["hospitals"].find({"regNumber": {"$in": reg_numbers}}))
        reg_map = {doc.get("regNumber"): doc for doc in hospital_docs if doc.get("regNumber")}
        primary = reg_map.get(args.reg_number)
        if primary:
            for partner_reg in partner_regs:
                partner = reg_map.get(partner_reg)
                if not partner:
                    continue
                agreement_rows.append(
                    {
                        "hospital": _ensure_object_id(primary.get("_id")),
                        "partner": _ensure_object_id(partner.get("_id")),
                        "dataTypes": ["beds", "resources", "staff", "ambulance"],
                        "status": "active",
                        "createdAt": now,
                        "updatedAt": now,
                        "seedTag": SEED_TAG,
                        "seedOwner": seed_owner,
                    }
                )

    staff = [
        {
            "hospital": hospital_scope_id,
            "name": name,
            "role": role,
            "department": dept,
            "shift": shift,
            "availability": True,
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for name, role, dept, shift in [
            ("Dr. Asha Raman", "Doctor", "Emergency", "Day"),
            ("Dr. Kiran Shah", "Doctor", "Cardiology", "Day"),
            ("Dr. Meera Nair", "Doctor", "Orthopedics", "Evening"),
            ("Riya Kulkarni", "Nurse", "ICU", "Night"),
            ("Sameer Das", "Technician", "Radiology", "Day"),
            ("Neha Patil", "Support", "Surgery", "Evening"),
        ]
    ]

    equipment = [
        {
            "hospital": hospital_scope_id,
            "name": name,
            "category": category,
            "quantity": quantity,
            "status": "Available",
            "minThreshold": 2,
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for name, category, quantity in [
            ("Ventilator", "Equipment", 12),
            ("Defibrillator", "Equipment", 6),
            ("MRI Scanner", "Imaging", 2),
            ("CT Scanner", "Imaging", 3),
            ("Ultrasound", "Imaging", 5),
        ]
    ]

    resources = [
        {
            "hospitalId": hospital_scope_id,
            "name": name,
            "category": category,
            "quantity": quantity,
            "unit": "units",
            "minThreshold": 25,
            "expiryDate": (now + timedelta(days=120)).date().isoformat(),
            "lastUpdated": now.isoformat(),
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for name, category, quantity in [
            ("Oxygen Cylinders", "Supply", 120),
            ("PPE Kits", "Supply", 340),
            ("IV Fluids", "Medicine", 260),
            ("Antibiotics", "Medicine", 180),
        ]
    ]

    invoices = []
    for idx in range(6):
        invoices.append(
            {
                "hospital": hospital_scope_id,
                "patientName": f"Patient {idx + 1}",
                "department": random.choice(["Cardiology", "Emergency", "Orthopedics", "ICU"]),
                "amount": round(random.uniform(4200, 18500), 2),
                "status": random.choice(["Unpaid", "Paid", "Pending"]),
                "insuranceProvider": random.choice(["CarePlus", "Apex", "ShieldCare"]),
                "dueDate": (now + timedelta(days=15)).date().isoformat(),
                "paidAmount": 0.0,
                "refundAmount": 0.0,
                "createdAt": now - timedelta(days=idx),
                "updatedAt": now,
                "seedTag": SEED_TAG,
                "seedOwner": seed_owner,
            }
        )

    claims = []
    for idx in range(4):
        claims.append(
            {
                "hospital": hospital_scope_id,
                "invoiceId": f"INV-{1000 + idx}",
                "insurer": random.choice(["CarePlus", "Apex"]),
                "amount": round(random.uniform(3000, 12000), 2),
                "status": random.choice(["Submitted", "Approved", "Pending"]),
                "approvedAmount": 0.0,
                "notes": "Auto-generated claim for demo",
                "createdAt": now - timedelta(days=idx + 1),
                "updatedAt": now,
                "seedTag": SEED_TAG,
                "seedOwner": seed_owner,
            }
        )

    expenses = [
        {
            "hospital": hospital_scope_id,
            "category": category,
            "amount": round(random.uniform(1800, 9200), 2),
            "notes": "Monthly operational cost",
            "createdAt": now - timedelta(days=idx * 2),
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for idx, category in enumerate(["Supplies", "Staffing", "Utilities", "Equipment"])
    ]

    emergency_events = []
    for idx, symptoms in enumerate(["Chest pain", "Road accident", "High fever", "Stroke signs", "Severe trauma"]):
        emergency_events.append(
            {
                "hospital": hospital_scope_id,
                "patientName": f"Emergency {idx + 1}",
                "symptoms": symptoms,
                "location": "Zone A",
                "source": "public",
                "severity": random.choice(["High", "Critical", "Medium"]),
                "priority": "High",
                "status": "Unassigned",
                "assignedDepartment": random.choice(["Emergency", "Cardiology", "Orthopedics"]),
                "assignedUnit": "ER-1",
                "notes": "Auto-triaged",
                "imagingMeta": {
                    "modality": random.choice(["CT", "X-Ray", "MRI"]),
                    "bodyPart": random.choice(["Head", "Chest", "Abdomen"]),
                    "priority": random.choice(["High", "Routine"]),
                },
                "createdAt": now - timedelta(minutes=idx * 12),
                "updatedAt": now,
                "seedTag": SEED_TAG,
                "seedOwner": seed_owner,
            }
        )

    opd_queue = []
    for idx, reason in enumerate(["Fever", "Injury", "Follow-up", "Headache", "Cough"]):
        opd_queue.append(
            {
                "hospital": hospital_scope_id,
                "patientName": f"Queue {idx + 1}",
                "reason": reason,
                "priority": random.choice(["Normal", "High"]),
                "status": "Waiting",
                "assignedDoctor": random.choice(["Dr. Asha Raman", "Dr. Kiran Shah"]),
                "notes": "Awaiting vitals",
                "checkInAt": now - timedelta(minutes=idx * 8),
                "createdAt": now - timedelta(minutes=idx * 8),
                "updatedAt": now,
                "seedTag": SEED_TAG,
                "seedOwner": seed_owner,
            }
        )

    opd_doctors = [
        {
            "hospital": hospital_scope_id,
            "name": name,
            "specialty": specialty,
            "availability": True,
            "shift": random.choice(["Morning", "Afternoon", "Night"]),
            "schedule": "Mon-Fri 9am-1pm",
            "normalizedShift": "Morning",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for name, specialty in [
            ("Dr. Asha Raman", "Emergency"),
            ("Dr. Kiran Shah", "Cardiology"),
            ("Dr. Meera Nair", "Orthopedics"),
        ]
    ]

    opd_appointments = [
        {
            "hospital": hospital_scope_id,
            "patient": name,
            "doctor": doctor,
            "time": time,
            "status": "Scheduled",
            "appointmentType": random.choice(["New", "Follow-up"]),
            "channel": random.choice(["Walk-in", "Online", "Referral"]),
            "expectedDurationMinutes": random.choice([15, 20, 30]),
            "reason": random.choice(["Consultation", "Vitals review", "Follow-up"]),
            "notes": "Auto-seeded appointment",
            "seasonTag": "Summer",
            "slotHour": int(time.split(" ")[1].split(":")[0]) if " " in time else None,
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for name, doctor, time in [
            ("Anika Rao", "Dr. Kiran Shah", "2026-04-04 10:00"),
            ("Varun Singh", "Dr. Asha Raman", "2026-04-04 11:00"),
            ("Sana Bhat", "Dr. Meera Nair", "2026-04-04 14:00"),
        ]
    ]

    opd_consultations = [
        {
            "hospital": hospital_scope_id,
            "patient": patient,
            "doctor": doctor,
            "notes": notes,
            "date": "2026-04-03",
            "status": "Open",
            "summary": notes.split(".")[0] + ".",
            "aiSummary": notes.split(".")[0] + ".",
            "keywords": ["review", "follow-up"],
            "followUpPlan": "Schedule follow-up in 7 days",
            "followUpDate": "2026-04-10",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for patient, doctor, notes in [
            ("Riya Nair", "Dr. Kiran Shah", "Follow-up on hypertension."),
            ("Arjun Rao", "Dr. Meera Nair", "Post-surgery review."),
        ]
    ]

    icu_patients = [
        {
            "hospital": hospital_scope_id,
            "name": name,
            "oxygen": oxygen,
            "heartRate": heart_rate,
            "bp": bp,
            "status": status,
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for name, oxygen, heart_rate, bp, status in [
            ("Suresh Kumar", 92, 110, "130/85", "Critical"),
            ("Nikhil Das", 96, 98, "120/78", "Stable"),
        ]
    ]

    icu_alerts = [
        {
            "hospital": hospital_scope_id,
            "message": message,
            "severity": severity,
            "status": "Active",
            "createdAt": now - timedelta(minutes=idx * 15),
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for idx, (message, severity) in enumerate(
            [
                ("Sepsis risk rising", "High"),
                ("Ventilator pressure drop", "Medium"),
            ]
        )
    ]

    radiology_requests = [
        {
            "hospital": hospital_scope_id,
            "patient": patient,
            "scan": scan,
            "status": "Queued",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for patient, scan in [
            ("Varun Singh", "CT Chest"),
            ("Anika Rao", "MRI Brain"),
        ]
    ]

    radiology_reports = [
        {
            "hospital": hospital_scope_id,
            "patient": patient,
            "scan": scan,
            "fileName": file_name,
            "notes": notes,
            "status": "Uploaded",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for patient, scan, file_name, notes in [
            ("Varun Singh", "CT Chest", "ct_chest_2026_04_03.pdf", "No acute findings."),
            ("Anika Rao", "MRI Brain", "mri_brain_2026_04_03.pdf", "Normal study."),
        ]
    ]

    ot_surgeries = [
        {
            "hospital": hospital_scope_id,
            "patient": patient,
            "procedure": procedure,
            "time": time,
            "status": "Scheduled",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for patient, procedure, time in [
            ("Neha Iyer", "Appendectomy", "2026-04-03 14:00"),
            ("Rahul Bhat", "Orthopedic Fixation", "2026-04-03 16:30"),
        ]
    ]

    ot_allocations = [
        {
            "hospital": hospital_scope_id,
            "department": "Surgery",
            "patient_load": "High",
            "shift": "Day",
            "allocation_decision": "Add 1 anesthetist",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    bed_allocations = [
        {
            "hospital": hospital_scope_id,
            "patientName": "Rahul Bhat",
            "bedType": "ICU",
            "status": "Assigned",
            "notes": "Ventilator required",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    patients = []
    for idx, (name, dept) in enumerate([("Rahul Bhat", "Cardiology"), ("Anika Rao", "Orthopedics"), ("Varun Singh", "Emergency")]):
        patients.append(
            {
                "patientId": f"PT-Y-{idx + 1:03d}",
                "hospitalId": hospital_scope_id,
                "name": name,
                "age": 25 + idx * 7,
                "gender": "Male" if idx % 2 == 0 else "Female",
                "dept": dept,
                "room": f"{dept[:2].upper()}-{210 + idx}",
                "condition": "Stable",
                "severity": "Stable",
                "oxygen": 96 - idx,
                "heartRate": 80 + idx * 4,
                "bp": "120/80",
                "status": "Admitted",
                "admitDate": (now - timedelta(days=idx)).isoformat(),
                "createdAt": now,
                "updatedAt": now,
                "seedTag": SEED_TAG,
                "seedOwner": seed_owner,
            }
        )

    department_logs = [
        {
            "hospital": hospital_scope_id,
            "department": dept,
            "avgTreatmentMinutes": avg,
            "dischargeRate": rate,
            "delayRate": delay,
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for dept, avg, rate, delay in [
            ("Emergency", 28, 0.82, 0.12),
            ("Cardiology", 36, 0.88, 0.08),
            ("Orthopedics", 40, 0.79, 0.15),
        ]
    ]

    ambulances = [
        {
            "ambulanceId": f"AMB-Y-{idx + 1:02d}",
            "registrationNumber": f"KA-01-AB-{3200 + idx}",
            "hospital": hospital_scope_id,
            "status": random.choice(["available", "en_route", "at_location"]),
            "driver": {
                "name": f"Driver {idx + 1}",
                "licenseNumber": f"DL-{9100 + idx}",
                "phone": f"+91-90000{3200 + idx}",
                "availability": True,
            },
            "metrics": {
                "averageResponseTime": 12 + idx,
                "onTimeDeliveryRate": 92,
                "totalTripsToday": 4 + idx,
                "totalDistanceTodayKm": 120 + idx * 12,
            },
            "currentLocation": {
                "latitude": args.lat + (idx * 0.01),
                "longitude": args.lng + (idx * 0.01),
            },
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
        for idx in range(3)
    ]

    ambulance_assignments = [
        {
            "ambulanceId": "AMB-Y-01",
            "ambulanceUserId": str(user_doc["_id"]),
            "hospital": str(user_doc["_id"]),
            "patient": "Rahul Bhat",
            "emergencyType": "Cardiac",
            "status": "Active",
            "etaMinutes": 12,
            "pickup": "MG Road",
            "destination": args.name,
            "patientVitals": {"bp": "130/85", "oxygen": 93, "heartRate": 110},
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    analytics_events = [
        {
            "hospitalId": str(user_doc["_id"]),
            "eventType": "ai_insight",
            "module": "emergency",
            "summary": "Elevated surge risk detected",
            "createdAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    alerts = [
        {
            "user": user_doc["_id"],
            "userId": str(user_doc["_id"]),
            "hospitalId": str(user_doc["_id"]),
            "message": "Critical SOS alert received",
            "priority": "High",
            "status": "Active",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    health_records = [
        {
            "patientId": str(user_doc["_id"]),
            "patient_name": args.name,
            "diagnosis": "Hypertension",
            "notes": "Stable under medication",
            "createdAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    donations = [
        {
            "userId": str(user_doc["_id"]),
            "donorName": "Ajay Menon",
            "blood_group": "O+",
            "amount": 1,
            "status": "Available",
            "createdAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    resource_requests = [
        {
            "requester_id": str(user_doc["_id"]),
            "type": "blood",
            "urgency": "high",
            "details": "O+ required within 4 hours",
            "createdAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    family_members = [
        {
            "userId": str(user_doc["_id"]),
            "name": "Isha Rao",
            "relationship": "Spouse",
            "status": "Stable",
            "createdAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    predictions = [
        {
            "userId": str(user_doc["_id"]),
            "riskScore": 0.68,
            "riskLevel": "Medium",
            "createdAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    government_reports = [
        {
            "title": "Quarterly Capacity Review",
            "scope": "State",
            "summary": "Stable occupancy with localized surges.",
            "status": "Ready",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    government_compliance = [
        {
            "hospitalId": str(hospital_oid),
            "status": "Compliant",
            "findings": "All key standards met.",
            "owner": "State Health Authority",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    audit_logs = [
        {
            "hospitalId": str(hospital_oid),
            "summary": "Audit completed with minor observations.",
            "severity": "Low",
            "createdAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    hospital_messages = [
        {
            "fromHospital": hospital_oid,
            "toHospital": hospital_oid,
            "messageType": "resource",
            "subject": "Mutual aid request",
            "details": "Requesting two ventilators for surge coverage.",
            "requestDetails": {"urgencyLevel": "medium"},
            "status": "pending",
            "createdAt": now,
            "updatedAt": now,
            "seedTag": SEED_TAG,
            "seedOwner": seed_owner,
        }
    ]

    seeded = 0
    seeded += _seed_collection(db, "hospital_staff", staff, seed_owner)
    seeded += _seed_collection(db, "equipment_inventory", equipment, seed_owner)
    seeded += _seed_collection(db, "resources", resources, seed_owner)
    seeded += _seed_collection(db, "billing_invoices", invoices, seed_owner)
    seeded += _seed_collection(db, "insurance_claims", claims, seed_owner)
    seeded += _seed_collection(db, "finance_expenses", expenses, seed_owner)
    seeded += _seed_collection(db, "emergency_events", emergency_events, seed_owner)
    seeded += _seed_collection(db, "opd_queue", opd_queue, seed_owner)
    seeded += _seed_collection(db, "opd_doctors", opd_doctors, seed_owner)
    seeded += _seed_collection(db, "opd_appointments", opd_appointments, seed_owner)
    seeded += _seed_collection(db, "opd_consultations", opd_consultations, seed_owner)
    seeded += _seed_collection(db, "icu_patients", icu_patients, seed_owner)
    seeded += _seed_collection(db, "icu_alerts", icu_alerts, seed_owner)
    seeded += _seed_collection(db, "radiology_requests", radiology_requests, seed_owner)
    seeded += _seed_collection(db, "radiology_reports", radiology_reports, seed_owner)
    seeded += _seed_collection(db, "ot_surgeries", ot_surgeries, seed_owner)
    seeded += _seed_collection(db, "ot_allocations", ot_allocations, seed_owner)
    seeded += _seed_collection(db, "bed_allocations", bed_allocations, seed_owner)
    seeded += _seed_collection(db, "patients", patients, seed_owner)
    seeded += _seed_collection(db, "department_logs", department_logs, seed_owner)
    seeded += _seed_collection(db, "ambulances", ambulances, seed_owner)
    seeded += _seed_collection(db, "ambulance_assignments", ambulance_assignments, seed_owner)
    seeded += _seed_collection(db, "analytics_events", analytics_events, seed_owner)
    seeded += _seed_collection(db, "alerts", alerts, seed_owner)
    seeded += _seed_collection(db, "health_records", health_records, seed_owner)
    seeded += _seed_collection(db, "donations", donations, seed_owner)
    seeded += _seed_collection(db, "resourcerequests", resource_requests, seed_owner)
    seeded += _seed_collection(db, "family_members", family_members, seed_owner)
    seeded += _seed_collection(db, "predictions", predictions, seed_owner)
    seeded += _seed_collection(db, "government_reports", government_reports, seed_owner)
    seeded += _seed_collection(db, "government_compliance", government_compliance, seed_owner)
    seeded += _seed_collection(db, "audit_logs", audit_logs, seed_owner)
    seeded += _seed_collection(db, "hospitalmessages", hospital_messages, seed_owner)
    seeded += _seed_collection(db, "hospital_network_agreements", agreement_rows, seed_owner)

    print("Demo hospital seeded")
    print(f"Hospital user id: {user_doc['_id']}")
    print(f"Hospital doc id: {hospital_doc['_id']}")
    print(f"Seeded records: {seeded}")


if __name__ == "__main__":
    main()
