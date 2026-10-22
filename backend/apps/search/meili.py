"""Meilisearch client wrapper.

The search backend is behind this interface so it can be swapped (DECISIONS
D2), and so the app keeps working when Meilisearch is down: every call falls
back to the PostgreSQL implementation in `apps.search.postgres`.

Meilisearch gives us lexical matching, typo tolerance, faceting and
autocomplete; PostgreSQL gives us the guaranteed-available baseline.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

#: The index that holds the searchable documents.
INDEX_ENTITIES = "entities"
INDEX_PRODUCTS = "products"
INDEX_PAGES = "pages"

#: Facets the UI can filter on.
ENTITY_FACETS = ["type", "brand", "status", "category"]
PRODUCT_FACETS = ["entity_type", "brand", "in_stock"]


@dataclass
class SearchResult:
    """One search result, normalised across backends."""

    id: str
    slug: str
    title: str
    subtitle: str = ""
    kind: str = "entity"  # entity | product | page
    score: float = 0.0
    price: str | None = None
    in_stock: bool | None = None
    extra: dict[str, Any] | None = None


@dataclass
class SearchResponse:
    """A full search response."""

    query: str
    hits: list[SearchResult]
    total: int
    facets: dict[str, dict[str, int]] | None = None
    took_ms: int = 0
    backend: str = "postgres"

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "total": self.total,
            "hits": [
                {
                    "id": hit.id,
                    "slug": hit.slug,
                    "title": hit.title,
                    "subtitle": hit.subtitle,
                    "kind": hit.kind,
                    "score": hit.score,
                    "price": hit.price,
                    "in_stock": hit.in_stock,
                    **(hit.extra or {}),
                }
                for hit in self.hits
            ],
            "facets": self.facets or {},
            "took_ms": self.took_ms,
            "backend": self.backend,
        }


class MeiliClient:
    """A thin wrapper over the Meilisearch HTTP API.

    Every method returns `None` (or an empty response) when Meilisearch is
    unreachable, so callers can fall back to PostgreSQL.
    """

    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        self.url = (url or settings.MEILI_HOST).rstrip("/")
        self.key = key if key is not None else settings.MEILI_MASTER_KEY
        self._client: Any = None
        self._unavailable = False

    # --- plumbing ----------------------------------------------------------

    @property
    def client(self):
        """The underlying client, or None when Meilisearch is unavailable."""
        if self._unavailable:
            return None
        if self._client is None:
            try:
                import meilisearch

                self._client = meilisearch.Client(self.url, self.key or None)
            except Exception as exc:  # not installed, bad URL, …
                logger.warning("meilisearch client unavailable: %s", exc)
                self._unavailable = True
                return None
        return self._client

    def available(self) -> bool:
        """Whether Meilisearch answers right now."""
        client = self.client
        if client is None:
            return False
        try:
            client.health()
            return True
        except Exception as exc:
            logger.info("meilisearch health check failed: %s", exc)
            self._unavailable = True
            return False

    # --- indexes -----------------------------------------------------------

    def ensure_index(self, index: str, primary_key: str = "id") -> bool:
        """Create the index and its searchable/facet attributes if missing."""
        client = self.client
        if client is None:
            return False
        # The index usually exists already — that is the normal case.
        with contextlib.suppress(Exception):
            client.create_index(index, {"primaryKey": primary_key})
        try:
            client.index(index).update_settings(
                {
                    "searchableAttributes": [
                        "title",
                        "title_fa",
                        "summary",
                        "summary_fa",
                        "aliases",
                        "brand",
                        "content",
                    ],
                    "filterableAttributes": ENTITY_FACETS + PRODUCT_FACETS,
                    "sortableAttributes": ["price", "updated_at"],
                    "rankingRules": [
                        "words",
                        "typo",
                        "proximity",
                        "attribute",
                        "sort",
                        "exactness",
                    ],
                    # Persian needs a separator set that treats ZWNJ as a word
                    # boundary, otherwise "می‌شود" indexes as one token.
                    "separatorTokens": ["_", "-", "،", "‌"],
                }
            )
            return True
        except Exception as exc:
            logger.warning("could not configure meilisearch index %s: %s", index, exc)
            return False

    def index_documents(self, index: str, documents: list[dict]) -> bool:
        """Add or replace documents in an index."""
        client = self.client
        if client is None or not documents:
            return False
        try:
            task = client.index(index).add_documents(documents)
            client.wait_for_task(task.task_uid, timeout_in_ms=30000)
            return True
        except Exception as exc:
            logger.warning("meilisearch indexing failed for %s: %s", index, exc)
            return False

    def delete_all(self, index: str) -> bool:
        """Remove every document from an index."""
        client = self.client
        if client is None:
            return False
        try:
            task = client.index(index).delete_all_documents()
            client.wait_for_task(task.task_uid, timeout_in_ms=30000)
            return True
        except Exception as exc:
            logger.warning("meilisearch delete failed for %s: %s", index, exc)
            return False

    # --- queries -----------------------------------------------------------

    def search(
        self,
        index: str,
        query: str,
        *,
        limit: int = 24,
        filters: str | None = None,
        facets: list[str] | None = None,
    ) -> dict | None:
        """Run a search. Returns None when Meilisearch is unavailable."""
        client = self.client
        if client is None:
            return None
        params: dict[str, Any] = {
            "limit": limit,
            "attributesToHighlight": [],
        }
        if filters:
            params["filter"] = filters
        if facets:
            params["facets"] = facets
        try:
            return client.index(index).search(query, params)
        except Exception as exc:
            logger.warning("meilisearch query failed on %s: %s", index, exc)
            return None

    def autocomplete(self, index: str, query: str, limit: int = 10) -> list[dict] | None:
        """Prefix suggestions. Returns None when Meilisearch is unavailable."""
        client = self.client
        if client is None:
            return None
        try:
            result = client.index(index).search(
                query,
                {
                    "limit": limit,
                    "attributesToRetrieve": ["title", "title_fa", "slug", "id"],
                    "matchingStrategy": "prefix",
                },
            )
            return list(result.get("hits", []))
        except Exception as exc:
            logger.warning("meilisearch autocomplete failed on %s: %s", index, exc)
            return None


#: The shared client instance.
_client: MeiliClient | None = None


def get_client() -> MeiliClient:
    """The shared Meilisearch client."""
    global _client
    if _client is None:
        _client = MeiliClient()
    return _client
