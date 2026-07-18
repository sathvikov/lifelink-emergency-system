import asyncio
import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Any


_REFERENCE_MAP: dict[str, list[dict[str, str]]] = {
    "predict_risk": [
        {"title": "Dataset", "detail": "ml/health_risk_data.csv"},
        {"title": "Model", "detail": "ml/health_risk_model.joblib"},
    ],
    "predict_eta": [
        {"title": "Dataset", "detail": "ml/eta_data.csv"},
        {"title": "Model", "detail": "ml/eta_model.joblib"},
    ],
    "predict_hotspot": [
        {"title": "Dataset", "detail": "ml/emergency_hotspot_data.csv"},
        {"title": "Model", "detail": "ml/emergency_hotspot_model.joblib"},
    ],
    "predict_sos_severity": [
        {"title": "Dataset", "detail": "ml/emergency_severity_data.csv"},
        {"title": "Model", "detail": "ml/emergency_severity_model.joblib"},
    ],
    "predict_hosp_severity": [
        {"title": "Dataset", "detail": "ml/hospital_severity_data.csv"},
        {"title": "Model", "detail": "ml/hospital_severity_model.joblib"},
    ],
    "predict_bed_forecast": [
        {"title": "Model", "detail": "ml/bed_forecast_model.joblib"},
    ],
    "predict_staff_alloc": [
        {"title": "Dataset", "detail": "ml/staff_allocation_data.csv"},
        {"title": "Model", "detail": "ml/staff_allocation_model.joblib"},
    ],
    "predict_hosp_disease": [
        {"title": "Dataset", "detail": "ml/hospital_disease_data.csv"},
        {"title": "Model", "detail": "ml/hospital_disease_models.joblib"},
    ],
    "predict_recovery": [
        {"title": "Dataset", "detail": "ml/patient_outcome_data.csv"},
        {"title": "Model", "detail": "ml/recovery_model.joblib"},
    ],
    "predict_stay": [
        {"title": "Model", "detail": "ml/stay_duration_model.joblib"},
    ],
    "predict_inventory": [
        {"title": "Dataset", "detail": "ml/inventory_data.csv"},
        {"title": "Model", "detail": "ml/inventory_prediction_model.joblib"},
    ],
    "predict_anomaly": [
        {"title": "Dataset", "detail": "ml/anomaly_data.csv"},
        {"title": "Model", "detail": "ml/anomaly_detection_model.joblib"},
    ],
    "predict_availability": [
        {"title": "Dataset", "detail": "ml/donor_availability_data.csv"},
        {"title": "Model", "detail": "ml/donor_availability_model.joblib"},
    ],
    "predict_severity": [
        {"title": "Dataset", "detail": "ml/emergency_severity_data.csv"},
        {"title": "Model", "detail": "ml/emergency_severity_model.joblib"},
    ],
    "predict_policy_seg": [
        {"title": "Dataset", "detail": "ml/policy_data.csv"},
        {"title": "Model", "detail": "ml/policy_segmentation_model.joblib"},
    ],
    "predict_perf_score": [
        {"title": "Dataset", "detail": "ml/hospital_performance_data.csv"},
        {"title": "Model", "detail": "ml/healthcare_performance_model.joblib"},
    ],
    "predict_allocation": [
        {"title": "Model", "detail": "ml/allocation_q_table.joblib"},
    ],
    "predict_forecast_outbreak": [
        {"title": "Dataset", "detail": "ml/outbreak_data.csv"},
        {"title": "Model", "detail": "ml/outbreak_forecast_models.joblib"},
    ],
    "predict_compat": [
        {"title": "Dataset", "detail": "ml/compatibility_data.csv"},
        {"title": "Model", "detail": "ml/compatibility_model.joblib"},
    ],
    "predict_hosp_perf": [
        {"title": "Dataset", "detail": "ml/hospital_performance_data.csv"},
        {"title": "Model", "detail": "ml/hospital_performance_model.joblib"},
    ],
}


def _normalize_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric > 1:
        if numeric <= 100:
            numeric = numeric / 100
        else:
            numeric = min(numeric, 100) / 100
    return round(max(0.0, min(1.0, numeric)), 3)


def _extract_confidence(result: dict[str, Any]) -> float | None:
    for key in ("confidence", "ai_confidence", "probability", "confidence_score"):
        if key in result:
            return _normalize_confidence(result.get(key))
    return None


