import re
from datetime import datetime, timedelta
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import (
    ALERTS,
    AMBULANCE_ASSIGNMENTS,
    AMBULANCES,
    ANALYTICS_EVENTS,
    BED_ALLOCATIONS,
    BILLING_INVOICES,
    DEPARTMENT_LOGS,
    EMERGENCY_EVENTS,
    EQUIPMENT_INVENTORY,
    FINANCE_EXPENSES,
    HOSPITAL_BENCHMARKS,
    HOSPITAL_DEPARTMENTS,
    HOSPITAL_MESSAGES,
    HOSPITAL_NETWORK_AGREEMENTS,
    HOSPITALS,
    HOSPITAL_REPORTS,
    HOSPITAL_STAFF,
    ICU_ALERTS,
    ICU_PATIENTS,
    INSURANCE_CLAIMS,
    OPD_QUEUE,
    OPD_APPOINTMENTS,
    OPD_CONSULTATIONS,
    OPD_DOCTORS,
    OT_ALLOCATIONS,
    OT_SURGERIES,
    PATIENTS,
    PREDICTIONS,
    RADIOLOGY_REPORTS,
    RADIOLOGY_REQUESTS,
    RESOURCES,
    VENDOR_LEAD_TIMES,
)
from app.core.celery_app import celery_app
from app.services.prediction_store import get_latest_prediction
from app.services.repository import MongoRepository

router = APIRouter(tags=["hospital-ops"])

SEED_VERSION = 3


class OpdAppointmentCreate(BaseModel):
    hospitalId: str
    patient: str
    doctor: str
    time: str
    status: str | None = "Scheduled"
    appointmentType: str | None = None
    channel: str | None = None
    expectedDurationMinutes: int | None = None
    reason: str | None = None
    notes: str | None = None


class OpdAppointmentUpdate(BaseModel):
    patient: str | None = None
    doctor: str | None = None
    time: str | None = None
    status: str | None = None
    appointmentType: str | None = None
    channel: str | None = None
    expectedDurationMinutes: int | None = None
    reason: str | None = None
    notes: str | None = None


class OpdDoctorCreate(BaseModel):
    hospitalId: str
    name: str
    specialty: str
    availability: bool | None = True
    shift: str | None = None
    schedule: str | None = None


class OpdDoctorUpdate(BaseModel):
    name: str | None = None
    specialty: str | None = None
    availability: bool | None = None
    shift: str | None = None
    schedule: str | None = None


class OpdConsultationCreate(BaseModel):
    hospitalId: str
    patient: str
    doctor: str
    notes: str
    date: str | None = None
    status: str | None = "Open"
    followUpDate: str | None = None
    summary: str | None = None
    aiSummary: str | None = None
    keywords: list[str] | None = None
    followUpPlan: str | None = None


class OpdConsultationUpdate(BaseModel):
    patient: str | None = None
    doctor: str | None = None
    notes: str | None = None
    date: str | None = None
    status: str | None = None
    followUpDate: str | None = None
    summary: str | None = None
    aiSummary: str | None = None
    keywords: list[str] | None = None
    followUpPlan: str | None = None


class IcuPatientCreate(BaseModel):
    hospitalId: str
    name: str
    oxygen: int
    heartRate: int
    bp: str
    status: str | None = "Stable"


class IcuPatientUpdate(BaseModel):
    name: str | None = None
    oxygen: int | None = None
    heartRate: int | None = None
    bp: str | None = None
    status: str | None = None


class IcuAlertCreate(BaseModel):
    hospitalId: str
    message: str
    severity: str
    status: str | None = "Active"


class IcuAlertUpdate(BaseModel):
    message: str | None = None
    severity: str | None = None
    status: str | None = None


class RadiologyRequestCreate(BaseModel):
    hospitalId: str
    patient: str
    scan: str
    status: str | None = "Queued"


class RadiologyRequestUpdate(BaseModel):
    status: str | None = None


class RadiologyReportCreate(BaseModel):
    hospitalId: str
    patient: str
    scan: str
    fileName: str | None = None
    notes: str | None = None
    status: str | None = "Uploaded"


class OTSurgeryCreate(BaseModel):
    hospitalId: str
    patient: str
    procedure: str
    time: str
    status: str | None = "Scheduled"


class OTSurgeryUpdate(BaseModel):
    patient: str | None = None
    procedure: str | None = None
    time: str | None = None
    status: str | None = None


class OTAllocationCreate(BaseModel):
    hospitalId: str
    department: str
    patient_load: str
    shift: str


class StaffMemberCreate(BaseModel):
    hospitalId: str
    name: str
    role: str
    department: str
    shift: str | None = None
    availability: bool | None = True
    skillTags: list[str] | None = None
    certifications: list[str] | None = None
    maxPatients: int | None = None


class StaffMemberUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    department: str | None = None
    shift: str | None = None
    availability: bool | None = None
    skillTags: list[str] | None = None
    certifications: list[str] | None = None
    maxPatients: int | None = None


class EmergencyEventCreate(BaseModel):
    hospitalId: str
    patientName: str
    symptoms: str
    location: str | None = None
    source: str | None = "public"
    imagingMeta: dict | None = None


class EmergencyEventUpdate(BaseModel):
    status: str | None = None
    assignedDepartment: str | None = None
    assignedUnit: str | None = None
    notes: str | None = None
    imagingMeta: dict | None = None


class EmergencyIntakeCreate(BaseModel):
    hospitalId: str
    name: str
    age: int
    gender: str
    symptoms: str
    contact: str | None = None
    severity: str | None = None
    department: str | None = None


class EmergencyIntakeUpdate(BaseModel):
    status: str | None = None
    severity: str | None = None
    department: str | None = None
    notes: str | None = None


class BedAllocationCreate(BaseModel):
    hospitalId: str
    patientName: str
    bedType: str
    override: bool | None = False
    notes: str | None = None


class BedAllocationUpdate(BaseModel):
    bedType: str | None = None
    status: str | None = None
    notes: str | None = None


class BillingInvoiceCreate(BaseModel):
    hospitalId: str
    patientName: str
    department: str
    amount: float
    status: str | None = "Unpaid"
    insuranceProvider: str | None = None
    dueDate: str | None = None
    payer: str | None = None
    paidAt: str | None = None


class BillingInvoiceUpdate(BaseModel):
    status: str | None = None
    paidAmount: float | None = None
    refundAmount: float | None = None
    paidAt: str | None = None


class InsuranceClaimCreate(BaseModel):
    hospitalId: str
    invoiceId: str
    insurer: str
    amount: float
    status: str | None = "Submitted"
    submittedAt: str | None = None
    paidAt: str | None = None


class InsuranceClaimUpdate(BaseModel):
    status: str | None = None
    approvedAmount: float | None = None
    notes: str | None = None
    paidAt: str | None = None


class FinanceExpenseCreate(BaseModel):
    hospitalId: str
    category: str
    amount: float
    notes: str | None = None
    vendor: str | None = None
    contractRef: str | None = None


class HospitalReportGenerate(BaseModel):
    hospitalId: str
    reportKey: str


class ReportIngestCreate(BaseModel):
    hospitalId: str
    name: str
    content: str
    category: str | None = None


class DepartmentLogCreate(BaseModel):
    hospitalId: str
    department: str
    avgTreatmentMinutes: float
    dischargeRate: float
    delayRate: float
    throughputPerHour: float | None = None
    queueLength: int | None = None
    notes: str | None = None


class BenchmarkCreate(BaseModel):
    region: str
    metric: str
    value: float
    source: str | None = "external_feed"


class VendorLeadTimeCreate(BaseModel):
    hospitalId: str
    resourceName: str
    category: str
    vendorName: str | None = None
    leadTimeDays: int


class EquipmentCreate(BaseModel):
    hospitalId: str
    name: str
    category: str
    quantity: int
    status: str | None = "Available"
    minThreshold: int | None = 1


class EquipmentUpdate(BaseModel):
    quantity: int | None = None
    status: str | None = None
    minThreshold: int | None = None


class OpdQueueCreate(BaseModel):
    hospitalId: str
    patientName: str
    reason: str
    priority: str | None = "Normal"
    assignedDoctor: str | None = None
    notes: str | None = None


class OpdQueueUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assignedDoctor: str | None = None
    notes: str | None = None


UUID_HEX_RE = re.compile(r"^[0-9a-fA-F]{32}$")
UUID_CANON_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


def _normalize_hospital_id(hospital_id: str) -> ObjectId | str:
    text = (hospital_id or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="hospitalId is required")
    if re.fullmatch(r"[0-9a-fA-F]{24}", text):
        return ObjectId(text)
    if UUID_HEX_RE.fullmatch(text) or UUID_CANON_RE.fullmatch(text):
        return text
    raise HTTPException(status_code=400, detail="Invalid hospitalId format")


def _require_hospital_id(hospital_id: str | None) -> ObjectId | str:
    if not hospital_id:
        raise HTTPException(status_code=400, detail="hospitalId is required")
    return _normalize_hospital_id(hospital_id)


