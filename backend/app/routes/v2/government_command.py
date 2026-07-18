from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from faker import Faker
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sqlalchemy import or_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.auth import require_roles
from app.core.config import get_settings
from app.core.dependencies import get_realtime_service
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.db.models import (
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
    GovUser,
    GovVerificationRequest,
)
from app.services.cache_store import CacheStore
from app.services.realtime_service import RealtimeService
from app.services.collections import USERS
from app.services.repository import MongoRepository

router = APIRouter(tags=["government-command"])

faker = Faker()

LIVE_MONITOR_WINDOW_MINUTES = 90
LIVE_MONITOR_MAX_WINDOW_MINUTES = 1440
LIVE_MONITOR_DEFAULT_LIMIT = 50
LIVE_MONITOR_MAX_LIMIT = 120
LIVE_MONITOR_MAX_ACTIVE = 800
LIVE_MONITOR_AUTO_RESOLVE_MINUTES = 240
RESOURCE_MAX_LIMIT = 500
DECISION_CACHE_TTL_SECONDS = 60
ANOMALY_CACHE_TTL_SECONDS = 120
DECISION_EMERGENCY_LIMIT = 300
ANOMALY_EMERGENCY_LIMIT = 500


def _uuid() -> str:
    return uuid4().hex


def _require_district(ctx: AuthContext) -> None:
    if (ctx.sub_role or "").lower() != "district_admin":
        raise HTTPException(status_code=403, detail="District authority required")


async def _log_audit(session: AsyncSession, action: str, actor_id: str, entity_type: str, entity_id: str, details: dict) -> None:
    session.add(
        GovAuditLog(
            id=_uuid(),
            action=action,
            actor_id=str(actor_id),
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            created_at=datetime.utcnow(),
        )
    )


async def _mark_entity_verified(session: AsyncSession, entity_type: str, entity_id: str) -> bool:
    entity_type = entity_type.lower()
    model_map = {
        "hospital": GovHospital,
        "ambulance": GovAmbulance,
    }
    model = model_map.get(entity_type)
    if entity_type in {"hospital", "ambulance"}:
        db = get_db()
        repo = MongoRepository(db, USERS)
        await repo.update_one({"_id": entity_id}, {"$set": {"isVerified": True}}, return_new=False)

    if not model:
        return False
    entity = await session.get(model, entity_id)
    if not entity:
        return False
    if hasattr(entity, "verified"):
        entity.verified = True
    if hasattr(entity, "updated_at"):
        entity.updated_at = datetime.utcnow()
    return True


