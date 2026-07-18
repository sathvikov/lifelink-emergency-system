from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from bson import ObjectId
from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import ColumnElement

from app.db.models import Document
from app.services.serializer import normalize_mongo_doc, to_serializable


def _normalize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(val) for key, val in value.items()}
    return value


def _split_path(field: str) -> list[str]:
    return [segment for segment in field.split(".") if segment]


def _json_path_expr(field: str) -> ColumnElement:
    path = _split_path(field)
    if not path:
        return Document.data
    return func.jsonb_extract_path_text(Document.data, *path)


def _build_predicate(field: str, value: Any) -> ColumnElement:
    if field == "_id":
        return Document.id == str(_normalize_value(value))
    if field == "createdAt":
        return Document.created_at == _ensure_datetime(value)
    if field == "updatedAt":
        return Document.updated_at == _ensure_datetime(value)

    expr = _json_path_expr(field)
    norm_value = _normalize_value(value)
    return expr == str(norm_value)


def _build_filters(query: dict[str, Any]) -> list[ColumnElement]:
    filters: list[ColumnElement] = []
    for key, value in (query or {}).items():
        if key == "$or" and isinstance(value, list):
            clauses = [and_(*_build_filters(item)) for item in value if isinstance(item, dict)]
            if clauses:
                filters.append(or_(*clauses))
            continue
        if key == "$and" and isinstance(value, list):
            clauses = [and_(*_build_filters(item)) for item in value if isinstance(item, dict)]
            if clauses:
                filters.append(and_(*clauses))
            continue

        if isinstance(value, dict):
            for operator, operand in value.items():
                if operator == "$in":
                    values = [_normalize_value(item) for item in (operand or [])]
                    expr = _json_path_expr(key) if key not in {"_id", "createdAt", "updatedAt"} else None
                    if key == "_id":
                        filters.append(Document.id.in_([str(v) for v in values]))
                    elif key == "createdAt":
                        filters.append(Document.created_at.in_(values))
                    elif key == "updatedAt":
                        filters.append(Document.updated_at.in_(values))
                    elif expr is not None:
                        filters.append(expr.in_([str(v) for v in values]))
                elif operator == "$ne":
                    expr = _json_path_expr(key) if key not in {"_id", "createdAt", "updatedAt"} else None
                    norm_value = _normalize_value(operand)
                    if key == "_id":
                        filters.append(Document.id != str(norm_value))
                    elif key == "createdAt":
                        filters.append(Document.created_at != norm_value)
                    elif key == "updatedAt":
                        filters.append(Document.updated_at != norm_value)
                    elif expr is not None:
                        filters.append(expr != str(norm_value))
                elif operator == "$gte":
                    expr = _json_path_expr(key) if key not in {"_id", "createdAt", "updatedAt"} else None
                    norm_value = _normalize_value(operand)
                    if key == "createdAt":
                        filters.append(Document.created_at >= _ensure_datetime(norm_value))
                    elif key == "updatedAt":
                        filters.append(Document.updated_at >= _ensure_datetime(norm_value))
                    elif expr is not None:
                        filters.append(expr >= str(norm_value))
                elif operator == "$lte":
                    expr = _json_path_expr(key) if key not in {"_id", "createdAt", "updatedAt"} else None
                    norm_value = _normalize_value(operand)
                    if key == "createdAt":
                        filters.append(Document.created_at <= _ensure_datetime(norm_value))
                    elif key == "updatedAt":
                        filters.append(Document.updated_at <= _ensure_datetime(norm_value))
                    elif expr is not None:
                        filters.append(expr <= str(norm_value))
                elif operator == "$regex":
                    expr = _json_path_expr(key)
                    pattern = str(operand)
                    like = pattern.strip("^").strip("$")
                    like = like.replace(".*", "%")
                    if "%" not in like:
                        like = f"%{like}%"
                    filters.append(expr.ilike(like))
                elif operator == "$exists":
                    expr = func.jsonb_extract_path(Document.data, *_split_path(key))
                    if operand:
                        filters.append(expr.isnot(None))
                    else:
                        filters.append(expr.is_(None))
            continue

        filters.append(_build_predicate(key, value))

    return filters


def _ensure_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _apply_projection(doc: dict[str, Any], projection: dict[str, Any] | None) -> dict[str, Any]:
    if not projection:
        return doc

    include_fields = [key for key, enabled in projection.items() if enabled]
    if not include_fields:
        return doc

    result: dict[str, Any] = {"_id": doc.get("_id")}
    for field in include_fields:
        if field == "_id":
            continue
        if "." not in field:
            if field in doc:
                result[field] = doc[field]
            continue
        path = _split_path(field)
        current = doc
        for segment in path:
            if not isinstance(current, dict) or segment not in current:
                current = None
                break
            current = current.get(segment)
        if current is None:
            continue
        pointer = result
        for segment in path[:-1]:
            pointer = pointer.setdefault(segment, {})
        pointer[path[-1]] = current
    return result


