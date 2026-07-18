from __future__ import annotations

import os
import time

import requests

from tests.utils.auth import build_token
from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "ai_results.json"


def test_predictions():
    token = build_token("hospital")
    headers = {"Authorization": f"Bearer {token}"}
    trigger_payload = {
        "type": "demand_forecast",
        "payload": {"series": [12, 15, 18, 22], "steps": 4},
    }

    trigger = requests.post(f"{BASE_URL}/v2/system/predictions/trigger", json=trigger_payload, headers=headers, timeout=10)
    trigger_out = trigger.json() if trigger.headers.get("content-type", "").startswith("application/json") else {}

    latest = None
    for _ in range(12):
        time.sleep(1)
        resp = requests.get(f"{BASE_URL}/v2/system/predictions/latest?type=demand_forecast", headers=headers, timeout=10)
        if resp.status_code == 200:
            latest = resp.json()
            break

    valid = trigger.status_code in (200, 202) and latest is not None
    status = "PASS" if valid else "FAIL"
    record = log_test(
        "ai_output",
        status,
        details="Prediction exists and is retrievable",
        input_data=trigger_payload,
        output_data={"trigger": trigger_out, "latest": latest},
    )
    save_result(RESULT_FILE, record)
    assert status == "PASS"
