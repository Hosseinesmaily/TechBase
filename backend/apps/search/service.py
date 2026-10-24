"""The hybrid search service.

The pipeline is:
  1. Meilisearch — lexical, typo-tolerant, faceted.
  2. PostgreSQL — the always-available baseline.
  3. Reciprocal Rank Fusion (RRF) merges the two ranked lists.

RRF is parameter-free and robust (docs/PLAN.md D3): a document's fused score
is `Σ 1/(k + rank)`, so a document that ranks well in *either* list wins,
without having to calibrate two different score scales.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import postgres
from .intent import SearchIntent, understand_search
from .meili import (
    INDEX_ENTITIES,
    INDEX_PAGES,
    INDEX_PRODUCTS,
    MeiliClient,
    SearchResponse,
    SearchResult,
    get_client,
)
from .normalizer import normalize

logger = logging.getLogger(__name__)

#: The RRF constant. 60 is the value from the original paper; it damps the
#: influence of the very top ranks, which matters when the two backends
#: disagree.
RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[SearchResult]], k: int = RRF_K
) -> list[SearchResult]:
    """Merge several ranked lists into one.

    Each result is identified by `kind` + `slug`, so the same product found by
    both backends counts twice — which is exactly what we want.
    """
    scores: dict[tuple[str, str], float] = {}
    merged: dict[tuple[str, str], SearchResult] = {}

    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            key = (hit.kind, hit.slug)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in merged:
                merged[key] = hit
            else:
                # Keep the richest payload.
                existing = merged[key]
                if hit.subtitle and not existing.subtitle:
                    existing.subtitle = hit.subtitle
                if hit.price and not existing.price:
                    existing.price = hit.price
                if hit.in_stock is not None and existing.in_stock is None:
                    existing.in_stock = hit.in_stock

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    results: list[SearchResult] = []
    for (kind, slug), score in ordered:
        hit = merged[(kind, slug)]
        hit.score = round(score, 6)
        results.append(hit)
    return results


def _meili_to_results(raw: dict[str, Any], kind: str) -> list[SearchResult]:
    """Convert a Meilisearch response into our result shape."""
    results: list[SearchResult] = []
    for hit in raw.get("hits", []):
        results.append(
            SearchResult(
                id=str(hit.get("id", "")),
                slug=hit.get("slug", ""),
                title=hit.get("title_fa") or hit.get("title", ""),
                subtitle=(
                    "" if kind == "product" else hit.get("summary_fa") or hit.get("summary", "")
                ),
                kind=hit.get("kind", kind),
                score=0.0,
                price=hit.get("price"),
                in_stock=hit.get("in_stock"),
                extra={
                    k: v
                    for k, v in hit.items()
                    if k
                    in {
                        "entity_type",
                        "entity_slug",
                        "sku",
                        "currency",
                        "stock",
                        "updated_at",
                        "brand",
                        "page_type",
                    }
                },
            )
        )
    return results


def search(
    query: str,
    *,
    limit: int = 24,
    entity_type: str | None = None,
    brand: str | None = None,
    in_stock: bool | None = None,
    kind: str | None = None,
    use_meili: bool = True,
) -> SearchResponse:
    """Search the catalog, fusing the lexical and the PostgreSQL results.

    When Meilisearch is unavailable the PostgreSQL results are returned
    unchanged — the search still works, it is just less forgiving of typos.
    """
    started = time.perf_counter()
    original_query = query.strip()
    if not original_query:
        return SearchResponse(query="", hits=[], total=0, backend="postgres")

    intent = understand_search(original_query)
    effective_type = entity_type or intent.entity_type or None
    effective_query = intent.query or ("" if effective_type else normalize(original_query))
    effective_kind = kind or ("product" if effective_type and not effective_query else None)

    # The PostgreSQL baseline is always computed: it is the fallback and it
    # also catches what the lexical index has not seen yet.
    pg_response = postgres.search(
        effective_query,
        limit=limit * 2,
        entity_type=effective_type,
        brand=brand,
        in_stock=in_stock,
        kind=effective_kind,
    )

    meili_rankings: list[list[SearchResult]] = []
    facets: dict[str, dict[str, int]] = dict(pg_response.facets or {})

    if use_meili:
        client: MeiliClient = get_client()
        if client.available():
            filters = _build_filters(effective_type, brand, in_stock)
            for index, kind_name in (
                (INDEX_ENTITIES, "entity"),
                (INDEX_PRODUCTS, "product"),
                (INDEX_PAGES, "page"),
            ):
                if effective_kind is not None and effective_kind != kind_name:
                    continue
                raw = client.search(index, effective_query, limit=limit, filters=filters)
                if raw is None:
                    continue
                meili_rankings.append(_meili_to_results(raw, kind_name))
                for facet_name, values in (raw.get("facetDistribution") or {}).items():
                    facets.setdefault(facet_name, {})
                    for value, count in values.items():
                        facets[facet_name][value] = facets[facet_name].get(value, 0) + count

    if meili_rankings:
        fused = reciprocal_rank_fusion([*meili_rankings, pg_response.hits])
        hits = _rank_recommendations(fused, intent)
        backend = "hybrid"
    else:
        hits = _rank_recommendations(pg_response.hits, intent)
        backend = "postgres"

    total = max(pg_response.total, len(hits))
    hits = hits[:limit]

    took_ms = int((time.perf_counter() - started) * 1000)

    return SearchResponse(
        query=original_query,
        hits=hits,
        total=total,
        facets=facets,
        took_ms=took_ms,
        backend=backend,
        intent={
            "entity_type": effective_type or "",
            "use_case": intent.use_case,
            "resolution": intent.resolution,
            "recommendations": "gaming" if intent.use_case == "gaming" else "",
        },
    )


def _rank_recommendations(hits: list[SearchResult], intent: SearchIntent) -> list[SearchResult]:
    """Put in-stock gaming parts first and use measured FPS when available."""
    if intent.use_case != "gaming" or intent.entity_type != "gpu":
        return hits

    products = [hit for hit in hits if hit.kind == "product"]
    frame_rates: dict[str, float] = {}
    if products and intent.resolution:
        from apps.benchmarks.models import Benchmark

        slugs = [str((hit.extra or {}).get("entity_slug", "")) for hit in products]
        rows = Benchmark.objects.filter(
            component__slug__in=[slug for slug in slugs if slug],
            resolution=intent.resolution,
        ).values_list("component__slug", "avg_fps")
        totals: dict[str, list[float]] = {}
        for slug, fps in rows:
            totals.setdefault(slug, []).append(float(fps))
        frame_rates = {slug: sum(values) / len(values) for slug, values in totals.items()}

    def key(hit: SearchResult) -> tuple[int, float, float]:
        extra = hit.extra or {}
        slug = str(extra.get("entity_slug", ""))
        price = float(hit.price or 0)
        available_rank = 0 if hit.in_stock else 1
        fps = frame_rates.get(slug)
        if fps is not None:
            extra["recommendation_reason"] = (
                f"میانگین {fps:g} فریم‌برثانیه در {intent.resolution} بر اساس بنچمارک ثبت‌شده"
            )
            return (available_rank, -fps, price)
        if intent.resolution:
            extra["recommendation_reason"] = (
                "بنچمارک این رزولوشن ثبت نشده؛ بر اساس موجودی و قیمت مرتب شده"
            )
        else:
            extra["recommendation_reason"] = "بر اساس موجودی و قیمت مرتب شده"
        return (available_rank, 0, price)

    product_ids = {id(hit) for hit in products}
    products.sort(key=key)
    other_hits = [hit for hit in hits if id(hit) not in product_ids]
    return products + other_hits


def _build_filters(entity_type: str | None, brand: str | None, in_stock: bool | None) -> str | None:
    """Build a Meilisearch filter expression."""
    clauses: list[str] = []
    if entity_type:
        clauses.append(f'entity_type = "{entity_type}"')
    if brand:
        clauses.append(f'brand = "{brand}"')
    if in_stock is not None:
        clauses.append(f"in_stock = {str(in_stock).lower()}")
    return " AND ".join(clauses) if clauses else None


def autocomplete(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Prefix suggestions, preferring Meilisearch when it is available."""
    client = get_client()
    if client.available():
        hits = client.autocomplete(INDEX_ENTITIES, normalize(query), limit)
        if hits is not None:
            return [
                {
                    "id": str(hit.get("id", "")),
                    "text": hit.get("title_fa") or hit.get("title", ""),
                    "slug": hit.get("slug", ""),
                    "kind": "entity",
                }
                for hit in hits
            ]
    return postgres.autocomplete(query, limit)
