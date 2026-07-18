from __future__ import annotations

import asyncio
import json
import os
import socket
from datetime import datetime
from pathlib import Path

import asyncpg


def _normalize_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _load_postgres_url() -> str:
    env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("POSTGRES_URL="):
                return line.split("=", 1)[1].strip()
    return "postgresql://postgres:postgres@localhost:5432/lifelink_db"


async def _ensure_user(conn: asyncpg.Connection, user_id: str, role: str, sub_role: str | None = None) -> None:
    row = await conn.fetchrow(
        "SELECT id FROM documents WHERE id = $1 AND collection = 'users'",
        user_id,
    )
    if row:
        return
    now = datetime.utcnow()
    payload = json.dumps(
        {
            "name": f"Test {role.title()}",
            "email": f"{role}@test.local",
            "role": role,
            "subRole": sub_role,
            "isVerified": True,
            "createdAt": now.isoformat(),
        }
    )
    await conn.execute(
        """
        INSERT INTO documents (id, collection, data, created_at, updated_at)
        VALUES ($1, $2, $3::jsonb, $4, $5)
        """,
        user_id,
        "users",
        payload,
        now,
        now,
    )


def pytest_sessionstart(session):
    url = os.getenv("LIFELINK_POSTGRES_URL") or os.getenv("POSTGRES_URL") or _load_postgres_url()
    dsn = _normalize_dsn(url)
    if not os.getenv("LIFELINK_BASE_URL"):
        def _port_open(port: int) -> bool:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return True
            except OSError:
                return False

        candidate_ports = [3010, 3001]
        chosen = next((p for p in candidate_ports if _port_open(p)), 3010)
        os.environ["LIFELINK_BASE_URL"] = f"http://127.0.0.1:{chosen}"

    async def _seed():
        conn = await asyncpg.connect(dsn=dsn)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id VARCHAR(40) PRIMARY KEY,
                type VARCHAR(80) NOT NULL,
                result JSONB NOT NULL DEFAULT '{}'::jsonb,
                confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id VARCHAR(40) PRIMARY KEY,
                action VARCHAR(120) NOT NULL,
                actor VARCHAR(120) NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
                hash VARCHAR(128) NOT NULL,
                prev_hash VARCHAR(128)
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS emergencies (
                id VARCHAR(40) PRIMARY KEY,
                type VARCHAR(80) NOT NULL,
                severity VARCHAR(40) NOT NULL,
                location VARCHAR(240) NOT NULL,
                status VARCHAR(40) NOT NULL DEFAULT 'active',
                timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
                assigned_hospital VARCHAR(40)
            )
            """
        )
        await _ensure_user(conn, "test-public", "public")
        await _ensure_user(conn, "test-hospital", "hospital")
        await _ensure_user(conn, "test-government", "government", "district_admin")
        await conn.close()

    asyncio.run(_seed())


def pytest_sessionfinish(session, exitstatus):
    results_dir = Path(__file__).resolve().parent / "results"
    summary_path = results_dir / "summary_report.txt"
    results = {
        "Privacy": results_dir / "privacy_results.json",
        "Security": results_dir / "security_results.json",
        "AI": results_dir / "ai_results.json",
        "Performance": results_dir / "performance_results.json",
    }

    totals = 0
    passed = 0
    lines = ["## Test Summary:\n"]
    for label, path in results.items():
        status = "PENDING"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = []
            if payload:
                totals += len(payload)
                passed += sum(1 for item in payload if item.get("status") == "PASS")
                status = "PASS" if all(item.get("status") == "PASS" for item in payload) else "FAIL"
        lines.append(f"{label}: {status}\n")

    percentage = int((passed / totals) * 100) if totals else 0
    lines.append("\n")
    lines.append(f"Overall: {percentage}% PASS\n")
    summary_path.write_text("".join(lines), encoding="utf-8")
