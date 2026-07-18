from __future__ import annotations

from typing import Any

from app.services.rag.vector_store import search as vector_search, upsert_documents


def _match_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, value in filters.items():
        if key not in metadata:
            return False
        if isinstance(value, (list, tuple, set)):
            if metadata.get(key) not in value:
                return False
        else:
            if metadata.get(key) != value:
                return False
    return True


def _confidence_from_score(score: float) -> float:
    if score <= 1.0 and score >= -1.0:
        return max(0.0, min(1.0, (score + 1.0) / 2.0))
    return max(0.0, min(1.0, score))


def _citation_from_metadata(metadata: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "source": metadata.get("source", "unknown"),
        "reference": metadata.get("id") or metadata.get("ref") or metadata.get("title"),
        "score": score,
    }


class RetrievalIndex:
    def ingest(self, docs: list[dict[str, Any]]) -> dict[str, Any]:
        return upsert_documents(docs)

    def search(
        self,
        query: str,
        top_k: int = 6,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        results = vector_search(query, top_k=top_k)
        if filters:
            results = [item for item in results if _match_filters(item.get("metadata", {}), filters)]

        enriched = []
        citations = []
        for item in results:
            score = float(item.get("score") or 0.0)
            confidence = _confidence_from_score(score)
            metadata = item.get("metadata", {})
            enriched.append({
                "content": item.get("content"),
                "metadata": metadata,
                "score": score,
                "confidence": confidence,
            })
            citations.append(_citation_from_metadata(metadata, score))

        return {
            "results": enriched,
            "citations": citations,
        }