async def _seed_core_data(session: AsyncSession, center_lat: float, center_lng: float) -> dict[str, int]:
    hospital_count = await session.scalar(select(func.count()).select_from(GovHospital))
    ambulance_count = await session.scalar(select(func.count()).select_from(GovAmbulance))
    user_count = await session.scalar(select(func.count()).select_from(GovUser))

    created = {"hospitals": 0, "ambulances": 0, "users": 0}

    if (hospital_count or 0) < 100:
        for _ in range(120):
            lat = center_lat + random.uniform(-0.6, 0.6)
            lng = center_lng + random.uniform(-0.6, 0.6)
            beds_total = random.randint(80, 240)
            beds_available = random.randint(8, max(12, int(beds_total * 0.45)))
            session.add(
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
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            created["hospitals"] += 1

    if (ambulance_count or 0) < 200:
        for idx in range(220):
            lat = center_lat + random.uniform(-0.5, 0.5)
            lng = center_lng + random.uniform(-0.5, 0.5)
            session.add(
                GovAmbulance(
                    id=_uuid(),
                    code=f"AMB-{1000 + idx}",
                    driver=faker.name(),
                    latitude=lat,
                    longitude=lng,
                    status=random.choice(["available", "assigned", "offline"]),
                    verified=random.choice([True, False]),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            created["ambulances"] += 1

    if (user_count or 0) < 1000:
        for _ in range(1100):
            lat = center_lat + random.uniform(-0.6, 0.6)
            lng = center_lng + random.uniform(-0.6, 0.6)
            session.add(
                GovUser(
                    id=_uuid(),
                    role=random.choice(["public", "hospital", "ambulance"]),
                    sub_role=None,
                    latitude=lat,
                    longitude=lng,
                    created_at=datetime.utcnow(),
                )
            )
            created["users"] += 1

    await session.commit()
    return created


async def _generate_emergencies(session: AsyncSession, count: int, center_lat: float, center_lng: float) -> list[GovEmergency]:
    existing_active = await session.scalar(
        select(func.count()).select_from(GovEmergency).where(GovEmergency.status == "active")
    )
    capacity = max(0, LIVE_MONITOR_MAX_ACTIVE - int(existing_active or 0))
    if capacity <= 0:
        return []
    count = min(count, capacity)

    emergencies: list[GovEmergency] = []
    for _ in range(count):
        lat = center_lat + random.uniform(-0.4, 0.4)
        lng = center_lng + random.uniform(-0.4, 0.4)
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
                occurred_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
            )
        )
    session.add_all(emergencies)
    await session.commit()
    return emergencies


async def _list_policy_actions(session: AsyncSession, status: str | None = None) -> list[GovPolicyAction]:
    stmt = select(GovPolicyAction)
    if status:
        stmt = stmt.where(GovPolicyAction.status == status)
    return (await session.scalars(stmt.order_by(GovPolicyAction.created_at.desc()))).all()


def _decision_payload(event: str, location: str, reason: str, confidence: float, action: str, impact: str, affected: list[str]) -> dict:
    return {
        "event": event,
        "location": location,
        "reason": reason,
        "confidence": confidence,
        "suggested_action": action,
        "impact": impact,
        "affected_entities": affected,
    }


def _phase_defaults(intensity: str) -> dict[str, int]:
    intensity = (intensity or "medium").lower()
    if intensity == "low":
        return {"count": 20, "duration": 15}
    if intensity == "high":
        return {"count": 60, "duration": 35}
    if intensity == "extreme":
        return {"count": 90, "duration": 50}
    return {"count": 40, "duration": 25}


def _after_action_recommendations(summary: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    if summary.get("critical", 0) > 10:
        recommendations.append("Increase critical care bed buffer by 15% in high-load zones")
    if summary.get("response_gap_minutes", 0) > 12:
        recommendations.append("Deploy rapid response teams to reduce response time")
    if summary.get("total", 0) > 80:
        recommendations.append("Activate reserve ambulance fleet and surge staffing")
    if not recommendations:
        recommendations.append("Maintain current readiness posture and continue monitoring")
    return recommendations


async def _compute_decisions(session: AsyncSession) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=20)
    emergencies = (
        await session.scalars(
            select(GovEmergency)
            .where(GovEmergency.occurred_at >= window_start)
            .order_by(GovEmergency.occurred_at.desc())
            .limit(DECISION_EMERGENCY_LIMIT)
        )
    ).all()

    decisions: list[dict[str, Any]] = []

    if len(emergencies) >= 15:
        decisions.append(_decision_payload(
            "Emergency Spike",
            "City Center",
            f"{len(emergencies)} incidents in 20 minutes",
            0.92,
            "Deploy 3 ambulances",
            "High",
            ["Ambulance Cluster 2"],
        ))

    hospitals = (await session.scalars(select(GovHospital))).all()
    overloaded = [h for h in hospitals if h.beds_total and (h.beds_available / max(1, h.beds_total)) < 0.15]
    if overloaded:
        decisions.append(_decision_payload(
            "Hospital Overload",
            overloaded[0].city or "Zone A",
            f"{len(overloaded)} hospitals above 85% load",
            0.88,
            "Reserve 20 beds and divert ambulances",
            "High",
            [h.name for h in overloaded[:3]],
        ))

    ambulances = (await session.scalars(select(GovAmbulance))).all()
    available = len([a for a in ambulances if a.status == "available"])
    if ambulances and (available / max(1, len(ambulances))) < 0.3:
        decisions.append(_decision_payload(
            "Ambulance Shortage",
            "Zone B",
            f"Only {available} of {len(ambulances)} ambulances available",
            0.86,
            "Activate reserve fleet",
            "Medium",
            ["Reserve Fleet"],
        ))

    if emergencies:
        coords = np.array([[e.latitude, e.longitude] for e in emergencies])
        if len(coords) > 200:
            idx = np.random.choice(len(coords), size=200, replace=False)
            coords = coords[idx]
        if len(coords) >= 3:
            kmeans = KMeans(n_clusters=min(3, len(coords)), n_init=5, random_state=42)
            labels = kmeans.fit_predict(coords)
            largest_cluster = np.argmax(np.bincount(labels))
            cluster_count = int(np.sum(labels == largest_cluster))
            if cluster_count >= 5:
                decisions.append(_decision_payload(
                    "Emergency Cluster",
                    "Zone Cluster",
                    f"Cluster of {cluster_count} incidents detected",
                    0.84,
                    "Deploy rapid response unit",
                    "Medium",
                    ["Rapid Response Unit"],
                ))

    return decisions


async def _search_entities(session: AsyncSession, query: str) -> dict[str, Any] | None:
    search = (query or "").strip()
    if not search:
        return None
    term = f"%{search}%"

    results: dict[str, Any] = {}

    if "hospital" in search.lower():
        hospitals = (
            await session.scalars(
                select(GovHospital).where(
                    or_(
                        GovHospital.name.ilike(term),
                        GovHospital.city.ilike(term),
                        GovHospital.state.ilike(term),
                    )
                ).limit(10)
            )
        ).all()
        results["hospitals"] = [
            {
                "id": item.id,
                "name": item.name,
                "city": item.city,
                "state": item.state,
                "beds_available": item.beds_available,
            }
            for item in hospitals
        ]

    if "ambulance" in search.lower():
        ambulances = (
            await session.scalars(
                select(GovAmbulance).where(
                    or_(
                        GovAmbulance.code.ilike(term),
                        GovAmbulance.driver.ilike(term),
                    )
                ).limit(10)
            )
        ).all()
        results["ambulances"] = [
            {
                "id": item.id,
                "code": item.code,
                "status": item.status,
                "verified": item.verified,
            }
            for item in ambulances
        ]

    if "emergency" in search.lower():
        emergencies = (
            await session.scalars(
                select(GovEmergency).where(
                    or_(
                        GovEmergency.emergency_type.ilike(term),
                        GovEmergency.severity.ilike(term),
                    )
                ).limit(10)
            )
        ).all()
        results["emergencies"] = [
            {
                "id": item.id,
                "type": item.emergency_type,
                "severity": item.severity,
                "status": item.status,
            }
            for item in emergencies
        ]

    if "disaster" in search.lower():
        disasters = (
            await session.scalars(
                select(GovDisasterEvent).where(
                    or_(
                        GovDisasterEvent.disaster_type.ilike(term),
                        GovDisasterEvent.zone.ilike(term),
                    )
                ).limit(10)
            )
        ).all()
        results["disasters"] = [
            {
                "id": item.id,
                "type": item.disaster_type,
                "zone": item.zone,
                "severity": item.severity,
            }
            for item in disasters
        ]

    if "policy" in search.lower():
        policies = (
            await session.scalars(
                select(GovPolicyAction).where(
                    or_(
                        GovPolicyAction.title.ilike(term),
                        GovPolicyAction.action.ilike(term),
                    )
                ).limit(10)
            )
        ).all()
        results["policies"] = [
            {
                "id": item.id,
                "title": item.title,
                "status": item.status,
                "impact": item.impact,
            }
            for item in policies
        ]

    knowledge = (
        await session.scalars(
            select(GovKnowledgeBase).where(
                or_(
                    GovKnowledgeBase.title.ilike(term),
                    GovKnowledgeBase.content.ilike(term),
                    GovKnowledgeBase.module.ilike(term),
                )
            ).limit(8)
        )
    ).all()
    if knowledge:
        results["knowledge"] = [
            {
                "id": item.id,
                "module": item.module,
                "title": item.title,
                "source": item.source,
            }
            for item in knowledge
        ]

    return results or None


async def _detect_anomalies(session: AsyncSession) -> dict[str, Any] | None:
    now = datetime.utcnow()
    start = now - timedelta(hours=24)
    emergencies = (
        await session.scalars(
            select(GovEmergency)
            .where(GovEmergency.occurred_at >= start)
            .order_by(GovEmergency.occurred_at.desc())
            .limit(ANOMALY_EMERGENCY_LIMIT)
        )
    ).all()
    if not emergencies:
        return None

    buckets: dict[str, int] = {}
    for event in emergencies:
        hour_key = event.occurred_at.replace(minute=0, second=0, microsecond=0).isoformat()
        buckets[hour_key] = buckets.get(hour_key, 0) + 1

    hours = sorted(buckets.keys())
    counts = [buckets[hour] for hour in hours]
    if len(counts) < 4:
        return None

    data = np.array([[count] for count in counts])
    model = IsolationForest(contamination=0.2, random_state=42)
    flags = model.fit_predict(data)
    anomalies = [hours[idx] for idx, flag in enumerate(flags) if flag == -1]
    return {
        "anomaly_hours": anomalies,
        "counts": {hours[idx]: counts[idx] for idx in range(len(hours))},
    }


@router.post("/command/seed")
async def seed_command_center(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_roles("government")),
):
    db = get_db()
    center_lat = float(payload.get("lat", 12.9716))
    center_lng = float(payload.get("lng", 77.5946))
    async with db() as session:
        created = await _seed_core_data(session, center_lat, center_lng)
        await _generate_emergencies(session, count=50, center_lat=center_lat, center_lng=center_lng)
    return {"status": "ok", "created": created}


