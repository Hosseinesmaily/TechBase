"""Celery tasks for inventory/price sync.

The task is idempotent: running it twice with the same source produces the same
result. It records what it changed so the UI can show "last updated".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from celery import shared_task

from .adapters import InventoryAdapter, get_adapter

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Outcome of one sync run."""

    source: str
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    price_changed: list[str] = field(default_factory=list)
    stock_changed: list[str] = field(default_factory=list)
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "unknown": self.unknown,
            "price_changed": self.price_changed,
            "stock_changed": self.stock_changed,
            "counts": {
                "updated": len(self.updated),
                "unchanged": len(self.unchanged),
                "unknown": len(self.unknown),
            },
            "error": self.error,
        }


def apply_records(records, adapter_name: str) -> SyncResult:
    """Apply inventory records to the catalog. Pure-ish: takes records, not a source.

    Kept separate from the Celery wrapper so it can be tested without Celery.
    """
    result = SyncResult(source=adapter_name)
    now = timezone.now()

    existing = {p.sku: p for p in Product.objects.all()}

    with transaction.atomic():
        for record in records:
            product = existing.get(record.sku)
            if product is None:
                result.unknown.append(record.sku)
                continue

            new_price = int(record.price)
            price_differs = int(product.price) != new_price
            stock_differs = product.stock != record.stock

            if not price_differs and not stock_differs:
                result.unchanged.append(record.sku)
                continue

            product.price = new_price
            product.stock = record.stock
            product.currency = record.currency or product.currency
            product.source = adapter_name
            product.price_updated_at = now
            product.save(
                update_fields=[
                    "price",
                    "stock",
                    "currency",
                    "source",
                    "price_updated_at",
                    "updated_at",
                ]
            )
            result.updated.append(record.sku)
            if price_differs:
                result.price_changed.append(record.sku)
            if stock_differs:
                result.stock_changed.append(record.sku)

    return result


@shared_task(name="integrations.sync_inventory")
def sync_inventory(adapter: str = "mock", path: str | None = None) -> dict:
    """Fetch from the adapter and update the catalog."""
    try:
        source: InventoryAdapter = get_adapter(adapter, path)
    except ValueError as exc:
        logger.error("inventory sync: %s", exc)
        return SyncResult(source=adapter, error=str(exc)).as_dict()

    try:
        records = source.fetch()
    except Exception as exc:
        logger.exception("inventory sync failed while fetching")
        return SyncResult(source=adapter, error=str(exc)).as_dict()

    result = apply_records(records, source.name)
    logger.info(
        "inventory sync (%s): %d updated, %d unchanged, %d unknown",
        source.name,
        len(result.updated),
        len(result.unchanged),
        len(result.unknown),
    )
    return result.as_dict()
