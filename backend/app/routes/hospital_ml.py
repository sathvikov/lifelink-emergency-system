from fastapi import APIRouter, Body, HTTPException

from app.core.celery_app import celery_app
from app.services.ml_runner import run_ml_model
from app.services.prediction_store import get_latest_prediction

router = APIRouter(tags=["hospital-ml"])


async def _run(command: str, payload: dict):
    celery_app.send_task("system.generate_predictions", args=[command, payload])
    cached = await get_latest_prediction(command)
    if cached and isinstance(cached.get("result"), dict):
        result = cached["result"]
        if "meta" not in result:
            result["meta"] = {
                "confidence": cached.get("confidence", 0.0),
                "reasoning": ["Serving latest cached prediction; fresh run queued."],
                "references": [{"title": "Task", "detail": f"system.generate_predictions::{command}"}],
            }
        return result

    if command == "predict_inventory":
        try:
            result = await run_ml_model(command, payload, "ai_ml.py")
            if isinstance(result, dict):
                return result
        except Exception as exc:
            return {
                "status": "queued",
                "error": f"Inventory prediction fallback failed: {exc}",
                "meta": {
                    "confidence": 0.0,
                    "reasoning": ["Prediction queued for background processing."],
                    "references": [{"title": "Task", "detail": f"system.generate_predictions::{command}"}],
                },
            }

    return {
        "status": "queued",
        "meta": {
            "confidence": 0.0,
            "reasoning": ["Prediction queued for background processing."],
            "references": [{"title": "Task", "detail": f"system.generate_predictions::{command}"}],
        },
    }


@router.post("/triage")
async def triage(payload: dict = Body(default_factory=dict)):
    return await _run("predict_hosp_severity", payload)


@router.post("/eta")
async def eta(payload: dict = Body(default_factory=dict)):
    return await _run("predict_eta", payload)


@router.post("/bed_forecast")
async def bed_forecast(payload: dict = Body(default_factory=dict)):
    body = {**payload, "hospital_id": 1}
    return await _run("predict_bed_forecast", body)


@router.post("/staff")
async def staff(payload: dict = Body(default_factory=dict)):
    return await _run("predict_staff_alloc", payload)


@router.post("/donors")
async def donors(payload: dict = Body(default_factory=dict)):
    return await _run("predict_compat", payload)


@router.post("/performance")
async def performance(payload: dict = Body(default_factory=dict)):
    return await _run("predict_hosp_perf", payload)


@router.post("/predict_eta")
async def predict_eta(payload: dict = Body(default_factory=dict)):
    return await _run("predict_eta", payload)


@router.post("/predict_bed_forecast")
async def predict_bed_forecast(payload: dict = Body(default_factory=dict)):
    return await _run("predict_bed_forecast", payload)


@router.post("/predict_staff_allocation")
async def predict_staff_allocation(payload: dict = Body(default_factory=dict)):
    return await _run("predict_staff_alloc", payload)


@router.post("/predict_disease_forecast")
async def predict_disease_forecast(payload: dict = Body(default_factory=dict)):
    return await _run("predict_hosp_disease", payload)


@router.post("/predict_recovery")
async def predict_recovery(payload: dict = Body(default_factory=dict)):
    return await _run("predict_recovery", payload)


@router.post("/predict_stay_duration")
async def predict_stay_duration(payload: dict = Body(default_factory=dict)):
    return await _run("predict_stay", payload)


@router.post("/predict_performance")
async def predict_performance(payload: dict = Body(default_factory=dict)):
    return await _run("predict_hosp_perf", payload)


@router.post("/inventory")
async def inventory(payload: dict = Body(default_factory=dict)):
    return await _run("predict_inventory", payload)
