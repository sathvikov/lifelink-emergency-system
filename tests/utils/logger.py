from __future__ import annotations

import json
from datetime import datetime
from typing import Any

_COLOR = {
    "PASS": "\033[92m",
    "FAIL": "\033[91m",
    "INFO": "\033[94m",
    "RESET": "\033[0m",
}


def _colorize(text: str, status: str) -> str:
    return f"{_COLOR.get(status, _COLOR['INFO'])}{text}{_COLOR['RESET']}"


def log_test(
    name: str,
    status: str,
    details: str = "",
    input_data: Any | None = None,
    output_data: Any | None = None,
) -> dict:
    timestamp = datetime.utcnow().isoformat()
    header = f"[{timestamp}] {name} - {status}"
    print(_colorize(header, status))
    if details:
        print(f"  details: {details}")
    if input_data is not None:
        print(f"  input: {json.dumps(input_data, default=str)[:800]}")
    if output_data is not None:
        print(f"  output: {json.dumps(output_data, default=str)[:800]}")
    return {
        "timestamp": timestamp,
        "test": name,
        "status": status,
        "details": details,
        "input": input_data,
        "output": output_data,
    }
