"""Inventory/price adapters.

Real ERP integration is out of scope for v1 (docs/PLAN.md D15). What matters
is that the *pipeline* is real: a Protocol, two implementations (mock + CSV),
and a Celery job that runs the sync and records what changed.

Adding a real ERP later = one new class implementing `InventoryAdapter`.
"""

from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass
from typing import Protocol

from apps.catalog.models import Product


@dataclass(frozen=True)
class InventoryRecord:
    """One price/stock record coming from an external system."""

    sku: str
    price: str  # decimal string, e.g. "48900000"
    stock: int
    currency: str = "IRT"


class InventoryAdapter(Protocol):
    """The contract every inventory source must satisfy."""

    name: str

    def fetch(self) -> list[InventoryRecord]:
        """Return the current price/stock for every known SKU."""
        ...


class MockInventoryAdapter:
    """Simulates an ERP: prices drift and stock moves.

    Deterministic-ish (seeded) so repeated syncs produce a believable but
    changing dataset instead of random noise on every call.
    """

    name = "mock_erp"

    def __init__(self, seed: int = 1337, volatility: float = 0.05) -> None:
        self._rng = random.Random(seed)
        self._volatility = volatility

    def fetch(self) -> list[InventoryRecord]:
        records: list[InventoryRecord] = []
        for product in Product.objects.all():
            # Price moves by at most ±volatility, rounded to whole tomans.
            base = float(product.price)
            factor = 1 + self._rng.uniform(-self._volatility, self._volatility)
            price = round(base * factor)
            # Stock: mostly stable, occasionally restocked or depleted.
            if self._rng.random() < 0.15:
                stock = max(0, product.stock + self._rng.randint(-5, 15))
            else:
                stock = product.stock
            records.append(
                InventoryRecord(
                    sku=product.sku,
                    price=str(price),
                    stock=stock,
                    currency=product.currency,
                )
            )
        return records


class CSVInventoryAdapter:
    """Reads a CSV file: `sku,price,stock[,currency]`.

    Rows for unknown SKUs are reported, not created — the catalog stays
    editor-controlled.
    """

    name = "csv"

    def __init__(self, path: str) -> None:
        self.path = path

    def fetch(self) -> list[InventoryRecord]:
        with open(self.path, encoding="utf-8-sig", newline="") as handle:
            return list(self._parse(handle.read()))

    @staticmethod
    def _parse(text: str) -> list[InventoryRecord]:
        reader = csv.DictReader(io.StringIO(text))
        records: list[InventoryRecord] = []
        for row in reader:
            sku = (row.get("sku") or "").strip()
            if not sku:
                continue
            try:
                price = str(int(float((row.get("price") or "0").strip())))
                stock = int((row.get("stock") or "0").strip())
            except ValueError:
                continue
            records.append(
                InventoryRecord(
                    sku=sku,
                    price=price,
                    stock=stock,
                    currency=(row.get("currency") or "IRT").strip() or "IRT",
                )
            )
        return records


def get_adapter(name: str, path: str | None = None) -> InventoryAdapter:
    """Factory used by the Celery task and the management command."""
    if name == "mock":
        return MockInventoryAdapter()
    if name == "csv":
        if not path:
            raise ValueError("the csv adapter needs a file path")
        return CSVInventoryAdapter(path)
    raise ValueError(f"unknown inventory adapter: {name!r}")