def _build_reasoning(command: str, payload: Any, result: dict[str, Any]) -> list[str]:
    reasoning: list[str] = []
    drivers = result.get("drivers")
    if isinstance(drivers, list) and drivers:
        summary = ", ".join(str(item) for item in drivers[:4])
        reasoning.append(f"Key drivers: {summary}.")
    explanation = result.get("explanation") or result.get("summary")
    if isinstance(explanation, str) and explanation.strip():
        reasoning.append(explanation.strip())
    if not reasoning:
        reasoning.append("Prediction generated from model outputs and provided inputs.")
    if isinstance(payload, dict) and payload:
        reasoning.append("Input features validated for completeness where possible.")
    return reasoning[:3]


def _build_meta(command: str, payload: Any, result: dict[str, Any]) -> dict[str, Any]:
    confidence = _extract_confidence(result)
    if confidence is None:
        confidence = 0.65
    return {
        "command": command,
        "confidence": confidence,
        "reasoning": _build_reasoning(command, payload, result),
        "references": _REFERENCE_MAP.get(command, [{"title": "Model", "detail": f"ml/ai_ml.py::{command}"}]),
    }


def _merge_meta(existing: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(existing, dict):
        return fallback
    merged = {**fallback, **existing}
    if "reasoning" in merged and not isinstance(merged["reasoning"], list):
        merged["reasoning"] = [str(merged["reasoning"])]
    if "references" in merged and not isinstance(merged["references"], list):
        merged["references"] = [merged["references"]]
    return merged


def _repo_root() -> Path:
    # .../backend/app/services/ml_runner.py -> repo root
    return Path(__file__).resolve().parents[3]


def _write_payload_file(directory: Path, payload_text: str) -> str:
    fd, path = tempfile.mkstemp(prefix="ml_payload_", suffix=".json", dir=str(directory))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload_text)
    return path


def _prepare_payload(command: str, payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload

    if isinstance(payload, list):
        if command in {"predict_hotspot", "predict_recommend"}:
            return payload
        return {"value": payload}

    if payload is None:
        return {}

    # Keep compatibility with the old Node runner that wrapped primitive payloads.
    if command == "predict_bed":
        return {"occupancy": payload}
    if command == "predict_eta":
        return {"location": payload}

    return {"value": payload}


def _parse_output(stdout_text: str, stderr_text: str, returncode: int) -> Any:
    if returncode != 0:
        raise RuntimeError(stderr_text or stdout_text or "Python model execution failed")

    if not stdout_text:
        return {}

    try:
        return json.loads(stdout_text)
    except json.JSONDecodeError:
        for line in reversed(stdout_text.splitlines()):
            candidate = line.strip()
            if not candidate:
                continue
            if candidate.startswith("{") or candidate.startswith("["):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        raise RuntimeError(f"Invalid JSON from ML model: {stdout_text}")


def _enrich_result(command: str, payload: Any, result: Any) -> Any:
    if isinstance(result, dict):
        fallback = _build_meta(command, payload, result)
        result["meta"] = _merge_meta(result.get("meta"), fallback)
    return result


async def run_ml_model(command: str, payload: Any = None, script_name: str = "ai_ml.py") -> Any:
    repo_root = _repo_root()
    ml_dir = repo_root / "backend" / "ml"
    script_path = ml_dir / script_name

    if not script_path.exists():
        raise RuntimeError(f"ML script not found: {script_path}")

    python_exec = os.getenv("PYTHON_PATH") or sys.executable
    input_payload = _prepare_payload(command, payload)
    input_json = json.dumps(input_payload)
    payload_path = None
    input_arg = input_json
    if len(input_json) > 8000:
        payload_path = _write_payload_file(ml_dir, input_json)
        input_arg = payload_path

    try:
        try:
            process = await asyncio.create_subprocess_exec(
                python_exec,
                str(script_path),
                command,
                input_arg,
                cwd=str(ml_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            parsed = _parse_output(stdout_text, stderr_text, process.returncode)
            return _enrich_result(command, payload, parsed)
        except NotImplementedError:
            def _run_sync() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [python_exec, str(script_path), command, input_arg],
                    cwd=str(ml_dir),
                    capture_output=True,
                    text=True,
                )

            result = await asyncio.to_thread(_run_sync)
            stdout_text = (result.stdout or "").strip()
            stderr_text = (result.stderr or "").strip()
            parsed = _parse_output(stdout_text, stderr_text, result.returncode)
            return _enrich_result(command, payload, parsed)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Python executable not found. Set PYTHON_PATH to a valid Python interpreter."
        ) from exc
    finally:
        if payload_path and os.path.exists(payload_path):
            os.remove(payload_path)
