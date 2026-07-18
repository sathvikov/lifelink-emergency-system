from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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


def _slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed high-quality hospitals and patient data.")
    parser.add_argument("--drop", action="store_true", help="Drop existing hospitals and patients before insert")
    parser.add_argument("--export", action="store_true", help="Export seed data JSON into backend/seed")
    parser.add_argument("--hospital-count", type=int, default=10, help="Number of hospitals to seed")
    parser.add_argument("--patients-per-hospital", type=int, default=3, help="Patients per hospital")
    return parser.parse_args()


CITY_CATALOG = [
    {"code": "BLR", "city": "Bengaluru", "state": "Karnataka", "lat": 12.9716, "lng": 77.5946},
    {"code": "MYS", "city": "Mysuru", "state": "Karnataka", "lat": 12.2958, "lng": 76.6394},
    {"code": "MNG", "city": "Mangaluru", "state": "Karnataka", "lat": 12.9141, "lng": 74.8560},
    {"code": "HBL", "city": "Hubballi", "state": "Karnataka", "lat": 15.3647, "lng": 75.1240},
    {"code": "BLG", "city": "Belagavi", "state": "Karnataka", "lat": 15.8497, "lng": 74.4977},
    {"code": "DVG", "city": "Davanagere", "state": "Karnataka", "lat": 14.4644, "lng": 75.9218},
    {"code": "SHM", "city": "Shivamogga", "state": "Karnataka", "lat": 13.9299, "lng": 75.5681},
    {"code": "TMR", "city": "Tumakuru", "state": "Karnataka", "lat": 13.3409, "lng": 77.1010},
    {"code": "HSN", "city": "Hassan", "state": "Karnataka", "lat": 13.0072, "lng": 76.0962},
    {"code": "MDY", "city": "Mandya", "state": "Karnataka", "lat": 12.5239, "lng": 76.8958},
    {"code": "BJP", "city": "Vijayapura", "state": "Karnataka", "lat": 16.8302, "lng": 75.7100},
    {"code": "BDR", "city": "Bidar", "state": "Karnataka", "lat": 17.9149, "lng": 77.5046},
    {"code": "KLR", "city": "Kalaburagi", "state": "Karnataka", "lat": 17.3297, "lng": 76.8343},
    {"code": "RCR", "city": "Raichur", "state": "Karnataka", "lat": 16.2076, "lng": 77.3556},
    {"code": "CHT", "city": "Chitradurga", "state": "Karnataka", "lat": 14.2266, "lng": 76.4006},
    {"code": "KLR2", "city": "Kolar", "state": "Karnataka", "lat": 13.1362, "lng": 78.1291},
    {"code": "UDP", "city": "Udupi", "state": "Karnataka", "lat": 13.3409, "lng": 74.7421},
    {"code": "GAD", "city": "Gadag", "state": "Karnataka", "lat": 15.4319, "lng": 75.6356},
    {"code": "BGL", "city": "Bagalkot", "state": "Karnataka", "lat": 16.1850, "lng": 75.6969},
    {"code": "BLL", "city": "Ballari", "state": "Karnataka", "lat": 15.1394, "lng": 76.9214},
]

HOSPITAL_TEMPLATES = [
    {
        "suffix": "General Hospital",
        "type": "Government",
        "specialties": ["Emergency", "Internal Medicine", "Orthopedics", "Pediatrics"],
        "base_beds": 620,
        "ambulances": 10,
        "rating": 4.1,
    },
    {
        "suffix": "Medical College & Research Center",
        "type": "Teaching",
        "specialties": ["Emergency", "Cardiology", "Neurology", "ICU"],
        "base_beds": 780,
        "ambulances": 12,
        "rating": 4.3,
    },
    {
        "suffix": "Heart Institute",
        "type": "Specialty",
        "specialties": ["Cardiology", "Cardiac Surgery", "Emergency", "Rehab"],
        "base_beds": 260,
        "ambulances": 6,
        "rating": 4.5,
    },
    {
        "suffix": "Children's Hospital",
        "type": "Specialty",
        "specialties": ["Pediatrics", "Neonatology", "Pediatric Surgery", "Emergency"],
        "base_beds": 220,
        "ambulances": 5,
        "rating": 4.4,
    },
    {
        "suffix": "Multi-Specialty Center",
        "type": "Private",
        "specialties": ["Emergency", "Orthopedics", "Neurology", "Oncology"],
        "base_beds": 420,
        "ambulances": 8,
        "rating": 4.2,
    },
]

COORD_OFFSETS = [
    (0.012, 0.007),
    (-0.009, -0.011),
    (0.015, -0.006),
    (-0.013, 0.009),
    (0.006, 0.014),
]

DOCTOR_NAMES = [
    "Asha Raman", "Vikram Desai", "Meera Nair", "Arjun Rao", "Sneha Menon",
    "Kiran Shah", "Nandita Iyer", "Rahul Bhat", "Divya Suresh", "Karthik Jain",
]

PATIENT_FIRST = [
    "Aarav", "Ishaan", "Vihaan", "Anika", "Diya", "Kavya", "Rohan", "Sana", "Leela", "Nikhil",
    "Riya", "Varun", "Meera", "Aditya", "Priya", "Rahul", "Suresh", "Neha", "Arjun", "Isha",
]

PATIENT_LAST = [
    "Nair", "Reddy", "Shetty", "Patil", "Rao", "Joshi", "Kulkarni", "Bhat", "Sharma", "Das",
    "Iyer", "Kumar", "Menon", "Singh", "Gupta", "Mahajan", "Hegde", "Nayak", "Jain", "Shekar",
]

