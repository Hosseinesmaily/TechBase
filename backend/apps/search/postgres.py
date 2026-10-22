"""PostgreSQL search fallback.

This is the guaranteed-available backend: it works without Meilisearch, which
means `docker compose up` gives a working search even before the search
container is healthy, and the dev machine without Docker still searches.

It is a *lexical* search over the normalised text: the same normaliser the
indexer uses, applied to the query and to the stored fields.
"""

from __future__ import annotations

import time
from typing import Any

from apps.catalog.models import Entity, Product
from apps.content.models import WikiPage

from .meili import SearchResponse, SearchResult
from .normalizer import normalize


def _contains(normalized_value: str, normalized_query: str) -> bool:
    """Whether the normalised value contains the normalised query.

    Every query token must be present, so "rtx 4060" does not match a
    document that only says "rtx".
    """
    if not normalized_query:
        return True
    tokens = normalized_query.split()
    return all(token in normalized_value for token in tokens)


def _entity_text(entity: Entity) -> str:
    parts = [entity.title, entity.title_fa, entity.summary, entity.summary_fa]
    parts.extend(entity.aliases)
    brand = entity.brand
    if brand is not None:
        parts.extend([brand.name, brand.name_fa])
    return normalize(" ".join(p for p in parts if p))


def _product_text(product: Product) -> str:
    parts = [
        product.title,
        product.title_fa,
        product.sku,
        product.entity.title,
        product.entity.title_fa,
    ]
    brand = product.entity.brand
    if brand is not None:
        parts.append(brand.name)
    return normalize(" ".join(p for p in parts if p))


def search(
    query: str,
    *,
    limit: int = 24,
    entity_type: str | None = None,
    brand: str | None = None,
    in_stock: bool | None = None,
    kind: str | None = None,
) -> SearchResponse:
    """Search the catalog with PostgreSQL."""
    started = time.perf_counter()
    normalized_query = normalize(query)
    if not normalized_query:
        # An empty query matches everything — that is a browse, not a search.
        return SearchResponse(
            query=query, hits=[], total=0, facets={}, took_ms=0, backend="postgres"
        )

    hits: list[SearchResult] = []

    if kind in (None, "entity", "product"):
        entities = Entity.objects.filter(is_active=True).select_related("brand")
        if entity_type:
            entities = entities.filter(type=entity_type)
        if brand:
            entities = entities.filter(brand__slug=brand)

        for entity in entities:
            if not _contains(_entity_text(entity), normalized_query):
                continue
            active_products = [p for p in entity.products.all() if p.is_active]
            price = min((p.price for p in active_products), default=None)
            hits.append(
                SearchResult(
                    id=str(entity.id),
                    slug=entity.slug,
                    title=entity.display_title,
                    subtitle=entity.summary_fa or entity.summary,
                    kind="entity",
                    score=1.0,
                    price=str(price) if price is not None else None,
                    in_stock=any(p.in_stock for p in active_products),
                    extra={"entity_type": entity.type},
                )
            )

    if kind in (None, "product"):
        products = Product.objects.filter(is_active=True).select_related("entity", "entity__brand")
        if entity_type:
            products = products.filter(entity__type=entity_type)
        if brand:
            products = products.filter(entity__brand__slug=brand)
        if in_stock is not None:
            products = products.filter(stock__gt=0) if in_stock else products.filter(stock=0)

        for product in products:
            if not _contains(_product_text(product), normalized_query):
                continue
            hits.append(
                SearchResult(
                    id=str(product.id),
                    slug=product.sku,
                    title=product.display_title,
                    subtitle=product.entity.display_title,
                    kind="product",
                    score=0.9,
                    price=str(product.price),
                    in_stock=product.in_stock,
                    extra={"entity_slug": product.entity.slug, "entity_type": product.entity.type},
                )
            )

    if kind in (None, "page"):
        for page in WikiPage.objects.live().filter(first_published_at__isnull=False):
            text = normalize(f"{page.title} {page.summary}")
            if not _contains(text, normalized_query):
                continue
            hits.append(
                SearchResult(
                    id=str(page.id),
                    slug=page.slug,
                    title=page.title,
                    subtitle=page.summary,
                    kind="page",
                    score=0.8,
                    extra={
                        "page_type": (
                            page.specific_class.__name__ if page.specific_class else "WikiPage"
                        )
                    },
                )
            )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    took_ms = int((time.perf_counter() - started) * 1000)

    return SearchResponse(
        query=query,
        hits=hits[:limit],
        total=len(hits),
        facets=build_facets(hits),
        took_ms=took_ms,
        backend="postgres",
    )


def build_facets(hits: list[SearchResult]) -> dict[str, dict[str, int]]:
    """Count the facet values among the hits."""
    facets: dict[str, dict[str, int]] = {}

    for hit in hits:
        if hit.kind == "entity" and hit.extra:
            entity_type = hit.extra.get("entity_type")
            if entity_type:
                facets.setdefault("type", {})
                facets["type"][entity_type] = facets["type"].get(entity_type, 0) + 1
        if hit.kind == "product" and hit.extra:
            entity_type = hit.extra.get("entity_type")
            if entity_type:
                facets.setdefault("entity_type", {})
                facets["entity_type"][entity_type] = facets["entity_type"].get(entity_type, 0) + 1
        if hit.in_stock is not None:
            facets.setdefault("in_stock", {})
            key = "yes" if hit.in_stock else "no"
            facets["in_stock"][key] = facets["in_stock"].get(key, 0) + 1

    return facets


def autocomplete(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Prefix suggestions over entity names.

    The prefix may match the start of a name **or of any word in it** — the
    same rule Meilisearch's "prefix" matching strategy uses. Typing "RTX"
    should suggest "NVIDIA GeForce RTX 4060" even though the title does not
    begin with "RTX".
    """
    normalized_query = normalize(query)
    if len(normalized_query) < 2:
        return []

    suggestions: list[dict[str, Any]] = []
    for entity in Entity.objects.filter(is_active=True).select_related("brand"):
        names = [entity.title, entity.title_fa, *entity.aliases]
        brand = entity.brand
        if brand is not None:
            names.extend([brand.name, brand.name_fa])
        if not any(_prefix_match(name, normalized_query) for name in names if name):
            continue
        suggestions.append(
            {
                "id": str(entity.id),
                "text": entity.display_title,
                "slug": entity.slug,
                "kind": "entity",
            }
        )
        if len(suggestions) >= limit:
            break
    return suggestions


def _prefix_match(name: str, normalized_query: str) -> bool:
    """Whether a name starts with the query, or one of its words does."""
    normalized = normalize(name)
    if not normalized:
        return False
    if normalized.startswith(normalized_query):
        return True
    # A multi-word query must appear as a phrase.
    if " " in normalized_query:
        return normalized_query in normalized
    return any(word.startswith(normalized_query) for word in normalized.split())
