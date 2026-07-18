from __future__ import annotations

import os
import time

import requests

from tests.utils.auth import build_token
from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "privacy_results.json"


def _latest_prediction(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/v2/system/predictions/latest?type=federated_local"
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        return None
    return response.json()


def test_differential_privacy():
    token = build_token("hospital")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"hospital_id": "demo-hospital", "weight_count": 8, "noise_std": 0.08}
    requests.post(f"{BASE_URL}/v2/system/federated/train", json=payload, headers=headers, timeout=10)
    time.sleep(2)
    first = None
    for _ in range(12):
        first = _latest_prediction(token)
        if first:
            break
        time.sleep(1)

    requests.post(f"{BASE_URL}/v2/system/federated/train", json=payload, headers=headers, timeout=10)
    time.sleep(2)
    second = None
    for _ in range(12):
        second = _latest_prediction(token)
        if second:
            break
        time.sleep(1)

    difference_detected = False
    if first and second:
        w1 = (first.get("result") or {}).get("weights") or []
        w2 = (second.get("result") or {}).get("weights") or []
        if w1 and w2 and len(w1) == len(w2):
            difference_detected = any(abs(a - b) > 1e-6 for a, b in zip(w1, w2))

    status = "PASS" if difference_detected else "FAIL"
    record = log_test(
        "differential_privacy",
        status,
        details="Noise detected in weights" if difference_detected else "No weight variation detected",
        input_data=payload,
        output_data={"first": first, "second": second},
    )
    record["difference_detected"] = difference_detected
    save_result(RESULT_FILE, record)
    assert status == "PASS"
