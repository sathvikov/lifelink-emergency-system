from __future__ import annotations

import os
import time

import requests

from tests.utils.auth import build_token
from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "privacy_results.json"


def test_federated_privacy():
    token = build_token("hospital")
    payload = {
        "hospital_id": "demo-hospital",
        "metrics": {"samples": 120},
        "weights": [0.1, 0.2, 0.3],
        "name": "Jane Doe",
        "phone": "+100000000",
        "patient_id": "p-123",
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.post(f"{BASE_URL}/v2/system/federated/train", json=payload, headers=headers, timeout=10)
        output = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    except Exception as exc:
        record = log_test("federated_privacy", "FAIL", details=str(exc), input_data=payload, output_data={})
        save_result(RESULT_FILE, record)
        assert False, "Federated privacy test failed"

    pii_fields = {"name", "phone", "patient_id"}
    contains_pii = any(field in output for field in pii_fields)
    status = "PASS" if response.ok and not contains_pii else "FAIL"
    details = "Only weights transmitted" if status == "PASS" else "PII detected in response"

    record = log_test("federated_privacy", status, details=details, input_data=payload, output_data=output)
    save_result(RESULT_FILE, record)
    assert status == "PASS"
