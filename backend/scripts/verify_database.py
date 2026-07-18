from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import asyncpg


def _normalize_dsn(postgres_url: str) -> str:
    if postgres_url.startswith("postgresql+asyncpg://"):
        return postgres_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return postgres_url


def _load_env() -> None:
    env_path = Path(__file__).resolve().parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)


async def _fetch_table_counts(dsn: str) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        if not tables:
            print('No public tables found.')
            return

        print(f"Found {len(tables)} public table(s):")
        for row in tables:
            print(f" - {row['tablename']}")

        print('\nRow counts:')
        for row in tables:
            name = row['tablename']
            try:
                count_row = await conn.fetchrow(f"SELECT COUNT(*) AS count FROM {name}")
                count = count_row['count'] if count_row else 0
                print(f"{name}: {count}")
            except Exception as exc:
                print(f"{name}: unable to count ({exc})")
    finally:
        await conn.close()


def main() -> None:
    _load_env()
    postgres_url = os.getenv('POSTGRES_URL') or os.getenv('LIFELINK_POSTGRES_URL')
    if not postgres_url:
        print('ERROR: POSTGRES_URL is not set in the environment or backend/.env')
        return

    dsn = _normalize_dsn(postgres_url)
    print(f'Using Postgres DSN: {dsn}')
    asyncio.run(_fetch_table_counts(dsn))


if __name__ == '__main__':
    main()
