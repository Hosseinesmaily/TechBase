"""Inventory sync tests.

The sync is what makes price/stock "last updated" meaningful, so the tests
pin the contract: prices and stock move, `price_updated_at` is stamped, unknown
SKUs are reported, and running twice is safe.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.catalog.models import Entity, EntityType, Product
from apps.integrations.adapters import CSVInventoryAdapter, MockInventoryAdapter
from apps.integrations.tasks import apply_records, sync_inventory

pytestmark = pytest.mark.django_db


@pytest.fixture
def product() -> Product:
    entity = Entity.objects.create(
        type=EntityType.GPU, slug="rtx-4060", title="NVIDIA GeForce RTX 4060"
    )
    return Product.objects.create(
        sku="tb-gpu-4060",
        entity=entity,
        title="NVIDIA GeForce RTX 4060",
        price=Decimal("18900000"),
        currency="IRT",
        stock=18,
        source="seed",
    )


class TestMockAdapter:
    def test_returns_a_record_per_product(self, product):
        records = MockInventoryAdapter().fetch()
        assert len(records) == 1
        assert records[0].sku == "tb-gpu-4060"
        assert records[0].stock >= 0

    def test_prices_stay_near_the_original(self, product):
        """The mock must not invent absurd prices — that would poison the demo."""
        for record in MockInventoryAdapter().fetch():
            price = int(record.price)
            assert 0.8 * 18_900_000 <= price <= 1.2 * 18_900_000


class TestCsvAdapter:
    def test_parses_rows(self, tmp_path):
        path = tmp_path / "inv.csv"
        path.write_text("sku,price,stock\ntb-1,1000,5\ntb-2,2000,0\n", encoding="utf-8")
        records = CSVInventoryAdapter(str(path)).fetch()
        assert [r.sku for r in records] == ["tb-1", "tb-2"]
        assert records[0].price == "1000"
        assert records[1].stock == 0

    def test_skips_malformed_rows(self, tmp_path):
        path = tmp_path / "inv.csv"
        path.write_text("sku,price,stock\ntb-1,abc,5\ntb-2,2000,3\n", encoding="utf-8")
        records = CSVInventoryAdapter(str(path)).fetch()
        assert [r.sku for r in records] == ["tb-2"]

    def test_reads_a_bom_encoded_file(self, tmp_path):
        path = tmp_path / "inv.csv"
        path.write_text("sku,price,stock\ntb-1,1000,5\n", encoding="utf-8-sig")
        assert len(CSVInventoryAdapter(str(path)).fetch()) == 1


class TestApplyRecords:
    def test_updates_price_and_stock(self, product):
        result = apply_records(
            [
                type(
                    "R",
                    (),
                    {"sku": "tb-gpu-4060", "price": "17500000", "stock": 3, "currency": "IRT"},
                )()
            ],
            "csv",
        )
        product.refresh_from_db()
        assert int(product.price) == 17500000
        assert product.stock == 3
        assert result.updated == ["tb-gpu-4060"]
        assert result.price_changed == ["tb-gpu-4060"]
        assert result.stock_changed == ["tb-gpu-4060"]

    def test_stamps_price_updated_at(self, product):
        assert product.price_updated_at is None
        apply_records(
            [
                type(
                    "R",
                    (),
                    {"sku": "tb-gpu-4060", "price": "17500000", "stock": 3, "currency": "IRT"},
                )()
            ],
            "csv",
        )
        product.refresh_from_db()
        assert product.price_updated_at is not None

    def test_unchanged_record_is_not_a_write(self, product):
        result = apply_records(
            [
                type(
                    "R",
                    (),
                    {"sku": "tb-gpu-4060", "price": "18900000", "stock": 18, "currency": "IRT"},
                )()
            ],
            "csv",
        )
        assert result.unchanged == ["tb-gpu-4060"]
        assert result.updated == []

    def test_unknown_sku_is_reported_not_created(self, product):
        result = apply_records(
            [
                type(
                    "R",
                    (),
                    {"sku": "not-in-catalog", "price": "1000", "stock": 1, "currency": "IRT"},
                )()
            ],
            "csv",
        )
        assert result.unknown == ["not-in-catalog"]
        assert Product.objects.filter(sku="not-in-catalog").count() == 0

    def test_source_is_recorded(self, product):
        apply_records(
            [
                type(
                    "R",
                    (),
                    {"sku": "tb-gpu-4060", "price": "17500000", "stock": 3, "currency": "IRT"},
                )()
            ],
            "csv",
        )
        product.refresh_from_db()
        assert product.source == "csv"


class TestSyncTask:
    def test_task_runs_and_reports(self, product):
        result = sync_inventory(adapter="mock")
        # The adapter's own name is recorded as the source.
        assert result["source"] == "mock_erp"
        assert result["error"] == ""
        assert "counts" in result

    def test_unknown_adapter_returns_an_error_not_a_crash(self, product):
        result = sync_inventory(adapter="nope")
        assert result["error"]
        assert "nope" in result["error"]


class TestManagementCommand:
    def test_sync_command_runs(self, product):
        call_command("sync_inventory", adapter="mock", verbosity=0)
        product.refresh_from_db()
        assert product.source == "mock_erp"
