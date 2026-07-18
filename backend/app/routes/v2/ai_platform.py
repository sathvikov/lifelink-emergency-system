from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from bson import ObjectId
from pydantic import BaseModel

from app.core.auth import require_scopes
from app.core.config import get_settings
from app.core.rbac import AuthContext
from app.db.mongo import get_db
from app.services.ai_platform import (
    EventStream,
    FeatureStore,
    ModelRegistry,
    ObservabilityService,
    RetrievalIndex,
    SyntheticDataService,
    redact_payload,
    scan_payload,
)
from app.services.ai_platform.insight_catalog import build_insights
from app.services.cache_store import CacheStore
from app.services.collections import (
    AI_EVENTS,
    ALERTS,
    AMBULANCES,
    AMBULANCE_ASSIGNMENTS,
    AUDIT_LOGS,
    BILLING_INVOICES,
    DONATIONS,
    EQUIPMENT_INVENTORY,
    FAMILY_MEMBERS,
    FINANCE_EXPENSES,
    GOVERNMENT_COMPLIANCE,
    GOVERNMENT_REPORTS,
    HOSPITAL_REPORTS,
    HEALTH_RECORDS,
    HOSPITALS,
    HOSPITAL_DEPARTMENTS,
    HOSPITAL_MESSAGES,
    HOSPITAL_STAFF,
    ICU_ALERTS,
    ICU_PATIENTS,
    INSURANCE_CLAIMS,
    OPD_APPOINTMENTS,
    OPD_CONSULTATIONS,
    OPD_DOCTORS,
    OPD_QUEUE,
    OT_ALLOCATIONS,
    OT_SURGERIES,
    PATIENTS,
    PREDICTIONS,
    RADIOLOGY_REPORTS,
    RADIOLOGY_REQUESTS,
    RESOURCE_REQUESTS,
    RESOURCES,
    USERS,
    VECTOR_STORE,
    BED_ALLOCATIONS,
    ANALYTICS_EVENTS,
    DEPARTMENT_LOGS,
    EMERGENCY_EVENTS,
    HOSPITAL_BENCHMARKS,
    HOSPITAL_NETWORK_AGREEMENTS,
    VENDOR_LEAD_TIMES,
)
from app.services.repository import MongoRepository
from app.core.celery_app import celery_app
from app.services.prediction_store import get_latest_prediction
from app.core.dependencies import get_realtime_service
from app.services.rag.vector_store import reset_index as reset_retrieval_index

router = APIRouter(tags=["ai-platform"])


class PublishEvent(BaseModel):
    stream: str
    event: dict
    role: str | None = None
    module_key: str | None = None


class RegisterModel(BaseModel):
    name: str
    version: str
    metadata: dict[str, Any] | None = None


class SyntheticRequest(BaseModel):
    role: str
    module_key: str
    count: int | None = 25


class InferenceRequest(BaseModel):
    model_key: str
    module_key: str
    payload: dict[str, Any] | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    model_version: str | None = None
    publish_realtime: bool | None = False
    stream: str | None = None
    cache_ttl: int | None = 120


class TaskInferenceRequest(BaseModel):
    role: str | None = None
    module_key: str | None = None
    sub_role: str | None = None
    payload: dict[str, Any] | None = None
    publish_realtime: bool | None = False
    stream: str | None = None
    cache_ttl: int | None = 120


class RetrievalIngestRequest(BaseModel):
    documents: list[dict[str, Any]]
    reset: bool | None = False


class RetrievalSearchRequest(BaseModel):
    query: str
    top_k: int | None = None
    filters: dict[str, Any] | None = None


@router.get("/insights")
async def insights(
    role: str = Query("public"),
    module_key: str = Query("overview"),
    sub_role: str | None = Query(None),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="ai:insights")
    cache_key = _cache_key(
        "insights",
        {
            "role": role,
            "module_key": module_key,
            "sub_role": sub_role,
            "user_id": ctx.user_id,
        },
    )
    cached = cache.get(cache_key)
    if cached:
        return cached

    summary, sources = await _module_data_summary(role, module_key, sub_role, ctx.user_id)
    payload = build_insights(role, module_key, sub_role)
    payload["data_summary"] = summary
    payload["data_sources"] = sources
    payload["narrative"] = _build_narrative(role, module_key, sub_role, summary)
    payload["status"] = "ok"
    cache.set(cache_key, payload, ttl=120)
    return payload


async def _count(db, collection: str, query: dict) -> int:
    try:
        return await db[collection].count_documents(query)
    except Exception:
        return 0


def _as_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


