"""Build the Meilisearch documents and push them to the index.

The documents are built from the same normaliser the query side uses, so a
document indexed with "می‌شود" is found by a query for "می شود".
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.catalog.models import Entity, Product
from apps.content.models import WikiPage

from .meili import INDEX_ENTITIES, INDEX_PAGES, INDEX_PRODUCTS, get_client

logger = logging.getLogger(__name__)


def _brand_name(entity: Entity) -> str:
    """The brand name of an entity, or an empty string."""
    brand = entity.brand
    return brand.name if brand is not None else ""


def _category_slug(entity: Entity) -> str:
    """The category slug of an entity, or an empty string."""
    category = entity.category
    return category.slug if category is not None else ""


def entity_document(entity: Entity) -> dict[str, Any]:
    """The Meilisearch document for an entity."""
    price = (
        entity.products.filter(is_active=True)
        .order_by("price")
        .values_list("price", flat=True)
        .first()
    )
    return {
        "id": str(entity.id),
        "kind": "entity",
        "slug": entity.slug,
        "title": entity.title,
        "title_fa": entity.display_title,
        "summary": entity.summary,
        "summary_fa": entity.summary_fa,
        "aliases": entity.aliases,
        "entity_type": entity.type,
        "brand": _brand_name(entity),
        "category": _category_slug(entity),
        "status": entity.status,
        "price": str(price) if price is not None else None,
        "in_stock": any(p.in_stock for p in entity.products.all() if p.is_active),
        "updated_at": entity.updated_at.isoformat(),
    }


def product_document(product: Product) -> dict[str, Any]:
    """The Meilisearch document for a product."""
    return {
        "id": str(product.id),
        "kind": "product",
        "slug": product.sku,
        "title": product.title,
        "title_fa": product.display_title,
        "summary": product.entity.display_title,
        "summary_fa": product.entity.summary_fa,
        "entity_slug": product.entity.slug,
        "entity_type": product.entity.type,
        "brand": _brand_name(product.entity),
        "category": _category_slug(product.entity),
        "price": str(product.price),
        "currency": product.currency,
        "in_stock": product.in_stock,
        "stock": product.stock,
        "updated_at": product.updated_at.isoformat(),
    }


def page_document(page: WikiPage) -> dict[str, Any]:
    """The Meilisearch document for a wiki page."""
    return {
        "id": str(page.id),
        "kind": "page",
        "slug": page.slug,
        "title": page.title,
        "title_fa": page.title,
        "summary": page.summary,
        "summary_fa": page.summary,
        "entity_type": page.entity.type if page.entity is not None else "",
        "brand": _brand_name(page.entity) if page.entity is not None else "",
        "category": "wiki",
        "page_type": page.specific_class.__name__ if page.specific_class else "WikiPage",
        "updated_at": (
            page.last_published_at or page.latest_revision_created_at or timezone.now()
        ).isoformat(),
    }


def build_documents() -> dict[str, list[dict[str, Any]]]:
    """Build every document, grouped by index."""
    entities = [
        entity_document(entity)
        for entity in Entity.objects.filter(is_active=True).select_related("brand", "category")
    ]
    products = [
        product_document(product)
        for product in Product.objects.filter(is_active=True).select_related(
            "entity", "entity__brand", "entity__category"
        )
    ]
    pages = [
        page_document(page)
        for page in WikiPage.objects.live()
        .filter(first_published_at__isnull=False)
        .select_related("entity", "entity__brand")
    ]
    return {
        INDEX_ENTITIES: entities,
        INDEX_PRODUCTS: products,
        INDEX_PAGES: pages,
    }


def reindex_all(*, reset: bool = True) -> dict[str, Any]:
    """Rebuild every Meilisearch index from the database.

    Returns a report: which indexes were updated, how many documents each
    got, and whether Meilisearch was reachable at all.
    """
    client = get_client()
    report: dict[str, Any] = {
        "meilisearch": client.available(),
        "indexes": {},
        "errors": [],
    }

    documents = build_documents()
    for index, docs in documents.items():
        if not client.available():
            report["errors"].append(f"{index}: meilisearch unavailable")
            continue
        if reset:
            client.delete_all(index)
        client.ensure_index(index)
        ok = client.index_documents(index, docs)
        report["indexes"][index] = {
            "documents": len(docs),
            "indexed": ok,
        }
        if not ok:
            report["errors"].append(f"{index}: indexing failed")

    total = sum(entry["documents"] for entry in report["indexes"].values())
    report["total_documents"] = total
    logger.info("reindex: %d documents across %d indexes", total, len(documents))
    return report