CONDITIONS = [
    ("Cardiac", "Chest pain"),
    ("Trauma", "Road traffic injury"),
    ("Respiratory", "Severe asthma"),
    ("Neuro", "Stroke observation"),
    ("Ortho", "Fracture management"),
    ("Gastro", "Acute gastritis"),
    ("Renal", "Kidney stone"),
    ("Infection", "High fever"),
    ("Pediatrics", "Viral fever"),
]


def build_hospitals(limit: int) -> list[dict[str, Any]]:
    hospitals: list[dict[str, Any]] = []
    reg_counter = 1
    for city in CITY_CATALOG:
        for idx, template in enumerate(HOSPITAL_TEMPLATES, start=1):
            if len(hospitals) >= limit:
                return hospitals
            offset = COORD_OFFSETS[idx - 1]
            total_beds = template["base_beds"] + (reg_counter % 4) * 15
            occupied = int(total_beds * (0.62 + (idx * 0.03)))
            available = max(0, total_beds - occupied)

            name = f"{city['city']} {template['suffix']}"
            slug = _slugify(name)
            reg_number = f"KA-{city['code']}-{reg_counter:03d}"
            address = f"{idx * 12} {city['city']} Central Road"

            doctors = []
            for d_idx in range(3):
                doc_name = DOCTOR_NAMES[(reg_counter + d_idx) % len(DOCTOR_NAMES)]
                doctors.append({
                    "name": f"Dr. {doc_name}",
                    "department": template["specialties"][d_idx % len(template["specialties"])],
                    "availability": True,
                    "role": "Doctor",
                })

            hospitals.append(
                {
                    "hospital_id": f"{city['code']}-{idx:02d}",
                    "name": name,
                    "regNumber": reg_number,
                    "type": template["type"],
                    "phone": f"080-{700000 + reg_counter:06d}",
                    "email": f"info@{slug}.org",
                    "location": {
                        "lat": round(city["lat"] + offset[0], 6),
                        "lng": round(city["lng"] + offset[1], 6),
                        "address": address,
                        "city": city["city"],
                        "state": city["state"],
                    },
                    "specialties": template["specialties"],
                    "beds": {
                        "totalBeds": total_beds,
                        "occupiedBeds": occupied,
                        "availableBeds": available,
                    },
                    "ambulances": template["ambulances"],
                    "rating": template["rating"],
                    "establishedYear": 1975 + (reg_counter % 30),
                    "doctors": doctors,
                    "resources": [],
                    "createdAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow(),
                }
            )
            reg_counter += 1
    return hospitals


def build_patients(hospital_ids: list[Any], patients_per_hospital: int) -> list[dict[str, Any]]:
    patients: list[dict[str, Any]] = []
    patient_counter = 1
    for index, hospital_id in enumerate(hospital_ids):
        for p_idx in range(patients_per_hospital):
            first = PATIENT_FIRST[(patient_counter + p_idx) % len(PATIENT_FIRST)]
            last = PATIENT_LAST[(patient_counter + p_idx) % len(PATIENT_LAST)]
            dept, condition = CONDITIONS[(patient_counter + p_idx) % len(CONDITIONS)]
            age = 18 + (patient_counter % 55)
            gender = "Male" if patient_counter % 2 == 0 else "Female"
            admit_date = datetime.utcnow() - timedelta(days=(patient_counter % 12))

            patients.append(
                {
                    "patientId": f"PT-{index + 1:03d}-{p_idx + 1:02d}",
                    "hospitalId": hospital_id,
                    "name": f"{first} {last}",
                    "age": age,
                    "gender": gender,
                    "dept": dept,
                    "room": f"{dept[:2].upper()}-{200 + p_idx}",
                    "condition": condition,
                    "severity": "Critical" if patient_counter % 7 == 0 else "Stable",
                    "oxygen": 95 - (patient_counter % 6),
                    "heartRate": 80 + (patient_counter % 20),
                    "bp": "120/80",
                    "status": "Admitted",
                    "admitDate": admit_date.isoformat(),
                    "createdAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow(),
                }
            )
            patient_counter += 1
    return patients


def main() -> None:
    args = _parse_args()
    load_dotenv(_repo_root() / "backend" / ".env")

    mongo_uri = _get_mongo_uri()
    db_name = _get_db_name(mongo_uri)
    client = MongoClient(mongo_uri)
    db = client[db_name]

    hospitals = build_hospitals(args.hospital_count)
    if len(hospitals) != args.hospital_count:
        raise SystemExit(f"Expected {args.hospital_count} hospitals, got {len(hospitals)}")

    if args.drop:
        db["hospitals"].drop()
        db["patients"].drop()
        print("Dropped existing hospitals and patients collections")

    result = db["hospitals"].insert_many(hospitals)
    hospital_ids = result.inserted_ids

    patients = build_patients(hospital_ids, args.patients_per_hospital)
    if patients:
        db["patients"].insert_many(patients)

    print(f"Inserted hospitals: {len(hospital_ids)}")
    print(f"Inserted patients: {len(patients)}")

    if args.export:
        seed_dir = _repo_root() / "backend" / "seed"
        seed_dir.mkdir(parents=True, exist_ok=True)

        export_hospitals = []
        for idx, doc in enumerate(hospitals):
            export_doc = {**doc, "_id": str(hospital_ids[idx])}
            export_hospitals.append(export_doc)

        (seed_dir / "quality_hospitals.json").write_text(
            json.dumps(export_hospitals, indent=2, default=str),
            encoding="utf-8",
        )
        (seed_dir / "quality_patients.json").write_text(
            json.dumps(patients, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Exported seed data to {seed_dir}")

    print("Quality data seed complete")


if __name__ == "__main__":
    main()
