import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from uuid import uuid4

from faker import Faker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from app.core.config import get_settings  # noqa: E402
from app.db.models import (  # noqa: E402
    Document,
    GovAmbulance,
    GovAuditLog,
    GovDecisionEvent,
    GovDisasterEvent,
    GovEmergency,
    GovHospital,
    GovKnowledgeBase,
    GovPolicyAction,
    GovPrediction,
    GovSimulationSession,
    GovVerificationRequest,
)
from app.services import collections as c  # noqa: E402
from app.services.rag.vector_store import reset_index, upsert_documents  # noqa: E402

faker = Faker("en_US")

COUNT_PER_TABLE = 2000
BATCH_SIZE = 250

CENTER_LAT = 12.9716
CENTER_LNG = 77.5946

MODULES = [
    "command-center",
    "live-monitoring",
    "disaster-management",
    "policy-workflow",
    "verification-center",
    "simulation-recovery",
    "ai-ml-lab",
    "eva-assistant",
]


def _uuid() -> str:
    return uuid4().hex


def _ascii(text: str) -> str:
    return (text or "").encode("ascii", "ignore").decode("ascii")


def _coords(scale: float = 0.6) -> tuple[float, float]:
    return (
        CENTER_LAT + random.uniform(-scale, scale),
        CENTER_LNG + random.uniform(-scale, scale),
    )


def _doc(collection: str, payload: dict, created_at: datetime) -> Document:
    return Document(
        id=_uuid(),
        collection=collection,
        data=payload,
        created_at=created_at,
        updated_at=created_at,
    )


def _base_payload() -> dict:
    return {
        "title": _ascii(faker.catch_phrase()),
        "status": random.choice(["active", "pending", "completed", "resolved"]),
        "summary": _ascii(faker.sentence(nb_words=10)),
        "createdAt": datetime.utcnow().isoformat(),
    }


def _hospital_payload() -> dict:
    return {
        "name": _ascii(f"{faker.company()} Hospital"),
        "location": {
            "city": _ascii(faker.city()),
            "state": _ascii(faker.state()),
            "address": _ascii(faker.street_address()),
        },
        "beds": {
            "totalBeds": random.randint(80, 260),
            "availableBeds": random.randint(10, 140),
        },
        "rating": round(random.uniform(3.4, 4.9), 1),
        "createdAt": datetime.utcnow().isoformat(),
    }


def _ambulance_payload() -> dict:
    lat, lng = _coords(0.8)
    return {
        "ambulanceId": f"AMB-{random.randint(1000, 9999)}",
        "currentLocation": {"latitude": lat, "longitude": lng},
        "status": random.choice(["available", "busy", "offline"]),
        "createdAt": datetime.utcnow().isoformat(),
    }


def _alert_payload() -> dict:
    return {
        "message": _ascii(faker.sentence(nb_words=8)),
        "severity": random.choice(["Low", "Medium", "High", "Critical"]),
        "status": random.choice(["pending", "dispatched", "resolved"]),
        "locationDetails": _ascii(faker.city()),
        "createdAt": datetime.utcnow().isoformat(),
    }