def _merge_query(scope: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    if not extra:
        return scope
    if "$or" in scope:
        return {"$and": [scope, extra]}
    return {**scope, **extra}


async def _resolve_hospital_scope(db, user_id: str) -> tuple[dict[str, Any], ObjectId | None]:
    hospital_oid: ObjectId | None = None
    oid = _as_object_id(user_id)
    repo = MongoRepository(db, HOSPITALS)
    if oid:
        hospital_doc = await repo.find_one({"_id": oid})
        if not hospital_doc:
            hospital_doc = await repo.find_one({"user": oid})
        if hospital_doc:
            hospital_oid = hospital_doc.get("_id")
        else:
            hospital_oid = oid

    clauses: list[dict[str, Any]] = [{"hospitalId": user_id}]
    if hospital_oid:
        clauses.append({"hospital": hospital_oid})
        clauses.append({"hospitalId": hospital_oid})
    return {"$or": clauses}, hospital_oid


def _cache_key(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def _confidence_from_result(result: Any) -> float:
    if isinstance(result, dict):
        for key in ("confidence", "score", "risk_score", "probability"):
            value = result.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, min(1.0, float(value)))
    return 0.82


def _build_task_result(task_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    key = task_key.replace("-", " ")
    outputs = {
        "insight": f"Generated {key} insight.",
        "recommendations": [
            "Validate with clinical lead before action.",
            "Review supporting signals for consistency.",
        ],
    }
    if "eta" in task_key:
        outputs["eta_minutes"] = payload.get("eta_minutes", 12)
    if "forecast" in task_key or "prediction" in task_key:
        outputs["forecast_window_hours"] = payload.get("forecast_window_hours", 24)
    if "risk" in task_key or "anomaly" in task_key:
        outputs["risk_score"] = payload.get("risk_score", 0.71)
    if "summary" in task_key or "scribe" in task_key:
        outputs["summary"] = payload.get("summary", "Summary generated from recent inputs.")
    return outputs


def _coerce_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _summary_sentence(summary: list[dict[str, Any]]) -> str:
    if not summary:
        return "Signals are still warming up; data will populate shortly."
    top = sorted(summary, key=lambda item: _coerce_number(item.get("value")), reverse=True)[:3]
    if not any(_coerce_number(item.get("value")) > 0 for item in top):
        return "Signals are still warming up; early indicators are low."
    parts = []
    for item in top:
        value = _coerce_number(item.get("value"))
        label = item.get("label") or "Signal"
        if value.is_integer():
            parts.append(f"{label} at {int(value)}")
        else:
            parts.append(f"{label} at {value:.1f}")
    return "Current signals show " + ", ".join(parts) + "."


def _build_narrative(
    role: str,
    module_key: str,
    sub_role: str | None,
    summary: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = (module_key or "overview").replace("-", " ").title()
    headline = f"{normalized} brief"
    base_actions = [
        "Confirm signal accuracy with the latest operations update.",
        "Align the next shift plan with the current signal mix.",
    ]
    hospital_actions = {
        "global-overview": [
            "Review occupancy and staffing balance before peak hours.",
            "Confirm escalation coverage for critical inflow.",
        ],
        "ai-insights": [
            "Validate anomaly flags with department heads.",
            "Prioritize the top two cost pressure drivers.",
        ],
        "department-analytics": [
            "Address bottleneck departments with targeted staffing.",
            "Align throughput targets with current queue volumes.",
        ],
        "bed-management": [
            "Confirm ICU availability and discharge candidates.",
            "Coordinate bed allocation with ER triage updates.",
        ],
        "resource-management": [
            "Replenish low stock items with long lead times.",
            "Validate vendor ETAs before the next shift handoff.",
        ],
        "ambulance-coordination": [
            "Synchronize inbound routing with ER readiness.",
            "Confirm handoff notes for active ambulance cases.",
        ],
        "finance-overview": [
            "Review revenue vs expense variance for the week.",
            "Follow up on outstanding invoice approvals.",
        ],
        "staff-management": [
            "Check skill coverage gaps before next rota.",
            "Redistribute staff to high-load departments.",
        ],
        "reports": [
            "Finalize report highlights and compliance notes.",
            "Share operational summaries with leadership.",
        ],
        "multi-hospital-network": [
            "Review mutual aid requests and partner status.",
            "Update data-sharing agreements as needed.",
        ],
        "live-emergency-feed": [
            "Monitor critical cases and triage response times.",
            "Prepare overflow routing if surge continues.",
        ],
        "patient-intake": [
            "Confirm triage categories for new intakes.",
            "Route high-risk cases to specialty teams.",
        ],
        "bed-allocation": [
            "Validate bed assignments against patient acuity.",
            "Update bed status before shift change.",
        ],
        "ai-decision-panel": [
            "Review AI recommendations with clinical lead.",
            "Document any overrides and rationale.",
        ],
        "billing": [
            "Prioritize high-value invoices for follow-up.",
            "Confirm payer status on delayed claims.",
        ],
        "revenue-analytics": [
            "Compare payer mix trends to targets.",
            "Investigate leakage signals flagged in claims.",
        ],
        "insurance": [
            "Review claims at risk of rejection.",
            "Align recovery actions with payer SLAs.",
        ],
        "appointment-scheduling": [
            "Balance appointment load across high-demand hours.",
            "Notify patients with elevated no-show risk.",
        ],
        "doctor-management": [
            "Rebalance specialty coverage for peak slots.",
            "Confirm on-call availability for tomorrow.",
        ],
        "patient-queue": [
            "Prioritize urgent cases based on wait time.",
            "Update queue status every 30 minutes.",
        ],
        "consultation-records": [
            "Verify AI summaries and follow-up plans.",
            "Tag high-risk consults for review.",
        ],
        "live-patient-monitoring": [
            "Monitor deteriorating vitals and escalation triggers.",
            "Confirm shift handoff notes for critical patients.",
        ],
        "critical-alerts": [
            "Acknowledge high-severity alerts immediately.",
            "Reduce alert fatigue by consolidating duplicates.",
        ],
        "ai-risk-prediction": [
            "Review risk predictions with ICU lead.",
            "Schedule additional monitoring for high-risk cases.",
        ],
        "vitals-dashboard": [
            "Validate abnormal vitals trends with nursing staff.",
            "Escalate deviations beyond threshold.",
        ],
        "scan-requests": [
            "Prioritize urgent imaging requests first.",
            "Communicate ETAs to ordering physicians.",
        ],
        "report-upload": [
            "Ensure imaging reports are uploaded on time.",
            "Review draft findings with radiologists.",
        ],
        "ai-scan-insights": [
            "Validate AI flags with radiology lead.",
            "Record follow-up actions for QA.",
        ],
        "surgery-scheduling": [
            "Confirm OT schedules with surgical teams.",
            "Adjust block times for overruns.",
        ],
        "staff-allocation": [
            "Balance OT staff across shifts.",
            "Confirm critical skill coverage.",
        ],
        "equipment-tracking": [
            "Check readiness of critical OT equipment.",
            "Schedule sterilization for next-day cases.",
        ],
    }

    actions = base_actions
    if role == "hospital":
        actions = hospital_actions.get(module_key, base_actions)

    return {
        "headline": headline,
        "summary": _summary_sentence(summary),
        "next_steps": actions,
        "confidence": 0.78,
        "sub_role": sub_role,
    }


async def _module_data_summary(
    role: str,
    module_key: str,
    sub_role: str | None,
    user_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    db = get_db()
    summary: list[dict[str, Any]] = []
    sources: set[str] = set()
    role = (role or "public").lower()
    module_key = (module_key or "overview").lower()
    sub_role = (sub_role or "").lower() or None

    if role == "public":
        if module_key == "emergency":
            count_alerts = await _count(db, ALERTS, {"userId": user_id})
            summary.append({"label": "SOS Alerts", "value": count_alerts, "source": ALERTS})
            sources.add(ALERTS)
        elif module_key == "health-dashboard":
            donations = await _count(db, DONATIONS, {"userId": user_id})
            requests = await _count(db, RESOURCE_REQUESTS, {"requester_id": user_id})
            summary.extend([
                {"label": "Donations", "value": donations, "source": DONATIONS},
                {"label": "Requests", "value": requests, "source": RESOURCE_REQUESTS},
            ])
            sources.update([DONATIONS, RESOURCE_REQUESTS])
        elif module_key == "health-risk":
            predictions = await _count(db, PREDICTIONS, {"userId": user_id})
            summary.append({"label": "Risk Checks", "value": predictions, "source": PREDICTIONS})
            sources.add(PREDICTIONS)
        elif module_key == "medical-records":
            records = await _count(db, HEALTH_RECORDS, {"patientId": user_id})
            summary.append({"label": "Records", "value": records, "source": HEALTH_RECORDS})
            sources.add(HEALTH_RECORDS)
        elif module_key == "donor-matching":
            donors = await _count(db, DONATIONS, {})
            summary.append({"label": "Active Donors", "value": donors, "source": DONATIONS})
            sources.add(DONATIONS)
        elif module_key == "nearby-hospitals":
            total = await _count(db, HOSPITALS, {})
            summary.append({"label": "Hospitals", "value": total, "source": HOSPITALS})
            sources.add(HOSPITALS)
        elif module_key == "family-monitoring":
            members = await _count(db, FAMILY_MEMBERS, {"userId": user_id})
            summary.append({"label": "Family Members", "value": members, "source": FAMILY_MEMBERS})
            sources.add(FAMILY_MEMBERS)
        elif module_key == "lifelink-ai-search":
            total = await _count(db, VECTOR_STORE, {})
            summary.append({"label": "Indexed Docs", "value": total, "source": VECTOR_STORE})
            sources.add(VECTOR_STORE)

    if role == "hospital":
        hospital_id = user_id
        hospital_scope, hospital_oid = await _resolve_hospital_scope(db, hospital_id)
        if module_key == "global-overview":
            alerts = await _count(db, ALERTS, hospital_scope)
            staff = await _count(db, HOSPITAL_STAFF, hospital_scope)
            benchmarks = await _count(db, HOSPITAL_BENCHMARKS, {})
            summary.extend([
                {"label": "Active Alerts", "value": alerts, "source": ALERTS},
                {"label": "Staff", "value": staff, "source": HOSPITAL_STAFF},
                {"label": "Benchmarks", "value": benchmarks, "source": HOSPITAL_BENCHMARKS},
            ])
            sources.update([ALERTS, HOSPITAL_STAFF, HOSPITAL_BENCHMARKS])
        elif module_key == "ai-insights":
            events = await _count(db, ANALYTICS_EVENTS, hospital_scope)
            summary.append({"label": "AI Events", "value": events, "source": ANALYTICS_EVENTS})
            sources.add(ANALYTICS_EVENTS)
        elif module_key == "department-analytics":
            departments = await _count(db, HOSPITAL_DEPARTMENTS, hospital_scope)
            logs = await _count(db, DEPARTMENT_LOGS, hospital_scope)
            summary.extend([
                {"label": "Departments", "value": departments, "source": HOSPITAL_DEPARTMENTS},
                {"label": "Dept Logs", "value": logs, "source": DEPARTMENT_LOGS},
            ])
            sources.update([HOSPITAL_DEPARTMENTS, DEPARTMENT_LOGS])
        elif module_key == "bed-management":
            allocations = await _count(db, BED_ALLOCATIONS, hospital_scope)
            summary.append({"label": "Allocations", "value": allocations, "source": BED_ALLOCATIONS})
            sources.add(BED_ALLOCATIONS)
        elif module_key == "resource-management":
            inventory = await _count(db, RESOURCES, hospital_scope)
            equipment = await _count(db, EQUIPMENT_INVENTORY, hospital_scope)
            vendors = await _count(db, VENDOR_LEAD_TIMES, hospital_scope)
            summary.extend([
                {"label": "Inventory Items", "value": inventory, "source": RESOURCES},
                {"label": "Equipment", "value": equipment, "source": EQUIPMENT_INVENTORY},
                {"label": "Vendor Lead Times", "value": vendors, "source": VENDOR_LEAD_TIMES},
            ])
            sources.update([RESOURCES, EQUIPMENT_INVENTORY, VENDOR_LEAD_TIMES])
        elif module_key == "ambulance-coordination":
            ambulances = await _count(db, AMBULANCES, {})
            summary.append({"label": "Active Ambulances", "value": ambulances, "source": AMBULANCES})
            sources.add(AMBULANCES)
        elif module_key == "ambulance-tracking":
            ambulances = await _count(db, AMBULANCES, {})
            assignments = await _count(db, AMBULANCE_ASSIGNMENTS, {})
            summary.extend([
                {"label": "Tracked Units", "value": ambulances, "source": AMBULANCES},
                {"label": "Assignments", "value": assignments, "source": AMBULANCE_ASSIGNMENTS},
            ])
            sources.update([AMBULANCES, AMBULANCE_ASSIGNMENTS])
        elif module_key == "finance-overview":
            invoices = await _count(db, BILLING_INVOICES, hospital_scope)
            expenses = await _count(db, FINANCE_EXPENSES, hospital_scope)
            summary.extend([
                {"label": "Invoices", "value": invoices, "source": BILLING_INVOICES},
                {"label": "Expenses", "value": expenses, "source": FINANCE_EXPENSES},
            ])
            sources.update([BILLING_INVOICES, FINANCE_EXPENSES])
        elif module_key == "cost-optimization":
            expenses = await _count(db, FINANCE_EXPENSES, hospital_scope)
            inventory = await _count(db, RESOURCES, hospital_scope)
            summary.extend([
                {"label": "Expense Items", "value": expenses, "source": FINANCE_EXPENSES},
                {"label": "Resource Lines", "value": inventory, "source": RESOURCES},
            ])
            sources.update([FINANCE_EXPENSES, RESOURCES])
        elif module_key == "staff-management":
            staff = await _count(db, HOSPITAL_STAFF, hospital_scope)
            summary.append({"label": "Staff", "value": staff, "source": HOSPITAL_STAFF})
            sources.add(HOSPITAL_STAFF)
        elif module_key == "reports":
            reports = await _count(db, HOSPITAL_REPORTS, hospital_scope)
            summary.append({"label": "Reports", "value": reports, "source": HOSPITAL_REPORTS})
            sources.add(HOSPITAL_REPORTS)
        elif module_key == "multi-hospital-network":
            message_query = {"$or": []}
            if hospital_oid:
                message_query["$or"].extend([
                    {"fromHospital": hospital_oid},
                    {"toHospital": hospital_oid},
                ])
            else:
                message_query["$or"].append({"fromHospital": hospital_id})
            messages = await _count(db, HOSPITAL_MESSAGES, message_query)
            agreements = 0
            if hospital_oid:
                agreements = await _count(
                    db,
                    HOSPITAL_NETWORK_AGREEMENTS,
                    {"$or": [{"hospital": hospital_oid}, {"partner": hospital_oid}]},
                )
            summary.extend([
                {"label": "Network Messages", "value": messages, "source": HOSPITAL_MESSAGES},
                {"label": "Agreements", "value": agreements, "source": HOSPITAL_NETWORK_AGREEMENTS},
            ])
            sources.update([HOSPITAL_MESSAGES, HOSPITAL_NETWORK_AGREEMENTS])
        elif module_key == "live-emergency-feed":
            emergencies = await _count(db, EMERGENCY_EVENTS, hospital_scope)
            summary.append({"label": "Live Emergencies", "value": emergencies, "source": EMERGENCY_EVENTS})
            sources.add(EMERGENCY_EVENTS)
        elif module_key == "patient-intake":
            patients = await _count(db, PATIENTS, hospital_scope)
            summary.append({"label": "Intakes", "value": patients, "source": PATIENTS})
            sources.add(PATIENTS)
        elif module_key == "bed-allocation":
            allocations = await _count(db, BED_ALLOCATIONS, hospital_scope)
            summary.append({"label": "Bed Allocations", "value": allocations, "source": BED_ALLOCATIONS})
            sources.add(BED_ALLOCATIONS)
        elif module_key == "ai-decision-panel":
            events = await _count(db, ANALYTICS_EVENTS, hospital_scope)
            summary.append({"label": "Decision Events", "value": events, "source": ANALYTICS_EVENTS})
            sources.add(ANALYTICS_EVENTS)
        elif module_key == "billing":
            invoices = await _count(db, BILLING_INVOICES, hospital_scope)
            summary.append({"label": "Invoices", "value": invoices, "source": BILLING_INVOICES})
            sources.add(BILLING_INVOICES)
        elif module_key == "revenue-analytics":
            expenses = await _count(db, FINANCE_EXPENSES, hospital_scope)
            summary.append({"label": "Expenses", "value": expenses, "source": FINANCE_EXPENSES})
            sources.add(FINANCE_EXPENSES)
        elif module_key == "insurance":
            claims = await _count(db, INSURANCE_CLAIMS, hospital_scope)
            summary.append({"label": "Claims", "value": claims, "source": INSURANCE_CLAIMS})
            sources.add(INSURANCE_CLAIMS)
        elif module_key == "appointment-scheduling":
            appointments = await _count(db, OPD_APPOINTMENTS, hospital_scope)
            summary.append({"label": "Appointments", "value": appointments, "source": OPD_APPOINTMENTS})
            sources.add(OPD_APPOINTMENTS)
        elif module_key == "doctor-management":
            doctors = await _count(db, OPD_DOCTORS, hospital_scope)
            summary.append({"label": "Doctors", "value": doctors, "source": OPD_DOCTORS})
            sources.add(OPD_DOCTORS)
        elif module_key == "patient-queue":
            queue = await _count(db, OPD_QUEUE, hospital_scope)
            summary.append({"label": "Queue Items", "value": queue, "source": OPD_QUEUE})
            sources.add(OPD_QUEUE)
        elif module_key == "consultation-records":
            consults = await _count(db, OPD_CONSULTATIONS, hospital_scope)
            summary.append({"label": "Consultations", "value": consults, "source": OPD_CONSULTATIONS})
            sources.add(OPD_CONSULTATIONS)
        elif module_key == "live-patient-monitoring":
            patients = await _count(db, ICU_PATIENTS, hospital_scope)
            summary.append({"label": "ICU Patients", "value": patients, "source": ICU_PATIENTS})
            sources.add(ICU_PATIENTS)
        elif module_key == "critical-alerts":
            alerts = await _count(db, ICU_ALERTS, hospital_scope)
            summary.append({"label": "ICU Alerts", "value": alerts, "source": ICU_ALERTS})
            sources.add(ICU_ALERTS)
        elif module_key == "ai-risk-prediction":
            preds = await _count(db, PREDICTIONS, hospital_scope)
            summary.append({"label": "Risk Scores", "value": preds, "source": PREDICTIONS})
            sources.add(PREDICTIONS)
        elif module_key == "vitals-dashboard":
            patients = await _count(db, ICU_PATIENTS, hospital_scope)
            summary.append({"label": "Vitals Streams", "value": patients, "source": ICU_PATIENTS})
            sources.add(ICU_PATIENTS)
        elif module_key == "scan-requests":
            requests = await _count(db, RADIOLOGY_REQUESTS, hospital_scope)
            summary.append({"label": "Scan Requests", "value": requests, "source": RADIOLOGY_REQUESTS})
            sources.add(RADIOLOGY_REQUESTS)
        elif module_key == "report-upload":
            reports = await _count(db, RADIOLOGY_REPORTS, hospital_scope)
            summary.append({"label": "Reports", "value": reports, "source": RADIOLOGY_REPORTS})
            sources.add(RADIOLOGY_REPORTS)
        elif module_key == "ai-scan-insights":
            reports = await _count(db, RADIOLOGY_REPORTS, hospital_scope)
            summary.append({"label": "AI Scans", "value": reports, "source": RADIOLOGY_REPORTS})
            sources.add(RADIOLOGY_REPORTS)
        elif module_key == "surgery-scheduling":
            surgeries = await _count(db, OT_SURGERIES, hospital_scope)
            summary.append({"label": "Surgeries", "value": surgeries, "source": OT_SURGERIES})
            sources.add(OT_SURGERIES)
        elif module_key == "staff-allocation":
            allocations = await _count(db, OT_ALLOCATIONS, hospital_scope)
            summary.append({"label": "OT Allocations", "value": allocations, "source": OT_ALLOCATIONS})
            sources.add(OT_ALLOCATIONS)
        elif module_key == "equipment-tracking":
            equipment = await _count(db, EQUIPMENT_INVENTORY, hospital_scope)
            summary.append({"label": "Equipment", "value": equipment, "source": EQUIPMENT_INVENTORY})
            sources.add(EQUIPMENT_INVENTORY)

    if role == "ambulance":
        if module_key == "assignments":
            assignments = await _count(db, AMBULANCE_ASSIGNMENTS, {"ambulanceId": user_id})
            summary.append({"label": "Assignments", "value": assignments, "source": AMBULANCE_ASSIGNMENTS})
            sources.add(AMBULANCE_ASSIGNMENTS)
        elif module_key == "live-tracking":
            count = await _count(db, AMBULANCES, {})
            summary.append({"label": "Tracked Units", "value": count, "source": AMBULANCES})
            sources.add(AMBULANCES)
        elif module_key == "patient-info":
            assignments = await _count(db, AMBULANCE_ASSIGNMENTS, {"ambulanceId": user_id})
            summary.append({"label": "Patient Updates", "value": assignments, "source": AMBULANCE_ASSIGNMENTS})
            sources.add(AMBULANCE_ASSIGNMENTS)
        elif module_key == "navigation":
            assignments = await _count(db, AMBULANCE_ASSIGNMENTS, {"ambulanceId": user_id})
            summary.append({"label": "Routes", "value": assignments, "source": AMBULANCE_ASSIGNMENTS})
            sources.add(AMBULANCE_ASSIGNMENTS)
        elif module_key == "emergency-status":
            alerts = await _count(db, ALERTS, {})
            summary.append({"label": "Active Alerts", "value": alerts, "source": ALERTS})
            sources.add(ALERTS)
        elif module_key == "history":
            history = await _count(db, AMBULANCE_ASSIGNMENTS, {"ambulanceId": user_id})
            summary.append({"label": "Completed", "value": history, "source": AMBULANCE_ASSIGNMENTS})
            sources.add(AMBULANCE_ASSIGNMENTS)

    if role == "government":
        if module_key in ("country-dashboard", "state-dashboard"):
            hospitals = await _count(db, HOSPITALS, {})
            users = await _count(db, USERS, {})
            summary.extend([
                {"label": "Hospitals", "value": hospitals, "source": HOSPITALS},
                {"label": "Registered Users", "value": users, "source": USERS},
            ])
            sources.update([HOSPITALS, USERS])
        elif module_key == "emergency-heatmap":
            alerts = await _count(db, ALERTS, {})
            summary.append({"label": "Alerts", "value": alerts, "source": ALERTS})
            sources.add(ALERTS)
        elif module_key == "resource-allocation":
            resources = await _count(db, RESOURCES, {})
            summary.append({"label": "Resources", "value": resources, "source": RESOURCES})
            sources.add(RESOURCES)
        elif module_key == "policy-insights":
            reports = await _count(db, GOVERNMENT_REPORTS, {})
            summary.append({"label": "Reports", "value": reports, "source": GOVERNMENT_REPORTS})
            sources.add(GOVERNMENT_REPORTS)
        elif module_key == "hospital-monitoring":
            hospitals = await _count(db, HOSPITALS, {})
            summary.append({"label": "Hospitals", "value": hospitals, "source": HOSPITALS})
            sources.add(HOSPITALS)
        elif module_key == "reports":
            reports = await _count(db, GOVERNMENT_REPORTS, {})
            summary.append({"label": "Reports", "value": reports, "source": GOVERNMENT_REPORTS})
            sources.add(GOVERNMENT_REPORTS)
        elif module_key == "district-emergencies":
            alerts = await _count(db, ALERTS, {})
            summary.append({"label": "District Alerts", "value": alerts, "source": ALERTS})
            sources.add(ALERTS)
        elif module_key == "ambulance-tracking":
            ambulances = await _count(db, AMBULANCES, {})
            summary.append({"label": "Ambulances", "value": ambulances, "source": AMBULANCES})
            sources.add(AMBULANCES)
        elif module_key == "hospital-audits":
            audits = await _count(db, AUDIT_LOGS, {})
            summary.append({"label": "Audits", "value": audits, "source": AUDIT_LOGS})
            sources.add(AUDIT_LOGS)
        elif module_key == "compliance-monitoring":
            compliance = await _count(db, GOVERNMENT_COMPLIANCE, {})
            summary.append({"label": "Compliance Cases", "value": compliance, "source": GOVERNMENT_COMPLIANCE})
            sources.add(GOVERNMENT_COMPLIANCE)

    return summary, sorted(sources)


@router.post("/events/publish")
async def publish_event(
    payload: PublishEvent,
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    settings = get_settings()
    stream = EventStream(settings.redis_url)
    redacted = redact_payload(payload.event)
    result = stream.publish(payload.stream, redacted)

    realtime = get_realtime_service()
    await realtime.broadcast(
        "ai",
        {"type": "ai_event", "stream": payload.stream, "payload": redacted},
    )

    repo = MongoRepository(get_db(), AI_EVENTS)
    record = await repo.insert_one({
        "stream": payload.stream,
        "event": redacted,
        "role": payload.role or ctx.role,
        "module_key": payload.module_key,
        "created_at": time.time(),
    })

    return {"status": result.get("status"), "event": record}


@router.post("/infer")
async def infer(
    payload: InferenceRequest,
    ctx: AuthContext = Depends(require_scopes("ai:ask")),
) -> dict:
    model_map = {
        "health-risk": "predict_risk",
        "emergency-detection": "predict_sos_severity",
        "eta": "predict_eta",
        "hospital-load": "predict_bed_forecast",
        "heatmap": "predict_hotspot",
    }
    if payload.model_key not in model_map:
        raise HTTPException(status_code=400, detail="Unsupported model key")
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="ai:inference")

    feature_context: dict[str, Any] = {}
    if payload.entity_type and payload.entity_id:
        store = FeatureStore()
        record = await store.get(payload.entity_type, payload.entity_id)
        if record and isinstance(record.get("features"), dict):
            feature_context = record.get("features")

    merged_payload = {**feature_context, **(payload.payload or {})}
    cache_key = _cache_key(
        "infer",
        {
            "model_key": payload.model_key,
            "module_key": payload.module_key,
            "entity_type": payload.entity_type,
            "entity_id": payload.entity_id,
            "payload": merged_payload,
        },
    )
    if payload.cache_ttl and payload.cache_ttl > 0:
        cached = cache.get(cache_key)
        if cached:
            cached["cached"] = True
            return cached

    registry = ModelRegistry()
    latest = await registry.get_latest(payload.model_key)
    model_version = payload.model_version or (latest.get("version") if latest else None)

    command = model_map[payload.model_key]
    celery_app.send_task("system.generate_predictions", args=[command, merged_payload])
    cached = await get_latest_prediction(command)
    result = cached.get("result") if cached and isinstance(cached.get("result"), dict) else {}
    latency_ms = 0.0
    confidence = cached.get("confidence", 0.0) if cached else 0.0

    explanation = {
        "summary": f"Generated {payload.model_key} insight for {payload.module_key}.",
        "inputs_used": list(merged_payload.keys()),
        "features_used": list(feature_context.keys()),
    }
    response = {
        "status": "ok",
        "model_key": payload.model_key,
        "module_key": payload.module_key,
        "result": result,
        "confidence": confidence,
        "explanation": explanation,
        "latency_ms": latency_ms,
        "model_version": model_version,
        "cached": False,
    }

    service = ObservabilityService()
    drift_score = (payload.payload or {}).get("drift_score") if isinstance(payload.payload, dict) else None
    data_freshness = (payload.payload or {}).get("data_freshness_hours") if isinstance(payload.payload, dict) else None
    await service.log_inference(
        role=ctx.role,
        module_key=payload.module_key,
        model_name=payload.model_key,
        model_version=model_version,
        latency_ms=latency_ms,
        status="queued",
        payload=merged_payload,
        response=result if isinstance(result, dict) else {"result": result},
        quality_score=confidence,
        drift_score=drift_score,
        data_freshness_hours=data_freshness,
        explanation_quality=0.8,
    )

    if payload.cache_ttl and payload.cache_ttl > 0:
        cache.set(cache_key, response, ttl=payload.cache_ttl)

    if payload.publish_realtime or payload.stream:
        stream_name = payload.stream or f"infer:{payload.module_key}"
        stream = EventStream(settings.redis_url)
        event_payload = {
            "type": "ai_inference",
            "role": ctx.role,
            "module_key": payload.module_key,
            "model_key": payload.model_key,
            "confidence": confidence,
            "result": result,
        }
        publish_result = stream.publish(stream_name, event_payload)
        realtime = get_realtime_service()
        await realtime.broadcast("ai", {"type": "ai_inference", "stream": stream_name, "payload": event_payload})
        response["event_id"] = publish_result.get("event_id")

    return response


@router.post("/tasks/{task_key}/infer")
async def infer_task(
    task_key: str,
    payload: TaskInferenceRequest,
    ctx: AuthContext = Depends(require_scopes("ai:ask")),
) -> dict:
    settings = get_settings()
    cache = CacheStore(settings.redis_url, namespace="ai:tasks")
    module_key = payload.module_key or "overview"
    role = payload.role or ctx.role
    sub_role = payload.sub_role
    task_payload = payload.payload or {}
    cache_key = _cache_key(
        "task",
        {
            "task_key": task_key,
            "role": role,
            "sub_role": sub_role,
            "module_key": module_key,
            "payload": task_payload,
        },
    )
    if payload.cache_ttl and payload.cache_ttl > 0:
        cached = cache.get(cache_key)
        if cached:
            cached["cached"] = True
            return cached

    start = time.time()
    result = _build_task_result(task_key, task_payload)
    latency_ms = round((time.time() - start) * 1000, 2)
    confidence = _confidence_from_result(result)

    explanation = {
        "summary": f"Generated {task_key} output for {module_key}.",
        "inputs_used": list(task_payload.keys()),
    }
    response = {
        "status": "ok",
        "task_key": task_key,
        "role": role,
        "sub_role": sub_role,
        "module_key": module_key,
        "result": result,
        "confidence": confidence,
        "explanation": explanation,
        "latency_ms": latency_ms,
        "cached": False,
    }

    service = ObservabilityService()
    await service.log_inference(
        role=role,
        module_key=module_key,
        model_name=task_key,
        model_version="task",
        latency_ms=latency_ms,
        status="ok",
        payload=task_payload,
        response=result,
        quality_score=confidence,
        explanation_quality=0.75,
    )

    if payload.cache_ttl and payload.cache_ttl > 0:
        cache.set(cache_key, response, ttl=payload.cache_ttl)

    if payload.publish_realtime or payload.stream:
        stream_name = payload.stream or f"task:{module_key}"
        stream = EventStream(settings.redis_url)
        event_payload = {
            "type": "ai_task",
            "task_key": task_key,
            "role": role,
            "module_key": module_key,
            "confidence": confidence,
            "result": result,
        }
        publish_result = stream.publish(stream_name, event_payload)
        realtime = get_realtime_service()
        await realtime.broadcast("ai", {"type": "ai_task", "stream": stream_name, "payload": event_payload})
        response["event_id"] = publish_result.get("event_id")

    return response


@router.get("/events/{stream}")
async def read_events(
    stream: str,
    count: int = Query(50, ge=1, le=200),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    settings = get_settings()
    reader = EventStream(settings.redis_url)
    items = reader.read(stream, count=count)
    return {"stream": stream, "count": len(items), "items": items}


@router.post("/features/{entity_type}/{entity_id}")
async def upsert_features(
    entity_type: str,
    entity_id: str,
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    store = FeatureStore()
    data = await store.upsert(entity_type, entity_id, payload)
    return {"status": "ok", "feature": data}


@router.get("/features/{entity_type}/{entity_id}")
async def get_features(
    entity_type: str,
    entity_id: str,
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    store = FeatureStore()
    data = await store.get(entity_type, entity_id)
    if not data:
        raise HTTPException(status_code=404, detail="Feature not found")
    return {"status": "ok", "feature": data}


@router.get("/features/{entity_type}")
async def list_features(
    entity_type: str,
    limit: int = Query(100, ge=1, le=500),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    store = FeatureStore()
    data = await store.list(entity_type, limit=limit)
    return {"status": "ok", "items": data}


@router.post("/registry")
async def register_model(
    payload: RegisterModel,
    ctx: AuthContext = Depends(require_scopes("ai:ask")),
) -> dict:
    registry = ModelRegistry()
    record = await registry.register(payload.name, payload.version, payload.metadata or {})
    return {"status": "ok", "model": record}


@router.get("/registry")
async def list_registry(
    name: str | None = Query(None),
    ctx: AuthContext = Depends(require_scopes("ai:ask")),
) -> dict:
    registry = ModelRegistry()
    records = await registry.list(name)
    return {"status": "ok", "items": records}


@router.post("/retrieval/ingest")
async def ingest_retrieval(
    payload: RetrievalIngestRequest,
    ctx: AuthContext = Depends(require_scopes("ai:ask")),
) -> dict:
    if payload.reset:
        reset_retrieval_index()
    if not payload.documents:
        raise HTTPException(status_code=400, detail="documents are required")
    retrieval = RetrievalIndex()
    result = retrieval.ingest(payload.documents)
    return {"status": "ok", "result": result, "count": result.get("count", 0)}


@router.post("/retrieval/search")
async def search_retrieval(
    payload: RetrievalSearchRequest,
    ctx: AuthContext = Depends(require_scopes("ai:ask")),
) -> dict:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    retrieval = RetrievalIndex()
    results = retrieval.search(query, top_k=payload.top_k or 6, filters=payload.filters)
    return {
        "status": "ok",
        "query": query,
        "results": results.get("results", []),
        "citations": results.get("citations", []),
    }


@router.get("/observability")
async def observability_summary(
    hours: int = Query(24, ge=1, le=168),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    service = ObservabilityService()
    summary = await service.summary(hours=hours)
    return {"status": "ok", "summary": summary}


@router.post("/synthetic/bootstrap")
async def bootstrap_synthetic(
    payload: SyntheticRequest,
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    service = SyntheticDataService()
    result = await service.bootstrap(payload.role, payload.module_key, payload.count or 25)
    return {"status": "ok", "result": result}


@router.post("/privacy/redact")
async def redact_text(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    return {"status": "ok", "redacted": redact_payload(payload)}


@router.post("/privacy/scan")
async def scan_text(
    payload: dict = Body(default_factory=dict),
    ctx: AuthContext = Depends(require_scopes("dashboard:read")),
) -> dict:
    return {"status": "ok", "scan": scan_payload(payload)}
