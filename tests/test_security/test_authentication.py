from __future__ import annotations

import os

import requests

from tests.utils.auth import build_token
from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "security_results.json"


def test_authentication():
    endpoint = f"{BASE_URL}/v2/system/predictions/latest?type=federated_local"

    no_token = requests.get(endpoint, timeout=10)
    invalid_token = requests.get(endpoint, headers={"Authorization": "Bearer invalid"}, timeout=10)

    valid_token = build_token("hospital")
    valid_resp = requests.get(endpoint, headers={"Authorization": f"Bearer {valid_token}"}, timeout=10)

    status = "PASS"
    if no_token.status_code not in (401, 403):
        status = "FAIL"
    if invalid_token.status_code not in (401, 403):
        status = "FAIL"
    if valid_resp.status_code in (401, 403):
        status = "FAIL"

    record = log_test(
        "authentication",
        status,
        details="Token validation behavior",
        input_data={"no_token": no_token.status_code, "invalid": invalid_token.status_code, "valid": valid_resp.status_code},
        output_data={"valid_body": valid_resp.text[:300]},
    )
    save_result(RESULT_FILE, record)
    assert status == "PASS"
