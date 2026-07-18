import asyncio
import json
import random
from datetime import datetime, timedelta, date
from uuid import uuid4

from faker import Faker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

RECORDS_PER_TABLE = 2000
BATCH_SIZE = 500

faker = Faker()
random.seed(42)

SEVERITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["pending", "assigned", "resolved"]
BLOOD_GROUPS = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]
ROLES = ["Doctor", "Nurse", "Technician", "Support"]
SHIFTS = ["Day", "Night", "Evening"]
BED_TYPES = ["General", "ICU", "NICU", "Emergency"]
EQUIP_CATEGORIES = ["Imaging", "Monitoring", "Surgical", "Lab"]


def _chunks(rows, size):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


async def _insert_batches(conn, sql, rows):
    if not rows:
        return
    stmt = text(sql)
    for batch in _chunks(rows, BATCH_SIZE):
        await conn.execute(stmt, batch)


def _random_coords():
    lat = 12.97 + random.uniform(-0.6, 0.6)
    lng = 77.59 + random.uniform(-0.6, 0.6)
    return round(lat, 6), round(lng, 6)


async def seed_public_users(conn):
    rows = []
    user_ids = []
    for _ in range(RECORDS_PER_TABLE):
        user_id = uuid4()
        lat, lng = _random_coords()
        rows.append(
            {
                "id": user_id,
                "full_name": faker.name(),
                "email": faker.unique.email(),
                "phone": faker.phone_number(),
                "age": random.randint(18, 80),
                "gender": random.choice(["Male", "Female", "Other"]),
                "blood_group": random.choice(BLOOD_GROUPS),
                "city": faker.city(),
                "state": faker.state(),
                "latitude": lat,
                "longitude": lng,
                "created_at": datetime.utcnow(),
            }
        )
        user_ids.append(user_id)

    await _insert_batches(
        conn,
        """
        INSERT INTO public_users
        (id, full_name, email, phone, age, gender, blood_group, city, state, latitude, longitude, created_at)
        VALUES
        (:id, :full_name, :email, :phone, :age, :gender, :blood_group, :city, :state, :latitude, :longitude, :created_at)
        """,
        rows,
    )
    return user_ids


async def seed_public_donors(conn, user_ids):
    rows = []
    for user_id in user_ids:
        rows.append(
            {
                "id": uuid4(),
                "user_id": user_id,
                "availability": random.choice(["Available", "On Call", "Unavailable"]),
                "organ_types": json.dumps(["Blood"]),
                "last_donation": date.today() - timedelta(days=random.randint(10, 320)),
                "donor_since": date.today() - timedelta(days=random.randint(180, 1500)),
                "created_at": datetime.utcnow(),
            }
        )

    await _insert_batches(
        conn,
        """
        INSERT INTO public_donor_profiles
        (id, user_id, availability, organ_types, last_donation, donor_since, created_at)
        VALUES
        (:id, :user_id, :availability, :organ_types, :last_donation, :donor_since, :created_at)
        """,
        rows,
    )


async def seed_public_sos(conn, user_ids):
    rows = []
    for _ in range(RECORDS_PER_TABLE):
        user_id = random.choice(user_ids)
        lat, lng = _random_coords()
        rows.append(
            {
                "id": uuid4(),
                "user_id": user_id,
                "message": faker.sentence(nb_words=8),
                "severity": random.choice(SEVERITIES),
                "status": random.choice(STATUSES),
                "latitude": lat,
                "longitude": lng,
                "eta_minutes": random.randint(4, 28),
                "assigned_hospital_id": None,
                "assigned_ambulance_code": f"AMB-{random.randint(1000, 9999)}",
                "created_at": datetime.utcnow() - timedelta(minutes=random.randint(0, 1200)),
                "updated_at": datetime.utcnow(),
            }
        )

    await _insert_batches(
        conn,
        """
        INSERT INTO public_sos_requests
        (id, user_id, message, severity, status, latitude, longitude, eta_minutes, assigned_hospital_id, assigned_ambulance_code, created_at, updated_at)
        VALUES
        (:id, :user_id, :message, :severity, :status, :latitude, :longitude, :eta_minutes, :assigned_hospital_id, :assigned_ambulance_code, :created_at, :updated_at)
        """,
        rows,
    )


