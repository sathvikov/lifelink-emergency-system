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

from app.core.config import get_settings
from app.db.mongo import connect_to_mongo, close_mongo_connection
from scripts.seed_mass_demo_data import seed

SCHEMA_FILE = ROOT_DIR / "schema.sql"
BOOTSTRAP_CHECK_TABLE = "gov_hospitals"


def _normalize_dsn(postgres_url: str) -> str:
    if postgres_url.startswith("postgresql+asyncpg://"):
        return postgres_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return postgres_url


def _load_env() -> None:
    env_path = ROOT_DIR / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


async def _wait_for_postgres(dsn: str, retries: int = 12, delay_seconds: int = 5) -> None:
    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            conn = await asyncpg.connect(dsn=dsn)
            await conn.close()
            return
        except Exception as exc:
            last_exc = exc
            print(f"[bootstrap_database] Postgres unavailable (attempt {attempt}/{retries}): {exc}")
            if attempt < retries:
                await asyncio.sleep(delay_seconds)
    raise RuntimeError("Unable to connect to Postgres after multiple attempts") from last_exc


async def _apply_schema(dsn: str) -> None:
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file missing: {SCHEMA_FILE}")

    print(f"[bootstrap_database] Applying schema from {SCHEMA_FILE}")
    raw_sql = SCHEMA_FILE.read_text(encoding='utf-8')
    statements = [stmt.strip() for stmt in raw_sql.split(";") if stmt.strip()]
    async with await asyncpg.connect(dsn=dsn) as conn:
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


async def _needs_demo_seed(dsn: str) -> bool:
    async with await asyncpg.connect(dsn=dsn) as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = $1)",
            BOOTSTRAP_CHECK_TABLE,
        )
        if not exists:
            return True
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {BOOTSTRAP_CHECK_TABLE}")
        return count == 0


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