def _donation_payload() -> dict:
    return {
        "donorName": _ascii(faker.name()),
        "bloodGroup": random.choice(["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]),
        "city": _ascii(faker.city()),
        "status": random.choice(["available", "pending", "on_hold"]),
        "createdAt": datetime.utcnow().isoformat(),
    }


def _emergency_payload() -> dict:
    return {
        "type": random.choice(["accident", "cardiac", "trauma", "fire"]),
        "severity": random.choice(["Low", "Medium", "High", "Critical"]),
        "status": "active",
        "createdAt": datetime.utcnow().isoformat(),
    }


def _compliance_payload() -> dict:
    return {
        "hospitalId": f"HOSP-{random.randint(1000, 9999)}",
        "status": random.choice(["Open", "Resolved", "Pending"]),
        "findings": _ascii(faker.sentence(nb_words=6)),
        "owner": _ascii(faker.name()),
        "createdAt": datetime.utcnow().isoformat(),
    }


def _report_payload(scope: str) -> dict:
    return {
        "title": _ascii(faker.catch_phrase()),
        "scope": scope,
        "summary": _ascii(faker.sentence(nb_words=10)),
        "status": "Ready",
        "createdAt": datetime.utcnow().isoformat(),
    }


def _hospital_message_payload() -> dict:
    return {
        "hospitalId": f"HOSP-{random.randint(1000, 9999)}",
        "message": _ascii(faker.sentence(nb_words=12)),
        "status": random.choice(["pending", "resolved", "assigned"]),
        "createdAt": datetime.utcnow().isoformat(),
    }


def _knowledge_payload(module: str) -> dict:
    return {
        "content": _ascii(faker.paragraph(nb_sentences=4)),
        "metadata": {
            "source": "module_knowledge",
            "module": module,
            "title": _ascii(faker.catch_phrase()),
            "roles": ["government"],
            "tags": ["policy", "operations", module],
        },
        "createdAt": datetime.utcnow().isoformat(),
    }


def _generic_payload(module: str) -> dict:
    payload = _base_payload()
    payload["module"] = module
    return payload


GENERATOR_OVERRIDES = {
    c.HOSPITALS: _hospital_payload,
    c.AMBULANCES: _ambulance_payload,
    c.ALERTS: _alert_payload,
    c.DONATIONS: _donation_payload,
    c.EMERGENCY_EVENTS: _emergency_payload,
    c.GOVERNMENT_COMPLIANCE: _compliance_payload,
    c.GOVERNMENT_REPORTS: lambda: _report_payload("National"),
    c.HOSPITAL_REPORTS: lambda: _report_payload("Hospital"),
    c.HOSPITAL_MESSAGES: _hospital_message_payload,
    c.VECTOR_STORE: lambda: _knowledge_payload(random.choice(MODULES)),
}


async def _bulk_insert(session, rows, batch_size=BATCH_SIZE):
    for idx in range(0, len(rows), batch_size):
        session.add_all(rows[idx : idx + batch_size])
        await session.commit()
        session.expunge_all()


async def _ensure_gov_knowledge_table(session) -> None:
    await session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS gov_knowledge_base (
                id VARCHAR(40) PRIMARY KEY,
                module VARCHAR(120),
                title VARCHAR(240),
                content TEXT,
                tags JSONB NOT NULL,
                source VARCHAR(120),
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )
    )
    await session.execute(
        text("CREATE INDEX IF NOT EXISTS ix_gov_knowledge_base_module ON gov_knowledge_base (module)")
    )
    await session.execute(
        text("CREATE INDEX IF NOT EXISTS ix_gov_knowledge_base_title ON gov_knowledge_base (title)")
    )
    await session.commit()


async def _seed_documents(session, collection: str):
    docs: list[Document] = []
    for _ in range(COUNT_PER_TABLE):
        created_at = datetime.utcnow() - timedelta(days=random.randint(0, 365))
        generator = GENERATOR_OVERRIDES.get(collection)
        if generator:
            payload = generator()
        else:
            payload = _generic_payload(collection)
            payload["details"] = _ascii(faker.sentence(nb_words=8))
        docs.append(_doc(collection, payload, created_at))

        if len(docs) >= BATCH_SIZE:
            await _bulk_insert(session, docs)
            docs = []
    if docs:
        await _bulk_insert(session, docs)


async def _seed_pg_tables(session):
    now = datetime.utcnow()

    hospitals = []
    for _ in range(COUNT_PER_TABLE):
        lat, lng = _coords(0.8)
        beds_total = random.randint(80, 260)
        beds_available = random.randint(10, max(12, int(beds_total * 0.5)))
        hospitals.append(
            GovHospital(
                id=_uuid(),
                name=_ascii(f"{faker.city()} Medical Center"),
                city=_ascii(faker.city()),
                state=_ascii(faker.state()),
                latitude=lat,
                longitude=lng,
                status="active",
                verified=random.choice([True, False]),
                beds_total=beds_total,
                beds_available=beds_available,
                load_score=round(1 - (beds_available / max(1, beds_total)), 2),
                rating=round(random.uniform(3.5, 4.9), 1),
                created_at=now,
                updated_at=now,
            )
        )
    await _bulk_insert(session, hospitals)

    ambulances = []
    for idx in range(COUNT_PER_TABLE):
        lat, lng = _coords(0.7)
        ambulances.append(
            GovAmbulance(
                id=_uuid(),
                code=f"AMB-{5000 + idx}",
                driver=_ascii(faker.name()),
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
    for _ in range(COUNT_PER_TABLE):
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

    disasters = []
    for _ in range(COUNT_PER_TABLE):
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
                meta={"lat": lat, "lng": lng, "impact": _ascii(faker.word())},
                created_at=now,
            )
        )
    await _bulk_insert(session, disasters)

    decisions = []
    for _ in range(COUNT_PER_TABLE):
        decisions.append(
            GovDecisionEvent(
                id=_uuid(),
                event="Resource Shift",
                location=f"Zone {random.choice(['A', 'B', 'C'])}",
                reason=_ascii(faker.sentence(nb_words=8)),
                confidence=round(random.uniform(0.6, 0.95), 2),
                suggested_action=_ascii(faker.sentence(nb_words=6)),
                impact=random.choice(["Low", "Medium", "High"]),
                affected_entities={"items": [_ascii(faker.word()) for _ in range(3)]},
                created_at=now,
            )
        )
    await _bulk_insert(session, decisions)

    predictions = []
    for _ in range(COUNT_PER_TABLE):
        predictions.append(
            GovPrediction(
                id=_uuid(),
                prediction_type=random.choice(["emergency_anomaly", "capacity", "surge"]),
                result={"score": round(random.random(), 3)},
                confidence=round(random.uniform(0.6, 0.95), 2),
                created_at=now,
            )
        )
    await _bulk_insert(session, predictions)

    policies = []
    for _ in range(COUNT_PER_TABLE):
        policies.append(
            GovPolicyAction(
                id=_uuid(),
                title=_ascii(faker.catch_phrase()),
                action=_ascii(faker.sentence(nb_words=7)),
                status=random.choice(["Draft", "In Review", "Approved"]),
                impact=random.choice(["Low", "Medium", "High"]),
                decision_event_id=None,
                created_at=now,
                updated_at=now,
            )
        )
    await _bulk_insert(session, policies)

    verifications = []
    for _ in range(COUNT_PER_TABLE):
        verifications.append(
            GovVerificationRequest(
                id=_uuid(),
                entity_type=random.choice(["hospital", "ambulance"]),
                entity_id=_uuid(),
                status=random.choice(["pending", "approved", "rejected"]),
                notes=_ascii(faker.sentence(nb_words=6)),
                requested_by=_uuid(),
                reviewed_by=_uuid(),
                reviewed_at=now,
                created_at=now,
                updated_at=now,
            )
        )
    await _bulk_insert(session, verifications)

    audits = []
    for _ in range(COUNT_PER_TABLE):
        audits.append(
            GovAuditLog(
                id=_uuid(),
                action=random.choice(["verification_approved", "policy_updated", "disaster_triggered"]),
                actor_id=_uuid(),
                entity_type=random.choice(["hospital", "ambulance", "policy_action"]),
                entity_id=_uuid(),
                details={"note": _ascii(faker.word())},
                created_at=now,
            )
        )
    await _bulk_insert(session, audits)

    simulations = []
    for _ in range(COUNT_PER_TABLE):
        simulations.append(
            GovSimulationSession(
                id=_uuid(),
                status=random.choice(["completed", "stopped", "recovery"]),
                intensity=random.choice(["low", "medium", "high"]),
                started_at=now - timedelta(hours=random.randint(1, 72)),
                ended_at=now,
                meta={"note": _ascii(faker.sentence(nb_words=6))},
            )
        )
    await _bulk_insert(session, simulations)

    knowledge_rows = []
    for idx in range(COUNT_PER_TABLE):
        module = MODULES[idx % len(MODULES)]
        knowledge_rows.append(
            GovKnowledgeBase(
                id=_uuid(),
                module=module,
                title=_ascii(faker.catch_phrase()),
                content=_ascii(faker.paragraph(nb_sentences=4)),
                tags=["policy", "operations", module],
                source="seed",
                created_at=now,
                updated_at=now,
            )
        )
    await _bulk_insert(session, knowledge_rows)


async def seed_all():
    settings = get_settings()
    engine = create_async_engine(settings.postgres_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await _ensure_gov_knowledge_table(session)
        await _seed_pg_tables(session)

        collection_names = [
            getattr(c, name)
            for name in dir(c)
            if name.isupper() and isinstance(getattr(c, name), str)
        ]
        for collection in collection_names:
            if collection == c.USERS:
                continue
            await _seed_documents(session, collection)

    knowledge_docs = []
    for idx in range(COUNT_PER_TABLE):
        module = MODULES[idx % len(MODULES)]
        knowledge_docs.append(
            {
                "content": _ascii(faker.paragraph(nb_sentences=4)),
                "metadata": {
                    "source": "module_knowledge",
                    "module": module,
                    "title": _ascii(faker.catch_phrase()),
                    "roles": ["government"],
                    "tags": ["policy", "operations", module],
                },
            }
        )

    try:
        reset_index()
        for idx in range(0, len(knowledge_docs), 200):
            batch = knowledge_docs[idx : idx + 200]
            upsert_documents(batch)
    except Exception:
        pass

    await engine.dispose()
    print("Seed complete: 2000 entries per table and collection (excluding users).")


if __name__ == "__main__":
    asyncio.run(seed_all())