def _build_update(payload: BaseModel, fields: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field in fields:
        value = getattr(payload, field)
        if value is not None:
            data[field] = value
    if not data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    data["updatedAt"] = datetime.utcnow()
    return data


def _build_search(search: str | None, fields: list[str]) -> dict[str, Any] | None:
    if not search:
        return None
    text = search.strip()
    if not text:
        return None
    escaped = re.escape(text)
    return {"$or": [{field: {"$regex": escaped, "$options": "i"}} for field in fields]}


def _build_sort(sort_by: str | None, sort_dir: str | None, allowed: set[str], fallback: str) -> list[tuple[str, int]]:
    field = sort_by if sort_by in allowed else fallback
    direction = 1 if (sort_dir or "").lower() == "asc" else -1
    return [(field, direction)]


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _season_tag(target: datetime | None) -> str | None:
    if not target:
        return None
    month = target.month
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Summer"
    if month in (6, 7, 8):
        return "Monsoon"
    return "Autumn"


def _normalize_shift(shift: str | None, schedule: str | None) -> str | None:
    if shift:
        return shift.strip().title()
    if not schedule:
        return None
    lower = schedule.lower()
    if any(token in lower for token in ["night", "evening", "eve"]):
        return "Night"
    if any(token in lower for token in ["afternoon", "pm"]):
        return "Afternoon"
    if any(token in lower for token in ["morning", "am"]):
        return "Morning"
    return None


def _summarize_note(text: str | None) -> str:
    content = (text or "").strip()
    if not content:
        return ""
    sentences = [segment.strip() for segment in content.split(".") if segment.strip()]
    if sentences:
        return f"{sentences[0]}."
    return content[:120]


def _extract_keywords(text: str | None, limit: int = 5) -> list[str]:
    content = (text or "").strip().lower()
    if not content:
        return []
    cleaned = re.sub(r"[^a-z0-9\s]", " ", content)
    tokens = [token for token in cleaned.split() if len(token) >= 4]
    stopwords = {
        "with",
        "from",
        "this",
        "that",
        "patient",
        "follow",
        "review",
        "check",
        "notes",
    }
    counts: dict[str, int] = {}
    for token in tokens:
        if token in stopwords:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [item[0] for item in ranked[:limit]]


def _follow_up_plan(text: str | None) -> str:
    lower = (text or "").lower()
    if any(token in lower for token in ["follow", "review", "recheck", "return"]):
        return "Schedule follow-up in 7 days"
    if any(token in lower for token in ["medication", "prescription", "therapy"]):
        return "Medication adherence check in 3 days"
    return "No follow-up flagged"


def _predict_wait_minutes(index: int, priority: str | None) -> int:
    base = 6
    multiplier = {"Critical": 0.6, "High": 0.8, "Normal": 1.0}
    weight = multiplier.get(priority or "Normal", 1.0)
    return max(4, round((index + 1) * base * weight))



async def _resolve_hospital_doc(db, hospital_id: str) -> dict[str, Any] | None:
    repo = MongoRepository(db, HOSPITALS)
    try:
        oid = _normalize_hospital_id(hospital_id)
    except HTTPException:
        return None
    doc = await repo.find_one({"_id": oid})
    if doc:
        return doc
    doc = await repo.find_one({"user": oid})
    return doc


def _bed_breakdown(beds: dict[str, Any] | None) -> dict[str, Any]:
    beds = beds or {}
    total = int(beds.get("totalBeds") or 0)
    occupied_raw = beds.get("occupiedBeds")
    available_raw = beds.get("availableBeds")
    occupied = int(occupied_raw or 0)
    available = int(available_raw if available_raw is not None else max(0, total - occupied))

    if (occupied_raw is None or occupied_raw == "") and available_raw is not None and total:
        occupied = max(0, total - available)
    if (available_raw is None or available_raw == "") and total:
        available = max(0, total - occupied)

    icu_total = int(beds.get("icuBeds") or max(1, round(total * 0.2)))
    emergency_total = int(beds.get("emergencyBeds") or max(1, round(total * 0.15)))
    general_total = max(0, total - icu_total - emergency_total)

    icu_occupied = min(icu_total, int(beds.get("icuOccupied") or max(0, round(occupied * 0.32))))
    emergency_occupied = min(emergency_total, int(beds.get("emergencyOccupied") or max(0, round(occupied * 0.22))))
    general_occupied = min(general_total, max(0, occupied - icu_occupied - emergency_occupied))

    return {
        "total": total,
        "occupied": occupied,
        "available": max(0, available),
        "icu": {
            "total": icu_total,
            "occupied": icu_occupied,
            "available": max(0, icu_total - icu_occupied),
        },
        "emergency": {
            "total": emergency_total,
            "occupied": emergency_occupied,
            "available": max(0, emergency_total - emergency_occupied),
        },
        "general": {
            "total": general_total,
            "occupied": general_occupied,
            "available": max(0, general_total - general_occupied),
        },
    }


def _severity_from_text(text: str) -> str:
    lower = (text or "").lower()
    if any(token in lower for token in ["cardiac", "unconscious", "severe", "stroke", "bleeding"]):
        return "Critical"
    if any(token in lower for token in ["fracture", "accident", "trauma", "chest"]):
        return "High"
    if any(token in lower for token in ["fever", "pain", "dizzy", "injury"]):
        return "Medium"
    return "Low"


def _department_from_symptoms(text: str) -> str:
    lower = (text or "").lower()
    if any(token in lower for token in ["chest", "cardiac", "heart"]):
        return "Cardiology"
    if any(token in lower for token in ["fracture", "ortho", "bone"]):
        return "Orthopedics"
    if any(token in lower for token in ["stroke", "neuro", "seizure"]):
        return "Neurology"
    if any(token in lower for token in ["trauma", "accident", "bleeding"]):
        return "Emergency"
    return "General"


def _estimate_discharge_hours(severity: str | None) -> int:
    level = (severity or "").lower()
    if level == "critical":
        return 72
    if level == "high":
        return 48
    if level == "medium":
        return 24
    return 12


def _score_department(patients: int, avg_time: float, discharge_rate: float, delay_rate: float) -> float:
    if patients <= 0:
        return 0.0
    time_score = max(0.0, 100 - avg_time * 3)
    delay_score = max(0.0, 100 - delay_rate * 100)
    return round((time_score * 0.4) + (discharge_rate * 0.4) + (delay_score * 0.2), 2)


def _simple_meta(confidence: float, reasoning: list[str], references: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "confidence": confidence,
        "reasoning": reasoning,
        "references": references or [],
    }


async def _safe_run_model(command: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    celery_app.send_task("system.generate_predictions", args=[command, payload])
    cached = await get_latest_prediction(command)
    if cached and isinstance(cached.get("result"), dict):
        return cached["result"]
    return None


async def _seed_collection(
    repo: MongoRepository,
    query: dict[str, Any],
    docs: list[dict[str, Any]],
    force: bool = False,
) -> int:
    if not force:
        existing = await repo.find_one(query)
        if existing:
            return 0
    inserted = 0
    for doc in docs:
        await repo.insert_one(doc)
        inserted += 1
    return inserted


async def _ensure_hospital_ops_seed(
    db,
    hospital_id: str,
    force: bool = False,
    scale: int | None = None,
) -> dict[str, Any]:
    hospital_repo = MongoRepository(db, HOSPITALS)
    hospital_oid = _require_hospital_id(hospital_id)
    hospital_doc = await hospital_repo.find_one({"_id": hospital_oid})
    if not hospital_doc:
        hospital_doc = await hospital_repo.find_one({"user": hospital_oid})

    now = datetime.utcnow()
    if not hospital_doc:
        hospital_doc = await hospital_repo.insert_one(
            {
                "_id": hospital_oid,
                "user": hospital_oid,
                "name": "LifeLink General Hospital",
                "location": {"city": "Bengaluru", "state": "Karnataka"},
                "createdAt": now,
                "updatedAt": now,
            }
        )

    seed_scale = max(220, min(int(scale or 280), 600))
    existing_version = hospital_doc.get("opsSeedVersion") if hospital_doc else None
    existing_scale = hospital_doc.get("opsSeedScale") if hospital_doc else None
    if existing_version == SEED_VERSION and existing_scale == seed_scale and not force:
        return {
            "seeded": False,
            "version": SEED_VERSION,
            "hospitalId": str(hospital_doc.get("_id")),
        }

    seed_force = force or existing_version != SEED_VERSION or existing_scale != seed_scale
    bed_total = max(260, int(seed_scale * 1.35))
    bed_occupied = int(bed_total * 0.72)
    bed_available = max(0, bed_total - bed_occupied)
    bed_icu = max(32, int(bed_total * 0.18))
    bed_emergency = max(28, int(bed_total * 0.16))
    bed_icu_occupied = min(bed_icu, int(bed_icu * 0.72))
    bed_emergency_occupied = min(bed_emergency, int(bed_emergency * 0.76))

    departments = [
        "Emergency",
        "ICU",
        "General",
        "Cardiology",
        "Orthopedics",
        "Neurology",
        "Pediatrics",
        "Radiology",
        "Surgery",
        "Oncology",
    ]
    staff_roles = ["Doctor", "Nurse", "Technician", "Support", "Consultant"]
    shifts = ["Day", "Evening", "Night"]
    specialties = ["Trauma", "ICU", "Cardiology", "Neuro", "Ortho", "Radiology", "Surgery", "Pediatrics"]
    severity_cycle = ["Critical", "High", "Medium", "Low"]
    status_cycle = ["Admitted", "Observation", "Intake", "ICU", "Recovered"]

    hospital_update = {
        "opsSeedVersion": SEED_VERSION,
        "opsSeededAt": now,
        "opsSeedScale": seed_scale,
        "name": hospital_doc.get("name") or "LifeLink General Hospital",
        "location": hospital_doc.get("location") or {"city": "Bengaluru", "state": "Karnataka"},
        "specialties": hospital_doc.get("specialties")
        or departments,
        "beds": (hospital_doc.get("beds") if not seed_force else None)
        or {
            "totalBeds": bed_total,
            "occupiedBeds": bed_occupied,
            "availableBeds": bed_available,
            "icuBeds": bed_icu,
            "icuOccupied": bed_icu_occupied,
            "emergencyBeds": bed_emergency,
            "emergencyOccupied": bed_emergency_occupied,
        },
        "doctors": hospital_doc.get("doctors")
        or [
            {
                "name": f"Dr. {dept} Lead",
                "department": dept,
                "specialization": specialties[idx % len(specialties)],
                "availability": idx % 4 != 0,
            }
            for idx, dept in enumerate(departments[:8])
        ],
        "resources": hospital_doc.get("resources")
        or [
            {
                "name": "Ventilators",
                "category": "Equipment",
                "availableUnits": 48,
                "totalUnits": 70,
                "unit": "units",
            },
            {
                "name": "Oxygen Cylinders",
                "category": "Consumables",
                "availableUnits": 320,
                "totalUnits": 460,
                "unit": "units",
            },
            {
                "name": "Blood Units",
                "category": "Blood Bank",
                "availableUnits": 160,
                "totalUnits": 240,
                "unit": "units",
            },
            {
                "name": "PPE Kits",
                "category": "Supplies",
                "availableUnits": 680,
                "totalUnits": 920,
                "unit": "kits",
            },
        ],
        "updatedAt": now,
    }

    await hospital_repo.update_one({"_id": hospital_doc.get("_id")}, {"$set": hospital_update}, return_new=True)

    counts: dict[str, int] = {}
    patient_repo = MongoRepository(db, PATIENTS)
    staff_repo = MongoRepository(db, HOSPITAL_STAFF)
    invoice_repo = MongoRepository(db, BILLING_INVOICES)
    emergency_repo = MongoRepository(db, EMERGENCY_EVENTS)
    assignment_repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    dept_log_repo = MongoRepository(db, DEPARTMENT_LOGS)
    resource_repo = MongoRepository(db, RESOURCES)
    equipment_repo = MongoRepository(db, EQUIPMENT_INVENTORY)
    vendor_repo = MongoRepository(db, VENDOR_LEAD_TIMES)
    allocation_repo = MongoRepository(db, BED_ALLOCATIONS)
    report_repo = MongoRepository(db, HOSPITAL_REPORTS)
    expense_repo = MongoRepository(db, FINANCE_EXPENSES)
    claim_repo = MongoRepository(db, INSURANCE_CLAIMS)
    opd_appt_repo = MongoRepository(db, OPD_APPOINTMENTS)
    opd_doctor_repo = MongoRepository(db, OPD_DOCTORS)
    opd_queue_repo = MongoRepository(db, OPD_QUEUE)
    opd_consult_repo = MongoRepository(db, OPD_CONSULTATIONS)
    icu_patient_repo = MongoRepository(db, ICU_PATIENTS)
    icu_alert_repo = MongoRepository(db, ICU_ALERTS)
    radiology_request_repo = MongoRepository(db, RADIOLOGY_REQUESTS)
    radiology_report_repo = MongoRepository(db, RADIOLOGY_REPORTS)
    ot_surgery_repo = MongoRepository(db, OT_SURGERIES)
    ot_alloc_repo = MongoRepository(db, OT_ALLOCATIONS)
    benchmark_repo = MongoRepository(db, HOSPITAL_BENCHMARKS)
    ambulance_repo = MongoRepository(db, AMBULANCES)
    alert_repo = MongoRepository(db, ALERTS)
    analytics_repo = MongoRepository(db, ANALYTICS_EVENTS)
    prediction_repo = MongoRepository(db, PREDICTIONS)
    dept_repo = MongoRepository(db, HOSPITAL_DEPARTMENTS)
    message_repo = MongoRepository(db, HOSPITAL_MESSAGES)
    agreement_repo = MongoRepository(db, HOSPITAL_NETWORK_AGREEMENTS)

    patient_count = seed_scale + 40
    counts["patients"] = await _seed_collection(
        patient_repo,
        {"hospitalId": hospital_oid},
        [
            {
                "hospitalId": hospital_oid,
                "name": f"Patient {idx + 1}",
                "age": 18 + (idx % 62),
                "gender": "F" if idx % 2 == 0 else "M",
                "dept": departments[idx % len(departments)],
                "condition": f"{departments[idx % len(departments)]} case",
                "severity": severity_cycle[idx % len(severity_cycle)],
                "status": status_cycle[idx % len(status_cycle)],
                "createdAt": now - timedelta(hours=idx % 240),
                "updatedAt": now - timedelta(hours=idx % 120),
            }
            for idx in range(patient_count)
        ],
        force=seed_force,
    )

    staff_count = int(seed_scale * 0.85)
    counts["staff"] = await _seed_collection(
        staff_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "name": f"Staff {idx + 1}",
                "role": staff_roles[idx % len(staff_roles)],
                "department": departments[idx % len(departments)],
                "shift": shifts[idx % len(shifts)],
                "availability": idx % 5 != 0,
                "skillTags": [specialties[idx % len(specialties)], departments[idx % len(departments)]],
                "certifications": ["BLS", "ACLS"] if idx % 3 == 0 else ["BLS"],
                "maxPatients": 12 + (idx % 10),
                "createdAt": now - timedelta(days=idx % 30),
                "updatedAt": now - timedelta(days=idx % 10),
            }
            for idx in range(staff_count)
        ],
        force=seed_force,
    )

    invoice_count = seed_scale + 120
    counts["invoices"] = await _seed_collection(
        invoice_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patientName": f"Patient {idx + 1}",
                "department": departments[idx % len(departments)],
                "amount": 15000 + (idx % 18) * 2200,
                "status": "Paid" if idx % 3 == 0 else "Unpaid",
                "insuranceProvider": "Care Plus" if idx % 4 == 0 else "Star Health",
                "payer": "Insurer" if idx % 4 == 0 else "Self",
                "paidAt": (now - timedelta(days=idx % 30)).isoformat() if idx % 3 == 0 else None,
                "paidAmount": float(15000 + (idx % 18) * 2200) if idx % 3 == 0 else 0.0,
                "refundAmount": 0.0,
                "createdAt": now - timedelta(days=idx % 30, hours=idx % 18),
                "updatedAt": now - timedelta(days=idx % 15),
            }
            for idx in range(invoice_count)
        ],
        force=seed_force,
    )

    emergency_count = int(seed_scale * 0.45)
    counts["emergencies"] = await _seed_collection(
        emergency_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patientName": f"Emergency {idx + 1}",
                "symptoms": "Trauma" if idx % 4 == 0 else "Chest pain",
                "location": "Central Zone",
                "source": "public",
                "severity": severity_cycle[idx % len(severity_cycle)],
                "priority": "High" if idx % 3 == 0 else "Medium",
                "status": "Assigned" if idx % 5 == 0 else "Unassigned",
                "createdAt": now - timedelta(hours=idx % 48),
                "updatedAt": now - timedelta(hours=idx % 24),
            }
            for idx in range(emergency_count)
        ],
        force=seed_force,
    )

    assignment_count = int(seed_scale * 0.2)
    counts["assignments"] = await _seed_collection(
        assignment_repo,
        {"hospital": hospital_id},
        [
            {
                "ambulanceId": f"AMB-{100 + idx}",
                "hospital": hospital_id,
                "eventId": None,
                "status": "Active" if idx % 4 != 0 else "Completed",
                "etaMinutes": 6 + (idx % 14),
                "pickup": "Central Zone",
                "destination": "LifeLink General Hospital",
                "createdAt": now - timedelta(hours=idx % 36),
                "updatedAt": now - timedelta(hours=idx % 18),
            }
            for idx in range(assignment_count)
        ],
        force=seed_force,
    )

    counts["department_logs"] = await _seed_collection(
        dept_log_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "department": dept,
                "avgTreatmentMinutes": 30 + (idx % 10) * 2.2,
                "dischargeRate": round(0.55 + (idx % 5) * 0.05, 2),
                "delayRate": round(0.06 + (idx % 4) * 0.03, 2),
                "throughputPerHour": 3.2 + (idx % 6) * 0.7,
                "queueLength": 6 + (idx % 14),
                "notes": "Stable throughput",
                "createdAt": now - timedelta(days=idx % 5),
                "updatedAt": now - timedelta(days=idx % 3),
            }
            for idx, dept in enumerate(departments)
        ],
        force=seed_force,
    )

    resource_catalog = [
        {"name": "IV Kits", "category": "Supplies", "unit": "kits", "base": 320},
        {"name": "Dialysis Filters", "category": "Equipment", "unit": "filters", "base": 80},
        {"name": "Ventilator Circuits", "category": "Consumables", "unit": "sets", "base": 140},
        {"name": "Glucose Monitors", "category": "Supplies", "unit": "units", "base": 220},
        {"name": "Surgical Gloves", "category": "Supplies", "unit": "boxes", "base": 480},
        {"name": "Oxygen Masks", "category": "Consumables", "unit": "units", "base": 260},
    ]
    resource_count = 60
    counts["resources"] = await _seed_collection(
        resource_repo,
        {"hospitalId": hospital_oid},
        [
            {
                "hospitalId": hospital_oid,
                "name": f"{resource_catalog[idx % len(resource_catalog)]['name']} {idx + 1}",
                "category": resource_catalog[idx % len(resource_catalog)]["category"],
                "quantity": resource_catalog[idx % len(resource_catalog)]["base"] + (idx % 6) * 25,
                "minThreshold": max(12, int((resource_catalog[idx % len(resource_catalog)]["base"] + (idx % 6) * 25) * 0.2)),
                "unit": resource_catalog[idx % len(resource_catalog)]["unit"],
                "createdAt": now - timedelta(days=idx % 20),
                "updatedAt": now - timedelta(days=idx % 7),
            }
            for idx in range(resource_count)
        ],
        force=seed_force,
    )

    equipment_catalog = [
        {"name": "MRI Scanner", "category": "Imaging", "base": 4},
        {"name": "CT Scanner", "category": "Imaging", "base": 3},
        {"name": "Ventilators", "category": "ICU", "base": 48},
        {"name": "ECG Machines", "category": "Cardiology", "base": 18},
        {"name": "Ultrasound", "category": "Imaging", "base": 12},
        {"name": "Infusion Pumps", "category": "ICU", "base": 36},
    ]
    equipment_count = 30
    counts["equipment"] = await _seed_collection(
        equipment_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "name": f"{equipment_catalog[idx % len(equipment_catalog)]['name']} {idx + 1}",
                "category": equipment_catalog[idx % len(equipment_catalog)]["category"],
                "quantity": equipment_catalog[idx % len(equipment_catalog)]["base"] + (idx % 4),
                "status": "Available" if idx % 6 != 0 else "Maintenance",
                "minThreshold": max(1, int(equipment_catalog[idx % len(equipment_catalog)]["base"] * 0.2)),
                "createdAt": now - timedelta(days=idx % 60),
                "updatedAt": now - timedelta(days=idx % 20),
            }
            for idx in range(equipment_count)
        ],
        force=seed_force,
    )

    vendor_count = 15
    counts["vendors"] = await _seed_collection(
        vendor_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "resourceName": resource_catalog[idx % len(resource_catalog)]["name"],
                "category": resource_catalog[idx % len(resource_catalog)]["category"],
                "vendorName": f"Vendor {idx + 1}",
                "leadTimeDays": 4 + (idx % 10),
                "createdAt": now - timedelta(days=idx % 30),
                "updatedAt": now - timedelta(days=idx % 12),
            }
            for idx in range(vendor_count)
        ],
        force=seed_force,
    )

    allocation_count = int(seed_scale * 0.35)
    bed_types = ["ICU", "Emergency", "General", "Ward"]
    counts["allocations"] = await _seed_collection(
        allocation_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patientName": f"Patient {idx + 1}",
                "bedType": bed_types[idx % len(bed_types)],
                "status": "Assigned" if idx % 6 != 0 else "Waiting",
                "notes": "Auto allocation",
                "createdAt": now - timedelta(hours=idx % 96),
                "updatedAt": now - timedelta(hours=idx % 48),
            }
            for idx in range(allocation_count)
        ],
        force=seed_force,
    )

    report_templates = _report_templates()
    ingested_reports = [
        "Vendor Audit Notes",
        "Patient Feedback Digest",
        "Safety Drill Summary",
        "Clinical Quality Review",
        "Supply Chain Risk",
        "Ambulance KPI Snapshot",
    ]
    counts["reports"] = await _seed_collection(
        report_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "reportKey": template["key"],
                "name": template["name"],
                "status": "Ready",
                "generatedAt": now - timedelta(days=idx + 1),
                "content": f"{template['name']} content.",
                "summary": f"{template['name']} summary.",
                "createdAt": now - timedelta(days=idx + 1),
                "updatedAt": now - timedelta(days=idx + 1),
            }
            for idx, template in enumerate(report_templates)
        ]
        + [
            {
                "hospital": hospital_oid,
                "reportKey": "ingested",
                "name": name,
                "category": "Quality" if idx % 2 == 0 else "Compliance",
                "status": "Ready",
                "generatedAt": now - timedelta(days=idx + 1),
                "content": f"{name} content.",
                "summary": f"{name} summary.",
                "createdAt": now - timedelta(days=idx + 1),
                "updatedAt": now - timedelta(days=idx + 1),
            }
            for idx, name in enumerate(ingested_reports)
        ],
        force=seed_force,
    )

    expense_categories = ["Supplies", "Equipment", "Staffing", "Facilities", "IT", "Logistics"]
    expense_count = int(seed_scale * 0.6)
    counts["expenses"] = await _seed_collection(
        expense_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "category": expense_categories[idx % len(expense_categories)],
                "amount": 18000 + (idx % 12) * 3200,
                "notes": "Monthly expense",
                "vendor": f"Vendor {idx % 15 + 1}",
                "contractRef": f"CN-{2024 + (idx % 2)}-{100 + idx}",
                "createdAt": now - timedelta(days=idx % 60),
                "updatedAt": now - timedelta(days=idx % 30),
            }
            for idx in range(expense_count)
        ],
        force=seed_force,
    )

    claim_count = int(seed_scale * 0.7)
    counts["claims"] = await _seed_collection(
        claim_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "invoiceId": f"INV-{1000 + idx}",
                "insurer": "Star Health" if idx % 2 == 0 else "Care Plus",
                "amount": 28000 + (idx % 10) * 2600,
                "status": "Approved" if idx % 4 == 0 else "Submitted",
                "approvedAmount": float(26000 + (idx % 10) * 2400) if idx % 4 == 0 else 0.0,
                "submittedAt": (now - timedelta(days=idx % 45)).isoformat(),
                "paidAt": (now - timedelta(days=idx % 30)).isoformat() if idx % 4 == 0 else None,
                "createdAt": now - timedelta(days=idx % 45),
                "updatedAt": now - timedelta(days=idx % 20),
            }
            for idx in range(claim_count)
        ],
        force=seed_force,
    )

    appointment_count = seed_scale
    appointment_types = ["New", "Follow-up", "Consultation"]
    channels = ["Online", "Walk-in", "Referral"]
    counts["opd_appointments"] = await _seed_collection(
        opd_appt_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patient": f"Patient {idx + 1}",
                "doctor": f"Dr. {departments[idx % len(departments)]} Lead",
                "time": (now + timedelta(days=idx % 21, hours=8 + (idx % 8))).isoformat(),
                "status": "Scheduled" if idx % 6 != 0 else "Completed",
                "appointmentType": appointment_types[idx % len(appointment_types)],
                "channel": channels[idx % len(channels)],
                "expectedDurationMinutes": 15 + (idx % 4) * 10,
                "reason": "Routine check",
                "notes": "Auto generated",
                "seasonTag": _season_tag(now),
                "slotHour": (now + timedelta(days=idx % 21, hours=8 + (idx % 8))).hour,
                "createdAt": now - timedelta(hours=idx % 72),
                "updatedAt": now - timedelta(hours=idx % 36),
            }
            for idx in range(appointment_count)
        ],
        force=seed_force,
    )

    doctor_count = 48
    counts["opd_doctors"] = await _seed_collection(
        opd_doctor_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "name": f"Dr. OPD {idx + 1}",
                "specialty": departments[idx % len(departments)],
                "availability": idx % 5 != 0,
                "shift": shifts[idx % len(shifts)],
                "schedule": "Mon-Sat",
                "normalizedShift": shifts[idx % len(shifts)],
                "createdAt": now - timedelta(days=idx % 14),
                "updatedAt": now - timedelta(days=idx % 7),
            }
            for idx in range(doctor_count)
        ],
        force=seed_force,
    )

    queue_count = int(seed_scale * 0.6)
    queue_statuses = ["Waiting", "In Service", "Completed"]
    counts["opd_queue"] = await _seed_collection(
        opd_queue_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patientName": f"Patient {idx + 1}",
                "reason": "General check",
                "priority": "High" if idx % 7 == 0 else "Normal",
                "status": queue_statuses[idx % len(queue_statuses)],
                "assignedDoctor": f"Dr. OPD {(idx % doctor_count) + 1}",
                "notes": "Queue flow",
                "checkInAt": now - timedelta(minutes=idx % 180),
                "serviceStartedAt": now - timedelta(minutes=idx % 90) if idx % 3 == 0 else None,
                "createdAt": now - timedelta(minutes=idx % 180),
                "updatedAt": now - timedelta(minutes=idx % 60),
            }
            for idx in range(queue_count)
        ],
        force=seed_force,
    )

    consult_count = int(seed_scale * 0.7)
    counts["opd_consults"] = await _seed_collection(
        opd_consult_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patient": f"Patient {idx + 1}",
                "doctor": f"Dr. OPD {(idx % doctor_count) + 1}",
                "notes": "Clinical notes summary.",
                "date": (now - timedelta(days=idx % 30)).date().isoformat(),
                "status": "Closed" if idx % 4 == 0 else "Open",
                "summary": "Consultation summary.",
                "aiSummary": "Follow-up in 2 weeks.",
                "keywords": ["follow-up", "review"],
                "followUpPlan": "Schedule follow-up",
                "followUpDate": (now + timedelta(days=idx % 14)).date().isoformat(),
                "createdAt": now - timedelta(days=idx % 30),
                "updatedAt": now - timedelta(days=idx % 15),
            }
            for idx in range(consult_count)
        ],
        force=seed_force,
    )

    icu_patient_count = int(seed_scale * 0.2)
    counts["icu_patients"] = await _seed_collection(
        icu_patient_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "name": f"ICU Patient {idx + 1}",
                "oxygen": 90 + (idx % 8),
                "heartRate": 84 + (idx % 40),
                "bp": f"{110 + (idx % 20)}/{70 + (idx % 15)}",
                "status": "Critical" if idx % 5 == 0 else "Stable",
                "createdAt": now - timedelta(hours=idx % 120),
                "updatedAt": now - timedelta(hours=idx % 60),
            }
            for idx in range(icu_patient_count)
        ],
        force=seed_force,
    )

    icu_alert_count = int(seed_scale * 0.15)
    icu_alert_levels = ["High", "Medium", "Low"]
    counts["icu_alerts"] = await _seed_collection(
        icu_alert_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "message": f"Vitals fluctuation {idx + 1}",
                "severity": icu_alert_levels[idx % len(icu_alert_levels)],
                "status": "Active" if idx % 3 != 0 else "Resolved",
                "createdAt": now - timedelta(hours=idx % 48),
                "updatedAt": now - timedelta(hours=idx % 24),
            }
            for idx in range(icu_alert_count)
        ],
        force=seed_force,
    )

    radiology_request_count = int(seed_scale * 0.55)
    scan_types = ["CT", "MRI", "X-Ray", "Ultrasound"]
    counts["radiology_requests"] = await _seed_collection(
        radiology_request_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patient": f"Patient {idx + 1}",
                "scan": f"{scan_types[idx % len(scan_types)]} Scan",
                "status": "Queued" if idx % 4 != 0 else "In Progress",
                "createdAt": now - timedelta(hours=idx % 72),
                "updatedAt": now - timedelta(hours=idx % 48),
            }
            for idx in range(radiology_request_count)
        ],
        force=seed_force,
    )

    radiology_report_count = int(seed_scale * 0.4)
    counts["radiology_reports"] = await _seed_collection(
        radiology_report_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patient": f"Patient {idx + 1}",
                "scan": f"{scan_types[idx % len(scan_types)]} Scan",
                "fileName": f"scan_{idx + 1}.pdf",
                "notes": "No acute findings",
                "status": "Uploaded",
                "createdAt": now - timedelta(hours=idx % 60),
                "updatedAt": now - timedelta(hours=idx % 36),
            }
            for idx in range(radiology_report_count)
        ],
        force=seed_force,
    )

    surgery_count = int(seed_scale * 0.5)
    procedures = ["Ortho Fixation", "Cardiac Cath", "Neuro Observation", "General Surgery"]
    counts["ot_surgeries"] = await _seed_collection(
        ot_surgery_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "patient": f"Patient {idx + 1}",
                "procedure": procedures[idx % len(procedures)],
                "time": (now + timedelta(hours=idx % 36)).isoformat(),
                "status": "Scheduled" if idx % 5 != 0 else "Completed",
                "createdAt": now - timedelta(hours=idx % 48),
                "updatedAt": now - timedelta(hours=idx % 24),
            }
            for idx in range(surgery_count)
        ],
        force=seed_force,
    )

    ot_alloc_count = int(seed_scale * 0.35)
    patient_loads = ["High", "Medium", "Low"]
    counts["ot_allocations"] = await _seed_collection(
        ot_alloc_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "department": departments[idx % len(departments)],
                "patient_load": patient_loads[idx % len(patient_loads)],
                "shift": shifts[idx % len(shifts)],
                "allocation_decision": "Auto scheduled OT team",
                "createdAt": now - timedelta(hours=idx % 60),
                "updatedAt": now - timedelta(hours=idx % 36),
            }
            for idx in range(ot_alloc_count)
        ],
        force=seed_force,
    )

    counts["benchmarks"] = await _seed_collection(
        benchmark_repo,
        {"region": "global"},
        [
            {"region": "global", "metric": "avg_occupancy", "value": 79.5, "source": "ops_feed", "createdAt": now - timedelta(days=7)},
            {"region": "global", "metric": "avg_wait_minutes", "value": 26.4, "source": "ops_feed", "createdAt": now - timedelta(days=7)},
            {"region": "global", "metric": "staff_coverage", "value": 86.9, "source": "ops_feed", "createdAt": now - timedelta(days=7)},
            {"region": "global", "metric": "opd_utilization", "value": 72.3, "source": "ops_feed", "createdAt": now - timedelta(days=7)},
        ],
        force=seed_force,
    )

    ambulance_count = 24
    counts["ambulances"] = await _seed_collection(
        ambulance_repo,
        {"hospital": hospital_oid},
        [
            {
                "ambulanceId": f"AMB-{100 + idx}",
                "registrationNumber": f"KA-01-AA-{1000 + idx}",
                "hospital": hospital_oid,
                "status": "available" if idx % 4 != 0 else "en_route",
                "driver": {
                    "name": f"Driver {idx + 1}",
                    "licenseNumber": f"DL-{2000 + idx}",
                    "phone": f"900000{idx:04d}",
                    "availability": idx % 4 != 0,
                },
                "metrics": {
                    "averageResponseTime": 8 + (idx % 6),
                    "onTimeDeliveryRate": 90 + (idx % 8),
                    "totalTripsToday": 3 + (idx % 6),
                    "totalDistanceTodayKm": round(30 + (idx % 12) * 3.2, 1),
                },
                "createdAt": now - timedelta(days=idx % 10),
                "updatedAt": now - timedelta(days=idx % 4),
            }
            for idx in range(ambulance_count)
        ],
        force=seed_force,
    )

    alert_count = 40
    counts["alerts"] = await _seed_collection(
        alert_repo,
        {"hospitalId": hospital_id},
        [
            {
                "hospitalId": hospital_id,
                "message": f"Operational alert {idx + 1}",
                "priority": "High" if idx % 5 == 0 else "Medium",
                "status": "pending" if idx % 4 != 0 else "resolved",
                "createdAt": now - timedelta(hours=idx % 72),
                "updatedAt": now - timedelta(hours=idx % 36),
            }
            for idx in range(alert_count)
        ],
        force=seed_force,
    )

    analytics_count = 90
    analytics_types = ["bed_forecast", "staff_load", "er_wait", "supply_risk", "opd_demand"]
    counts["analytics_events"] = await _seed_collection(
        analytics_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "eventType": analytics_types[idx % len(analytics_types)],
                "value": round(0.4 + (idx % 10) * 0.05, 2),
                "createdAt": now - timedelta(hours=idx % 120),
                "updatedAt": now - timedelta(hours=idx % 60),
            }
            for idx in range(analytics_count)
        ],
        force=seed_force,
    )

    prediction_count = 120
    prediction_models = ["icu_risk", "opd_no_show", "readmission", "supply_runout"]
    counts["predictions"] = await _seed_collection(
        prediction_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "risk_score": round(0.2 + (idx % 15) * 0.05, 2),
                "model": prediction_models[idx % len(prediction_models)],
                "createdAt": now - timedelta(hours=idx % 96),
                "updatedAt": now - timedelta(hours=idx % 48),
            }
            for idx in range(prediction_count)
        ],
        force=seed_force,
    )

    counts["departments"] = await _seed_collection(
        dept_repo,
        {"hospital": hospital_oid},
        [
            {
                "hospital": hospital_oid,
                "name": dept,
                "createdAt": now - timedelta(days=idx % 14),
                "updatedAt": now - timedelta(days=idx % 7),
            }
            for idx, dept in enumerate(departments)
        ],
        force=seed_force,
    )

    message_count = 10
    counts["messages"] = await _seed_collection(
        message_repo,
        {"fromHospital": hospital_doc.get("_id")},
        [
            {
                "fromHospital": hospital_doc.get("_id"),
                "toHospital": hospital_doc.get("_id"),
                "messageType": "resource",
                "subject": f"Resource request {idx + 1}",
                "details": "Requesting supplies.",
                "requestDetails": {
                    "urgencyLevel": "medium",
                    "resourceName": resource_catalog[idx % len(resource_catalog)]["name"],
                    "resourceQuantity": 8 + (idx % 10),
                },
                "status": "pending" if idx % 3 != 0 else "approved",
                "createdAt": now - timedelta(days=idx % 10),
                "updatedAt": now - timedelta(days=idx % 5),
            }
            for idx in range(message_count)
        ],
        force=seed_force,
    )

    agreement_count = 6
    counts["agreements"] = await _seed_collection(
        agreement_repo,
        {"hospital": hospital_doc.get("_id")},
        [
            {
                "hospital": hospital_doc.get("_id"),
                "partner": hospital_doc.get("_id"),
                "dataTypes": ["beds", "resources", "staff"],
                "status": "active",
                "createdAt": now - timedelta(days=idx % 20),
                "updatedAt": now - timedelta(days=idx % 10),
            }
            for idx in range(agreement_count)
        ],
        force=seed_force,
    )

    return {
        "seeded": True,
        "version": SEED_VERSION,
        "hospitalId": str(hospital_doc.get("_id")),
        "counts": counts,
    }