@router.get("/command/overview")
async def command_overview(ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    async with db() as session:
        hospitals = await session.scalar(select(func.count()).select_from(GovHospital))
        ambulances = await session.scalar(select(func.count()).select_from(GovAmbulance))
        emergencies = await session.scalar(select(func.count()).select_from(GovEmergency))
    return {
        "hospitals": hospitals or 0,
        "ambulances": ambulances or 0,
        "emergencies": emergencies or 0,
    }


@router.post("/decision/engine")
async def decision_engine(ctx: AuthContext = Depends(require_roles("government"))):
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="gov")
    cached = cache.get("decision_engine")
    if cached:
        return cached

    db = get_db()
    async with db() as session:
        decisions = await _compute_decisions(session)
        stored = []
        for item in decisions:
            record = GovDecisionEvent(
                id=_uuid(),
                event=item["event"],
                location=item["location"],
                reason=item["reason"],
                confidence=item["confidence"],
                suggested_action=item["suggested_action"],
                impact=item["impact"],
                affected_entities={"items": item["affected_entities"]},
                created_at=datetime.utcnow(),
            )
            session.add(record)
            stored.append(record)
        await session.commit()
    payload = {"status": "ok", "decisions": decisions}
    cache.set("decision_engine", payload, ttl=DECISION_CACHE_TTL_SECONDS)
    return payload


