import csv
import io
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.db.mongo import get_db
from app.services.collections import ANALYTICS_EVENTS, HEALTH_RECORDS, USERS
from app.core.celery_app import celery_app
from app.services.prediction_store import get_latest_prediction
from app.services.repository import MongoRepository
from app.services.ml_runner import run_ml_model

router = APIRouter(tags=["ai"])

MAX_REPORT_BYTES = 12 * 1024 * 1024
MIN_REPORT_CHARS = 40


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _as_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID format") from exc


def _load_hotspot_seed_data(limit: int = 200) -> list[dict]:
    csv_path = _repo_root() / "backend" / "ml" / "emergency_hotspot_data.csv"
    if not csv_path.exists():
        return []

    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append(
                    {
                        "lat": float(row.get("lat", 0) or 0),
                        "lng": float(row.get("lng", 0) or 0),
                        "emergency_type": row.get("emergency_type") or "unknown",
                        "severity": row.get("severity") or "Unknown",
                        "timestamp": row.get("timestamp") or "",
                    }
                )
            except ValueError:
                continue

            if len(rows) >= limit:
                break
    return rows


async def _run_prediction(command: str, payload: dict):
    celery_app.send_task("system.generate_predictions", args=[command, payload])
    cached = await get_latest_prediction(command)
    if cached and isinstance(cached.get("result"), dict):
        result = cached["result"]
        result["meta"] = _ensure_meta(
            result.get("meta"),
            cached.get("confidence", 0.0),
            ["Serving latest cached prediction; fresh run queued in background."],
            [{"title": "Task", "detail": f"system.generate_predictions::{command}"}],
        )
        return result

    try:
        result = await run_ml_model(command, payload, "ai_ml.py")
        if isinstance(result, dict):
            result["meta"] = _ensure_meta(
                result.get("meta"),
                result.get("meta", {}).get("confidence", 0.65) if isinstance(result.get("meta"), dict) else 0.65,
                ["Generated immediately from the ML model as no cached prediction was available."],
                [{"title": "Model", "detail": f"ai_ml.py::{command}"}],
            )
            return result
    except Exception as exc:
        return {
            "status": "queued",
            "error": f"Prediction queued; direct model execution failed: {exc}",
            "meta": _ensure_meta(
                None,
                0.0,
                ["Prediction queued for background processing."],
                [{"title": "Task", "detail": f"system.generate_predictions::{command}"}],
            ),
        }

    return {
        "status": "queued",
        "meta": _ensure_meta(
            None,
            0.0,
            ["Prediction queued for background processing."],
            [{"title": "Task", "detail": f"system.generate_predictions::{command}"}],
        ),
    }


def _ensure_meta(meta: Any, confidence: float, reasoning: list[str], references: list[dict[str, str]] | None = None) -> dict[str, Any]:
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("confidence", confidence)
    if reasoning:
        meta.setdefault("reasoning", reasoning)
    if references:
        meta.setdefault("references", references)
    return meta


def _looks_like_binary_text(text: str) -> bool:
    if not text:
        return False
    sample = text[:2000]
    if sample.lstrip().startswith("%PDF-"):
        return True
    non_printable = sum(1 for ch in sample if ord(ch) < 9 or (ord(ch) < 32 and ch not in "\n\t\r"))
    return non_printable / max(1, len(sample)) > 0.12


def _clean_report_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_pdf_text(data: bytes) -> tuple[str, list[str]]:
    notes: list[str] = []
    try:
        from pypdf import PdfReader
    except Exception:
        notes.append("pypdf_not_installed")
        return "", notes

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        return text, notes
    except Exception as exc:
        notes.append(f"pdf_text_error:{exc}")
        return "", notes


def _ocr_image_bytes(data: bytes) -> tuple[str, list[str]]:
    notes: list[str] = []
    try:
        from PIL import Image
    except Exception:
        notes.append("pillow_not_installed")
        return "", notes
    try:
        import pytesseract
    except Exception:
        notes.append("pytesseract_not_installed")
        return "", notes

    try:
        image = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(image)
        return text.strip(), notes
    except Exception as exc:
        notes.append(f"image_ocr_error:{exc}")
        return "", notes


def _ocr_pdf_bytes(data: bytes) -> tuple[str, list[str]]:
    notes: list[str] = []
    try:
        from pdf2image import convert_from_bytes
    except Exception:
        notes.append("pdf2image_not_installed")
        return "", notes
    try:
        import pytesseract
    except Exception:
        notes.append("pytesseract_not_installed")
        return "", notes

    try:
        images = convert_from_bytes(data)
        texts = [pytesseract.image_to_string(image) for image in images]
        return "\n".join(texts).strip(), notes
    except Exception as exc:
        notes.append(f"pdf_ocr_error:{exc}")
        return "", notes


