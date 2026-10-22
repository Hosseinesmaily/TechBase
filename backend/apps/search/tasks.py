"""Celery tasks for the search index.

Reindexing runs after a bulk catalog change (a price sync, a new product
batch) and on a schedule, so the lexical index never drifts far from the
database.
"""

from __future__ import annotations

import logging

from celery import shared_task

from .indexer import reindex_all

logger = logging.getLogger(__name__)


@shared_task(name="search.reindex")
def reindex_task() -> dict:
    """Rebuild every search index."""
    report = reindex_all()
    logger.info(
        "search reindex: %d documents, meilisearch=%s",
        report.get("total_documents", 0),
        report.get("meilisearch"),
    )
    return report


@shared_task(name="search.reindex_entities")
def reindex_entities_task() -> dict:
    """Re-index only the entities — the cheap path after a spec change."""
    from .indexer import entity_document
    from .meili import INDEX_ENTITIES, get_client

    client = get_client()
    if not client.available():
        return {"meilisearch": False, "documents": 0}

    from apps.catalog.models import Entity

    documents = [
        entity_document(entity)
        for entity in Entity.objects.filter(is_active=True).select_related("brand", "category")
    ]
    client.ensure_index(INDEX_ENTITIES)
    ok = client.index_documents(INDEX_ENTITIES, documents)
    return {"meilisearch": True, "documents": len(documents), "indexed": ok}