@router.post("/disaster/detect")
async def detect_disaster(ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    async with db() as session:
        emergencies = (await session.scalars(select(GovEmergency).where(GovEmergency.status == "active"))).all()
        if len(emergencies) < 5:
            return {"status": "ok", "disaster": None}
        coords = np.array([[e.latitude, e.longitude] for e in emergencies])
        kmeans = KMeans(n_clusters=min(3, len(coords)), n_init=5, random_state=42)
        labels = kmeans.fit_predict(coords)
        largest = int(np.max(np.bincount(labels)))
        if largest < 6:
            return {"status": "ok", "disaster": None}

        centroid = coords.mean(axis=0)

        disaster = GovDisasterEvent(
            id=_uuid(),
            disaster_type="road_accident_cluster",
            status="active",
            zone="Zone A",
            severity="Critical",
            started_at=datetime.utcnow(),
            peak_at=None,
            resolved_at=None,
            timeline={"events": ["cluster_detected"]},
            meta={"cluster_size": largest, "lat": float(centroid[0]), "lng": float(centroid[1])},
            created_at=datetime.utcnow(),
        )
        session.add(disaster)
        await session.commit()
    return {"status": "ok", "disaster": {"id": disaster.id, "type": disaster.disaster_type, "severity": disaster.severity}}


@router.post("/disaster/trigger")
async def trigger_disaster(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    lat = payload.get("lat")
    lng = payload.get("lng")
    disaster = GovDisasterEvent(
        id=_uuid(),
        disaster_type=payload.get("type", "manual"),
        status="active",
        zone=payload.get("zone", "Zone A"),
        severity=payload.get("severity", "High"),
        started_at=datetime.utcnow(),
        peak_at=None,
        resolved_at=None,
        timeline={"events": ["manual_trigger"]},
        meta={"reason": payload.get("reason", "manual"), "lat": lat, "lng": lng},
        created_at=datetime.utcnow(),
    )
    async with db() as session:
        session.add(disaster)
        await session.commit()
    return {"status": "ok", "disaster_id": disaster.id}


@router.post("/disaster/broadcast")
async def broadcast_disaster(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    realtime: RealtimeService = get_realtime_service()
    await realtime.broadcast("government", {"type": "disaster", "payload": payload})
    return {"status": "ok"}


@router.get("/disaster/recent")
async def recent_disasters(ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    async with db() as session:
        items = (
            await session.scalars(
                select(GovDisasterEvent).order_by(GovDisasterEvent.started_at.desc()).limit(20)
            )
        ).all()
    return {
        "count": len(items),
        "data": [
            {
                "id": item.id,
                "disaster_type": item.disaster_type,
                "status": item.status,
                "zone": item.zone,
                "severity": item.severity,
                "lat": (item.meta or {}).get("lat"),
                "lng": (item.meta or {}).get("lng"),
                "started_at": item.started_at.isoformat(),
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            }
            for item in items
        ],
    }


@router.get("/resources/hospitals")
async def list_hospitals(
    ctx: AuthContext = Depends(require_roles("government")),
    limit: int | None = Query(None, ge=1),
    offset: int | None = Query(None, ge=0),
):
    db = get_db()
    async with db() as session:
        stmt = select(GovHospital)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(min(limit, RESOURCE_MAX_LIMIT))
        hospitals = (await session.scalars(stmt)).all()
    return {
        "count": len(hospitals),
        "data": [
            {
                "id": item.id,
                "name": item.name,
                "city": item.city,
                "state": item.state,
                "lat": item.latitude,
                "lng": item.longitude,
                "beds_total": item.beds_total,
                "beds_available": item.beds_available,
                "load_score": item.load_score,
                "verified": item.verified,
            }
            for item in hospitals
        ],
    }


@router.get("/resources/ambulances")
async def list_ambulances(
    ctx: AuthContext = Depends(require_roles("government")),
    limit: int | None = Query(None, ge=1),
    offset: int | None = Query(None, ge=0),
):
    db = get_db()
    async with db() as session:
        stmt = select(GovAmbulance)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(min(limit, RESOURCE_MAX_LIMIT))
        ambulances = (await session.scalars(stmt)).all()
    return {
        "count": len(ambulances),
        "data": [
            {
                "id": item.id,
                "code": item.code,
                "lat": item.latitude,
                "lng": item.longitude,
                "status": item.status,
                "verified": item.verified,
            }
            for item in ambulances
        ],
    }


@router.get("/monitoring/summary")
async def monitoring_summary(ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    async with db() as session:
        resolve_before = datetime.utcnow() - timedelta(minutes=LIVE_MONITOR_AUTO_RESOLVE_MINUTES)
        await session.execute(
            update(GovEmergency)
            .where(GovEmergency.status == "active", GovEmergency.occurred_at < resolve_before)
            .values(status="resolved")
        )
        await session.commit()
        window_start = datetime.utcnow() - timedelta(minutes=LIVE_MONITOR_WINDOW_MINUTES)
        emergencies = await session.scalar(
            select(func.count()).select_from(GovEmergency).where(
                GovEmergency.status == "active",
                GovEmergency.occurred_at >= window_start,
            )
        )
        hospitals = (await session.scalars(select(GovHospital))).all()
        ambulances = (await session.scalars(select(GovAmbulance))).all()

    active_emergencies = emergencies or 0
    avg_response = 11
    utilization = round(sum(h.load_score for h in hospitals) / max(1, len(hospitals)) * 100, 1) if hospitals else 0
    return {
        "active_emergencies": active_emergencies,
        "avg_response_minutes": avg_response,
        "resource_utilization": utilization,
        "ambulances": {
            "total": len(ambulances),
            "available": len([a for a in ambulances if a.status == "available"]),
        },
    }


@router.get("/monitoring/feed")
async def monitoring_feed(
    limit: int | None = Query(None, ge=1),
    window_minutes: int | None = Query(None, ge=5),
    ctx: AuthContext = Depends(require_roles("government")),
):
    resolved_limit = min(limit or LIVE_MONITOR_DEFAULT_LIMIT, LIVE_MONITOR_MAX_LIMIT)
    resolved_window = min(window_minutes or LIVE_MONITOR_WINDOW_MINUTES, LIVE_MONITOR_MAX_WINDOW_MINUTES)
    window_start = datetime.utcnow() - timedelta(minutes=resolved_window)
    db = get_db()
    async with db() as session:
        resolve_before = datetime.utcnow() - timedelta(minutes=LIVE_MONITOR_AUTO_RESOLVE_MINUTES)
        await session.execute(
            update(GovEmergency)
            .where(GovEmergency.status == "active", GovEmergency.occurred_at < resolve_before)
            .values(status="resolved")
        )
        await session.commit()
        emergencies = (
            await session.scalars(
                select(GovEmergency)
                .where(
                    GovEmergency.status == "active",
                    GovEmergency.occurred_at >= window_start,
                )
                .order_by(GovEmergency.occurred_at.desc())
                .limit(resolved_limit)
            )
        ).all()
    return {
        "count": len(emergencies),
        "data": [
            {
                "id": e.id,
                "type": e.emergency_type,
                "severity": e.severity,
                "lat": e.latitude,
                "lng": e.longitude,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in emergencies
        ],
    }


@router.post("/verification/submit")
async def submit_verification(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    entity_type = payload.get("entity_type")
    entity_id = payload.get("entity_id")
    if not entity_type or not entity_id:
        raise HTTPException(status_code=400, detail="entity_type and entity_id required")
    db = get_db()
    req = GovVerificationRequest(
        id=_uuid(),
        entity_type=entity_type,
        entity_id=entity_id,
        status="pending",
        notes=payload.get("notes"),
        requested_by=ctx.user_id,
        reviewed_by=None,
        reviewed_at=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    async with db() as session:
        session.add(req)
        await _log_audit(session, "verification_submitted", ctx.user_id, entity_type, entity_id, {"notes": payload.get("notes")})
        await session.commit()
    return {"status": "ok", "request_id": req.id}


@router.get("/verification/pending")
async def pending_verification(ctx: AuthContext = Depends(require_roles("government"))):
    _require_district(ctx)
    db = get_db()
    async with db() as session:
        requests = (await session.scalars(select(GovVerificationRequest).where(GovVerificationRequest.status == "pending"))).all()
    return {
        "count": len(requests),
        "data": [
            {
                "id": r.id,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "notes": r.notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in requests
        ],
    }


@router.post("/verification/{request_id}/approve")
async def approve_verification(request_id: str, ctx: AuthContext = Depends(require_roles("government"))):
    _require_district(ctx)
    db = get_db()
    async with db() as session:
        req = await session.get(GovVerificationRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        req.status = "approved"
        req.reviewed_by = ctx.user_id
        req.reviewed_at = datetime.utcnow()
        req.updated_at = datetime.utcnow()
        await _mark_entity_verified(session, req.entity_type, req.entity_id)
        await _log_audit(session, "verification_approved", ctx.user_id, req.entity_type, req.entity_id, {})
        await session.commit()
    return {"status": "approved"}


@router.post("/verification/{request_id}/reject")
async def reject_verification(request_id: str, payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    _require_district(ctx)
    db = get_db()
    async with db() as session:
        req = await session.get(GovVerificationRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        req.status = "rejected"
        req.notes = payload.get("notes")
        req.reviewed_by = ctx.user_id
        req.reviewed_at = datetime.utcnow()
        req.updated_at = datetime.utcnow()
        await _log_audit(session, "verification_rejected", ctx.user_id, req.entity_type, req.entity_id, {"notes": req.notes})
        await session.commit()
    return {"status": "rejected"}


@router.post("/simulation/start")
async def start_simulation(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    session = GovSimulationSession(
        id=_uuid(),
        status="running",
        intensity=payload.get("intensity", "medium"),
        started_at=datetime.utcnow(),
        ended_at=None,
        meta={"note": payload.get("note")},
    )
    async with db() as session_db:
        session_db.add(session)
        await session_db.commit()
    return {"status": "running", "session_id": session.id}


@router.post("/simulation/run")
async def run_simulation(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    count = int(payload.get("count", 60))
    center_lat = float(payload.get("lat", 12.9716))
    center_lng = float(payload.get("lng", 77.5946))
    task = celery_app.send_task(
        "government.simulate",
        kwargs={"count": count, "center_lat": center_lat, "center_lng": center_lng},
    )
    return {"status": "queued", "task_id": task.id}


@router.post("/simulation/step")
async def simulation_step(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    count = int(payload.get("count", 25))
    center_lat = float(payload.get("lat", 12.9716))
    center_lng = float(payload.get("lng", 77.5946))
    db = get_db()
    async with db() as session:
        await _generate_emergencies(session, count=count, center_lat=center_lat, center_lng=center_lng)
    return {"status": "ok", "generated": count}


@router.post("/simulation/multi-phase")
async def simulation_multi_phase(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    phases = payload.get("phases") or []
    if not phases:
        raise HTTPException(status_code=400, detail="phases required")

    center_lat = float(payload.get("lat", 12.9716))
    center_lng = float(payload.get("lng", 77.5946))
    session_id = payload.get("session_id")
    auto_close = bool(payload.get("auto_close"))

    db = get_db()
    async with db() as session:
        sim = await session.get(GovSimulationSession, session_id) if session_id else None
        if not sim:
            sim = GovSimulationSession(
                id=_uuid(),
                status="running",
                intensity=payload.get("intensity", "medium"),
                started_at=datetime.utcnow(),
                ended_at=None,
                meta={"note": payload.get("note"), "phases": []},
            )
            session.add(sim)
            await session.commit()

        results: list[dict[str, Any]] = []
        for idx, phase in enumerate(phases):
            name = phase.get("name") or f"Phase {idx + 1}"
            intensity = (phase.get("intensity") or sim.intensity or "medium").lower()
            defaults = _phase_defaults(intensity)
            count = int(phase.get("count", defaults["count"]))
            duration = int(phase.get("duration", defaults["duration"]))
            await _generate_emergencies(session, count=count, center_lat=center_lat, center_lng=center_lng)
            results.append({
                "name": name,
                "intensity": intensity,
                "count": count,
                "duration_minutes": duration,
            })

        meta = dict(sim.meta or {})
        meta["phases"] = phases
        meta["phase_results"] = results
        sim.meta = meta
        if auto_close:
            sim.status = "completed"
            sim.ended_at = datetime.utcnow()
        await session.commit()

    return {"status": "ok", "session_id": sim.id, "results": results}


@router.post("/simulation/stop/{session_id}")
async def stop_simulation(session_id: str, ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    async with db() as session:
        sim = await session.get(GovSimulationSession, session_id)
        if not sim:
            raise HTTPException(status_code=404, detail="Simulation not found")
        sim.status = "stopped"
        sim.ended_at = datetime.utcnow()
        await session.commit()
    return {"status": "stopped", "session_id": session_id}


@router.post("/simulation/after-action/{session_id}")
async def after_action_report(session_id: str, ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    async with db() as session:
        sim = await session.get(GovSimulationSession, session_id)
        if not sim:
            raise HTTPException(status_code=404, detail="Simulation not found")

        end_time = sim.ended_at or datetime.utcnow()
        start_time = sim.started_at or (end_time - timedelta(hours=1))
        emergencies = (
            await session.scalars(
                select(GovEmergency)
                .where(GovEmergency.occurred_at >= start_time)
                .where(GovEmergency.occurred_at <= end_time)
            )
        ).all()

        severity_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for event in emergencies:
            severity_counts[event.severity] = severity_counts.get(event.severity, 0) + 1
            type_counts[event.emergency_type] = type_counts.get(event.emergency_type, 0) + 1

        total = len(emergencies)
        summary = {
            "total": total,
            "critical": severity_counts.get("Critical", 0),
            "high": severity_counts.get("High", 0),
            "medium": severity_counts.get("Medium", 0),
            "low": severity_counts.get("Low", 0),
            "response_gap_minutes": 12 if total > 0 else 0,
        }
        report = {
            "window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "summary": summary,
            "severity_breakdown": severity_counts,
            "type_breakdown": type_counts,
            "recommendations": _after_action_recommendations(summary),
        }

        meta = dict(sim.meta or {})
        meta["after_action_report"] = report
        meta["report_generated_at"] = datetime.utcnow().isoformat()
        sim.meta = meta
        sim.status = "recovery"
        sim.ended_at = end_time
        await session.commit()

    return {"status": "ok", "report": report}


@router.post("/cache/precompute")
async def precompute_metrics(ctx: AuthContext = Depends(require_roles("government"))):
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="gov")
    db = get_db()
    async with db() as session:
        hospitals = (await session.scalars(select(GovHospital))).all()
        emergencies = (await session.scalars(select(GovEmergency))).all()
    load = round(sum(h.load_score for h in hospitals) / max(1, len(hospitals)), 3) if hospitals else 0
    zone_risk = round(len(emergencies) / max(1, len(hospitals)), 3)
    avg_eta = 12 if emergencies else 8
    cache.set("hospital_load", {"value": load}, ttl=300)
    cache.set("zone_risk", {"value": zone_risk}, ttl=300)
    cache.set("avg_eta", {"value": avg_eta}, ttl=300)
    return {"status": "ok", "hospital_load": load, "zone_risk": zone_risk, "avg_eta": avg_eta}


@router.post("/ai/ask")
async def eva_assistant(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    query = payload.get("query", "")
    execute = bool(payload.get("execute"))
    db = get_db()
    async with db() as session:
        search_results = await _search_entities(session, query)
        if search_results:
            return {"query": query, "results": search_results, "executed": False}
        decisions = await _compute_decisions(session)
    suggestion = decisions[0] if decisions else _decision_payload(
        "System Check",
        "All Zones",
        "No anomalies detected",
        0.65,
        "Continue monitoring",
        "Low",
        ["System"],
    )
    if execute:
        async with db() as session:
            session.add(
                GovDecisionEvent(
                    id=_uuid(),
                    event=suggestion["event"],
                    location=suggestion["location"],
                    reason=suggestion["reason"],
                    confidence=suggestion["confidence"],
                    suggested_action=suggestion["suggested_action"],
                    impact=suggestion["impact"],
                    affected_entities={"items": suggestion["affected_entities"]},
                    created_at=datetime.utcnow(),
                )
            )
            await session.commit()
    return {"query": query, "decision": suggestion, "executed": execute}


@router.get("/predictions/anomaly")
async def anomaly_prediction(ctx: AuthContext = Depends(require_roles("government"))):
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="gov")
    cached = cache.get("anomaly_prediction")
    if cached:
        return cached

    db = get_db()
    async with db() as session:
        result = await _detect_anomalies(session)
        if not result:
            payload = {"status": "ok", "prediction": None}
            cache.set("anomaly_prediction", payload, ttl=ANOMALY_CACHE_TTL_SECONDS)
            return payload
        prediction = GovPrediction(
            id=_uuid(),
            prediction_type="emergency_anomaly",
            result=result,
            confidence=0.82,
            created_at=datetime.utcnow(),
        )
        session.add(prediction)
        await session.commit()
    payload = {"status": "ok", "prediction": result}
    cache.set("anomaly_prediction", payload, ttl=ANOMALY_CACHE_TTL_SECONDS)
    return payload


@router.get("/policy/actions")
async def list_policy_actions(
    status: str | None = None,
    limit: int | None = Query(None, ge=1),
    offset: int | None = Query(None, ge=0),
    ctx: AuthContext = Depends(require_roles("government")),
):
    db = get_db()
    async with db() as session:
        actions = await _list_policy_actions(session, status=status)
        if offset:
            actions = actions[offset:]
        if limit:
            actions = actions[:min(limit, RESOURCE_MAX_LIMIT)]
    return {
        "count": len(actions),
        "data": [
            {
                "id": item.id,
                "title": item.title,
                "action": item.action,
                "status": item.status,
                "impact": item.impact,
                "decision_event_id": item.decision_event_id,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in actions
        ],
    }


@router.post("/policy/actions")
async def create_policy_action(payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    title = payload.get("title")
    action = payload.get("action")
    if not title or not action:
        raise HTTPException(status_code=400, detail="title and action required")
    record = GovPolicyAction(
        id=_uuid(),
        title=title,
        action=action,
        status=payload.get("status", "Draft"),
        impact=payload.get("impact"),
        decision_event_id=payload.get("decision_event_id"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db = get_db()
    async with db() as session:
        session.add(record)
        await _log_audit(session, "policy_action_created", ctx.user_id, "policy_action", record.id, {"title": title})
        await session.commit()
    return {
        "id": record.id,
        "title": record.title,
        "action": record.action,
        "status": record.status,
        "impact": record.impact,
        "decision_event_id": record.decision_event_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


@router.patch("/policy/actions/{action_id}")
async def update_policy_action(action_id: str, payload: dict = Body(default_factory=dict), ctx: AuthContext = Depends(require_roles("government"))):
    db = get_db()
    async with db() as session:
        record = await session.get(GovPolicyAction, action_id)
        if not record:
            raise HTTPException(status_code=404, detail="Policy action not found")
        if "title" in payload:
            record.title = payload.get("title")
        if "action" in payload:
            record.action = payload.get("action")
        if "status" in payload:
            record.status = payload.get("status")
        if "impact" in payload:
            record.impact = payload.get("impact")
        record.updated_at = datetime.utcnow()
        await _log_audit(session, "policy_action_updated", ctx.user_id, "policy_action", record.id, payload)
        await session.commit()
    return {
        "id": record.id,
        "title": record.title,
        "action": record.action,
        "status": record.status,
        "impact": record.impact,
        "decision_event_id": record.decision_event_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
