from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AiChatMessage, AiChatSession


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _as_iso(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


class AiChatService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        msg_counts = (
            select(
                AiChatMessage.session_id,
                func.count(AiChatMessage.id).label("message_count"),
            )
            .where(AiChatMessage.user_id == user_id)
            .group_by(AiChatMessage.session_id)
            .subquery()
        )
        stmt = (
            select(AiChatSession, func.coalesce(msg_counts.c.message_count, 0))
            .outerjoin(msg_counts, AiChatSession.id == msg_counts.c.session_id)
            .where(AiChatSession.user_id == user_id)
            .order_by(AiChatSession.updated_at.desc())
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()
        sessions = []
        for record, message_count in rows:
            sessions.append(
                {
                    "id": record.id,
                    "title": record.title,
                    "module": record.module,
                    "mode": record.mode,
                    "createdAt": _as_iso(record.created_at),
                    "updatedAt": _as_iso(record.updated_at),
                    "messageCount": int(message_count or 0),
                }
            )
        return sessions

    async def get_session_summary(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        stmt = (
            select(AiChatSession)
            .where(AiChatSession.user_id == user_id)
            .where(AiChatSession.id == session_id)
        )
        async with self._session_factory() as session:
            record = (await session.execute(stmt)).scalar_one_or_none()
        if not record:
            return None
        return {
            "id": record.id,
            "title": record.title,
            "module": record.module,
            "mode": record.mode,
            "createdAt": _as_iso(record.created_at),
            "updatedAt": _as_iso(record.updated_at),
        }

    async def get_session_with_messages(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        session_row = await self.get_session_summary(user_id, session_id)
        if not session_row:
            return None

        stmt = (
            select(AiChatMessage)
            .where(AiChatMessage.user_id == user_id)
            .where(AiChatMessage.session_id == session_id)
            .order_by(AiChatMessage.created_at.asc())
        )
        async with self._session_factory() as session:
            messages = (await session.execute(stmt)).scalars().all()

        session_row["messages"] = [self._message_to_dict(msg) for msg in messages]
        return session_row

    async def get_recent_messages(self, user_id: str, session_id: str, limit: int = 6) -> list[dict[str, Any]]:
        stmt = (
            select(AiChatMessage)
            .where(AiChatMessage.user_id == user_id)
            .where(AiChatMessage.session_id == session_id)
            .order_by(AiChatMessage.created_at.desc())
            .limit(limit * 2)
        )
        async with self._session_factory() as session:
            messages = (await session.execute(stmt)).scalars().all()
        messages = list(reversed(messages))
        return [self._message_to_dict(msg) for msg in messages]

    async def create_session(
        self,
        user_id: str,
        title: str,
        module: str | None = None,
        mode: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        now = _now()
        session_id = session_id or uuid4().hex

        async with self._session_factory() as session:
            if session_id:
                existing = await session.get(AiChatSession, session_id)
                if existing:
                    if existing.user_id == user_id:
                        if title and existing.title == "New chat":
                            existing.title = title
                            existing.updated_at = now
                            await session.commit()
                        return {
                            "id": existing.id,
                            "title": existing.title,
                            "module": existing.module,
                            "mode": existing.mode,
                            "createdAt": _as_iso(existing.created_at),
                            "updatedAt": _as_iso(existing.updated_at),
                        }
                    # Requested session_id belongs to another user; generate a new one.
                    session_id = uuid4().hex

            record = AiChatSession(
                id=session_id,
                user_id=user_id,
                title=title,
                module=module,
                mode=mode,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await session.get(AiChatSession, session_id)
                if existing and existing.user_id == user_id:
                    return {
                        "id": existing.id,
                        "title": existing.title,
                        "module": existing.module,
                        "mode": existing.mode,
                        "createdAt": _as_iso(existing.created_at),
                        "updatedAt": _as_iso(existing.updated_at),
                    }
                session_id = uuid4().hex
                record.id = session_id
                session.add(record)
                await session.commit()

        return {
            "id": record.id,
            "title": record.title,
            "module": record.module,
            "mode": record.mode,
            "createdAt": _as_iso(record.created_at),
            "updatedAt": _as_iso(record.updated_at),
        }

    async def update_title(self, user_id: str, session_id: str, title: str) -> None:
        async with self._session_factory() as session:
            record = await session.get(AiChatSession, session_id)
            if not record or record.user_id != user_id:
                return
            record.title = title
            record.updated_at = _now()
            await session.commit()

    async def touch_session(self, session_id: str) -> None:
        async with self._session_factory() as session:
            record = await session.get(AiChatSession, session_id)
            if not record:
                return
            record.updated_at = _now()
            await session.commit()

    async def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = _now()
        record = AiChatMessage(
            id=uuid4().hex,
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            payload=payload,
            created_at=now,
        )
        async with self._session_factory() as session:
            session.add(record)
            session_obj = await session.get(AiChatSession, session_id)
            if session_obj:
                session_obj.updated_at = now
            await session.commit()
        return self._message_to_dict(record)

    @staticmethod
    def _message_to_dict(message: AiChatMessage) -> dict[str, Any]:
        payload = dict(message.payload or {})
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "createdAt": _as_iso(message.created_at),
            **payload,
        }