@dataclass
class PgCursor:
    session_factory: async_sessionmaker[AsyncSession]
    collection: str
    query: dict[str, Any]
    projection: dict[str, Any] | None = None
    sort_spec: list[tuple[str, int]] | None = None
    limit_value: int | None = None

    def sort(self, sort: list[tuple[str, int]] | None):
        self.sort_spec = sort
        return self

    def limit(self, limit: int | None):
        self.limit_value = limit
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        limit = length or self.limit_value or 1000
        async with self.session_factory() as session:
            stmt = select(Document).where(Document.collection == self.collection)
            filters = _build_filters(self.query)
            if filters:
                stmt = stmt.where(and_(*filters))
            if self.sort_spec:
                for field, direction in self.sort_spec:
                    if field == "createdAt":
                        sort_col = Document.created_at
                    elif field == "updatedAt":
                        sort_col = Document.updated_at
                    elif field == "_id":
                        sort_col = Document.id
                    else:
                        sort_col = _json_path_expr(field)
                    stmt = stmt.order_by(sort_col.desc() if direction < 0 else sort_col.asc())
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            docs = []
            for row in result.scalars():
                payload = dict(row.data or {})
                payload.setdefault("_id", row.id)
                payload["createdAt"] = payload.get("createdAt") or row.created_at.isoformat()
                payload["updatedAt"] = payload.get("updatedAt") or row.updated_at.isoformat()
                docs.append(_apply_projection(normalize_mongo_doc(payload), self.projection))
            return docs


class PgCollection:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], collection: str):
        self._session_factory = session_factory
        self._collection = collection

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        cursor = PgCursor(self._session_factory, self._collection, query)
        docs = await cursor.to_list(length=1)
        return docs[0] if docs else None

    def find(self, query: dict[str, Any], projection: dict[str, Any] | None = None) -> PgCursor:
        return PgCursor(self._session_factory, self._collection, query, projection=projection)

    async def insert_one(self, document: dict[str, Any]):
        async with self._session_factory() as session:
            doc_data = to_serializable(document)
            doc_id = doc_data.get("_id") or str(ObjectId())
            doc_data["_id"] = doc_id
            created_at = _ensure_datetime(doc_data.get("createdAt") or datetime.utcnow())
            updated_at = _ensure_datetime(doc_data.get("updatedAt") or created_at)
            record = Document(
                id=str(doc_id),
                collection=self._collection,
                data=doc_data,
                created_at=created_at,
                updated_at=updated_at,
            )
            session.add(record)
            await session.commit()
            return type("InsertResult", (), {"inserted_id": doc_id})()

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        async with self._session_factory() as session:
            stmt = select(Document).where(Document.collection == self._collection)
            filters = _build_filters(query)
            if filters:
                stmt = stmt.where(and_(*filters))
            result = await session.execute(stmt.limit(1))
            record = result.scalar_one_or_none()
            if record is None:
                return type("UpdateResult", (), {"modified_count": 0})()
            set_data = update.get("$set") or update
            next_data = dict(record.data or {})
            next_data.update(to_serializable(set_data))
            record.data = next_data
            record.updated_at = datetime.utcnow()
            await session.commit()
            return type("UpdateResult", (), {"modified_count": 1})()

    async def delete_one(self, query: dict[str, Any]):
        async with self._session_factory() as session:
            stmt = select(Document).where(Document.collection == self._collection)
            filters = _build_filters(query)
            if filters:
                stmt = stmt.where(and_(*filters))
            result = await session.execute(stmt.limit(1))
            record = result.scalar_one_or_none()
            if record is None:
                return type("DeleteResult", (), {"deleted_count": 0})()
            await session.delete(record)
            await session.commit()
            return type("DeleteResult", (), {"deleted_count": 1})()

    async def count_documents(self, query: dict[str, Any]) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(Document).where(Document.collection == self._collection)
            filters = _build_filters(query)
            if filters:
                stmt = stmt.where(and_(*filters))
            result = await session.execute(stmt)
            return int(result.scalar() or 0)


class MongoRepository:
    def __init__(self, db: async_sessionmaker[AsyncSession], collection_name: str):
        self.collection = PgCollection(db, collection_name)
        self._session_factory = db
        self._collection_name = collection_name

    def _raise_db_error(self, exc: Exception) -> None:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        try:
            doc = await self.collection.find_one(query)
            return normalize_mongo_doc(doc)
        except Exception as exc:
            self._raise_db_error(exc)

    async def find_many(
        self,
        query: dict[str, Any],
        projection: dict[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        try:
            cursor = self.collection.find(query, projection)
            if sort:
                cursor = cursor.sort(sort)
            if limit:
                cursor = cursor.limit(limit)
            docs = await cursor.to_list(length=limit or 1000)
            return [normalize_mongo_doc(doc) for doc in docs]
        except Exception as exc:
            self._raise_db_error(exc)

    async def insert_one(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self.collection.insert_one(document)
            inserted = await self.collection.find_one({"_id": result.inserted_id})
            return normalize_mongo_doc(inserted)  # type: ignore[return-value]
        except Exception as exc:
            self._raise_db_error(exc)

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        return_new: bool = True,
    ) -> dict[str, Any] | None:
        try:
            await self.collection.update_one(query, update)
            if not return_new:
                return None
            doc = await self.collection.find_one(query)
            return normalize_mongo_doc(doc)
        except Exception as exc:
            self._raise_db_error(exc)

    async def update_by_id(self, doc_id: str, set_data: dict[str, Any]) -> dict[str, Any] | None:
        try:
            await self.collection.update_one({"_id": doc_id}, {"$set": set_data})
            doc = await self.collection.find_one({"_id": doc_id})
            return normalize_mongo_doc(doc)
        except Exception as exc:
            self._raise_db_error(exc)

    async def delete_by_id(self, doc_id: str) -> bool:
        try:
            result = await self.collection.delete_one({"_id": doc_id})
            return result.deleted_count > 0
        except Exception as exc:
            self._raise_db_error(exc)
