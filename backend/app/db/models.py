from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    collection: Mapped[str] = mapped_column(String(120), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AiChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    module: Mapped[str | None] = mapped_column(String(80))
    mode: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AiChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(40), ForeignKey("ai_chat_sessions.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovHospital(Base):
    __tablename__ = "gov_hospitals"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active")
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    beds_total: Mapped[int] = mapped_column(Integer, default=0)
    beds_available: Mapped[int] = mapped_column(Integer, default=0)
    load_score: Mapped[float] = mapped_column(Float, default=0.0)
    rating: Mapped[float] = mapped_column(Float, default=4.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovAmbulance(Base):
    __tablename__ = "gov_ambulances"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    code: Mapped[str] = mapped_column(String(60), index=True)
    driver: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    status: Mapped[str] = mapped_column(String(40), default="available", index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovEmergency(Base):
    __tablename__ = "gov_emergencies"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    emergency_type: Mapped[str] = mapped_column(String(120), index=True)
    severity: Mapped[str] = mapped_column(String(40), index=True)
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    hospital_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("gov_hospitals.id"))
    ambulance_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("gov_ambulances.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovUser(Base):
    __tablename__ = "gov_users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    role: Mapped[str] = mapped_column(String(40), index=True)
    sub_role: Mapped[str | None] = mapped_column(String(60), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovPrediction(Base):
    __tablename__ = "gov_predictions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    prediction_type: Mapped[str] = mapped_column(String(80), index=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovVerificationRequest(Base):
    __tablename__ = "gov_verification_requests"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(40))
    reviewed_by: Mapped[str | None] = mapped_column(String(40))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovAuditLog(Base):
    __tablename__ = "gov_audit_logs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    actor_id: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(40), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovDisasterEvent(Base):
    __tablename__ = "gov_disaster_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    disaster_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    zone: Mapped[str | None] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(40), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    peak_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timeline: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovDecisionEvent(Base):
    __tablename__ = "gov_decision_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event: Mapped[str] = mapped_column(String(120), index=True)
    location: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    suggested_action: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(String(40))
    affected_entities: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovPolicyAction(Base):
    __tablename__ = "gov_policy_actions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), index=True)
    impact: Mapped[str | None] = mapped_column(String(40))
    decision_event_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GovSimulationSession(Base):
    __tablename__ = "gov_simulation_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    intensity: Mapped[str] = mapped_column(String(40), default="medium")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)


class GovKnowledgeBase(Base):
    __tablename__ = "gov_knowledge_base"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    module: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CoreHospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    location: Mapped[str] = mapped_column(String(240), index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    occupancy: Mapped[int] = mapped_column(Integer, default=0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CoreAmbulance(Base):
    __tablename__ = "ambulances"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    driver: Mapped[str | None] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(240), index=True)
    status: Mapped[str] = mapped_column(String(40), default="available", index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class CoreUser(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    role: Mapped[str] = mapped_column(String(40), index=True)
    location: Mapped[str | None] = mapped_column(String(240), index=True)


class CoreEmergency(Base):
    __tablename__ = "emergencies"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    emergency_type: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(40), index=True)
    location: Mapped[str] = mapped_column(String(240), index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    occurred_at: Mapped[datetime] = mapped_column("timestamp", DateTime(timezone=True), index=True)
    assigned_hospital: Mapped[str | None] = mapped_column(String(40))


class CorePrediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    prediction_type: Mapped[str] = mapped_column(String(80), index=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CoreAuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    actor: Mapped[str] = mapped_column(String(120), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    hash: Mapped[str] = mapped_column(String(128))
    prev_hash: Mapped[str | None] = mapped_column(String(128))
