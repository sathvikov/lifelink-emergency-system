from __future__ import annotations

import os

import requests

from tests.utils.auth import build_token
from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "privacy_results.json"


def test_anonymization():
    token = build_token("public")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "id": "emg-1",
        "name": "Jane Doe",
        "phone": "+100000000",
        "address": "123 Test St",
        "severity": "High",
        "location": "12.9,77.5",
        "patient_id": "p-999",
    }

    response = requests.post(f"{BASE_URL}/v2/system/emergency/anonymized", json=payload, headers=headers, timeout=10)
    output = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

    anonymized = output.get("anonymized") or {}
    pii_found = any(key in anonymized for key in ["name", "phone", "address", "patient_id"])

    status = "PASS" if response.ok and not pii_found else "FAIL"
    record = log_test(
        "anonymization",
        status,
        details="PII removed from anonymized payload",
        input_data=payload,
        output_data=output,
    )
    record["pii_found"] = pii_found
    save_result(RESULT_FILE, record)
    assert status == "PASS"
