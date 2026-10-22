"""The semantic cache.

A repeated question should not cost a second model call. The cache is keyed
on the *meaning* of the question, not its wording: the query is embedded and
compared with the cached ones by cosine similarity (docs/PLAN.md D12).

Two guards keep it honest:
  * a turn that ended in a **clarifying question** is not cached — the answer
    depends on what the user says next;
  * the cache is only consulted when the question is complete, so a partial
    question never serves a complete answer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from apps.search.normalizer import normalize

from .embeddings import cosine_similarity, embed_texts
from .models import QueryLog

logger = logging.getLogger(__name__)

#: The similarity above which two questions are considered the same.
SIMILARITY_THRESHOLD = 0.95


@dataclass
class CacheEntry:
    """A cached answer."""

    query_log_id: str
    answer: str
    citations: list[dict]
    cards: list[dict]
    similarity: float = 0.0
    created_at: Any = None


def _is_cacheable(query_log: QueryLog) -> bool:
    """Whether a turn may be served from the cache later.

    A clarifying question is not an answer, and a turn that failed its
    guardrails must never be served as if it were a good answer.
    """
    metrics = query_log.metrics or {}
    guardrails = metrics.get("guardrails") or {}
    if guardrails.get("ok") is False:
        return False
    if metrics.get("clarifying_question"):
        return False
    return bool(query_log.answer)


def find_similar(
    query: str, *, threshold: float = SIMILARITY_THRESHOLD, limit: int = 50
) -> CacheEntry | None:
    """A cached answer for a question that means the same thing.

    Returns None when nothing similar enough is cached.
    """
    normalized = normalize(query)
    if not normalized:
        return None

    candidates = (
        QueryLog.objects.filter(query_hash=normalized)
        .exclude(query_embedding=None)
        .order_by("-created_at")[:limit]
    )

    # An exact normalised match is a hit without any embedding work.
    for candidate in candidates:
        if candidate.query_hash == normalized and _is_cacheable(candidate):
            return CacheEntry(
                query_log_id=str(candidate.id),
                answer=candidate.answer,
                citations=list(candidate.citations or []),
                cards=list((candidate.metrics or {}).get("cards_data") or []),
                similarity=1.0,
                created_at=candidate.created_at,
            )

    if not candidates:
        return None

    query_vector = embed_texts([query])
    if not query_vector:
        return None
    vector = query_vector[0]

    best: tuple[float, QueryLog] | None = None
    for candidate in candidates:
        if not _is_cacheable(candidate):
            continue
        similarity = cosine_similarity(
            vector, [float(x) for x in (candidate.query_embedding or [])]
        )
        if similarity >= threshold and (best is None or similarity > best[0]):
            best = (similarity, candidate)

    if best is None:
        return None

    similarity, candidate = best
    logger.info("semantic cache hit (%.3f) for %r", similarity, query[:60])
    return CacheEntry(
        query_log_id=str(candidate.id),
        answer=candidate.answer,
        citations=list(candidate.citations or []),
        cards=list((candidate.metrics or {}).get("cards_data") or []),
        similarity=similarity,
        created_at=candidate.created_at,
    )


def store(
    query: str,
    *,
    query_log: QueryLog,
    answer: str,
    citations: list[dict],
    cards: list[dict] | None = None,
) -> None:
    """Store a turn for later reuse."""
    if not answer:
        return
    try:
        vector = embed_texts([query])
    except Exception as exc:
        logger.warning("could not embed the query for the cache: %s", exc)
        return

    query_log.query_embedding = vector[0] if vector else None
    metrics = dict(query_log.metrics or {})
    metrics["cards_data"] = cards or []
    query_log.metrics = metrics
    query_log.save(update_fields=["query_embedding", "metrics"])


def invalidate() -> int:
    """Empty the cache — after a catalog change, the old answers are stale."""
    deleted = QueryLog.objects.exclude(query_embedding=None).update(query_embedding=None)
    logger.info("semantic cache invalidated (%d entries)", deleted)
    return deleted


def stats() -> dict:
    """How full the cache is."""
    total = QueryLog.objects.count()
    cached = QueryLog.objects.exclude(query_embedding=None).count()
    return {
        "total_turns": total,
        "cached_turns": cached,
        "hit_rate_capable": round(cached / total, 4) if total else 0.0,
        "threshold": SIMILARITY_THRESHOLD,
        "as_of": timezone.now().isoformat(),
    }
