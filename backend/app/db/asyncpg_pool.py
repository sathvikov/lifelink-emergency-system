from __future__ import annotations

from typing import Any

import asyncpg

from app.core.config import get_settings


class AsyncpgState:
    pool: asyncpg.Pool | None = None


asyncpg_state = AsyncpgState()


def _normalize_dsn(postgres_url: str) -> str:
    if postgres_url.startswith("postgresql+asyncpg://"):
        return postgres_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return postgres_url


async def connect_asyncpg() -> None:
    settings = get_settings()
    dsn = _normalize_dsn(settings.postgres_url)
    asyncpg_state.pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )


async def close_asyncpg() -> None:
    if asyncpg_state.pool is not None:
        await asyncpg_state.pool.close()
        asyncpg_state.pool = None


def get_asyncpg_pool() -> asyncpg.Pool:
    if asyncpg_state.pool is None:
        raise RuntimeError("Asyncpg pool not initialized")
    return asyncpg_state.pool


async def fetch_one(query: str, *args: Any) -> dict | None:
    pool = get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_all(query: str, *args: Any) -> list[dict]:
    pool = get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]


async def execute(query: str, *args: Any) -> str:
    pool = get_asyncpg_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
