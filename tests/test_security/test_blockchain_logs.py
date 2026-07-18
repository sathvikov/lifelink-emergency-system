from __future__ import annotations

import asyncio
import hashlib
import os
import time
from pathlib import Path

import asyncpg
import requests

from tests.utils.auth import build_token
from tests.utils.logger import log_test
from tests.utils.result_writer import save_result


BASE_URL = os.getenv("LIFELINK_BASE_URL", "http://localhost:3010")
RESULT_FILE = "security_results.json"


def _normalize_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _load_postgres_url() -> str | None:
    env_path = Path(__file__).resolve().parents[2] / "backend" / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("POSTGRES_URL="):
            return line.split("=", 1)[1].strip()
    return None


def _hash_chain(action: str, actor: str, details: str, timestamp: str, prev_hash: str | None) -> str:
    base = f"{action}|{actor}|{details}|{timestamp}"
    raw = f"{base}:{prev_hash or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_blockchain_logs():
    token = build_token("government", sub_role="district_admin")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"action": "test_audit", "details": "integrity_check"}

    resp = requests.post(f"{BASE_URL}/v2/system/audit/log", json=payload, headers=headers, timeout=10)
    if resp.status_code not in (200, 202):
        record = log_test("blockchain_integrity", "FAIL", details="Audit log API failed", input_data=payload, output_data={"status": resp.status_code})
        save_result(RESULT_FILE, record)
        assert False

    fallback = _load_postgres_url() or "postgresql://postgres:postgres@localhost:5432/lifelink_db"
    db_url = _normalize_dsn(os.getenv("LIFELINK_POSTGRES_URL", os.getenv("POSTGRES_URL", fallback)))

    async def _fetch_latest():
        conn = await asyncpg.connect(dsn=db_url)
        row = await conn.fetchrow(
            """
            SELECT action, actor, timestamp, hash, prev_hash
            FROM audit_logs
            WHERE action = $1 AND actor = $2
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            payload["action"],
            f"test-government",
        )
        await conn.close()
        return dict(row) if row else None

    record_row = None
    for _ in range(10):
        record_row = asyncio.run(_fetch_latest())
        if record_row:
            break
        time.sleep(1)
    if not record_row:
        record = log_test("blockchain_integrity", "FAIL", details="No audit log found", input_data=payload, output_data={})
        save_result(RESULT_FILE, record)
        assert False

    timestamp = record_row["timestamp"].isoformat() if record_row.get("timestamp") else ""
    expected_hash = _hash_chain(record_row["action"], record_row["actor"], payload["details"], timestamp, record_row.get("prev_hash"))
    tampered_hash = _hash_chain("tampered", record_row["actor"], payload["details"], timestamp, record_row.get("prev_hash"))

    tamper_detected = tampered_hash != record_row.get("hash")
    status = "PASS" if expected_hash == record_row.get("hash") and tamper_detected else "FAIL"

    record = log_test(
        "blockchain_integrity",
        status,
        details="Hash chain integrity validation",
        input_data=payload,
        output_data={"stored": record_row.get("hash"), "expected": expected_hash, "tampered": tampered_hash},
    )
    record["tamper_detected"] = tamper_detected
    save_result(RESULT_FILE, record)
    assert status == "PASS"
