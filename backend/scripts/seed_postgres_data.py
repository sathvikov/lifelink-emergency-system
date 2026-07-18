import asyncio
import random
from datetime import datetime

import bcrypt
from faker import Faker

from app.db.mongo import close_mongo_connection, connect_to_mongo, get_db
from app.services.collections import AMBULANCES, FAMILY_MEMBERS, HOSPITALS, USERS
from app.services.repository import MongoRepository

faker = Faker()
random.seed(42)

HOSPITAL_COUNT = 100
AMBULANCE_COUNT = 300
PUBLIC_COUNT = 1000

CENTER_LAT = 12.97
CENTER_LNG = 77.59


def _random_coords(spread=0.4):
    lat = CENTER_LAT + random.uniform(-spread, spread)
    lng = CENTER_LNG + random.uniform(-spread, spread)
    return round(lat, 6), round(lng, 6)


def _hash_password(value: str) -> str:
    return bcrypt.hashpw(value.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed_hospitals(db):
    repo = MongoRepository(db, HOSPITALS)
    for i in range(HOSPITAL_COUNT):
        lat, lng = _random_coords()
        beds_total = random.randint(80, 240)
        beds_available = random.randint(10, max(10, int(beds_total * 0.4)))
        icu_available = random.randint(2, max(3, int(beds_available * 0.3)))
        await repo.insert_one(
            {
                "name": f"{faker.city()} General Hospital",
                "location": {
                    "lat": lat,
                    "lng": lng,
                    "address": faker.street_address(),
                    "city": faker.city(),
                    "state": faker.state(),
                },
                "beds_total": beds_total,
                "beds_available": beds_available,
                "icu_available": icu_available,
                "load_score": round(1 - (beds_available / max(1, beds_total)), 2),
                "rating": round(random.uniform(3.5, 4.9), 1),
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
        )


async def seed_ambulances(db):
    repo = MongoRepository(db, AMBULANCES)
    for i in range(AMBULANCE_COUNT):
        lat, lng = _random_coords(0.6)
        await repo.insert_one(
            {
                "ambulanceId": f"AMB-{i+1000}",
                "status": "Available" if i % 4 != 0 else "Idle",
                "location": {"lat": lat, "lng": lng},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
        )


async def seed_public_users(db):
    repo = MongoRepository(db, USERS)
    family_repo = MongoRepository(db, FAMILY_MEMBERS)
    password_hash = _hash_password("password")

    for i in range(PUBLIC_COUNT):
        lat, lng = _random_coords(0.5)
        is_donor = i % 3 == 0
        donor_profile = None
        if is_donor:
            donor_profile = {
                "bloodGroup": random.choice(["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]),
                "availability": "Available" if i % 4 != 0 else "Unavailable",
                "organTypes": ["Blood"],
                "location": {"lat": lat, "lng": lng},
                "lastDonation": faker.date_between(start_date="-1y", end_date="today").isoformat(),
            }

        user = await repo.insert_one(
            {
                "name": faker.name(),
                "email": faker.unique.email(),
                "password": password_hash,
                "role": "public",
                "location": {"lat": lat, "lng": lng},
                "phone": faker.phone_number(),
                "isVerified": True,
                "publicProfile": {
                    "healthRecords": {
                        "age": random.randint(18, 76),
                        "bloodGroup": donor_profile["bloodGroup"] if donor_profile else random.choice(["O+", "A+", "B+"]),
                        "conditions": random.sample(["Hypertension", "Diabetes", "Asthma", "None"], 2),
                    },
                    "donorProfile": donor_profile,
                },
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }
        )

        if i % 6 == 0:
            await family_repo.insert_one(
                {
                    "user": user.get("_id"),
                    "name": faker.name(),
                    "relation": random.choice(["Mother", "Father", "Sibling", "Spouse"]),
                    "phone": faker.phone_number(),
                    "status": "Safe",
                    "createdAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow(),
                }
            )


async def main():
    await connect_to_mongo()
    db = get_db()

    await seed_hospitals(db)
    await seed_ambulances(db)
    await seed_public_users(db)

    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main())
