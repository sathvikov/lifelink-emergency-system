from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient
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


def _normalize_value(value: str) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    for caster in (int, float):
        try:
            number = caster(text)
            return number
        except ValueError:
            continue
    return text


def _load_csv(file_path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with file_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = {key: _normalize_value(value) for key, value in row.items()}
            rows.append(normalized)
            if limit and len(rows) >= limit:
                break
    return rows


def main() -> None:
    load_dotenv(_repo_root() / "backend" / ".env")
    mongo_uri = _get_mongo_uri()
    db_name = _get_db_name(mongo_uri)
    client = MongoClient(mongo_uri)
    db = client[db_name]

    data_dir = _repo_root() / "backend" / "ml"
    if not data_dir.exists():
        raise SystemExit(f"Dataset directory not found: {data_dir}")

    mapping = {
        "911_calls.csv": "emergency_events",
        "emergency_hotspot_data.csv": "emergency_events",
        "emergency_severity_data.csv": "emergency_events",
        "outbreak_data.csv": "emergency_events",
        "hospital_data.csv": "hospitals",
        "hospital_resource_data.csv": "resources",
        "inventory_data.csv": "resources",
        "staff_allocation_data.csv": "hospital_departments",
        "hospital_disease_data.csv": "hospital_departments",
        "patient_outcome_data.csv": "patients",
        "health_risk_data.csv": "health_records",
        "user_activity_data.csv": "health_records",
        "compatibility_data.csv": "predictions",
        "donor_availability_data.csv": "predictions",
        "eta_data.csv": "predictions",
        "hospital_performance_data.csv": "predictions",
        "policy_data.csv": "audit_logs",
    }

    for file_path in sorted(data_dir.glob("*.csv")):
        collection = mapping.get(file_path.name, "predictions")
        rows = _load_csv(file_path)
        if not rows:
            continue
        for row in rows:
            row["source_file"] = file_path.name
            row["ingested_at"] = datetime.utcnow().isoformat()
        db[collection].insert_many(rows)
        print(f"Imported {len(rows)} rows from {file_path.name} into {collection}")

    print("Migration complete")


if __name__ == "__main__":
    main()
