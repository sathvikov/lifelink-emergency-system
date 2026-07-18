import argparse
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri


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
    parser = argparse.ArgumentParser(description="Seed hospital module operational data.")
    parser.add_argument("--drop", action="store_true", help="Drop hospital module collections before seeding")
    parser.add_argument("--limit", type=int, default=10, help="Number of hospitals to seed")
    parser.add_argument("--bind-hospital-id", type=str, default=None, help="Seed data for a specific hospital/user ObjectId")
    return parser.parse_args()


STAFF_ROLES = ["Doctor", "Nurse", "Technician", "Support"]
DEPARTMENTS = ["Emergency", "ICU", "OPD", "Radiology", "Surgery", "General"]
EQUIPMENT = [
    ("Ventilator", "Equipment"),
    ("Defibrillator", "Equipment"),
    ("MRI Scanner", "Imaging"),
    ("CT Scanner", "Imaging"),
    ("Ultrasound", "Imaging"),
]
RESOURCES = [
    ("Oxygen Cylinders", "Supply"),
    ("PPE Kits", "Supply"),
    ("IV Fluids", "Supply"),
    ("Antibiotics", "Medicine"),
]


def _safe_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


def _seed_staff(hospital_oid: ObjectId) -> list[dict]:
    staff = []
    for idx in range(12):
        staff.append(
            {
                "hospital": hospital_oid,
                "name": f"Staff {idx + 1}",
                "role": random.choice(STAFF_ROLES),
                "department": random.choice(DEPARTMENTS),
                "shift": random.choice(["Day", "Evening", "Night"]),
                "availability": random.random() > 0.2,
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
        )
    return staff


def _seed_equipment(hospital_oid: ObjectId) -> list[dict]:
    rows = []
    for name, category in EQUIPMENT:
        rows.append(
            {
                "hospital": hospital_oid,
                "name": name,
                "category": category,
                "quantity": random.randint(2, 12),
                "status": "Available",
                "minThreshold": 2,
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
        )
    return rows


def _seed_resources(hospital_oid: ObjectId) -> list[dict]:
    rows = []
    for name, category in RESOURCES:
        rows.append(
            {
                "hospitalId": hospital_oid,
                "name": name,
                "category": category,
                "quantity": random.randint(20, 200),
                "unit": "units",
                "minThreshold": 25,
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
        )
    return rows


def _seed_invoices(hospital_oid: ObjectId) -> list[dict]:
    invoices = []
    for idx in range(8):
        invoices.append(
            {
                "hospital": hospital_oid,
                "patientName": f"Patient {idx + 1}",
                "department": random.choice(DEPARTMENTS),
                "amount": round(random.uniform(3500, 18000), 2),
                "status": random.choice(["Unpaid", "Paid", "Pending"]),
                "insuranceProvider": random.choice(["CarePlus", "Apex", "None"]),
                "paidAmount": 0.0,
                "refundAmount": 0.0,
                "createdAt": datetime.utcnow() - timedelta(days=random.randint(0, 20)),
                "updatedAt": datetime.utcnow(),
            }
        )
    return invoices


def _seed_claims(hospital_oid: ObjectId) -> list[dict]:
    claims = []
    for idx in range(3):
        claims.append(
            {
                "hospital": hospital_oid,
                "invoiceId": f"INV-{idx + 1}",
                "insurer": random.choice(["CarePlus", "Apex"]),
                "amount": round(random.uniform(2500, 14000), 2),
                "status": random.choice(["Submitted", "Approved", "Pending"]),
                "approvedAmount": 0.0,
                "createdAt": datetime.utcnow() - timedelta(days=random.randint(1, 15)),
                "updatedAt": datetime.utcnow(),
            }
        )
    return claims


def _seed_expenses(hospital_oid: ObjectId) -> list[dict]:
    rows = []
    for category in ["Supplies", "Staffing", "Utilities", "Equipment"]:
        rows.append(
            {
                "hospital": hospital_oid,
                "category": category,
                "amount": round(random.uniform(1500, 9000), 2),
                "createdAt": datetime.utcnow() - timedelta(days=random.randint(0, 15)),
                "updatedAt": datetime.utcnow(),
            }
        )
    return rows


def _seed_emergencies(hospital_oid: ObjectId) -> list[dict]:
    rows = []
    for idx in range(5):
        rows.append(
            {
                "hospital": hospital_oid,
                "patientName": f"Emergency {idx + 1}",
                "symptoms": random.choice(["Chest pain", "Trauma", "High fever", "Stroke"]),
                "location": "Zone A",
                "source": "public",
                "severity": random.choice(["High", "Critical", "Medium"]),
                "priority": "High",
                "status": "Unassigned",
                "createdAt": datetime.utcnow() - timedelta(minutes=random.randint(5, 120)),
                "updatedAt": datetime.utcnow(),
            }
        )
    return rows


def _seed_queue(hospital_oid: ObjectId) -> list[dict]:
    rows = []
    for idx in range(6):
        rows.append(
            {
                "hospital": hospital_oid,
                "patientName": f"Queue {idx + 1}",
                "reason": random.choice(["Fever", "Injury", "Follow-up"]),
                "priority": random.choice(["Normal", "High"]),
                "status": "Waiting",
                "createdAt": datetime.utcnow() - timedelta(minutes=random.randint(5, 40)),
                "updatedAt": datetime.utcnow(),
            }
        )
    return rows


def main() -> None:
    args = _parse_args()
    load_dotenv(_repo_root() / "backend" / ".env")

    mongo_uri = _get_mongo_uri()
    db_name = _get_db_name(mongo_uri)
    client = MongoClient(mongo_uri)
    db = client[db_name]

    collections = {
        "hospital_staff": [],
        "equipment_inventory": [],
        "resources": [],
        "billing_invoices": [],
        "insurance_claims": [],
        "finance_expenses": [],
        "emergency_events": [],
        "opd_queue": [],
    }

    if args.drop:
        for name in collections.keys():
            db[name].drop()
        print("Dropped hospital module collections")

    hospitals = []
    if args.bind_hospital_id:
        target_oid = _safe_object_id(args.bind_hospital_id)
        if not target_oid:
            raise SystemExit("Invalid --bind-hospital-id")
        hospitals = [target_oid]
    else:
        hospital_docs = list(db["hospitals"].find({}).limit(args.limit))
        hospitals = [h.get("_id") for h in hospital_docs if h.get("_id")]

    if not hospitals:
        raise SystemExit("No hospitals found to seed")

    for hospital_oid in hospitals:
        collections["hospital_staff"].extend(_seed_staff(hospital_oid))
        collections["equipment_inventory"].extend(_seed_equipment(hospital_oid))
        collections["resources"].extend(_seed_resources(hospital_oid))
        collections["billing_invoices"].extend(_seed_invoices(hospital_oid))
        collections["insurance_claims"].extend(_seed_claims(hospital_oid))
        collections["finance_expenses"].extend(_seed_expenses(hospital_oid))
        collections["emergency_events"].extend(_seed_emergencies(hospital_oid))
        collections["opd_queue"].extend(_seed_queue(hospital_oid))

    for name, docs in collections.items():
        if docs:
            db[name].insert_many(docs)
            print(f"Seeded {len(docs)} documents into {name}")

    print("Hospital module seeding complete")


if __name__ == "__main__":
    main()
