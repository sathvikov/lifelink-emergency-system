from __future__ import annotations

import os
import time

import requests

from tests.utils.auth import build_token
from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "ai_results.json"


def test_reasoning():
    token = build_token("hospital")
    headers = {"Authorization": f"Bearer {token}"}

    trigger_payload = {
        "type": "demand_forecast",
        "payload": {"series": [9, 12, 14, 20], "steps": 4},
    }
    requests.post(f"{BASE_URL}/v2/system/predictions/trigger", json=trigger_payload, headers=headers, timeout=10)

    latest = None
    for _ in range(12):
        time.sleep(1)
        resp = requests.get(f"{BASE_URL}/v2/system/predictions/latest?type=demand_forecast", headers=headers, timeout=10)
        if resp.status_code == 200:
            latest = resp.json()
            break

    result = latest.get("result") if latest else {}
    prediction = result.get("prediction") if isinstance(result, dict) else None
    reasoning = result.get("reasoning") if isinstance(result, dict) else None
    confidence = result.get("confidence") if isinstance(result, dict) else None

    valid = bool(prediction) and confidence is not None and reasoning is not None
    status = "PASS" if valid else "FAIL"

    record = log_test(
        "ai_reasoning",
        status,
        details="Prediction contains confidence and reasoning",
        input_data=trigger_payload,
        output_data=latest,
    )
    record["valid"] = valid
    save_result(RESULT_FILE, record)
    assert status == "PASS"
