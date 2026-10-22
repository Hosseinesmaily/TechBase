"""Retrieval: the semantic and lexical search over the chunk store.

Two backends, fused the same way the catalog search is:

  * **semantic** — pgvector over the chunk embeddings, scored by cosine
    similarity.
  * **lexical** — the shared Persian normaliser over the chunk text.

When the database has no pgvector extension (SQLite, or a Postgres without
the extension), the semantic side is skipped and the lexical side carries the
search. The retrieval API does not change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from django.db import connection

from apps.search.meili import SearchResult
from apps.search.normalizer import normalize
from apps.search.service import reciprocal_rank_fusion

from .embeddings import cosine_similarity, embed_texts
from .models import ContentChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """One retrieved chunk, with its score and citation."""

    chunk: ContentChunk
    score: float = 0.0
    lexical_score: float = 0.0
    semantic_score: float = 0.0

    @property
    def text(self) -> str:
        return self.chunk.text

    @property
    def citation(self) -> dict:
        """The citation payload for this chunk."""
        return {
            "page_slug": self.chunk.page.slug,
            "page_title": self.chunk.page.title,
            "section_path": self.chunk.section_path,
            "heading": self.chunk.heading,
            "url": self.chunk.citation_url,
            "entity_slug": (self.chunk.entity.slug if self.chunk.entity is not None else None),
            "score": round(self.score, 6),
        }


@dataclass
class RetrievalResult:
    """The outcome of one retrieval."""

    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    semantic_available: bool = True

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "semantic_available": self.semantic_available,
            "chunks": [chunk.citation for chunk in self.chunks],
        }


def vector_available() -> bool:
    """Whether this database can do vector search."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            return cursor.fetchone() is not None
    except Exception:
        # SQLite, or Postgres without the extension.
        return False


def semantic_search(query: str, limit: int = 20) -> list[RetrievedChunk]:
    """Semantic search over the chunk embeddings.

    The embeddings are compared in Python rather than with a pgvector operator:
    the store is small in v1, and this keeps the code working on SQLite (the
    test database) without a second implementation.
    """
    if not vector_available():
        return []

    query_vector = embed_texts([query])
    if not query_vector:
        return []
    vector = query_vector[0]

    scored: list[RetrievedChunk] = []
    chunks = ContentChunk.objects.select_related("page", "entity").exclude(embedding=None)
    for chunk in chunks:
        if not chunk.embedding:
            continue
        similarity = cosine_similarity(vector, [float(x) for x in chunk.embedding])
        if similarity <= 0:
            continue
        scored.append(RetrievedChunk(chunk=chunk, score=similarity, semantic_score=similarity))

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]


def _searchable_text(chunk: ContentChunk) -> str:
    """The text a chunk is searched in.

    It is the chunk's own text plus the names of the page and of the entity it
    is about. Without the entity's latin name and aliases, an English
    question ("what socket does the Ryzen 7 7800X3D use?") would not match a
    Persian chunk — the specs table says "سوکت" but never "socket".
    """
    parts = [
        chunk.heading,
        chunk.section_path,
        chunk.text,
        chunk.page.title,
        # The slug is the latin handle of the page: a page titled
        # «حافظهٔ DDR5 چیست؟» has the slug "ddr5", which is what an English
        # question can match.
        chunk.page.slug,
    ]
    entity = chunk.entity
    if entity is not None:
        parts.extend([entity.title, entity.title_fa, *entity.aliases])
        brand = entity.brand
        if brand is not None:
            parts.extend([brand.name, brand.name_fa])
        spec = getattr(entity, "spec", None)
        if spec is not None:
            # The spec *values* belong in the searchable text: "AM5" lives in
            # the specs table, not in the prose, and an answer must be able to
            # state it.
            for values in (spec.common or {}, spec.extra or {}):
                parts.extend(str(value) for value in values.values())
    return " ".join(part for part in parts if part)


