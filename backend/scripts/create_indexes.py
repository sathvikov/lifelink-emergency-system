from __future__ import annotations

import os
from pathlib import Path

from pymongo import ASCENDING, MongoClient
from pymongo.uri_parser import parse_uri
from dotenv import load_dotenv


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


def main() -> None:
    load_dotenv(_repo_root() / "backend" / ".env")
    mongo_uri = _get_mongo_uri()
    db_name = _get_db_name(mongo_uri)
    client = MongoClient(mongo_uri)
    db = client[db_name]

    index_map = {
        "hospitals": [("location", ASCENDING), ("hospital_id", ASCENDING), ("hospitalId", ASCENDING)],
        "hospital_departments": [("hospital_id", ASCENDING), ("department", ASCENDING)],
        "patients": [("patient_id", ASCENDING), ("patientId", ASCENDING), ("hospital_id", ASCENDING)],
        "ambulances": [("ambulanceId", ASCENDING), ("hospital_id", ASCENDING)],
        "emergency_events": [("location", ASCENDING), ("hospital_id", ASCENDING), ("patient_id", ASCENDING)],
        "health_records": [("patient_id", ASCENDING), ("user_id", ASCENDING)],
        "predictions": [("patient_id", ASCENDING), ("hospital_id", ASCENDING), ("type", ASCENDING)],
        "alerts": [("user", ASCENDING), ("createdAt", ASCENDING)],
        "audit_logs": [("createdAt", ASCENDING), ("actor_id", ASCENDING)],
    }

    for collection, indexes in index_map.items():
        for fields in indexes:
            db[collection].create_index([fields], sparse=True)
        print(f"Indexes ensured for {collection}")

    print("Index creation complete")


if __name__ == "__main__":
    main()
