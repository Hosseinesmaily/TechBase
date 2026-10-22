"""Celery tasks for the linking engine.

The nightly integrity job is the one that matters: it tells the editorial
team which entities need a page (red links) and which pages nobody links to
(orphans).
"""

from __future__ import annotations

import logging

from celery import shared_task

from .services import check_integrity, link_page, record_integrity

logger = logging.getLogger(__name__)


@shared_task(name="linking.link_page")
def link_page_task(page_id: int) -> dict:
    """Re-link one page. Called when a page is published or edited."""
    from apps.content.models import WikiPage

    page = WikiPage.objects.filter(id=page_id).first()
    if page is None:
        return {"error": f"no page with id {page_id}"}
    result = link_page(page)
    return result.as_dict()


@shared_task(name="linking.relink_all")
def relink_all_pages() -> dict:
    """Re-link every published page. Used after a bulk catalog change."""
    from apps.content.models import WikiPage

    pages = WikiPage.objects.live().select_related("entity")
    created = 0
    removed = 0
    red = 0
    for page in pages:
        result = link_page(page)
        created += len(result.created)
        removed += len(result.removed)
        red += len(result.red_links)
    logger.info(
        "relinked %d pages: %d created, %d removed, %d red", pages.count(), created, removed, red
    )
    return {
        "pages": pages.count(),
        "created": created,
        "removed": removed,
        "red_links": red,
    }


@shared_task(name="linking.check_integrity")
def check_integrity_task() -> dict:
    """The nightly link-integrity audit."""
    result = check_integrity()
    report = record_integrity(result)
    logger.info(
        "link integrity: %d links, %d red, %d orphan, %d broken",
        result.total_links,
        result.red_links,
        result.orphan_pages,
        result.broken_links,
    )
    return {"report_id": str(report.id), **result.as_dict()}