def lexical_search(query: str, limit: int = 20) -> list[RetrievedChunk]:
    """Lexical search over the normalised chunk text.

    The matching is an **OR** over the query's tokens, scored by how many of
    them appear — the same shape as Meilisearch's default behaviour. Requiring
    *every* token would be far too strict for a natural-language question:
    "سوکت پردازنده‌های AMD چیست؟" would match nothing, because "پردازنده‌های"
    and "چیست؟" never appear verbatim in the text.
    """
    normalized_query = normalize(query)
    if not normalized_query:
        return []

    tokens = [token for token in normalized_query.split() if token]
    # Very common question words carry no signal; they would let any chunk
    # match. Both languages are listed: a Persian question and an English one
    # must be trimmed the same way.
    stopwords = {
        # Persian
        "چیست",
        "چه",
        "چگونه",
        "کدام",
        "است",
        "هست",
        "های",
        "ها",
        "در",
        "از",
        "با",
        "را",
        "که",
        "این",
        "آن",
        "می",
        "شود",
        "کنید",
        "کنم",
        "برای",
        "یک",
        "هم",
        "دربارهٔ",
        "درباره",
        "چیستی",
        "بدانید",
        "می‌دانید",
        "میدانید",
        "می‌دانیم",
        "بگو",
        "بگوید",
        "کنار",
        "روی",
        "بین",
        "تا",
        "یا",
        # English
        "the",
        "a",
        "an",
        "of",
        "is",
        "are",
        "to",
        "for",
        "about",
        "what",
        "which",
        "how",
        "do",
        "does",
        "did",
        "can",
        "should",
        "would",
        "and",
        "or",
        "it",
        "its",
        "i",
        "you",
        "we",
        "they",
        "my",
        "your",
        "our",
        "their",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "be",
        "been",
        "have",
        "has",
        "had",
        "there",
        "here",
        "that",
        "this",
        "these",
        "those",
        "if",
        "not",
        "no",
        "so",
        "than",
        "then",
        "too",
        "very",
        "just",
        "also",
        "know",
        "like",
        "get",
        "use",
        "using",
        "used",
        "tell",
        "give",
        "show",
        "need",
        "want",
        "much",
        "many",
        "some",
        "any",
    }
    # Strip the question mark and other trailing punctuation from a token.
    meaningful = [token.strip("?!.,؛:،") for token in tokens]
    meaningful = [token for token in meaningful if token and token not in stopwords]
    if not meaningful:
        meaningful = [token.strip("?!.,؛:،") for token in tokens if token.strip("?!.,؛:،")]

    scored: list[RetrievedChunk] = []

    for chunk in ContentChunk.objects.select_related("page", "entity"):
        haystack = normalize(_searchable_text(chunk))
        matched = [token for token in meaningful if token in haystack]
        if not matched:
            continue
        # The more of the query's terms a chunk covers, the better it matches.
        coverage = len(matched) / len(meaningful)
        # A term that appears many times is a stronger signal.
        frequency = sum(haystack.count(token) for token in matched)
        score = min(1.0, coverage * 0.8 + min(0.2, frequency / 20))
        # A chunk that only matches one word of a five-word question is noise.
        if len(matched) == 1 and len(meaningful) > 2 and score < 0.35:
            continue
        scored.append(RetrievedChunk(chunk=chunk, score=score, lexical_score=score))

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]


def retrieve(query: str, limit: int = 8) -> RetrievalResult:
    """Retrieve the chunks that best answer a query.

    The semantic and the lexical rankings are fused with RRF, so a chunk that
    one of them ranks highly is not lost to the other.
    """
    if not query.strip():
        return RetrievalResult(query=query, chunks=[])

    semantic = semantic_search(query, limit=limit * 3)
    lexical = lexical_search(query, limit=limit * 3)

    if not semantic:
        return RetrievalResult(
            query=query,
            chunks=lexical[:limit],
            semantic_available=False,
        )

    # Fuse the two rankings. The RRF helper works on `SearchResult`s, so the
    # chunks are mapped to a lightweight key first and the fused order is
    # applied back to the chunk objects.
    fused = reciprocal_rank_fusion(
        [
            [_as_search_result(chunk) for chunk in semantic],
            [_as_search_result(chunk) for chunk in lexical],
        ]
    )

    # Map the fused results back to the chunk objects, keeping the scores.
    by_key = {item.chunk.pk: item for item in [*semantic, *lexical]}
    results: list[RetrievedChunk] = []
    for item in fused:
        original = by_key.get(UUID(item.slug))
        if original is None:
            continue
        original.score = item.score
        results.append(original)

    return RetrievalResult(query=query, chunks=results[:limit], semantic_available=True)


def _as_search_result(chunk: RetrievedChunk) -> SearchResult:
    """A chunk as the search-result shape the RRF helper expects."""
    return SearchResult(
        id=str(chunk.chunk.pk),
        slug=str(chunk.chunk.pk),
        title=chunk.chunk.page.slug,
        kind="chunk",
        score=chunk.score,
    )