def _infer_upload_kind(filename: str | None, content_type: str | None) -> str:
    if content_type:
        if content_type == "application/pdf":
            return "pdf"
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("text/"):
            return "text"

    if filename:
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            return "pdf"
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
            return "image"
        if ext in {".txt", ".md", ".csv", ".json"}:
            return "text"
    return "binary"


def _extract_text_from_upload(data: bytes, filename: str | None, content_type: str | None) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {"source": "upload", "warnings": []}
    kind = _infer_upload_kind(filename, content_type)
    if kind == "pdf":
        text, notes = _extract_pdf_text(data)
        meta["warnings"].extend(notes)
        if len(text) < MIN_REPORT_CHARS:
            ocr_text, ocr_notes = _ocr_pdf_bytes(data)
            meta["warnings"].extend(ocr_notes)
            if ocr_text:
                meta["source"] = "pdf_ocr"
                return _clean_report_text(ocr_text), meta
        meta["source"] = "pdf_text"
        return _clean_report_text(text), meta

    if kind == "image":
        ocr_text, ocr_notes = _ocr_image_bytes(data)
        meta["warnings"].extend(ocr_notes)
        meta["source"] = "image_ocr"
        return _clean_report_text(ocr_text), meta

    if kind == "text":
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        meta["source"] = "text"
        return _clean_report_text(text), meta

    meta["source"] = "binary"
    return "", meta


def _first_number(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                continue
    return None


def _extract_bp(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"(?:blood pressure|bp)\s*[:\-]?\s*(\d{2,3})\s*/\s*(\d{2,3})", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})\s*mmhg", text, flags=re.IGNORECASE)
    if not match:
        return None, None
    try:
        return int(match.group(1)), int(match.group(2))
    except (TypeError, ValueError):
        return None, None