async def _ensure_seeded(db, hospital_id: str) -> None:
    try:
        await _ensure_hospital_ops_seed(db, hospital_id, scale=300)
    except HTTPException:
        return


def _report_templates() -> list[dict[str, str]]:
    return [
        {"key": "weekly-ops", "name": "Weekly Operations Summary"},
        {"key": "icu-performance", "name": "ICU Performance Review"},
        {"key": "finance-snapshot", "name": "Finance Snapshot"},
    ]


def _summarize_report_text(content: str) -> str:
    content = (content or "").strip()
    if not content:
        return "Summary unavailable."
    sentences = content.split(".")
    summary = ".".join(sentences[:2]).strip()
    if summary:
        return summary + "."
    return content[:240]


def _month_key(target: datetime) -> str:
    return target.strftime("%Y-%m")


@router.post("/preload")
async def preload_hospital_ops(payload: dict = Body(default_factory=dict)):
    hospital_id = payload.get("hospitalId")
    if not hospital_id:
        raise HTTPException(status_code=400, detail="hospitalId is required")
    force = bool(payload.get("force"))
    scale = payload.get("scale")
    db = get_db()
    return await _ensure_hospital_ops_seed(db, hospital_id, force=force, scale=scale)


async def _compute_finance_summary(invoice_repo, expense_repo, claim_repo, hospital_oid: ObjectId) -> dict[str, Any]:
    invoices = await invoice_repo.find_many({"hospital": hospital_oid}, limit=500)
    expenses = await expense_repo.find_many({"hospital": hospital_oid}, limit=300)
    claims = await claim_repo.find_many({"hospital": hospital_oid}, limit=300)

    dept_breakdown: dict[str, float] = {}
    total_revenue = 0.0
    for inv in invoices:
        amount = float(inv.get("amount") or 0)
        total_revenue += amount
        dept = inv.get("department") or "General"
        dept_breakdown[dept] = dept_breakdown.get(dept, 0) + amount

    total_expenses = sum(float(exp.get("amount") or 0) for exp in expenses)
    profit = total_revenue - total_expenses

    expense_by_category: dict[str, float] = {}
    for exp in expenses:
        category = exp.get("category") or "General"
        expense_by_category[category] = expense_by_category.get(category, 0) + float(exp.get("amount") or 0)

    payer_delays = []
    for claim in claims:
        submitted_at = claim.get("submittedAt")
        paid_at = claim.get("paidAt")
        if isinstance(submitted_at, str):
            try:
                submitted_at = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
            except ValueError:
                submitted_at = None
        if isinstance(paid_at, str):
            try:
                paid_at = datetime.fromisoformat(paid_at.replace("Z", "+00:00"))
            except ValueError:
                paid_at = None
        if isinstance(submitted_at, datetime) and isinstance(paid_at, datetime):
            payer_delays.append((paid_at - submitted_at).days)

    avg_payer_delay = round(sum(payer_delays) / max(1, len(payer_delays)), 1) if payer_delays else 0.0
    delinquent = len([d for d in payer_delays if d > 30])

    daily_series = []
    for day_offset in range(6, -1, -1):
        day = datetime.utcnow() - timedelta(days=day_offset)
        day_key = day.date().isoformat()
        total = 0.0
        for inv in invoices:
            created_at = inv.get("createdAt")
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if isinstance(created_at, datetime) and created_at.date().isoformat() == day_key:
                total += float(inv.get("amount") or 0)
        daily_series.append({"label": day.strftime("%a"), "value": round(total, 2), "dayKey": day_key})

    monthly_series = []
    for month_offset in range(5, -1, -1):
        target = datetime.utcnow().replace(day=1)
        month = (target.month - month_offset - 1) % 12 + 1
        year = target.year + ((target.month - month_offset - 1) // 12)
        total = 0.0
        for inv in invoices:
            created_at = inv.get("createdAt")
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if isinstance(created_at, datetime) and created_at.year == year and created_at.month == month:
                total += float(inv.get("amount") or 0)
        month_label = datetime(year, month, 1).strftime("%b")
        monthly_series.append({"label": month_label, "value": round(total, 2), "monthKey": f"{year:04d}-{month:02d}"})

    fraud_alerts = []
    avg_invoice = total_revenue / max(1, len(invoices))
    for inv in invoices:
        if float(inv.get("amount") or 0) > avg_invoice * 2.5:
            fraud_alerts.append(f"Invoice {inv.get('_id')} exceeds expected amount")

    return {
        "totalRevenue": round(total_revenue, 2),
        "totalExpenses": round(total_expenses, 2),
        "profit": round(profit, 2),
        "departmentBreakdown": [{"department": k, "amount": round(v, 2)} for k, v in dept_breakdown.items()],
        "expenseBreakdown": [{"category": k, "amount": round(v, 2)} for k, v in expense_by_category.items()],
        "dailySeries": daily_series,
        "monthlySeries": monthly_series,
        "fraudAlerts": fraud_alerts,
        "payerDelayDays": avg_payer_delay,
        "delinquentPayers": delinquent,
    }


@router.get("/opd/appointments")
async def list_opd_appointments(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    appointmentType: str | None = Query(None),
    channel: str | None = Query(None),
    season: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OPD_APPOINTMENTS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patient", "doctor", "reason", "notes", "appointmentType", "channel"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if appointmentType:
        query["appointmentType"] = appointmentType
    if channel:
        query["channel"] = channel
    if season:
        query["seasonTag"] = season
    sort = _build_sort(
        sort_by,
        sort_dir,
        {"createdAt", "updatedAt", "time", "status", "patient", "doctor", "appointmentType", "channel"},
        "createdAt",
    )
    records = await repo.find_many(query, sort=sort, limit=200)
    for record in records:
        if not record.get("seasonTag") or record.get("slotHour") is None:
            appt_time = _parse_datetime(record.get("time"))
            record["seasonTag"] = record.get("seasonTag") or _season_tag(appt_time)
            if appt_time:
                record["slotHour"] = appt_time.hour
    return {"count": len(records), "data": records}


@router.get("/opd/appointments/insights")
async def opd_appointment_insights(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OPD_APPOINTMENTS)
    oid = _require_hospital_id(hospitalId)
    records = await repo.find_many({"hospital": oid}, sort=[("createdAt", -1)], limit=500)

    now = datetime.utcnow()
    horizon_7 = now + timedelta(days=7)
    horizon_30 = now + timedelta(days=30)

    weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_counts = {day: 0 for day in weekday_order}
    season_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    hour_counts: dict[int, int] = {}
    next_7 = 0
    next_30 = 0

    for record in records:
        appt_time = _parse_datetime(record.get("time"))
        if appt_time:
            if now <= appt_time <= horizon_7:
                next_7 += 1
            if now <= appt_time <= horizon_30:
                next_30 += 1
            weekday_counts[appt_time.strftime("%a")] = weekday_counts.get(appt_time.strftime("%a"), 0) + 1
            hour_counts[appt_time.hour] = hour_counts.get(appt_time.hour, 0) + 1
            season = record.get("seasonTag") or _season_tag(appt_time) or "Unknown"
            season_counts[season] = season_counts.get(season, 0) + 1
        channel = record.get("channel") or "Walk-in"
        channel_counts[channel] = channel_counts.get(channel, 0) + 1
        appointment_type = record.get("appointmentType") or "New"
        type_counts[appointment_type] = type_counts.get(appointment_type, 0) + 1

    peak_day = max(weekday_counts.items(), key=lambda item: item[1])[0] if records else "Mon"
    peak_hour = max(hour_counts.items(), key=lambda item: item[1])[0] if hour_counts else None
    season_coverage_score = round((len([count for count in season_counts.values() if count > 0]) / 4) * 100) if records else 0
    demand_score = min(100, (len(records) * 4) + (next_7 * 6)) if records else 0

    return {
        "totalAppointments": len(records),
        "next7Days": next_7,
        "next30Days": next_30,
        "peakDay": peak_day,
        "peakHour": peak_hour,
        "demandScore": demand_score,
        "seasonCoverageScore": season_coverage_score,
        "weekdayVolume": [{"label": day, "value": weekday_counts.get(day, 0)} for day in weekday_order],
        "seasonCoverage": [{"label": season, "value": count} for season, count in season_counts.items()],
        "channelMix": [{"label": channel, "value": count} for channel, count in channel_counts.items()],
        "appointmentTypeMix": [{"label": key, "value": value} for key, value in type_counts.items()],
    }


@router.post("/opd/appointments", status_code=201)
async def create_opd_appointment(payload: OpdAppointmentCreate):
    db = get_db()
    repo = MongoRepository(db, OPD_APPOINTMENTS)
    oid = _require_hospital_id(payload.hospitalId)
    appt_time = _parse_datetime(payload.time)
    season_tag = _season_tag(appt_time)
    doc = {
        "hospital": oid,
        "patient": payload.patient,
        "doctor": payload.doctor,
        "time": payload.time,
        "status": payload.status or "Scheduled",
        "appointmentType": payload.appointmentType or "New",
        "channel": payload.channel or "Walk-in",
        "expectedDurationMinutes": payload.expectedDurationMinutes or 20,
        "reason": payload.reason,
        "notes": payload.notes,
        "seasonTag": season_tag,
        "slotHour": appt_time.hour if appt_time else None,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/opd/appointments/{appointment_id}")
async def update_opd_appointment(appointment_id: str, payload: OpdAppointmentUpdate):
    db = get_db()
    repo = MongoRepository(db, OPD_APPOINTMENTS)
    oid = _as_object_id(appointment_id)
    update_data = _build_update(
        payload,
        ["patient", "doctor", "time", "status", "appointmentType", "channel", "expectedDurationMinutes", "reason", "notes"],
    )
    if payload.time:
        appt_time = _parse_datetime(payload.time)
        update_data["seasonTag"] = _season_tag(appt_time)
        update_data["slotHour"] = appt_time.hour if appt_time else None
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return updated


@router.delete("/opd/appointments/{appointment_id}")
async def delete_opd_appointment(appointment_id: str):
    db = get_db()
    repo = MongoRepository(db, OPD_APPOINTMENTS)
    oid = _as_object_id(appointment_id)
    deleted = await repo.delete_one({"_id": oid})
    if not deleted:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"status": "ok"}


@router.get("/opd/doctors")
async def list_opd_doctors(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    specialty: str | None = Query(None),
    availability: bool | None = Query(None),
    shift: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OPD_DOCTORS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["name", "specialty", "schedule", "shift", "normalizedShift"])
    if search_query:
        query.update(search_query)
    if specialty:
        query["specialty"] = specialty
    if availability is not None:
        query["availability"] = availability
    if shift:
        query["normalizedShift"] = shift
    sort = _build_sort(
        sort_by,
        sort_dir,
        {"createdAt", "updatedAt", "name", "specialty", "availability", "normalizedShift"},
        "createdAt",
    )
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.get("/opd/doctors/coverage")
async def opd_doctor_coverage(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OPD_DOCTORS)
    oid = _require_hospital_id(hospitalId)
    records = await repo.find_many({"hospital": oid}, sort=[("createdAt", -1)], limit=200)
    hospital_doc = await _resolve_hospital_doc(db, hospitalId)
    expected_specialties = list({*([doc.get("specialty") for doc in records if doc.get("specialty")])})
    if hospital_doc and hospital_doc.get("specialties"):
        expected_specialties = list({*expected_specialties, *hospital_doc.get("specialties")})

    by_specialty: dict[str, int] = {}
    by_shift: dict[str, int] = {}
    available_count = 0
    available_by_specialty: dict[str, int] = {}

    for record in records:
        specialty = record.get("specialty") or "General"
        by_specialty[specialty] = by_specialty.get(specialty, 0) + 1
        if record.get("availability") is not False:
            available_count += 1
            available_by_specialty[specialty] = available_by_specialty.get(specialty, 0) + 1
        shift = record.get("normalizedShift") or record.get("shift") or "Unassigned"
        by_shift[shift] = by_shift.get(shift, 0) + 1

    coverage_gaps = [spec for spec in expected_specialties if by_specialty.get(spec, 0) == 0]
    availability_rate = round((available_count / max(1, len(records))) * 100, 1) if records else 0

    return {
        "total": len(records),
        "available": available_count,
        "availabilityRate": availability_rate,
        "specialtyCoverage": [
            {
                "specialty": spec,
                "total": by_specialty.get(spec, 0),
                "available": available_by_specialty.get(spec, 0),
            }
            for spec in expected_specialties
        ],
        "shiftCoverage": [{"shift": shift, "count": count} for shift, count in by_shift.items()],
        "coverageGaps": coverage_gaps,
    }


@router.post("/opd/doctors", status_code=201)
async def create_opd_doctor(payload: OpdDoctorCreate):
    db = get_db()
    repo = MongoRepository(db, OPD_DOCTORS)
    oid = _require_hospital_id(payload.hospitalId)
    normalized_shift = _normalize_shift(payload.shift, payload.schedule)
    doc = {
        "hospital": oid,
        "name": payload.name,
        "specialty": payload.specialty,
        "availability": payload.availability if payload.availability is not None else True,
        "shift": payload.shift or normalized_shift,
        "schedule": payload.schedule,
        "normalizedShift": normalized_shift,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/opd/doctors/{doctor_id}")
async def update_opd_doctor(doctor_id: str, payload: OpdDoctorUpdate):
    db = get_db()
    repo = MongoRepository(db, OPD_DOCTORS)
    oid = _as_object_id(doctor_id)
    update_data = _build_update(payload, ["name", "specialty", "availability", "shift", "schedule"])
    if payload.shift is not None or payload.schedule is not None:
        update_data["normalizedShift"] = _normalize_shift(payload.shift, payload.schedule)
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return updated


@router.delete("/opd/doctors/{doctor_id}")
async def delete_opd_doctor(doctor_id: str):
    db = get_db()
    repo = MongoRepository(db, OPD_DOCTORS)
    oid = _as_object_id(doctor_id)
    deleted = await repo.delete_one({"_id": oid})
    if not deleted:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {"status": "ok"}


@router.get("/opd/consultations")
async def list_opd_consultations(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OPD_CONSULTATIONS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patient", "doctor", "notes", "summary", "status", "aiSummary"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    sort = _build_sort(
        sort_by,
        sort_dir,
        {"createdAt", "updatedAt", "date", "status", "patient", "doctor"},
        "createdAt",
    )
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.get("/opd/consultations/insights")
async def opd_consultation_insights(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OPD_CONSULTATIONS)
    oid = _require_hospital_id(hospitalId)
    records = await repo.find_many({"hospital": oid}, sort=[("createdAt", -1)], limit=400)

    summary_count = 0
    follow_up_count = 0
    keyword_counts: dict[str, int] = {}

    for record in records:
        summary = record.get("aiSummary") or record.get("summary")
        if summary:
            summary_count += 1
        follow_plan = record.get("followUpPlan") or ""
        if follow_plan and follow_plan != "No follow-up flagged":
            follow_up_count += 1
        for keyword in record.get("keywords") or []:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

    top_keywords = sorted(keyword_counts.items(), key=lambda item: item[1], reverse=True)[:6]
    coverage_rate = round((summary_count / max(1, len(records))) * 100, 1) if records else 0

    return {
        "total": len(records),
        "summaryCoverage": coverage_rate,
        "followUps": follow_up_count,
        "topKeywords": [{"label": key, "value": value} for key, value in top_keywords],
    }


@router.post("/opd/consultations", status_code=201)
async def create_opd_consultation(payload: OpdConsultationCreate):
    db = get_db()
    repo = MongoRepository(db, OPD_CONSULTATIONS)
    oid = _require_hospital_id(payload.hospitalId)
    summary = payload.summary or _summarize_note(payload.notes)
    ai_summary = payload.aiSummary or summary
    keywords = payload.keywords or _extract_keywords(payload.notes)
    follow_up = payload.followUpPlan or _follow_up_plan(payload.notes)
    doc = {
        "hospital": oid,
        "patient": payload.patient,
        "doctor": payload.doctor,
        "notes": payload.notes,
        "date": payload.date or datetime.utcnow().date().isoformat(),
        "status": payload.status or "Open",
        "summary": summary,
        "aiSummary": ai_summary,
        "keywords": keywords,
        "followUpPlan": follow_up,
        "followUpDate": payload.followUpDate,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/opd/consultations/{consultation_id}")
async def update_opd_consultation(consultation_id: str, payload: OpdConsultationUpdate):
    db = get_db()
    repo = MongoRepository(db, OPD_CONSULTATIONS)
    oid = _as_object_id(consultation_id)
    update_data = _build_update(
        payload,
        ["patient", "doctor", "notes", "date", "status", "summary", "aiSummary", "keywords", "followUpPlan", "followUpDate"],
    )
    if payload.notes is not None:
        summary = _summarize_note(payload.notes)
        update_data.setdefault("summary", summary)
        update_data.setdefault("aiSummary", summary)
        update_data.setdefault("keywords", _extract_keywords(payload.notes))
        update_data.setdefault("followUpPlan", _follow_up_plan(payload.notes))
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return updated


@router.delete("/opd/consultations/{consultation_id}")
async def delete_opd_consultation(consultation_id: str):
    db = get_db()
    repo = MongoRepository(db, OPD_CONSULTATIONS)
    oid = _as_object_id(consultation_id)
    deleted = await repo.delete_one({"_id": oid})
    if not deleted:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return {"status": "ok"}


@router.get("/icu/patients")
async def list_icu_patients(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, ICU_PATIENTS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["name", "status", "bp"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    sort = _build_sort(
        sort_by,
        sort_dir,
        {"createdAt", "updatedAt", "name", "oxygen", "heartRate", "status"},
        "createdAt",
    )
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/icu/patients", status_code=201)
async def create_icu_patient(payload: IcuPatientCreate):
    db = get_db()
    repo = MongoRepository(db, ICU_PATIENTS)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "name": payload.name,
        "oxygen": payload.oxygen,
        "heartRate": payload.heartRate,
        "bp": payload.bp,
        "status": payload.status or "Stable",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/icu/patients/{patient_id}")
async def update_icu_patient(patient_id: str, payload: IcuPatientUpdate):
    db = get_db()
    repo = MongoRepository(db, ICU_PATIENTS)
    oid = _as_object_id(patient_id)
    update_data = _build_update(payload, ["name", "oxygen", "heartRate", "bp", "status"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="ICU patient not found")
    return updated


@router.get("/icu/alerts")
async def list_icu_alerts(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, ICU_ALERTS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["message", "severity", "status"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "severity", "status"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/icu/alerts", status_code=201)
async def create_icu_alert(payload: IcuAlertCreate):
    db = get_db()
    repo = MongoRepository(db, ICU_ALERTS)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "message": payload.message,
        "severity": payload.severity,
        "status": payload.status or "Active",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/icu/alerts/{alert_id}")
async def update_icu_alert(alert_id: str, payload: IcuAlertUpdate):
    db = get_db()
    repo = MongoRepository(db, ICU_ALERTS)
    oid = _as_object_id(alert_id)
    update_data = _build_update(payload, ["message", "severity", "status"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="ICU alert not found")
    return updated


@router.get("/icu/vitals")
async def icu_vitals(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, ICU_PATIENTS)
    oid = _require_hospital_id(hospitalId)
    records = await repo.find_many({"hospital": oid}, limit=200)

    if not records:
        return {
            "average_oxygen": 0,
            "average_heart_rate": 0,
            "critical_patients": 0,
            "patient_count": 0,
        }

    total_oxygen = 0
    total_hr = 0
    critical = 0
    count = 0

    for record in records:
        try:
            total_oxygen += int(record.get("oxygen") or 0)
        except (TypeError, ValueError):
            total_oxygen += 0
        try:
            total_hr += int(record.get("heartRate") or 0)
        except (TypeError, ValueError):
            total_hr += 0
        if (record.get("status") or "").lower() == "critical":
            critical += 1
        count += 1

    return {
        "average_oxygen": round(total_oxygen / count),
        "average_heart_rate": round(total_hr / count),
        "critical_patients": critical,
        "patient_count": count,
    }


@router.get("/radiology/requests")
async def list_radiology_requests(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, RADIOLOGY_REQUESTS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patient", "scan", "status"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "patient", "scan", "status"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/radiology/requests", status_code=201)
async def create_radiology_request(payload: RadiologyRequestCreate):
    db = get_db()
    repo = MongoRepository(db, RADIOLOGY_REQUESTS)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "patient": payload.patient,
        "scan": payload.scan,
        "status": payload.status or "Queued",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/radiology/requests/{request_id}")
async def update_radiology_request(request_id: str, payload: RadiologyRequestUpdate):
    db = get_db()
    repo = MongoRepository(db, RADIOLOGY_REQUESTS)
    oid = _as_object_id(request_id)
    update_data = _build_update(payload, ["status"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Radiology request not found")
    return updated


@router.get("/radiology/reports")
async def list_radiology_reports(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, RADIOLOGY_REPORTS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patient", "scan", "status", "fileName"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "patient", "scan", "status"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/radiology/reports", status_code=201)
async def create_radiology_report(payload: RadiologyReportCreate):
    db = get_db()
    repo = MongoRepository(db, RADIOLOGY_REPORTS)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "patient": payload.patient,
        "scan": payload.scan,
        "fileName": payload.fileName,
        "notes": payload.notes,
        "status": payload.status or "Uploaded",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.get("/ot/surgeries")
async def list_ot_surgeries(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OT_SURGERIES)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patient", "procedure", "status"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "time", "status", "patient", "procedure"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/ot/surgeries", status_code=201)
async def create_ot_surgery(payload: OTSurgeryCreate):
    db = get_db()
    repo = MongoRepository(db, OT_SURGERIES)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "patient": payload.patient,
        "procedure": payload.procedure,
        "time": payload.time,
        "status": payload.status or "Scheduled",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/ot/surgeries/{surgery_id}")
async def update_ot_surgery(surgery_id: str, payload: OTSurgeryUpdate):
    db = get_db()
    repo = MongoRepository(db, OT_SURGERIES)
    oid = _as_object_id(surgery_id)
    update_data = _build_update(payload, ["patient", "procedure", "time", "status"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Surgery not found")
    return updated


@router.get("/ot/allocations")
async def list_ot_allocations(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    department: str | None = Query(None),
    patient_load: str | None = Query(None),
    shift: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OT_ALLOCATIONS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["department", "patient_load", "shift", "allocation_decision"])
    if search_query:
        query.update(search_query)
    if department:
        query["department"] = department
    if patient_load:
        query["patient_load"] = patient_load
    if shift:
        query["shift"] = shift
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "department", "patient_load", "shift"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=50)
    return {"count": len(records), "data": records}


@router.post("/ot/allocations", status_code=201)
async def create_ot_allocation(payload: OTAllocationCreate):
    db = get_db()
    repo = MongoRepository(db, OT_ALLOCATIONS)
    oid = _require_hospital_id(payload.hospitalId)

    allocation_decision = None
    celery_app.send_task(
        "system.generate_predictions",
        args=[
            "predict_staff_alloc",
            {
                "department": payload.department,
                "patient_load": payload.patient_load,
                "shift": payload.shift,
            },
        ],
    )
    cached = await get_latest_prediction("predict_staff_alloc")
    if cached and isinstance(cached.get("result"), dict):
        allocation_decision = cached["result"].get("allocation_decision") or cached["result"].get("decision")

    if not allocation_decision:
        allocation_decision = (
            f"Allocate a core team for {payload.department} ({payload.shift} shift) "
            f"with {payload.patient_load.lower()} patient load."
        )

    doc = {
        "hospital": oid,
        "department": payload.department,
        "patient_load": payload.patient_load,
        "shift": payload.shift,
        "allocation_decision": allocation_decision,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }

    created = await repo.insert_one(doc)
    return created


@router.get("/ceo/global-metrics")
async def ceo_global_metrics(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    hospital_oid = _require_hospital_id(hospitalId)
    patient_repo = MongoRepository(db, PATIENTS)
    staff_repo = MongoRepository(db, HOSPITAL_STAFF)
    invoice_repo = MongoRepository(db, BILLING_INVOICES)
    emergency_repo = MongoRepository(db, EMERGENCY_EVENTS)
    assignment_repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    hospital_repo = MongoRepository(db, HOSPITALS)
    benchmark_repo = MongoRepository(db, HOSPITAL_BENCHMARKS)

    patients = await patient_repo.find_many({"hospitalId": hospital_oid}, limit=500)
    staff = await staff_repo.find_many({"hospital": hospital_oid}, limit=400)
    emergencies = await emergency_repo.find_many({"hospital": hospital_oid}, limit=200)
    assignments = await assignment_repo.find_many({"hospital": hospital_oid}, limit=200)
    hospital_doc = await _resolve_hospital_doc(db, hospitalId)

    dept_counts: dict[str, int] = {}
    for patient in patients:
        dept = patient.get("dept") or "General"
        dept_counts[dept] = dept_counts.get(dept, 0) + 1

    beds = _bed_breakdown(hospital_doc.get("beds") if hospital_doc else {})

    now = datetime.utcnow()
    day_cutoff = now - timedelta(days=1)
    week_cutoff = now - timedelta(days=7)
    month_cutoff = now - timedelta(days=30)

    invoices = await invoice_repo.find_many({"hospital": hospital_oid}, limit=400)
    daily_total = 0.0
    weekly_total = 0.0
    monthly_total = 0.0
    for inv in invoices:
        created_at = inv.get("createdAt") or now
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                created_at = now
        amount = float(inv.get("amount") or 0)
        if created_at >= month_cutoff:
            monthly_total += amount
        if created_at >= week_cutoff:
            weekly_total += amount
        if created_at >= day_cutoff:
            daily_total += amount

    staff_available = len([s for s in staff if s.get("availability") is not False])
    staff_total = len(staff)

    emergency_active = [e for e in emergencies if (e.get("status") or "").lower() not in ["resolved", "closed"]]
    emergency_critical = len([e for e in emergency_active if e.get("severity") == "Critical"])

    inbound = len([a for a in assignments if (a.get("status") or "").lower() in ["active", "en route", "arriving"]])
    outbound = len([a for a in assignments if (a.get("status") or "").lower() in ["completed", "resolved", "closed"]])

    demand_forecast = await _safe_run_model(
        "predict_bed_forecast",
        {
            "emergency_count": len(emergency_active),
            "disease_case_count": len(patients),
            "current_bed_occupancy": beds["occupied"],
            "hospital_id": 1,
        },
    )

    anomalies = []
    if beds["total"] and beds["occupied"] / max(1, beds["total"]) > 0.9:
        anomalies.append("Bed occupancy above 90%")
    if staff_total and staff_available / max(1, staff_total) < 0.65:
        anomalies.append("Staff availability below 65%")
    if emergency_critical >= 3:
        anomalies.append("Multiple critical emergencies detected")

    occupancy_rate = round((beds["occupied"] / max(1, beds["total"])) * 100, 1) if beds["total"] else 0
    staff_coverage = round((staff_available / max(1, staff_total)) * 100, 1) if staff_total else 0
    revenue_trend = "Up" if weekly_total > daily_total * 3 else "Down" if weekly_total < daily_total else "Stable"

    hospitals = await hospital_repo.find_many({}, limit=200)
    occ_rates = []
    for hospital in hospitals:
        hbeds = _bed_breakdown(hospital.get("beds") if hospital else {})
        if hbeds["total"]:
            occ_rates.append(hbeds["occupied"] / max(1, hbeds["total"]))
    internal_benchmark = {
        "avgOccupancyRate": round((sum(occ_rates) / max(1, len(occ_rates))) * 100, 1) if occ_rates else 0,
        "hospitalCount": len(hospitals),
    }

    region = None
    if hospital_doc:
        location = hospital_doc.get("location") if isinstance(hospital_doc.get("location"), dict) else {}
        region = location.get("state") or location.get("city")
    region = region or "global"
    external = await benchmark_repo.find_many({"region": region}, sort=[("createdAt", -1)], limit=50)
    external_benchmarks = {}
    for item in external:
        metric = item.get("metric")
        if not metric:
            continue
        external_benchmarks.setdefault(metric, []).append(float(item.get("value") or 0))
    external_benchmarks = {
        metric: round(sum(values) / max(1, len(values)), 2)
        for metric, values in external_benchmarks.items()
    }

    return {
        "patients": {
            "total": len(patients),
            "by_department": dept_counts,
        },
        "beds": beds,
        "revenue": {
            "daily": round(daily_total, 2),
            "weekly": round(weekly_total, 2),
            "monthly": round(monthly_total, 2),
        },
        "staff": {
            "available": staff_available,
            "total": staff_total,
        },
        "emergency": {
            "active": len(emergency_active),
            "critical": emergency_critical,
        },
        "ambulance": {
            "inbound": inbound,
            "outbound": outbound,
        },
        "ai": {
            "forecast": demand_forecast or {},
            "anomalies": anomalies,
        },
        "kpiSignals": {
            "occupancyRate": occupancy_rate,
            "staffCoverage": staff_coverage,
            "revenueTrend": revenue_trend,
            "emergencyLoad": len(emergency_active),
        },
        "benchmarks": {
            "region": region,
            "internal": internal_benchmark,
            "external": external_benchmarks,
        },
    }


@router.post("/ceo/benchmarks", status_code=201)
async def create_benchmark(payload: BenchmarkCreate):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_BENCHMARKS)
    doc = {
        "region": payload.region,
        "metric": payload.metric,
        "value": payload.value,
        "source": payload.source or "external_feed",
        "createdAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.get("/ceo/benchmarks")
async def list_benchmarks(
    region: str = Query("global"),
    search: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_BENCHMARKS)
    query: dict[str, Any] = {"region": region}
    search_query = _build_search(search, ["metric", "source"])
    if search_query:
        query.update(search_query)
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "metric", "value"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=100)
    return {"count": len(records), "data": records}


@router.get("/ceo/ai-insights")
async def ceo_ai_insights(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    hospital_oid = _require_hospital_id(hospitalId)
    patient_repo = MongoRepository(db, PATIENTS)
    staff_repo = MongoRepository(db, HOSPITAL_STAFF)
    emergency_repo = MongoRepository(db, EMERGENCY_EVENTS)
    invoice_repo = MongoRepository(db, BILLING_INVOICES)
    expense_repo = MongoRepository(db, FINANCE_EXPENSES)

    patients = await patient_repo.find_many({"hospitalId": hospital_oid}, limit=500)
    staff = await staff_repo.find_many({"hospital": hospital_oid}, limit=400)
    emergencies = await emergency_repo.find_many({"hospital": hospital_oid}, limit=200)
    invoices = await invoice_repo.find_many({"hospital": hospital_oid}, limit=300)
    expenses = await expense_repo.find_many({"hospital": hospital_oid}, limit=300)

    dept_counts: dict[str, int] = {}
    for patient in patients:
        dept = patient.get("dept") or "General"
        dept_counts[dept] = dept_counts.get(dept, 0) + 1

    top_departments = sorted(dept_counts.items(), key=lambda item: item[1], reverse=True)
    overloaded = [dept for dept, count in top_departments if count >= 20]

    staff_available = len([s for s in staff if s.get("availability") is not False])
    staff_total = len(staff)
    emergency_active = [e for e in emergencies if (e.get("status") or "").lower() not in ["resolved", "closed"]]

    forecast = await _safe_run_model(
        "predict_bed_forecast",
        {
            "emergency_count": len(emergency_active),
            "disease_case_count": len(patients),
            "current_bed_occupancy": max(1, len(patients)),
            "hospital_id": 1,
        },
    )
    forecast_meta = forecast.get("meta") if isinstance(forecast, dict) else None

    staff_suggestion = (
        "Increase ER coverage" if staff_total and staff_available / staff_total < 0.7 else "Maintain current staffing"
    )
    bed_strategy = "Reserve ICU beds for predicted critical inflow" if len(emergency_active) > 4 else "Maintain standard allocation"
    emergency_risk = "High" if len(emergency_active) >= 6 else "Moderate" if len(emergency_active) >= 3 else "Low"

    revenue_total = sum(float(inv.get("amount") or 0) for inv in invoices)
    expense_total = sum(float(exp.get("amount") or 0) for exp in expenses)
    margin = revenue_total - expense_total
    cost_pressure = round((expense_total / max(1, revenue_total)) * 100, 1) if revenue_total else 0.0
    expense_by_category: dict[str, float] = {}
    for exp in expenses:
        category = exp.get("category") or "General"
        expense_by_category[category] = expense_by_category.get(category, 0) + float(exp.get("amount") or 0)
    top_costs = sorted(expense_by_category.items(), key=lambda item: item[1], reverse=True)[:3]

    insight_notes = []
    if emergency_active:
        insight_notes.append(f"Active emergencies: {len(emergency_active)}")
    if staff_total and staff_available / staff_total < 0.7:
        insight_notes.append("Staff coverage below target threshold")
    if overloaded:
        insight_notes.append("Department load imbalance detected")
    if not insight_notes:
        insight_notes.append("Operational signals stable")

    meta = _simple_meta(
        0.67,
        [
            "Insights derived from patient volume, staffing availability, and emergency load.",
            "Bed forecast model informs predicted inflow and allocation strategy.",
        ],
        forecast_meta.get("references") if isinstance(forecast_meta, dict) else [
            {"title": "Model", "detail": "ml/bed_forecast_model.joblib"},
        ],
    )

    return {
        "predicted_inflow": forecast.get("predicted_bed_demand") if isinstance(forecast, dict) else None,
        "overloaded_departments": overloaded,
        "staff_redistribution": staff_suggestion,
        "emergency_spike_risk": emergency_risk,
        "bed_allocation_strategy": bed_strategy,
        "cost_pressure_index": cost_pressure,
        "margin_at_risk": round(max(0.0, expense_total - revenue_total), 2),
        "top_cost_drivers": [{"category": k, "amount": round(v, 2)} for k, v in top_costs],
        "cost_optimization": "Reduce non-critical overtime" if cost_pressure > 75 else "Maintain procurement plan",
        "insight_notes": insight_notes,
        "meta": meta,
    }


@router.post("/ceo/ai-insights/simulate")
async def ceo_ai_insights_simulate(payload: dict = Body(default_factory=dict)):
    hospital_id = payload.get("hospitalId")
    if not hospital_id:
        raise HTTPException(status_code=400, detail="hospitalId is required")
    emergency_delta = int(payload.get("emergencyDelta") or 0)
    staff_delta = int(payload.get("staffDelta") or 0)
    discharge_delta = int(payload.get("plannedDischarges") or 0)

    db = get_db()
    hospital_oid = _require_hospital_id(hospital_id)
    patient_repo = MongoRepository(db, PATIENTS)
    staff_repo = MongoRepository(db, HOSPITAL_STAFF)
    emergency_repo = MongoRepository(db, EMERGENCY_EVENTS)

    patients = await patient_repo.find_many({"hospitalId": hospital_oid}, limit=500)
    staff = await staff_repo.find_many({"hospital": hospital_oid}, limit=400)
    emergencies = await emergency_repo.find_many({"hospital": hospital_oid}, limit=200)

    active_emergencies = max(0, len(emergencies) + emergency_delta)
    staff_available = max(0, len([s for s in staff if s.get("availability") is not False]) + staff_delta)
    predicted_inflow = max(0, len(patients) - discharge_delta + emergency_delta * 3)
    cost_pressure = max(0, 60 + emergency_delta * 2 - discharge_delta)

    insight_notes = []
    if emergency_delta:
        insight_notes.append(f"Scenario adds {emergency_delta} emergency cases")
    if discharge_delta:
        insight_notes.append(f"Planned discharges: {discharge_delta}")
    if staff_delta:
        insight_notes.append(f"Staff availability delta: {staff_delta}")
    if not insight_notes:
        insight_notes.append("Scenario uses current baseline")

    meta = _simple_meta(
        0.58,
        [
            "Simulation adjusts emergency load, staff availability, and discharges.",
            "Outputs estimate operational strain under the provided scenario.",
        ],
        [{"title": "Scenario", "detail": "CEO AI insights simulation"}],
    )

    return {
        "predicted_inflow": predicted_inflow,
        "overloaded_departments": ["Emergency"] if active_emergencies > 6 else [],
        "staff_redistribution": "Increase ER coverage" if staff_available < 20 else "Maintain current staffing",
        "emergency_spike_risk": "High" if active_emergencies > 6 else "Moderate" if active_emergencies > 3 else "Low",
        "bed_allocation_strategy": "Hold 10% ICU beds" if active_emergencies > 4 else "Maintain standard allocation",
        "cost_pressure_index": round(cost_pressure, 1),
        "margin_at_risk": max(0, emergency_delta * 10000 - discharge_delta * 2500),
        "insight_notes": insight_notes,
        "meta": meta,
    }


@router.get("/ceo/department-performance")
async def ceo_department_performance(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    hospital_oid = _require_hospital_id(hospitalId)
    patient_repo = MongoRepository(db, PATIENTS)
    log_repo = MongoRepository(db, DEPARTMENT_LOGS)

    patients = await patient_repo.find_many({"hospitalId": hospital_oid}, limit=500)
    logs = await log_repo.find_many({"hospital": hospital_oid}, limit=200)

    dept_counts: dict[str, int] = {}
    for patient in patients:
        dept = patient.get("dept") or "General"
        dept_counts[dept] = dept_counts.get(dept, 0) + 1

    log_map: dict[str, dict[str, Any]] = {log.get("department"): log for log in logs if log.get("department")}

    performance = []
    bottlenecks = []
    for dept, count in dept_counts.items():
        log = log_map.get(dept, {})
        has_log = any(log.get(field) is not None for field in ["avgTreatmentMinutes", "dischargeRate", "delayRate"])
        avg_time = float(log.get("avgTreatmentMinutes") or 0) if has_log else None
        discharge_rate = float(log.get("dischargeRate") or 0) if has_log else None
        delay_rate = float(log.get("delayRate") or 0) if has_log else None
        throughput = float(log.get("throughputPerHour") or 0) if log.get("throughputPerHour") is not None else None
        queue_length = int(log.get("queueLength") or 0) if log.get("queueLength") is not None else None

        if not has_log and count:
            avg_time = 34 + min(count, 12)
            discharge_rate = 0.66
            delay_rate = 0.08
            throughput = round(max(2.5, count / 4), 1)
            queue_length = max(3, round(count / 2))

        score = _score_department(count, avg_time, (discharge_rate or 0) * 100, delay_rate or 0.0) if count else 0.0
        if delay_rate and delay_rate > 0.15 or (avg_time and avg_time > 45) or (queue_length and queue_length > 20):
            bottlenecks.append(dept)
        performance.append(
            {
                "department": dept,
                "patients": count,
                "avgTreatmentMinutes": round(avg_time, 1) if avg_time is not None else None,
                "dischargeRate": round(discharge_rate * 100, 1) if discharge_rate is not None else None,
                "delayRate": round(delay_rate * 100, 1) if delay_rate is not None else None,
                "score": score,
                "suggestion": "Add staffing" if delay_rate and delay_rate > 0.12 else "Maintain cadence",
                "throughputPerHour": throughput,
                "queueLength": queue_length,
            }
        )

    performance.sort(key=lambda item: item["score"], reverse=True)
    return {
        "count": len(performance),
        "departments": performance,
        "bottlenecks": bottlenecks,
    }


@router.post("/ceo/department-performance/logs", status_code=201)
async def create_department_log(payload: DepartmentLogCreate):
    db = get_db()
    repo = MongoRepository(db, DEPARTMENT_LOGS)
    hospital_oid = _require_hospital_id(payload.hospitalId)

    doc = {
        "hospital": hospital_oid,
        "department": payload.department,
        "avgTreatmentMinutes": payload.avgTreatmentMinutes,
        "dischargeRate": payload.dischargeRate,
        "delayRate": payload.delayRate,
        "throughputPerHour": payload.throughputPerHour,
        "queueLength": payload.queueLength,
        "notes": payload.notes,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.get("/ceo/resources")
async def ceo_resource_overview(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    hospital_oid = _require_hospital_id(hospitalId)
    hospital_doc = await _resolve_hospital_doc(db, hospitalId)
    resource_repo = MongoRepository(db, RESOURCES)
    equipment_repo = MongoRepository(db, EQUIPMENT_INVENTORY)
    staff_repo = MongoRepository(db, HOSPITAL_STAFF)
    vendor_repo = MongoRepository(db, VENDOR_LEAD_TIMES)

    beds = _bed_breakdown(hospital_doc.get("beds") if hospital_doc else {})
    resources = await resource_repo.find_many({"hospitalId": hospital_oid}, limit=300)
    equipment = await equipment_repo.find_many({"hospital": hospital_oid}, limit=200)
    staff = await staff_repo.find_many({"hospital": hospital_oid}, limit=400)

    shortages = []
    for item in resources:
        quantity = int(item.get("quantity") or 0)
        threshold = int(item.get("minThreshold") or 0)
        if threshold and quantity <= threshold:
            shortages.append({"name": item.get("name"), "category": item.get("category"), "quantity": quantity})

    for eq in equipment:
        quantity = int(eq.get("quantity") or 0)
        threshold = int(eq.get("minThreshold") or 1)
        if quantity <= threshold:
            shortages.append({"name": eq.get("name"), "category": eq.get("category"), "quantity": quantity})

    available_staff = len([s for s in staff if s.get("availability") is not False])

    lead_times = await vendor_repo.find_many({"hospital": hospital_oid}, limit=200)
    lead_map = {f"{item.get('category')}::{item.get('resourceName')}": item for item in lead_times}
    supply_risk = []
    for item in resources:
        key = f"{item.get('category')}::{item.get('name')}"
        lead = lead_map.get(key)
        if lead and int(lead.get("leadTimeDays") or 0) > 10:
            supply_risk.append({"resource": item.get("name"), "leadTimeDays": lead.get("leadTimeDays")})

    return {
        "beds": beds,
        "inventory": resources,
        "equipment": equipment,
        "vendorLeadTimes": lead_times,
        "supplyRisk": supply_risk,
        "staff": {
            "available": available_staff,
            "total": len(staff),
        },
        "shortages": shortages,
    }


@router.post("/ceo/resources/vendors", status_code=201)
async def create_vendor_lead_time(payload: VendorLeadTimeCreate):
    db = get_db()
    repo = MongoRepository(db, VENDOR_LEAD_TIMES)
    hospital_oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": hospital_oid,
        "resourceName": payload.resourceName,
        "category": payload.category,
        "vendorName": payload.vendorName,
        "leadTimeDays": payload.leadTimeDays,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.get("/ceo/beds/forecast")
async def ceo_bed_forecast(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    hospital_oid = _require_hospital_id(hospitalId)
    patient_repo = MongoRepository(db, PATIENTS)
    allocation_repo = MongoRepository(db, BED_ALLOCATIONS)

    patients = await patient_repo.find_many({"hospitalId": hospital_oid}, limit=500)
    allocations = await allocation_repo.find_many({"hospital": hospital_oid}, limit=200)

    discharge_candidates = 0
    detailed = []
    for patient in patients:
        eta_hours = _estimate_discharge_hours(patient.get("severity"))
        status = (patient.get("status") or "").lower()
        if status in ["stable", "recovered", "observation"]:
            discharge_candidates += 1
        detailed.append(
            {
                "patient": patient.get("name"),
                "severity": patient.get("severity"),
                "etaHours": eta_hours,
                "department": patient.get("dept"),
            }
        )

    forecast = await _safe_run_model(
        "predict_bed_forecast",
        {
            "emergency_count": len([a for a in allocations if a.get("status") == "Assigned"]),
            "disease_case_count": len(patients),
            "current_bed_occupancy": len(patients),
            "hospital_id": 1,
        },
    )

    return {
        "expectedDischarges24h": discharge_candidates,
        "allocationCount": len(allocations),
        "forecast": forecast or {},
        "patients": detailed[:30],
    }


@router.get("/ceo/ambulance/coordination")
async def ceo_ambulance_coordination(hospitalId: str = Query(...)):
    db = get_db()
    assignment_repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    ambulance_repo = MongoRepository(db, AMBULANCES)
    emergency_repo = MongoRepository(db, EMERGENCY_EVENTS)

    assignments = await assignment_repo.find_many({"hospital": _require_hospital_id(hospitalId)}, limit=200)
    ambulance_ids = [a.get("ambulanceId") for a in assignments if a.get("ambulanceId")]
    ambulances = await ambulance_repo.find_many({"ambulanceId": {"$in": ambulance_ids}}) if ambulance_ids else []
    emergencies = await emergency_repo.find_many({"hospital": _require_hospital_id(hospitalId)}, limit=200)

    active = [a for a in assignments if (a.get("status") or "").lower() in ["active", "en route", "arriving"]]
    available_units = [a for a in ambulances if (a.get("status") or "").lower() in ["available", "idle"]]
    critical = len([e for e in emergencies if e.get("severity") == "Critical"])

    guidance = []
    if critical >= 3 and len(available_units) < 2:
        guidance.append("Activate mutual aid ambulances from nearby hospitals")
    if len(active) > len(available_units):
        guidance.append("Prioritize high-severity dispatches and stagger non-critical pickups")
    if not guidance:
        guidance.append("Ambulance coverage stable")

    multi_vehicle_plan = []
    if critical >= 2:
        multi_vehicle_plan.append({
            "incidentType": "Critical surge",
            "recommendation": "Deploy dual ambulances for simultaneous triage",
            "vehicles": min(2, len(available_units)),
        })

    return {
        "assignments": assignments,
        "ambulances": ambulances,
        "activeAssignments": len(active),
        "availableUnits": len(available_units),
        "guidance": guidance,
        "multiVehiclePlan": multi_vehicle_plan,
    }


@router.get("/staff")
async def list_staff(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    department: str | None = Query(None),
    role: str | None = Query(None),
    availability: bool | None = Query(None),
    shift: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, HOSPITAL_STAFF)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["name", "role", "department", "shift"])
    if search_query:
        query.update(search_query)
    if department:
        query["department"] = department
    if role:
        query["role"] = role
    if availability is not None:
        query["availability"] = availability
    if shift:
        query["shift"] = shift
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "name", "department", "role", "availability"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=300)
    return {"count": len(records), "data": records}


@router.get("/staff/skills/summary")
async def staff_skill_summary(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, HOSPITAL_STAFF)
    oid = _require_hospital_id(hospitalId)
    staff = await repo.find_many({"hospital": oid}, limit=400)

    skill_counts: dict[str, int] = {}
    for member in staff:
        for skill in member.get("skillTags") or []:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

    top_skills = sorted(skill_counts.items(), key=lambda item: item[1], reverse=True)
    recommendations = []
    if skill_counts and top_skills[0][1] < 3:
        recommendations.append("Increase staffing for critical skill coverage")
    if not skill_counts:
        recommendations.append("Add skill tags to staff profiles")

    return {
        "skills": [{"skill": k, "count": v} for k, v in top_skills],
        "recommendations": recommendations,
    }


@router.get("/staff/optimizer")
async def staff_optimizer(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    staff_repo = MongoRepository(db, HOSPITAL_STAFF)
    patient_repo = MongoRepository(db, PATIENTS)
    hospital_oid = _require_hospital_id(hospitalId)
    staff = await staff_repo.find_many({"hospital": hospital_oid}, limit=400)
    patients = await patient_repo.find_many({"hospitalId": hospital_oid}, limit=400)

    dept_load: dict[str, int] = {}
    for patient in patients:
        dept = patient.get("dept") or "General"
        dept_load[dept] = dept_load.get(dept, 0) + 1

    recommendations = []
    for dept, count in dept_load.items():
        available = len([s for s in staff if s.get("department") == dept and s.get("availability") is not False])
        if count > 20 and available < 6:
            recommendations.append({"department": dept, "action": "Add 2 staff", "reason": "High patient load"})
    if not recommendations:
        recommendations.append({"department": "All", "action": "Maintain staffing", "reason": "Balanced load"})

    return {"recommendations": recommendations}


@router.post("/staff", status_code=201)
async def create_staff(payload: StaffMemberCreate):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_STAFF)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "name": payload.name,
        "role": payload.role,
        "department": payload.department,
        "shift": payload.shift or "Day",
        "availability": payload.availability if payload.availability is not None else True,
        "skillTags": payload.skillTags or [],
        "certifications": payload.certifications or [],
        "maxPatients": payload.maxPatients,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/staff/{staff_id}")
async def update_staff(staff_id: str, payload: StaffMemberUpdate):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_STAFF)
    oid = _as_object_id(staff_id)
    update_data = _build_update(payload, ["name", "role", "department", "shift", "availability", "skillTags", "certifications", "maxPatients"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return updated


@router.delete("/staff/{staff_id}")
async def delete_staff(staff_id: str):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_STAFF)
    deleted = await repo.delete_by_id(staff_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"message": "Staff member removed"}


@router.get("/emergency/feed")
async def emergency_feed(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    priority: str | None = Query(None),
    source: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, EMERGENCY_EVENTS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patientName", "symptoms", "location", "status", "severity", "priority", "source"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    if priority:
        query["priority"] = priority
    if source:
        query["source"] = source
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "severity", "status", "priority"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/emergency/feed", status_code=201)
async def create_emergency_event(payload: EmergencyEventCreate):
    db = get_db()
    repo = MongoRepository(db, EMERGENCY_EVENTS)
    oid = _require_hospital_id(payload.hospitalId)
    severity = _severity_from_text(payload.symptoms)
    priority = "High" if severity in ["Critical", "High"] else "Medium"
    doc = {
        "hospital": oid,
        "patientName": payload.patientName,
        "symptoms": payload.symptoms,
        "location": payload.location or "Unknown",
        "source": payload.source or "public",
        "severity": severity,
        "priority": priority,
        "status": "Unassigned",
        "imagingMeta": payload.imagingMeta,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/emergency/feed/{event_id}")
async def update_emergency_event(event_id: str, payload: EmergencyEventUpdate):
    db = get_db()
    repo = MongoRepository(db, EMERGENCY_EVENTS)
    oid = _as_object_id(event_id)
    update_data = _build_update(payload, ["status", "assignedDepartment", "assignedUnit", "notes", "imagingMeta"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Emergency event not found")
    return updated


@router.get("/emergency/ambulances")
async def emergency_ambulances(hospitalId: str = Query(...)):
    db = get_db()
    ambulance_repo = MongoRepository(db, AMBULANCES)
    assignment_repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)
    assignments = await assignment_repo.find_many({"hospital": _require_hospital_id(hospitalId)}, limit=200)
    ambulance_ids = [a.get("ambulanceId") for a in assignments if a.get("ambulanceId")]
    ambulances = await ambulance_repo.find_many({"ambulanceId": {"$in": ambulance_ids}}) if ambulance_ids else []
    return {
        "assignments": assignments,
        "ambulances": ambulances,
    }


@router.post("/emergency/dispatch", status_code=201)
async def emergency_dispatch(payload: dict = Body(default_factory=dict)):
    db = get_db()
    assignment_repo = MongoRepository(db, AMBULANCE_ASSIGNMENTS)

    event_id = payload.get("eventId")
    ambulance_id = payload.get("ambulanceId")
    hospital_id = payload.get("hospitalId")
    if not hospital_id or not ambulance_id:
        raise HTTPException(status_code=400, detail="hospitalId and ambulanceId are required")

    hospital_oid = _require_hospital_id(hospital_id)
    eta = await _safe_run_model("predict_eta", {"location": payload.get("location", "")})
    eta_minutes = eta.get("eta_minutes") if isinstance(eta, dict) else None
    if eta_minutes is None:
        eta_minutes = payload.get("etaMinutes")
    if eta_minutes is None:
        eta_minutes = 12

    doc = {
        "ambulanceId": ambulance_id,
        "hospital": hospital_oid,
        "eventId": event_id,
        "status": "Active",
        "etaMinutes": eta_minutes,
        "pickup": payload.get("pickup"),
        "destination": payload.get("destination"),
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await assignment_repo.insert_one(doc)
    return created


@router.get("/emergency/intake")
async def emergency_intake(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    department: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    patient_repo = MongoRepository(db, PATIENTS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospitalId": oid, "status": "Intake"}
    search_query = _build_search(search, ["name", "dept", "condition", "severity", "status"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    if department:
        query["dept"] = department
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "severity", "status", "dept"}, "createdAt")
    records = await patient_repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/emergency/intake", status_code=201)
async def create_emergency_intake(payload: EmergencyIntakeCreate):
    db = get_db()
    patient_repo = MongoRepository(db, PATIENTS)
    oid = _require_hospital_id(payload.hospitalId)
    severity = payload.severity or _severity_from_text(payload.symptoms)
    department = payload.department or _department_from_symptoms(payload.symptoms)

    doc = {
        "hospitalId": oid,
        "name": payload.name,
        "age": payload.age,
        "gender": payload.gender,
        "dept": department,
        "condition": payload.symptoms,
        "severity": severity,
        "status": "Intake",
        "contact": payload.contact,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await patient_repo.insert_one(doc)
    return created


@router.patch("/emergency/intake/{patient_id}")
async def update_emergency_intake(patient_id: str, payload: EmergencyIntakeUpdate):
    db = get_db()
    patient_repo = MongoRepository(db, PATIENTS)
    oid = _as_object_id(patient_id)
    update_data: dict[str, Any] = {}
    if payload.status is not None:
        update_data["status"] = payload.status
    if payload.severity is not None:
        update_data["severity"] = payload.severity
    if payload.department is not None:
        update_data["dept"] = payload.department
    if payload.notes is not None:
        update_data["notes"] = payload.notes
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    update_data["updatedAt"] = datetime.utcnow()
    updated = await patient_repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Patient intake not found")
    return updated


@router.get("/emergency/bed-allocation")
async def bed_allocation_list(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    bedType: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, BED_ALLOCATIONS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patientName", "bedType", "status"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if bedType:
        query["bedType"] = bedType
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "status", "bedType"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/emergency/bed-allocation", status_code=201)
async def bed_allocation_create(payload: BedAllocationCreate):
    db = get_db()
    repo = MongoRepository(db, BED_ALLOCATIONS)
    hospital_oid = _require_hospital_id(payload.hospitalId)
    hospital_doc = await _resolve_hospital_doc(db, payload.hospitalId)
    beds = _bed_breakdown(hospital_doc.get("beds") if hospital_doc else {})

    bed_type = payload.bedType
    available = beds.get(bed_type.lower(), {}).get("available", 0) if isinstance(bed_type, str) else beds["available"]
    if available <= 0 and not payload.override:
        raise HTTPException(status_code=409, detail="No beds available for selected type")

    doc = {
        "hospital": hospital_oid,
        "patientName": payload.patientName,
        "bedType": payload.bedType,
        "status": "Assigned",
        "notes": payload.notes,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/emergency/bed-allocation/{allocation_id}")
async def bed_allocation_update(allocation_id: str, payload: BedAllocationUpdate):
    db = get_db()
    repo = MongoRepository(db, BED_ALLOCATIONS)
    oid = _as_object_id(allocation_id)
    update_data = _build_update(payload, ["bedType", "status", "notes"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Bed allocation not found")
    return updated


@router.get("/finance/invoices")
async def finance_invoices(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    department: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, BILLING_INVOICES)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patientName", "department", "status", "insuranceProvider", "payer"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if department:
        query["department"] = department
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "status", "department", "amount", "dueDate"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/finance/invoices", status_code=201)
async def finance_create_invoice(payload: BillingInvoiceCreate):
    db = get_db()
    repo = MongoRepository(db, BILLING_INVOICES)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "patientName": payload.patientName,
        "department": payload.department,
        "amount": payload.amount,
        "status": payload.status or "Unpaid",
        "insuranceProvider": payload.insuranceProvider,
        "dueDate": payload.dueDate,
        "payer": payload.payer,
        "paidAt": payload.paidAt,
        "paidAmount": 0.0,
        "refundAmount": 0.0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/finance/invoices/{invoice_id}")
async def finance_update_invoice(invoice_id: str, payload: BillingInvoiceUpdate):
    db = get_db()
    repo = MongoRepository(db, BILLING_INVOICES)
    oid = _as_object_id(invoice_id)
    update_data = _build_update(payload, ["status", "paidAmount", "refundAmount", "paidAt"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return updated


@router.get("/finance/claims")
async def finance_claims(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    insurer: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, INSURANCE_CLAIMS)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["insurer", "invoiceId", "status"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if insurer:
        query["insurer"] = insurer
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "status", "insurer", "amount"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/finance/claims", status_code=201)
async def finance_create_claim(payload: InsuranceClaimCreate):
    db = get_db()
    repo = MongoRepository(db, INSURANCE_CLAIMS)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "invoiceId": payload.invoiceId,
        "insurer": payload.insurer,
        "amount": payload.amount,
        "status": payload.status or "Submitted",
        "approvedAmount": 0.0,
        "submittedAt": payload.submittedAt or datetime.utcnow().isoformat(),
        "paidAt": payload.paidAt,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/finance/claims/{claim_id}")
async def finance_update_claim(claim_id: str, payload: InsuranceClaimUpdate):
    db = get_db()
    repo = MongoRepository(db, INSURANCE_CLAIMS)
    oid = _as_object_id(claim_id)
    update_data = _build_update(payload, ["status", "approvedAmount", "notes", "paidAt"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Claim not found")
    return updated


@router.post("/finance/expenses", status_code=201)
async def finance_create_expense(payload: FinanceExpenseCreate):
    db = get_db()
    repo = MongoRepository(db, FINANCE_EXPENSES)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "category": payload.category,
        "amount": payload.amount,
        "notes": payload.notes,
        "vendor": payload.vendor,
        "contractRef": payload.contractRef,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.get("/finance/revenue")
async def finance_revenue(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    oid = _require_hospital_id(hospitalId)
    invoice_repo = MongoRepository(db, BILLING_INVOICES)
    expense_repo = MongoRepository(db, FINANCE_EXPENSES)
    claim_repo = MongoRepository(db, INSURANCE_CLAIMS)
    return await _compute_finance_summary(invoice_repo, expense_repo, claim_repo, oid)


@router.get("/finance/payer-delays")
async def finance_payer_delays(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    oid = _require_hospital_id(hospitalId)
    claim_repo = MongoRepository(db, INSURANCE_CLAIMS)
    claims = await claim_repo.find_many({"hospital": oid}, limit=300)

    delays = []
    by_insurer: dict[str, list[int]] = {}
    for claim in claims:
        submitted_at = claim.get("submittedAt")
        paid_at = claim.get("paidAt")
        if isinstance(submitted_at, str):
            try:
                submitted_at = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
            except ValueError:
                submitted_at = None
        if isinstance(paid_at, str):
            try:
                paid_at = datetime.fromisoformat(paid_at.replace("Z", "+00:00"))
            except ValueError:
                paid_at = None
        if isinstance(submitted_at, datetime) and isinstance(paid_at, datetime):
            delay = (paid_at - submitted_at).days
            delays.append(delay)
            insurer = claim.get("insurer") or "Unknown"
            by_insurer.setdefault(insurer, []).append(delay)

    insurer_stats = [
        {"insurer": k, "avgDelayDays": round(sum(v) / max(1, len(v)), 1), "count": len(v)}
        for k, v in by_insurer.items()
    ]

    return {
        "averageDelayDays": round(sum(delays) / max(1, len(delays)), 1) if delays else 0,
        "insurers": insurer_stats,
    }


async def _build_report_content(db, report_key: str, hospital_oid: ObjectId, hospital_id: str) -> dict[str, Any]:
    now = datetime.utcnow()
    if report_key == "weekly-ops":
        patient_repo = MongoRepository(db, PATIENTS)
        staff_repo = MongoRepository(db, HOSPITAL_STAFF)
        emergency_repo = MongoRepository(db, EMERGENCY_EVENTS)
        invoice_repo = MongoRepository(db, BILLING_INVOICES)
        hospital_doc = await _resolve_hospital_doc(db, hospital_id)

        patients = await patient_repo.find_many({"hospitalId": hospital_oid}, limit=500)
        staff = await staff_repo.find_many({"hospital": hospital_oid}, limit=400)
        emergencies = await emergency_repo.find_many({"hospital": hospital_oid}, limit=200)
        invoices = await invoice_repo.find_many({"hospital": hospital_oid}, limit=300)

        bed_stats = _bed_breakdown(hospital_doc.get("beds") if hospital_doc else {})
        staff_available = len([s for s in staff if s.get("availability") is not False])
        emergency_active = [e for e in emergencies if (e.get("status") or "").lower() not in ["resolved", "closed"]]
        emergency_critical = len([e for e in emergency_active if e.get("severity") == "Critical"])

        week_cutoff = now - timedelta(days=7)
        weekly_revenue = 0.0
        for inv in invoices:
            created_at = inv.get("createdAt") or now
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    created_at = now
            if isinstance(created_at, datetime) and created_at >= week_cutoff:
                weekly_revenue += float(inv.get("amount") or 0)

        content = [
            f"Weekly Operations Summary ({week_cutoff.date().isoformat()} to {now.date().isoformat()})",
            f"Total patients: {len(patients)}",
            f"Emergency events: {len(emergency_active)} (critical: {emergency_critical})",
            f"Bed occupancy: {bed_stats['occupied']}/{bed_stats['total']} (ICU {bed_stats['icu']['occupied']}/{bed_stats['icu']['total']})",
            f"Staff availability: {staff_available}/{len(staff)}",
            f"Weekly revenue: ₹{round(weekly_revenue, 2)}",
        ]
        return {"content": "\n".join(content)}

    if report_key == "icu-performance":
        patient_repo = MongoRepository(db, ICU_PATIENTS)
        alert_repo = MongoRepository(db, ICU_ALERTS)

        patients = await patient_repo.find_many({"hospital": hospital_oid}, limit=200)
        alerts = await alert_repo.find_many({"hospital": hospital_oid}, limit=200)

        if patients:
            avg_oxygen = round(sum(int(p.get("oxygen") or 0) for p in patients) / len(patients))
            avg_hr = round(sum(int(p.get("heartRate") or 0) for p in patients) / len(patients))
            critical = len([p for p in patients if (p.get("status") or "").lower() == "critical"])
        else:
            avg_oxygen = 0
            avg_hr = 0
            critical = 0

        content = [
            "ICU Performance Review",
            f"Active ICU patients: {len(patients)}",
            f"Critical patients: {critical}",
            f"Average oxygen saturation: {avg_oxygen}%",
            f"Average heart rate: {avg_hr} bpm",
            f"Active ICU alerts: {len(alerts)}",
        ]
        return {"content": "\n".join(content)}

    if report_key == "finance-snapshot":
        invoice_repo = MongoRepository(db, BILLING_INVOICES)
        expense_repo = MongoRepository(db, FINANCE_EXPENSES)
        claim_repo = MongoRepository(db, INSURANCE_CLAIMS)
        summary = await _compute_finance_summary(invoice_repo, expense_repo, claim_repo, hospital_oid)
        top_departments = summary.get("departmentBreakdown", [])[:3]

        content = [
            "Finance Snapshot",
            f"Total revenue: ₹{summary.get('totalRevenue', 0)}",
            f"Total expenses: ₹{summary.get('totalExpenses', 0)}",
            f"Profit: ₹{summary.get('profit', 0)}",
            "Top departments:",
        ]
        for dept in top_departments:
            content.append(f"- {dept.get('department')}: ₹{dept.get('amount')}")
        return {"content": "\n".join(content)}

    return {"content": "Report template not available."}


@router.get("/reports")
async def list_reports(hospitalId: str = Query(...)):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    hospital_oid = _require_hospital_id(hospitalId)
    repo = MongoRepository(db, HOSPITAL_REPORTS)
    records = await repo.find_many({"hospital": hospital_oid}, sort=[("generatedAt", -1)], limit=50)
    by_key = {record.get("reportKey"): record for record in records if record.get("reportKey")}

    response = []
    for template in _report_templates():
        existing = by_key.get(template["key"])
        status = None
        if existing:
            status = existing.get("status") or ("Ready" if existing.get("content") else "Draft")
        response.append(
            {
                "id": existing.get("_id") if existing else None,
                "reportKey": template["key"],
                "name": template["name"],
                "status": status if existing else "Draft",
                "generatedAt": existing.get("generatedAt") if existing else None,
            }
        )

    return {"data": response}


@router.get("/reports/ingested")
async def list_ingested_reports(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    category: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    hospital_oid = _require_hospital_id(hospitalId)
    repo = MongoRepository(db, HOSPITAL_REPORTS)
    query: dict[str, Any] = {"hospital": hospital_oid, "reportKey": "ingested"}
    search_query = _build_search(search, ["name", "category", "summary", "status"])
    if search_query:
        query.update(search_query)
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    sort = _build_sort(sort_by, sort_dir, {"generatedAt", "createdAt", "status", "name", "category"}, "generatedAt")
    records = await repo.find_many(query, sort=sort, limit=100)
    return {"count": len(records), "data": records}


@router.post("/reports/ingest", status_code=201)
async def ingest_report(payload: ReportIngestCreate):
    db = get_db()
    hospital_oid = _require_hospital_id(payload.hospitalId)
    repo = MongoRepository(db, HOSPITAL_REPORTS)

    summary = _summarize_report_text(payload.content)
    now = datetime.utcnow()
    doc = {
        "hospital": hospital_oid,
        "reportKey": "ingested",
        "name": payload.name,
        "category": payload.category or "General",
        "status": "Ready",
        "generatedAt": now,
        "content": payload.content,
        "summary": summary,
        "createdAt": now,
        "updatedAt": now,
    }
    created = await repo.insert_one(doc)
    return created


@router.post("/reports/generate")
async def generate_report(payload: HospitalReportGenerate):
    db = get_db()
    hospital_oid = _require_hospital_id(payload.hospitalId)
    template = next((t for t in _report_templates() if t["key"] == payload.reportKey), None)
    if not template:
        raise HTTPException(status_code=400, detail="Unknown reportKey")

    repo = MongoRepository(db, HOSPITAL_REPORTS)
    report_data = await _build_report_content(db, payload.reportKey, hospital_oid, payload.hospitalId)

    now = datetime.utcnow()
    update_doc = {
        "hospital": hospital_oid,
        "reportKey": payload.reportKey,
        "name": template["name"],
        "status": "Ready",
        "generatedAt": now,
        "content": report_data.get("content") or "",
        "updatedAt": now,
    }

    existing = await repo.find_one({"hospital": hospital_oid, "reportKey": payload.reportKey})
    if existing:
        updated = await repo.update_one({"_id": _as_object_id(existing.get("_id"))}, {"$set": update_doc}, return_new=True)
        return updated

    update_doc["createdAt"] = now
    created = await repo.insert_one(update_doc)
    return created


@router.get("/reports/{report_id}/download")
async def download_report(report_id: str):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_REPORTS)
    oid = _as_object_id(report_id)
    record = await repo.find_one({"_id": oid})
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")

    name = (record.get("name") or "report").strip().replace(" ", "_")
    content = record.get("content") or ""
    headers = {"Content-Disposition": f'attachment; filename="{name}.txt"'}
    return PlainTextResponse(content, headers=headers)


@router.get("/reports/{report_id}/summary")
async def report_summary(report_id: str):
    db = get_db()
    repo = MongoRepository(db, HOSPITAL_REPORTS)
    oid = _as_object_id(report_id)
    record = await repo.find_one({"_id": oid})
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")

    summary = record.get("summary")
    if not summary:
        summary = _summarize_report_text(record.get("content") or "")
        await repo.update_one({"_id": oid}, {"$set": {"summary": summary, "updatedAt": datetime.utcnow()}})

    return {
        "id": record.get("_id"),
        "name": record.get("name"),
        "summary": summary,
    }


@router.get("/opd/queue")
async def opd_queue(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, OPD_QUEUE)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["patientName", "reason", "assignedDoctor", "status", "priority"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "priority", "status", "patientName"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    wait_times = []
    for idx, record in enumerate(records):
        priority = record.get("priority") or "Normal"
        predicted = _predict_wait_minutes(idx, priority)
        wait_times.append(predicted)
        check_in = _parse_datetime(record.get("checkInAt")) or _parse_datetime(record.get("createdAt"))
        record["position"] = idx + 1
        record["predictedWaitMinutes"] = predicted
        record["checkInAt"] = check_in or record.get("createdAt")
        if isinstance(check_in, datetime):
            record["etaAt"] = check_in + timedelta(minutes=predicted)

    avg_wait = round(sum(wait_times) / max(1, len(wait_times))) if wait_times else 0
    queue_pressure = min(100, len(records) * 7)
    return {
        "count": len(records),
        "avgWaitMinutes": avg_wait,
        "queuePressure": queue_pressure,
        "data": records,
    }


@router.post("/opd/queue", status_code=201)
async def create_opd_queue(payload: OpdQueueCreate):
    db = get_db()
    repo = MongoRepository(db, OPD_QUEUE)
    oid = _require_hospital_id(payload.hospitalId)
    now = datetime.utcnow()
    doc = {
        "hospital": oid,
        "patientName": payload.patientName,
        "reason": payload.reason,
        "priority": payload.priority or "Normal",
        "status": "Waiting",
        "assignedDoctor": payload.assignedDoctor,
        "notes": payload.notes,
        "checkInAt": now,
        "createdAt": now,
        "updatedAt": now,
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/opd/queue/{queue_id}")
async def update_opd_queue(queue_id: str, payload: OpdQueueUpdate):
    db = get_db()
    repo = MongoRepository(db, OPD_QUEUE)
    oid = _as_object_id(queue_id)
    update_data = _build_update(payload, ["status", "priority", "assignedDoctor", "notes"])
    if payload.status:
        now = datetime.utcnow()
        if payload.status == "In Service":
            update_data["serviceStartedAt"] = now
        if payload.status in {"Completed", "Canceled"}:
            update_data["completedAt"] = now
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return updated


@router.delete("/opd/queue/{queue_id}")
async def delete_opd_queue(queue_id: str):
    db = get_db()
    repo = MongoRepository(db, OPD_QUEUE)
    oid = _as_object_id(queue_id)
    deleted = await repo.delete_one({"_id": oid})
    if not deleted:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return {"status": "ok"}


@router.post("/icu/risk")
async def icu_risk(payload: dict = Body(default_factory=dict)):
    oxygen = int(payload.get("oxygen") or 0)
    heart_rate = int(payload.get("heartRate") or 0)
    risk = 0
    if oxygen < 92:
        risk += 40
    if oxygen < 88:
        risk += 15
    if heart_rate > 110:
        risk += 30
    if heart_rate > 130:
        risk += 10
    if heart_rate < 50:
        risk += 20
    risk = min(100, risk)
    risk_level = "Critical" if risk >= 70 else "High" if risk >= 50 else "Moderate" if risk >= 30 else "Low"
    meta = _simple_meta(
        0.6,
        [
            "Risk computed from oxygen saturation and heart rate thresholds.",
            "Higher risk escalates when oxygen drops or heart rate spikes.",
        ],
        [{"title": "Rule set", "detail": "ICU triage thresholds"}],
    )
    return {
        "riskScore": risk,
        "riskLevel": risk_level,
        "meta": meta,
    }


@router.get("/equipment")
async def equipment_list(
    hospitalId: str = Query(...),
    search: str | None = Query(None),
    status: str | None = Query(None),
    category: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
):
    db = get_db()
    await _ensure_seeded(db, hospitalId)
    repo = MongoRepository(db, EQUIPMENT_INVENTORY)
    oid = _require_hospital_id(hospitalId)
    query: dict[str, Any] = {"hospital": oid}
    search_query = _build_search(search, ["name", "category", "status"])
    if search_query:
        query.update(search_query)
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    sort = _build_sort(sort_by, sort_dir, {"createdAt", "updatedAt", "name", "category", "quantity", "status"}, "createdAt")
    records = await repo.find_many(query, sort=sort, limit=200)
    return {"count": len(records), "data": records}


@router.post("/equipment", status_code=201)
async def create_equipment(payload: EquipmentCreate):
    db = get_db()
    repo = MongoRepository(db, EQUIPMENT_INVENTORY)
    oid = _require_hospital_id(payload.hospitalId)
    doc = {
        "hospital": oid,
        "name": payload.name,
        "category": payload.category,
        "quantity": payload.quantity,
        "status": payload.status or "Available",
        "minThreshold": payload.minThreshold or 1,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    created = await repo.insert_one(doc)
    return created


@router.patch("/equipment/{equipment_id}")
async def update_equipment(equipment_id: str, payload: EquipmentUpdate):
    db = get_db()
    repo = MongoRepository(db, EQUIPMENT_INVENTORY)
    oid = _as_object_id(equipment_id)
    update_data = _build_update(payload, ["quantity", "status", "minThreshold"])
    updated = await repo.update_one({"_id": oid}, {"$set": update_data}, return_new=True)
    if not updated:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return updated
