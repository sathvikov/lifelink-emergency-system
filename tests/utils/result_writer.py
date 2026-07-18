from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _results_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "results"


def save_result(filename: str, data: dict[str, Any]) -> None:
    results_dir = _results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    file_path = results_dir / filename
    if file_path.exists():
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = []
    else:
        payload = []
    if not isinstance(payload, list):
        payload = []
    payload.append(data)
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
