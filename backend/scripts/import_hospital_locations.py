from __future__ import annotations

import argparse
import asyncio
import csv
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from faker import Faker

from app.db.mongo import close_mongo_connection, connect_to_mongo, get_db
from app.services.collections import HOSPITALS
from app.services.repository import MongoRepository


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _resolve_column(headers: list[str], candidates: list[str], override: str | None) -> str | None:
    if override:
        return override
    normalized = {_normalize_key(h): h for h in headers}
    for candidate in candidates:
        key = _normalize_key(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _parse_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _randomize_location(center_lat: float, center_lng: float, radius_km: float) -> tuple[float, float]:
    radius_deg = radius_km / 111.0
    lat = center_lat + random.uniform(-radius_deg, radius_deg)
    lng = center_lng + random.uniform(-radius_deg, radius_deg)
    return lat, lng


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import hospital locations into PostgreSQL.")
    parser.add_argument("--input", required=True, help="Path to hospital CSV file")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows to import")
    parser.add_argument("--name-col", help="Column name for hospital name")
    parser.add_argument("--lat-col", help="Column name for latitude")
    parser.add_argument("--lng-col", help="Column name for longitude")
    parser.add_argument("--address-col", help="Column name for address")
    parser.add_argument("--city-col", help="Column name for city")
    parser.add_argument("--state-col", help="Column name for state")
    parser.add_argument("--phone-col", help="Column name for phone")
    parser.add_argument("--beds-col", help="Column name for bed count")
    parser.add_argument("--allow-fallback", action="store_true", help="Generate coordinates if missing")
    parser.add_argument("--center-lat", type=float, default=12.9716, help="Fallback center latitude")
    parser.add_argument("--center-lng", type=float, default=77.5946, help="Fallback center longitude")
    parser.add_argument("--radius-km", type=float, default=50.0, help="Fallback radius in km")
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    load_dotenv(_repo_root() / "backend" / ".env")

    csv_path = Path(args.input)
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    await connect_to_mongo()
    db = get_db()
    repo = MongoRepository(db, HOSPITALS)

    faker = Faker()

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []

        name_col = _resolve_column(headers, ["hospital_name", "name", "facility_name", "hospital", "facility"], args.name_col)
        lat_col = _resolve_column(headers, ["lat", "latitude", "y"], args.lat_col)
        lng_col = _resolve_column(headers, ["lng", "lon", "longitude", "x"], args.lng_col)
        address_col = _resolve_column(headers, ["address", "street", "address_line", "location"], args.address_col)
        city_col = _resolve_column(headers, ["city", "district", "town"], args.city_col)
        state_col = _resolve_column(headers, ["state", "province", "region"], args.state_col)
        phone_col = _resolve_column(headers, ["phone", "contact", "telephone"], args.phone_col)
        beds_col = _resolve_column(headers, ["beds", "total_beds", "bed_count"], args.beds_col)

        rows = 0
        inserted = 0
        skipped = 0
        for row in reader:
            rows += 1
            if args.limit and rows > args.limit:
                break

            name = (row.get(name_col) if name_col else None) or f"{faker.city()} Hospital"
            lat = _parse_float(row.get(lat_col)) if lat_col else None
            lng = _parse_float(row.get(lng_col)) if lng_col else None

            if (lat is None or lng is None) and args.allow_fallback:
                lat, lng = _randomize_location(args.center_lat, args.center_lng, args.radius_km)

            if lat is None or lng is None:
                skipped += 1
                continue

            location = {
                "lat": round(lat, 6),
                "lng": round(lng, 6),
            }
            address = row.get(address_col) if address_col else None
            if address:
                location["address"] = str(address).strip()
            city = row.get(city_col) if city_col else None
            if city:
                location["city"] = str(city).strip()
            state = row.get(state_col) if state_col else None
            if state:
                location["state"] = str(state).strip()

            record: dict[str, Any] = {
                "name": str(name).strip(),
                "location": location,
                "source": str(csv_path.name),
                "imported_at": datetime.utcnow().isoformat(),
            }

            phone = row.get(phone_col) if phone_col else None
            if phone:
                record["phone"] = str(phone).strip()

            beds = row.get(beds_col) if beds_col else None
            beds_value = _parse_float(beds)
            if beds_value is not None:
                record["beds_total"] = int(beds_value)

            await repo.insert_one(record)
            inserted += 1

    await close_mongo_connection()

    print(f"Rows processed: {rows}")
    print(f"Inserted: {inserted}")
    print(f"Skipped (missing coordinates): {skipped}")
    print("Hospital import complete")


if __name__ == "__main__":
    asyncio.run(main())