async def seed_public_risk(conn, user_ids):
    rows = []
    for _ in range(RECORDS_PER_TABLE):
        user_id = random.choice(user_ids)
        bmi = round(random.uniform(18.0, 35.0), 2)
        rows.append(
            {
                "id": uuid4(),
                "user_id": user_id,
                "risk_level": random.choice(["Low", "Moderate", "High"]),
                "risk_score": random.randint(20, 90),
                "bmi": bmi,
                "blood_pressure": random.randint(100, 170),
                "heart_rate": random.randint(55, 115),
                "lifestyle_factor": random.choice(["Sedentary", "Average", "Healthy"]),
                "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 120)),
            }
        )

    await _insert_batches(
        conn,
        """
        INSERT INTO public_health_risk_assessments
        (id, user_id, risk_level, risk_score, bmi, blood_pressure, heart_rate, lifestyle_factor, created_at)
        VALUES
        (:id, :user_id, :risk_level, :risk_score, :bmi, :blood_pressure, :heart_rate, :lifestyle_factor, :created_at)
        """,
        rows,
    )


async def seed_public_notifications(conn, user_ids):
    rows = []
    for _ in range(RECORDS_PER_TABLE):
        user_id = random.choice(user_ids)
        rows.append(
            {
                "id": uuid4(),
                "user_id": user_id,
                "type": random.choice(["sos_alert", "donor_match", "health_risk"]),
                "title": faker.sentence(nb_words=4),
                "message": faker.sentence(nb_words=12),
                "read": random.choice([True, False]),
                "metadata": json.dumps({"priority": random.choice(["low", "medium", "high"])}),
                "created_at": datetime.utcnow() - timedelta(hours=random.randint(0, 240)),
            }
        )

    await _insert_batches(
        conn,
        """
        INSERT INTO public_notifications
        (id, user_id, type, title, message, read, metadata, created_at)
        VALUES
        (:id, :user_id, :type, :title, :message, :read, :metadata, :created_at)
        """,
        rows,
    )


async def seed_hospital_facilities(conn):
    rows = []
    hospital_ids = []
    for _ in range(RECORDS_PER_TABLE):
        hospital_id = uuid4()
        lat, lng = _random_coords()
        beds_total = random.randint(80, 280)
        beds_available = random.randint(10, max(12, int(beds_total * 0.4)))
        rows.append(
            {
                "id": hospital_id,
                "name": f"{faker.city()} Medical Center",
                "city": faker.city(),
                "state": faker.state(),
                "latitude": lat,
                "longitude": lng,
                "status": random.choice(["active", "active", "active", "maintenance"]),
                "rating": round(random.uniform(3.6, 4.9), 1),
                "beds_total": beds_total,
                "beds_available": beds_available,
                "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 365)),
                "updated_at": datetime.utcnow(),
            }
        )
        hospital_ids.append(hospital_id)

    await _insert_batches(
        conn,
        """
        INSERT INTO hospital_facilities
        (id, name, city, state, latitude, longitude, status, rating, beds_total, beds_available, created_at, updated_at)
        VALUES
        (:id, :name, :city, :state, :latitude, :longitude, :status, :rating, :beds_total, :beds_available, :created_at, :updated_at)
        """,
        rows,
    )
    return hospital_ids


async def seed_hospital_departments(conn, hospital_ids):
    rows = []
    department_ids = []
    for _ in range(RECORDS_PER_TABLE):
        department_id = uuid4()
        rows.append(
            {
                "id": department_id,
                "hospital_id": random.choice(hospital_ids),
                "name": random.choice(["Emergency", "Cardiology", "Neurology", "Radiology", "Surgery"]),
                "head": faker.name(),
                "phone": faker.phone_number(),
                "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 365)),
            }
        )
        department_ids.append(department_id)

    await _insert_batches(
        conn,
        """
        INSERT INTO hospital_departments
        (id, hospital_id, name, head, phone, created_at)
        VALUES
        (:id, :hospital_id, :name, :head, :phone, :created_at)
        """,
        rows,
    )
    return department_ids


