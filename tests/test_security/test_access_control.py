from __future__ import annotations

import os

import requests

from tests.utils.auth import build_token
from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "security_results.json"


def test_access_control():
    endpoint = f"{BASE_URL}/v2/system/federated/aggregate"
    public_token = build_token("public")
    gov_token = build_token("government", sub_role="district_admin")

    public_resp = requests.post(endpoint, json={"limit": 2}, headers={"Authorization": f"Bearer {public_token}"}, timeout=10)
    gov_resp = requests.post(endpoint, json={"limit": 2}, headers={"Authorization": f"Bearer {gov_token}"}, timeout=10)

    public_denied = public_resp.status_code in (401, 403)
    gov_granted = gov_resp.status_code in (200, 202)

    status = "PASS" if public_denied and gov_granted else "FAIL"
    record = log_test(
        "rbac",
        status,
        details="Public denied, government granted",
        input_data={"public_status": public_resp.status_code, "gov_status": gov_resp.status_code},
        output_data={"public_body": public_resp.text[:200], "gov_body": gov_resp.text[:200]},
    )
    record.update({"public_access": "denied" if public_denied else "granted", "gov_access": "granted" if gov_granted else "denied"})
    save_result(RESULT_FILE, record)
    assert status == "PASS"
