from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base


class DbState:
    engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None


db_state = DbState()


async def connect_to_mongo() -> None:
    settings = get_settings()
    db_state.engine = create_async_engine(settings.postgres_url, pool_pre_ping=True)
    db_state.session_factory = async_sessionmaker(db_state.engine, expire_on_commit=False)

    async with db_state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_mongo_connection() -> None:
    if db_state.engine is not None:
        await db_state.engine.dispose()
        db_state.engine = None
        db_state.session_factory = None


def get_db() -> async_sessionmaker[AsyncSession]:
    if db_state.session_factory is None:
        raise RuntimeError("Database is not initialized")
    return db_state.session_factory
