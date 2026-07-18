from __future__ import annotations

import os
import time

import requests

from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "performance_results.json"


def test_api_speed():
    requests.get(f"{BASE_URL}/api/health", timeout=10)
    latencies = []
    response = None
    for _ in range(3):
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        elapsed = int((time.time() - start) * 1000)
        latencies.append(elapsed)
        time.sleep(0.1)

    best = min(latencies) if latencies else 0
    status = "PASS" if response and response.ok and best < 500 else "FAIL"
    record = log_test(
        "performance",
        status,
        details=f"Response time {best} ms",
        input_data={"endpoint": "/api/health"},
        output_data={"status_code": response.status_code if response else None, "response_time_ms": best, "samples": latencies},
    )
    record["response_time_ms"] = best
    save_result(RESULT_FILE, record)
    assert status == "PASS"
