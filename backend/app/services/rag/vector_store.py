from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("lifelink.rag")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _data_dir() -> Path:
    root = _repo_root() / ".rag"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _index_path() -> Path:
    return _data_dir() / "lifelink.faiss"


def _meta_path() -> Path:
    return _data_dir() / "lifelink_meta.jsonl"


def _embed_texts(texts: Iterable[str]) -> list[list[float]]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("sentence-transformers is required for embeddings") from exc

    settings = get_settings()
    model = SentenceTransformer(settings.embedding_model)
    return [embedding.tolist() for embedding in model.encode(list(texts), normalize_embeddings=True)]


def _load_index():
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("faiss-cpu is required for local vector search") from exc

    index_path = _index_path()
    if index_path.exists():
        return faiss.read_index(str(index_path))
    return None


def _save_index(index) -> None:
    import faiss

    faiss.write_index(index, str(_index_path()))


def _load_metadata() -> list[dict[str, Any]]:
    meta_path = _meta_path()
    if not meta_path.exists():
        return []
    items: list[dict[str, Any]] = []
    with meta_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def _save_metadata(items: list[dict[str, Any]]) -> None:
    meta_path = _meta_path()
    with meta_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=True))
            handle.write("\n")


def reset_index() -> None:
    index_path = _index_path()
    meta_path = _meta_path()
    if index_path.exists():
        index_path.unlink()
    if meta_path.exists():
        meta_path.unlink()


def upsert_documents(docs: list[dict[str, Any]]) -> dict:
    if not docs:
        return {"status": "noop"}

    embeddings = _embed_texts([doc["content"] for doc in docs])
    vectors = np.array(embeddings, dtype="float32")

    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("faiss-cpu is required for local vector search") from exc

    index = _load_index()
    if index is None:
        index = faiss.IndexFlatIP(vectors.shape[1])

    meta = _load_metadata()
    start_id = len(meta)

    index.add(vectors)
    for offset, doc in enumerate(docs):
        meta.append(
            {
                "id": start_id + offset,
                "content": doc["content"],
                "metadata": doc.get("metadata", {}),
            }
        )

    _save_index(index)
    _save_metadata(meta)
    return {"status": "inserted", "count": len(docs)}


def search(query: str, top_k: int | None = None, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    top_k = top_k or settings.rag_top_k

    index = _load_index()
    if index is None:
        return []

    meta = _load_metadata()
    if not meta:
        return []

    embedding = _embed_texts([query])[0]
    vector = np.array([embedding], dtype="float32")

    top_k = min(top_k, len(meta))
    distances, indices = index.search(vector, top_k)

    results: list[dict[str, Any]] = []
    for score, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(meta):
            continue
        item = meta[idx]
        results.append(
            {
                "content": item.get("content"),
                "metadata": item.get("metadata", {}),
                "score": float(score),
            }
        )

    if filters:
        role_filter = set(filters.get("roles") or [])
        user_filter = filters.get("user_id")
        module_filter = filters.get("module")
        filtered = []
        for item in results:
            metadata = item.get("metadata") or {}
            roles = set(metadata.get("roles") or [])
            module_tag = metadata.get("module")
            if role_filter and roles and not roles.intersection(role_filter):
                continue
            if user_filter and metadata.get("user_id") and str(metadata.get("user_id")) != str(user_filter):
                continue
            if module_filter and module_tag and str(module_tag) != str(module_filter):
                continue
            filtered.append(item)
        results = filtered

    tokens = [token for token in query.lower().split() if token]
    if tokens:
        for item in results:
            content = (item.get("content") or "").lower()
            lexical_hits = sum(content.count(token) for token in tokens)
            item["score"] = float(item.get("score", 0)) + (0.02 * lexical_hits)

    results.sort(key=lambda item: item.get("score", 0), reverse=True)
    return results