async def seed_hospital_staff(conn, hospital_ids, department_ids):
    rows = []
    for _ in range(RECORDS_PER_TABLE):
        rows.append(
            {
                "id": uuid4(),
                "hospital_id": random.choice(hospital_ids),
                "department_id": random.choice(department_ids),
                "full_name": faker.name(),
                "role": random.choice(ROLES),
                "shift": random.choice(SHIFTS),
                "availability": random.choice([True, True, False]),
                "certifications": json.dumps([faker.word().title()]),
                "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 365)),
            }
        )

    await _insert_batches(
        conn,
        """
        INSERT INTO hospital_staff
        (id, hospital_id, department_id, full_name, role, shift, availability, certifications, created_at)
        VALUES
        (:id, :hospital_id, :department_id, :full_name, :role, :shift, :availability, :certifications, :created_at)
        """,
        rows,
    )


async def seed_hospital_beds(conn, hospital_ids):
    rows = []
    for _ in range(RECORDS_PER_TABLE):
        status = random.choice(["Available", "Occupied", "Reserved"])
        rows.append(
            {
                "id": uuid4(),
                "hospital_id": random.choice(hospital_ids),
                "bed_type": random.choice(BED_TYPES),
                "status": status,
                "patient_name": faker.name() if status == "Occupied" else None,
                "updated_at": datetime.utcnow() - timedelta(hours=random.randint(0, 120)),
            }
        )

    await _insert_batches(
        conn,
        """
        INSERT INTO hospital_beds
        (id, hospital_id, bed_type, status, patient_name, updated_at)
        VALUES
        (:id, :hospital_id, :bed_type, :status, :patient_name, :updated_at)
        """,
        rows,
    )


async def seed_hospital_equipment(conn, hospital_ids):
    rows = []
    for _ in range(RECORDS_PER_TABLE):
        rows.append(
            {
                "id": uuid4(),
                "hospital_id": random.choice(hospital_ids),
                "name": faker.word().title(),
                "category": random.choice(EQUIP_CATEGORIES),
                "quantity": random.randint(1, 35),
                "status": random.choice(["Operational", "Maintenance", "Out of Service"]),
                "min_threshold": random.randint(1, 5),
                "updated_at": datetime.utcnow() - timedelta(days=random.randint(0, 45)),
            }
        )

    await _insert_batches(
        conn,
        """
        INSERT INTO hospital_equipment
        (id, hospital_id, name, category, quantity, status, min_threshold, updated_at)
        VALUES
        (:id, :hospital_id, :name, :category, :quantity, :status, :min_threshold, :updated_at)
        """,
        rows,
    )


async def seed_hospital_emergencies(conn, hospital_ids):
    rows = []
    for _ in range(RECORDS_PER_TABLE):
        rows.append(
            {
                "id": uuid4(),
                "hospital_id": random.choice(hospital_ids),
                "patient_name": faker.name(),
                "symptoms": faker.sentence(nb_words=6),
                "severity": random.choice(SEVERITIES),
                "status": random.choice(["Active", "Resolved", "Closed"]),
                "source": random.choice(["public", "ambulance", "internal"]),
                "created_at": datetime.utcnow() - timedelta(hours=random.randint(0, 240)),
            }
        )

    await _insert_batches(
        conn,
        """
        INSERT INTO hospital_emergency_events
        (id, hospital_id, patient_name, symptoms, severity, status, source, created_at)
        VALUES
        (:id, :hospital_id, :patient_name, :symptoms, :severity, :status, :source, :created_at)
        """,
        rows,
    )


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.postgres_url, pool_pre_ping=True)

    async with engine.begin() as conn:
        user_ids = await seed_public_users(conn)
        await seed_public_donors(conn, user_ids)
        await seed_public_sos(conn, user_ids)
        await seed_public_risk(conn, user_ids)
        await seed_public_notifications(conn, user_ids)

        hospital_ids = await seed_hospital_facilities(conn)
        department_ids = await seed_hospital_departments(conn, hospital_ids)
        await seed_hospital_staff(conn, hospital_ids, department_ids)
        await seed_hospital_beds(conn, hospital_ids)
        await seed_hospital_equipment(conn, hospital_ids)
        await seed_hospital_emergencies(conn, hospital_ids)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