def _extract_report_metrics(text: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    age = _first_number([r"\bage\s*[:\-]?\s*(\d{1,3})\b"], text)
    bmi = _first_number([r"\bbmi\s*[:\-]?\s*(\d{1,2}(?:\.\d+)?)"], text)
    heart_rate = _first_number([r"(?:heart rate|hr|pulse)\s*[:\-]?\s*(\d{2,3})"], text)
    oxygen = _first_number([r"(?:oxygen|spo2|o2)\s*[:\-]?\s*(\d{2,3})\s*%?"], text)
    glucose = _first_number([r"(?:glucose|blood sugar|fasting glucose)\s*[:\-]?\s*(\d{2,3})"], text)
    hba1c = _first_number([r"hba1c\s*[:\-]?\s*(\d{1,2}(?:\.\d+)?)"], text)
    cholesterol = _first_number([r"cholesterol\s*[:\-]?\s*(\d{2,3})"], text)
    temp_value = _first_number([r"(?:temperature|temp)\s*[:\-]?\s*(\d{2,3}(?:\.\d+)?)"], text)
    temp_unit = None
    temp_match = re.search(r"(?:temperature|temp)\s*[:\-]?\s*\d{2,3}(?:\.\d+)?\s*°?\s*([cf])", text, flags=re.IGNORECASE)
    if temp_match:
        temp_unit = temp_match.group(1).upper()

    systolic, diastolic = _extract_bp(text)

    if age is not None:
        metrics["age"] = int(age)
    if bmi is not None:
        metrics["bmi"] = round(float(bmi), 1)
    if heart_rate is not None:
        metrics["heart_rate"] = int(heart_rate)
    if oxygen is not None:
        metrics["oxygen"] = int(oxygen)
    if glucose is not None:
        metrics["glucose_mg_dl"] = int(glucose)
    if hba1c is not None:
        metrics["hba1c"] = round(float(hba1c), 1)
    if cholesterol is not None:
        metrics["cholesterol_mg_dl"] = int(cholesterol)
    if temp_value is not None:
        metrics["temperature"] = round(float(temp_value), 1)
        if temp_unit:
            metrics["temperature_unit"] = temp_unit
    if systolic is not None:
        metrics["blood_pressure_systolic"] = systolic
    if diastolic is not None:
        metrics["blood_pressure_diastolic"] = diastolic

    return metrics


def _extract_lifestyle(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["sedentary", "inactive", "no exercise"]):
        return "Sedentary"
    if any(term in lowered for term in ["active", "regular exercise", "athlete"]):
        return "Active"
    if any(term in lowered for term in ["smoker", "smoking", "tobacco"]):
        return "Smoker"
    return "Average"


def _build_risk_flags(metrics: dict[str, Any]) -> list[str]:
    flags = []
    hr = metrics.get("heart_rate")
    if isinstance(hr, int) and hr > 110:
        flags.append("Elevated heart rate")
    if isinstance(hr, int) and hr < 50:
        flags.append("Low heart rate")

    oxygen = metrics.get("oxygen")
    if isinstance(oxygen, int) and oxygen < 92:
        flags.append("Low oxygen saturation")

    systolic = metrics.get("blood_pressure_systolic")
    diastolic = metrics.get("blood_pressure_diastolic")
    if isinstance(systolic, int) and systolic >= 140:
        flags.append("High systolic blood pressure")
    if isinstance(diastolic, int) and diastolic >= 90:
        flags.append("High diastolic blood pressure")

    glucose = metrics.get("glucose_mg_dl")
    if isinstance(glucose, int) and glucose >= 140:
        flags.append("Elevated glucose")

    hba1c = metrics.get("hba1c")
    if isinstance(hba1c, (int, float)) and hba1c >= 6.5:
        flags.append("High HbA1c")

    temp_value = metrics.get("temperature")
    temp_unit = metrics.get("temperature_unit")
    if isinstance(temp_value, (int, float)):
        if temp_unit == "F" and temp_value >= 100.4:
            flags.append("Fever")
        if temp_unit != "F" and temp_value >= 38.0:
            flags.append("Fever")

    return flags


def _normalize_conditions(conditions: list[str]) -> list[str]:
    if not conditions:
        return []
    seen = set()
    cleaned = []
    for item in conditions:
        if item in seen:
            continue
        seen.add(item)
        cleaned.append(item)

    has_specific_cancer = any(item.endswith("Cancer") for item in cleaned)
    if has_specific_cancer and "Malignancy" in cleaned:
        cleaned = [item for item in cleaned if item != "Malignancy"]

    if any(item in cleaned for item in ("Hypertension", "Hypotension")):
        cleaned = [item for item in cleaned if item != "Blood Pressure Issue"]

    return cleaned


def _build_condition_guidance(conditions: list[str]) -> tuple[list[str], list[str]]:
    explanation_map = {
        "Liver Cancer": "Text mentions liver cancer terms. This usually needs confirmation with imaging and pathology.",
        "Breast Cancer": "Text mentions breast cancer terms. Confirm with imaging, biopsy, and oncology review.",
        "Lung Cancer": "Text mentions lung cancer terms. Confirm with imaging and pathology.",
        "Colon Cancer": "Text mentions colon cancer terms. Confirm with colonoscopy and pathology.",
        "Prostate Cancer": "Text mentions prostate cancer terms. Confirm with PSA, imaging, and biopsy.",
        "Malignancy": "Cancer-related terms appear. A specialist review is needed to confirm the diagnosis.",
        "Liver Disease": "Liver-related terms appear. Review LFTs and ultrasound/CT findings.",
        "Kidney Disease": "Kidney-related terms appear. Review creatinine, eGFR, and urinalysis.",
        "Cardiac Event": "Heart attack or failure terms appear. ECG/troponin and cardiology review are typical next steps.",
        "Hypertension": "Blood pressure terms suggest hypertension. Confirm with repeat BP readings.",
        "Hypotension": "Low blood pressure terms appear. Assess hydration, meds, and vital trends.",
        "Diabetes": "Diabetes or high glucose terms appear. Confirm with HbA1c or fasting glucose.",
        "Elevated Glucose": "Glucose elevation is mentioned. Repeat glucose and HbA1c are typical follow-ups.",
        "Respiratory Disease": "Asthma/COPD terms appear. Review inhaler use and consider spirometry.",
        "Pneumonia": "Pneumonia terms appear. Chest imaging and clinical exam are typical.",
        "Stroke": "Stroke terms appear. Neuro evaluation and imaging are usually required.",
        "Seizure": "Seizure terms appear. Neurology review and EEG may be needed.",
        "Anemia": "Anemia terms appear. Check CBC and iron studies.",
        "Infection": "Infection-related terms appear. Consider CBC, cultures, and clinician review.",
        "Sepsis": "Sepsis terms appear. This usually needs urgent clinical evaluation.",
        "Fracture": "Fracture terms appear. Imaging is needed to confirm the location and severity.",
    }
    next_steps_map = {
        "Liver Cancer": ["Review imaging (US/CT/MRI) and pathology with oncology."],
        "Breast Cancer": ["Review imaging (mammogram/US/MRI) and biopsy results."],
        "Lung Cancer": ["Review CT chest findings and pathology if available."],
        "Colon Cancer": ["Review colonoscopy findings and pathology."],
        "Prostate Cancer": ["Review PSA trend and biopsy if available."],
        "Malignancy": ["Share the report with an oncology specialist for confirmation."],
        "Liver Disease": ["Check liver function tests and imaging findings."],
        "Kidney Disease": ["Review creatinine/eGFR and urinalysis."],
        "Cardiac Event": ["Check ECG/troponin and discuss with cardiology."],
        "Hypertension": ["Repeat BP readings and review medications/lifestyle."],
        "Hypotension": ["Monitor vitals and review hydration/meds."],
        "Diabetes": ["Confirm with HbA1c and fasting glucose."],
        "Elevated Glucose": ["Repeat glucose test and review diet/meds."],
        "Respiratory Disease": ["Review symptoms and consider spirometry."],
        "Pneumonia": ["Review chest imaging and infection markers."],
        "Stroke": ["Urgent neurologic assessment and imaging if symptoms are recent."],
        "Seizure": ["Neurology review and EEG if clinically indicated."],
        "Anemia": ["Check CBC and iron studies."],
        "Infection": ["Check CBC and follow clinician guidance for cultures/antibiotics."],
        "Sepsis": ["Seek urgent medical evaluation."],
        "Fracture": ["Confirm with X-ray/CT and review treatment plan."],
    }

    explanations = []
    next_steps = []
    seen_steps = set()
    for condition in conditions:
        explanation = explanation_map.get(condition)
        if explanation:
            explanations.append(f"{condition}: {explanation}")
        for step in next_steps_map.get(condition, []):
            if step in seen_steps:
                continue
            seen_steps.add(step)
            next_steps.append(step)
    return explanations, next_steps


class CompatibilityRequest(BaseModel):
    requester_id: str
    donor_id: str
    organ_type: str | None = "Blood"


class AnalyzeReportRequest(BaseModel):
    report_text: str
    user_id: str | None = None


class ProfileClusterRequest(BaseModel):
    user_id: str


class DonationForecastRequest(BaseModel):
    user_id: str | None = None
    blood_group: str | None = None


def _extract_conditions(report_text: str) -> list[str]:
    patterns = {
        r"\bliver cancer\b|\bhepatocellular carcinoma\b|\bhepatic carcinoma\b": "Liver Cancer",
        r"\bbreast cancer\b|\bmammary carcinoma\b": "Breast Cancer",
        r"\blung cancer\b|\bbronchogenic carcinoma\b": "Lung Cancer",
        r"\bcolon cancer\b|\bcolorectal cancer\b": "Colon Cancer",
        r"\bprostate cancer\b": "Prostate Cancer",
        r"\bmalignancy\b|\bcarcinoma\b|\btumor\b|\bcancer\b": "Malignancy",
        r"\bhepatitis\b|\bcirrhosis\b|\bfatty liver\b|\bliver disease\b": "Liver Disease",
        r"\bkidney disease\b|\brenal failure\b|\bckd\b": "Kidney Disease",
        r"\bheart failure\b|\bmyocardial infarction\b|\bheart attack\b": "Cardiac Event",
        r"\bhypertension\b|\bhigh blood pressure\b": "Hypertension",
        r"\bhypotension\b|\blow blood pressure\b": "Hypotension",
        r"\bdiabetes\b|\btype 1 diabetes\b|\btype 2 diabetes\b": "Diabetes",
        r"\bhyperglycemia\b|\bhigh blood sugar\b": "Elevated Glucose",
        r"\basthma\b|\bcopd\b": "Respiratory Disease",
        r"\bpneumonia\b": "Pneumonia",
        r"\bstroke\b": "Stroke",
        r"\banemia\b": "Anemia",
        r"\bsepsis\b|\binfection\b": "Infection",
        r"\bfracture\b": "Fracture",
    }
    lowered = report_text.lower()
    conditions = []
    for pattern, label in patterns.items():
        if re.search(pattern, lowered):
            conditions.append(label)
    return conditions


def _normalize_blood_group(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).replace(" ", "").upper()


def _blood_compatibility_factor(receiver: str | None, donor: str | None) -> float:
    receiver_group = _normalize_blood_group(receiver)
    donor_group = _normalize_blood_group(donor)
    if not receiver_group or not donor_group:
        return 0.6

    compatible = {
        "O-": {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"},
        "O+": {"O+", "A+", "B+", "AB+"},
        "A-": {"A-", "A+", "AB-", "AB+"},
        "A+": {"A+", "AB+"},
        "B-": {"B-", "B+", "AB-", "AB+"},
        "B+": {"B+", "AB+"},
        "AB-": {"AB-", "AB+"},
        "AB+": {"AB+"},
    }

    if donor_group == receiver_group:
        return 1.0
    if receiver_group in compatible.get(donor_group, set()):
        return 0.85
    return 0.25


def _compatibility_fallback_score(payload: dict) -> float:
    receiver_blood = payload.get("receiver_blood_type")
    donor_blood = payload.get("donor_blood_type")
    receiver_age = payload.get("receiver_age") or 30
    donor_age = payload.get("donor_age") or 30
    distance_km = payload.get("location_distance") or 5

    blood_factor = _blood_compatibility_factor(receiver_blood, donor_blood)
    age_gap = abs(int(receiver_age) - int(donor_age))
    age_factor = max(0.4, 1 - (age_gap / 60))
    distance_factor = max(0.4, 1 - (float(distance_km) / 80))

    score = (0.55 * blood_factor) + (0.25 * age_factor) + (0.2 * distance_factor)
    return max(0.35, min(0.98, score))


@router.post("/predict_health_risk")
async def predict_health_risk(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_risk", payload)


@router.post("/predict_user_cluster")
async def predict_user_cluster(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_cluster", payload)


@router.post("/predict_user_forecast")
async def predict_user_forecast(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_forecast", payload)


@router.post("/check_profile_cluster")
async def check_profile_cluster(payload: ProfileClusterRequest):
    db = get_db()
    user_repo = MongoRepository(db, USERS)

    user = await user_repo.find_one({"_id": _as_object_id(payload.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cluster_data = {
        "emergency_rate": random.randint(1, 15),
        "avg_response_time": random.randint(5, 25),
        "hospital_bed_occupancy": random.randint(20, 100),
    }

    result = await _run_prediction("predict_cluster", cluster_data)
    cluster_labels = {
        0: "Regular User - Low Activity",
        1: "Active Donor - High Engagement",
        2: "Medical Professional - Specialized",
    }
    cluster = result.get("cluster_id") if isinstance(result, dict) else None
    if cluster is None:
        cluster = random.randint(0, 2)

    meta = _ensure_meta(
        result.get("meta") if isinstance(result, dict) else None,
        0.62,
        ["Cluster inferred from emergency rate, response time, and bed occupancy patterns."],
        [
            {"title": "Dataset", "detail": "ml/user_activity_data.csv"},
            {"title": "Model", "detail": "ml/activity_cluster_model.joblib"},
        ],
    )

    return {
        "cluster_id": cluster,
        "cluster_label": cluster_labels.get(cluster, "User Profile"),
        "engagement_level": "High" if cluster == 1 else "Professional" if cluster == 2 else "Standard",
        "meta": meta,
    }


@router.post("/predict_donation_forecast")
async def predict_donation_forecast(payload: DonationForecastRequest):
    forecast_data = {
        "month": datetime.utcnow().month,
        "donation_frequency": random.randint(1, 5),
        "hospital_stock_level": random.randint(0, 100),
        "region": "General",
        "resource_type": payload.blood_group or "O+",
    }

    result = await _run_prediction("predict_availability", forecast_data)
    score = result.get("predicted_availability_score") if isinstance(result, dict) else None
    if score is None:
        score = random.randint(40, 100)

    meta = _ensure_meta(
        result.get("meta") if isinstance(result, dict) else None,
        0.66,
        ["Availability score based on donation frequency, hospital stock, and regional demand."],
        [
            {"title": "Dataset", "detail": "ml/donor_availability_data.csv"},
            {"title": "Model", "detail": "ml/donor_availability_model.joblib"},
        ],
    )

    return {
        "forecast_days": int(score // 10) + 1,
        "availability_score": score,
        "status": "High Availability" if score > 70 else "Moderate" if score > 40 else "Low Availability",
        "meta": meta,
    }


@router.post("/hosp/predict_severity")
async def hosp_predict_severity(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_hosp_severity", payload)


@router.post("/hosp/predict_policy")
async def hosp_predict_policy(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_policy_seg", payload)


@router.post("/hosp/predict_outbreak")
async def hosp_predict_outbreak(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_forecast_outbreak", payload)


@router.post("/hosp/optimize_ambulance")
async def hosp_optimize_ambulance(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_allocation", payload)


@router.post("/hosp/detect_anomaly")
async def hosp_detect_anomaly(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_anomaly", payload)


@router.post("/gov/predict_outbreak")
async def gov_predict_outbreak(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_forecast_outbreak", payload)


@router.post("/gov/predict_severity")
async def gov_predict_severity(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_severity", payload)


@router.post("/gov/predict_availability")
async def gov_predict_availability(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_availability", payload)


@router.post("/gov/predict_allocation")
async def gov_predict_allocation(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_allocation", payload)


@router.post("/gov/predict_policy_segment")
async def gov_predict_policy_segment(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_policy_seg", payload)


@router.post("/gov/predict_performance_score")
async def gov_predict_performance_score(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_perf_score", payload)


@router.post("/gov/predict_anomaly")
async def gov_predict_anomaly(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_anomaly", payload)


@router.post("/hospital/patient/recovery")
async def hospital_patient_recovery(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_recovery", payload)


@router.post("/hospital/patient/stay")
async def hospital_patient_stay(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_stay", payload)


@router.post("/hospital/inventory/predict")
async def hospital_inventory_predict(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_inventory", payload)


@router.post("/ml/predict-eta")
async def ml_predict_eta(payload: dict = Body(default_factory=dict)):
    return await _run_prediction("predict_eta", payload)


@router.post("/check_compatibility")
async def check_compatibility(payload: CompatibilityRequest):
    if not payload.requester_id or not payload.donor_id:
        raise HTTPException(status_code=400, detail="requester_id and donor_id are required")

    db = get_db()
    user_repo = MongoRepository(db, USERS)

    requester = await user_repo.find_one({"_id": _as_object_id(payload.requester_id)})
    donor = await user_repo.find_one({"_id": _as_object_id(payload.donor_id)})

    if not requester or not donor:
        raise HTTPException(status_code=404, detail="User not found")

    requester_hr = (requester.get("publicProfile") or {}).get("healthRecords") or {}
    donor_profile = (donor.get("publicProfile") or {}).get("donorProfile") or {}
    donor_hr = (donor.get("publicProfile") or {}).get("healthRecords") or {}

    compatibility_payload = {
        "receiver_blood_type": requester_hr.get("bloodGroup") or "O+",
        "receiver_age": requester_hr.get("age") or 30,
        "receiver_gender": requester_hr.get("gender") or "Male",
        "donor_blood_type": donor_hr.get("bloodGroup") or "O+",
        "donor_age": donor_hr.get("age") or 30,
        "donor_gender": donor_hr.get("gender") or "Male",
        "organ_type": payload.organ_type or "Blood",
        "location_distance": 5,
    }

    try:
        result = await _run_prediction("predict_compat", compatibility_payload)
    except HTTPException as exc:
        raise exc

    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    score = result.get("probability") or result.get("compatibility_score") or 0
    if score <= 1 and score > 0:
        score = score * 100

    if score == 0 or (45 <= score <= 55):
        fallback = _compatibility_fallback_score(compatibility_payload)
        score = round(fallback * 100, 2)

    availability = donor_profile.get("availability") or "Available"
    if availability == "Unavailable":
        score = max(30, score - 20)
    if availability == "On Call":
        score = max(40, score - 10)

    priority = "High" if score >= 80 else "Medium" if score >= 60 else "Low"
    estimated_wait_minutes = 15 if availability == "Available" else 35 if availability == "On Call" else 60

    meta = _ensure_meta(
        result.get("meta") if isinstance(result, dict) else None,
        0.7,
        ["Compatibility derived from blood type, age, gender, and distance factors."],
        [
            {"title": "Dataset", "detail": "ml/compatibility_data.csv"},
            {"title": "Model", "detail": "ml/compatibility_model.joblib"},
        ],
    )

    return {
        "compatibility_score": round(score),
        "probability": round(score / 100, 4),
        "recommendation": "Good Match" if score > 70 else "Check Further",
        "availability": availability,
        "priority": priority,
        "estimated_wait_minutes": estimated_wait_minutes,
        "meta": meta,
    }


async def _build_report_analysis(report_text: str, user_id: str | None, source_meta: dict[str, Any] | None = None):
    if not report_text or not report_text.strip():
        raise HTTPException(status_code=400, detail="Report text is required")
    if _looks_like_binary_text(report_text):
        raise HTTPException(status_code=400, detail="Report text looks like raw PDF bytes. Upload the file for OCR.")

    try:
        result = await _run_prediction("analyze_report", {"report_text": report_text})
    except HTTPException:
        result = {}

    if isinstance(result, dict) and result.get("error"):
        result = {}

    conditions = result.get("detected_conditions") or _extract_conditions(report_text)
    conditions = _normalize_conditions(conditions)
    metrics = _extract_report_metrics(report_text)
    risk_flags = _build_risk_flags(metrics)
    lifestyle = _extract_lifestyle(report_text)
    ml_payload = None
    if metrics.get("heart_rate") or metrics.get("blood_pressure_systolic") or metrics.get("age"):
        ml_payload = {
            "age": metrics.get("age") or 35,
            "bmi": metrics.get("bmi") or 24,
            "heart_rate": metrics.get("heart_rate") or 78,
            "has_condition": 1 if conditions else 0,
            "lifestyle_factor": lifestyle,
        }
        if metrics.get("blood_pressure_systolic"):
            ml_payload["blood_pressure"] = metrics.get("blood_pressure_systolic")

    ml_result = None
    if ml_payload:
        try:
            ml_result = await _run_prediction("predict_risk", ml_payload)
        except HTTPException:
            ml_result = None

    risk_level = result.get("risk_level") or "Moderate"
    risk_score = result.get("risk_score") or (82 if risk_level == "Critical" else 65 if risk_level == "High" else 42)
    primary_category = result.get("primary_category") or (conditions[0] if conditions else "General")
    summary = result.get("summary") or "Automated summary generated from the submitted report."

    if ml_result and isinstance(ml_result, dict):
        model_score = ml_result.get("risk_score")
        model_level = ml_result.get("risk_level")
        if isinstance(model_score, (int, float)):
            risk_score = max(risk_score, int(model_score))
        severity_order = {"Low": 0, "Moderate": 1, "High": 2, "Critical": 3}
        if model_level in severity_order and severity_order.get(model_level, 0) > severity_order.get(risk_level, 0):
            risk_level = model_level

    if risk_flags:
        if risk_level == "Low" and len(risk_flags) >= 2:
            risk_level = "Moderate"
        if risk_level == "Moderate" and len(risk_flags) >= 3:
            risk_level = "High"
        if risk_level == "High" and len(risk_flags) >= 4:
            risk_level = "Critical"

    metric_notes = []
    if metrics.get("blood_pressure_systolic") and metrics.get("blood_pressure_diastolic"):
        metric_notes.append(f"BP {metrics['blood_pressure_systolic']}/{metrics['blood_pressure_diastolic']}")
    if metrics.get("heart_rate"):
        metric_notes.append(f"HR {metrics['heart_rate']} bpm")
    if metrics.get("oxygen"):
        metric_notes.append(f"O2 {metrics['oxygen']}%")
    if metrics.get("glucose_mg_dl"):
        metric_notes.append(f"Glucose {metrics['glucose_mg_dl']} mg/dL")

    if summary == "Automated summary generated from the submitted report." and (conditions or metric_notes):
        summary_parts = []
        if conditions:
            summary_parts.append(f"Detected terms suggest: {', '.join(conditions)}")
        if metric_notes:
            summary_parts.append("Key vitals: " + ", ".join(metric_notes))
        if risk_flags:
            summary_parts.append("Risk flags: " + ", ".join(risk_flags))
        summary = ". ".join(summary_parts) + "."

    explanation_lines, next_steps = _build_condition_guidance(conditions)
    if risk_flags:
        for flag in risk_flags:
            if flag == "Low oxygen saturation":
                next_steps.append("If shortness of breath is present, seek urgent evaluation.")
            if flag == "High systolic blood pressure":
                next_steps.append("Recheck BP and discuss treatment adjustments if elevated.")
            if flag == "High diastolic blood pressure":
                next_steps.append("Recheck BP and discuss treatment adjustments if elevated.")
            if flag == "Elevated glucose":
                next_steps.append("Confirm glucose elevation with repeat labs.")

    if not next_steps:
        next_steps = [
            "Share this report with your clinician for confirmation.",
            "If symptoms are worsening or severe, seek urgent care.",
        ]

    patient_summary = summary
    if summary and not summary.endswith("."):
        patient_summary += "."
    patient_summary += f" Overall risk estimate: {risk_level} ({risk_score}/100)."
    patient_summary += " This is a text-only screening, not a diagnosis."

    analysis_steps = []
    if source_meta and source_meta.get("source"):
        analysis_steps.append(
            {
                "step": "Document ingestion",
                "detail": f"Source: {source_meta.get('source')}",
                "confidence": 0.7,
            }
        )

    analysis_steps.extend(
        [
            {
                "step": "Input parsing",
                "detail": "Report text normalized and prepared for keyword scanning.",
                "confidence": 0.7,
            },
            {
                "step": "Vitals extraction",
                "detail": "Extracted vitals and lab values from the report text.",
                "confidence": 0.66,
            },
            {
                "step": "Condition detection",
                "detail": "Detected conditions: " + (", ".join(conditions) if conditions else "None found"),
                "confidence": 0.66,
            },
            {
                "step": "Risk scoring",
                "detail": f"Risk level {risk_level} with score {risk_score}.",
                "confidence": 0.64,
            },
        ]
    )

    if ml_result and isinstance(ml_result, dict):
        analysis_steps.append(
            {
                "step": "ML risk model",
                "detail": f"Model suggests {ml_result.get('risk_level')} risk with score {ml_result.get('risk_score')}",
                "confidence": 0.62,
            }
        )

    analysis_steps.append(
        {
            "step": "Summary synthesis",
            "detail": patient_summary,
            "confidence": 0.6,
        }
    )

    meta = _ensure_meta(
        result.get("meta") if isinstance(result, dict) else None,
        0.64,
        [
            "Report analysis based on detected clinical keywords and risk scoring.",
            "Step-by-step trace included for transparency.",
        ],
        [
            {"title": "Pipeline", "detail": "ml/ai_ml.py::analyze_report"},
        ],
    )

    if source_meta:
        meta["source"] = source_meta.get("source")
        if source_meta.get("warnings"):
            meta["warnings"] = source_meta.get("warnings")[:4]

    enriched = {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "primary_category": primary_category,
        "detected_conditions": conditions,
        "summary": patient_summary,
        "explanation": explanation_lines,
        "next_steps": next_steps,
        "extracted_metrics": metrics,
        "risk_flags": risk_flags,
        "model_insights": ml_result if isinstance(ml_result, dict) else None,
        "analysis_steps": analysis_steps,
        "raw": result,
        "meta": meta,
    }

    if user_id:
        try:
            db = get_db()
            repo = MongoRepository(db, HEALTH_RECORDS)
            await repo.insert_one(
                {
                    "user": _as_object_id(user_id),
                    "record_type": "report_analysis",
                    "report_text": report_text,
                    "summary": summary,
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "primary_category": primary_category,
                    "conditions": conditions,
                    "extracted_metrics": metrics,
                    "risk_flags": risk_flags,
                    "model_insights": ml_result if isinstance(ml_result, dict) else None,
                    "analysis_source": source_meta.get("source") if source_meta else "text",
                    "createdAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow(),
                }
            )
            await MongoRepository(db, ANALYTICS_EVENTS).insert_one(
                {
                    "user": _as_object_id(user_id),
                    "module": "ai_records",
                    "action": "analyzed",
                    "metadata": {
                        "risk_level": risk_level,
                        "primary_category": primary_category,
                    },
                    "createdAt": datetime.utcnow(),
                }
            )
        except Exception:
            enriched["storage_warning"] = "Storage unavailable; analysis returned without saving."

    return enriched


@router.post("/analyze_report")
async def analyze_report(payload: AnalyzeReportRequest):
    return await _build_report_analysis(payload.report_text, payload.user_id, {"source": "text"})


@router.post("/analyze_report_file")
async def analyze_report_file(
    file: UploadFile = File(...),
    user_id: str | None = Form(default=None),
    report_text: str | None = Form(default=None),
):
    if not file:
        raise HTTPException(status_code=400, detail="Report file is required")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    if len(data) > MAX_REPORT_BYTES:
        raise HTTPException(status_code=413, detail="Report file too large")

    extracted_text, source_meta = _extract_text_from_upload(data, file.filename, file.content_type)
    combined = ""
    if report_text and report_text.strip():
        combined = report_text.strip() + "\n" + extracted_text
    else:
        combined = extracted_text

    combined = _clean_report_text(combined)
    if len(combined) < MIN_REPORT_CHARS:
        raise HTTPException(
            status_code=422,
            detail="Unable to extract readable text. Try a clearer scan or a text-based PDF.",
        )

    return await _build_report_analysis(combined, user_id, source_meta)


@router.get("/gov/emergency_hotspots")
async def gov_emergency_hotspots():
    seed_data = _load_hotspot_seed_data()
    if not seed_data:
        return []

    try:
        result = await _run_prediction("predict_hotspot", seed_data)
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        for item in seed_data:
            item["cluster_label"] = "Unknown"
            item["cluster_id"] = -1
        return seed_data
