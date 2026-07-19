from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import asyncpg

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR.parent))

import app.core.patch_asyncpg
from app.core.config import get_settings
from app.db.mongo import connect_to_mongo, close_mongo_connection
from scripts.seed_mass_demo_data import seed

SCHEMA_FILE = ROOT_DIR / "schema.sql"
BOOTSTRAP_CHECK_TABLE = "gov_hospitals"


def _normalize_dsn(postgres_url: str) -> str:
    if postgres_url.startswith("postgresql+asyncpg://"):
        postgres_url = postgres_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if "?" in postgres_url:
        base, query = postgres_url.split("?", 1)
        params = [p for p in query.split("&") if not p.startswith(("sslmode=", "channel_binding="))]
        if params:
            return f"{base}?{'&'.join(params)}"
        return base
    return postgres_url


async def _asyncpg_connect(dsn: str) -> asyncpg.Connection:
    postgres_url = os.environ.get("POSTGRES_URL", "")
    ssl = "require" if "sslmode=require" in postgres_url else None
    return await asyncpg.connect(dsn=dsn, ssl=ssl)


def _load_env() -> None:
    env_path = ROOT_DIR / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


async def _wait_for_postgres(dsn: str, retries: int = 12, delay_seconds: int = 5) -> None:
    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            conn = await _asyncpg_connect(dsn=dsn)
            await conn.close()
            return
        except Exception as exc:
            last_exc = exc
            print(f"[bootstrap_database] Postgres unavailable (attempt {attempt}/{retries}): {exc}")
            if attempt < retries:
                await asyncio.sleep(delay_seconds)
    raise RuntimeError("Unable to connect to Postgres after multiple attempts") from last_exc


async def _apply_schema(dsn: str) -> None:
    schema_files = [ROOT_DIR / "schema.sql", ROOT_DIR / "schema1.sql"]
    for schema_path in schema_files:
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file missing: {schema_path}")

        print(f"[bootstrap_database] Applying schema from {schema_path}")
        raw_sql = schema_path.read_text(encoding='utf-8')
        statements = [stmt.strip() for stmt in raw_sql.split(";") if stmt.strip()]
        conn = await _asyncpg_connect(dsn=dsn)
        try:
            for statement in statements:
                try:
                    await conn.execute(statement)
                except asyncpg.PostgresError as exc:
                    text = str(exc).lower()
                    if "create extension" in statement.lower() and "permission denied" in text:
                        print(f"[bootstrap_database] Warning: extension creation skipped: {exc}")
                        continue
                    if "already exists" in text:
                        continue
                    raise
        finally:
            await conn.close()


async def _needs_demo_seed(dsn: str) -> bool:
    conn = await _asyncpg_connect(dsn=dsn)
    try:
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = $1)",
            BOOTSTRAP_CHECK_TABLE,
        )
        if not exists:
            return True
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {BOOTSTRAP_CHECK_TABLE}")
        return count == 0
    finally:
        await conn.close()


def main() -> None:
    _load_env()
    settings = get_settings()
    postgres_url = settings.postgres_url
    print("[bootstrap_database] Using POSTGRES_URL:", postgres_url)
    print("[bootstrap_database] Using REDIS_URL:", settings.redis_url)
    print("[bootstrap_database] Using LLM_PROVIDER:", settings.llm_provider)
    print("[bootstrap_database] Using GROQ_API_KEY set:", bool(settings.groq_api_key))
    print("[bootstrap_database] Using OPENAI_API_KEY set:", bool(settings.openai_api_key))

    dsn = _normalize_dsn(postgres_url)

    async def _run() -> None:
        await _wait_for_postgres(dsn)
        await _apply_schema(dsn)

        if await _needs_demo_seed(dsn):
            print("[bootstrap_database] No demo data found. Seeding fresh data...")
            await connect_to_mongo()
            try:
                await seed()
            finally:
                await close_mongo_connection()
        else:
            print("[bootstrap_database] Existing bootstrapped data detected; skipping demo seed.")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
