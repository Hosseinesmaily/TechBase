"""Catalog API tests: filtering, pagination, and the price/stock contract.

The API is what the assistant reads its facts from, so these tests pin the
shape of the data: prices are strings, `updated_at` is present, stock is a
plain integer, and filters actually filter.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import (
    Brand,
    Category,
    ComponentSpec,
    Entity,
    EntityStatus,
    EntityType,
    Product,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def sample_data():
    """A small catalog: 1 brand, 1 category, 3 entities, 3 products."""
    brand = Brand.objects.create(slug="amd", name="AMD", name_fa="ای‌ام‌دی")
    category = Category.objects.create(slug="gpus", name="Graphics Cards", name_fa="کارت گرافیک")

    gpu = Entity.objects.create(
        type=EntityType.GPU,
        slug="rtx-4060",
        title="NVIDIA GeForce RTX 4060",
        title_fa="انویدیا RTX 4060",
        brand=brand,
        category=category,
        status=EntityStatus.PUBLISHED,
    )
    ComponentSpec.objects.create(
        entity=gpu, category="gpu", common={"vram_gb": 8, "tdp": 115}, extra={"ray_tracing": True}
    )

    cheap = Entity.objects.create(
        type=EntityType.GPU,
        slug="rx-7600",
        title="AMD Radeon RX 7600",
        title_fa="ای‌ام‌دی RX 7600",
        brand=brand,
        category=category,
        status=EntityStatus.PUBLISHED,
    )

    cpu = Entity.objects.create(
        type=EntityType.CPU,
        slug="ryzen-5-7600",
        title="AMD Ryzen 5 7600",
        title_fa="رایزن ۵ ۷۶۰۰",
        brand=brand,
        status=EntityStatus.PUBLISHED,
    )

    Product.objects.create(
        sku="tb-gpu-4060",
        entity=gpu,
        title="NVIDIA GeForce RTX 4060",
        title_fa="کارت گرافیک RTX 4060",
        price=Decimal("18900000"),
        currency="IRT",
        stock=18,
    )
    Product.objects.create(
        sku="tb-gpu-7600",
        entity=cheap,
        title="AMD Radeon RX 7600",
        title_fa="کارت گرافیک RX 7600",
        price=Decimal("17200000"),
        currency="IRT",
        stock=0,
    )
    Product.objects.create(
        sku="tb-cpu-7600",
        entity=cpu,
        title="AMD Ryzen 5 7600",
        title_fa="پردازنده رایزن ۵ ۷۶۰۰",
        price=Decimal("15800000"),
        currency="IRT",
        stock=30,
    )
    return {"brand": brand, "category": category, "gpu": gpu, "cpu": cpu}


# --- Products ----------------------------------------------------------------


class TestProductList:
    def test_lists_all_products(self, api, sample_data):
        response = api.get(reverse("catalog:product-list"))
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_filters_by_entity_type(self, api, sample_data):
        response = api.get(reverse("catalog:product-list"), {"category": "gpu"})
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_filters_by_price_range(self, api, sample_data):
        response = api.get(
            reverse("catalog:product-list"), {"min_price": "17000000", "max_price": "18000000"}
        )
        assert response.data["count"] == 1
        assert response.data["results"][0]["sku"] == "tb-gpu-7600"

    def test_filters_in_stock(self, api, sample_data):
        response = api.get(reverse("catalog:product-list"), {"in_stock": "true"})
        assert response.data["count"] == 2
        skus = {row["sku"] for row in response.data["results"]}
        assert "tb-gpu-7600" not in skus  # stock = 0

    def test_search_by_persian_title(self, api, sample_data):
        response = api.get(reverse("catalog:product-list"), {"q": "رایزن"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["sku"] == "tb-cpu-7600"

    def test_pagination_is_configurable(self, api, sample_data):
        response = api.get(reverse("catalog:product-list"), {"page_size": 2})
        assert response.status_code == 200
        assert len(response.data["results"]) == 2
        assert response.data["count"] == 3

    def test_price_is_a_string_not_a_float(self, api, sample_data):
        """Money must not drift through JSON floats."""
        response = api.get(reverse("catalog:product-list"), {"sku": "tb-gpu-4060"} if False else {})
        row = next(r for r in response.data["results"] if r["sku"] == "tb-gpu-4060")
        assert isinstance(row["price"], str)
        assert row["price"] == "18900000.00"

    def test_product_card_carries_last_updated(self, api, sample_data):
        response = api.get(reverse("catalog:product-list"))
        row = next(r for r in response.data["results"] if r["sku"] == "tb-gpu-4060")
        assert row["updated_at"] is not None
        assert row["in_stock"] is True

    def test_out_of_stock_product_reports_false(self, api, sample_data):
        response = api.get(reverse("catalog:product-list"))
        row = next(r for r in response.data["results"] if r["sku"] == "tb-gpu-7600")
        assert row["in_stock"] is False
        assert row["stock"] == 0


class TestProductDetail:
    def test_lookup_by_sku(self, api, sample_data):
        response = api.get(reverse("catalog:product-detail", kwargs={"sku": "tb-gpu-4060"}))
        assert response.status_code == 200
        assert response.data["entity_slug"] == "rtx-4060"
        assert response.data["entity_type"] == "gpu"

    def test_unknown_sku_is_404(self, api, sample_data):
        response = api.get(reverse("catalog:product-detail", kwargs={"sku": "does-not-exist"}))
        assert response.status_code == 404


# --- Entities ----------------------------------------------------------------


class TestEntityList:
    def test_lists_entities(self, api, sample_data):
        response = api.get(reverse("catalog:entity-list"))
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_filters_by_type(self, api, sample_data):
        response = api.get(reverse("catalog:entity-list"), {"type": "cpu"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["slug"] == "ryzen-5-7600"

    def test_filters_by_brand(self, api, sample_data):
        response = api.get(reverse("catalog:entity-list"), {"brand": "amd"})
        assert response.data["count"] == 3

    def test_in_stock_filter(self, api, sample_data):
        response = api.get(reverse("catalog:entity-list"), {"in_stock": "true"})
        slugs = {row["slug"] for row in response.data["results"]}
        assert "rtx-4060" in slugs
        assert "rx-7600" not in slugs  # its only product is out of stock

    def test_price_min_is_the_cheapest_product(self, api, sample_data):
        response = api.get(reverse("catalog:entity-list"), {"type": "gpu"})
        by_slug = {row["slug"]: row for row in response.data["results"]}
        assert by_slug["rtx-4060"]["price_min"] == "18900000.00"
        assert by_slug["rx-7600"]["price_min"] == "17200000.00"

    def test_persian_display_title_is_used(self, api, sample_data):
        response = api.get(reverse("catalog:entity-list"), {"type": "cpu"})
        assert response.data["results"][0]["display_title"] == "رایزن ۵ ۷۶۰۰"


class TestEntityDetail:
    def test_includes_specs_and_products(self, api, sample_data):
        response = api.get(reverse("catalog:entity-detail", kwargs={"slug": "rtx-4060"}))
        assert response.status_code == 200
        assert response.data["spec"]["common"]["vram_gb"] == 8
        assert response.data["spec"]["extra"]["ray_tracing"] is True
        assert len(response.data["products"]) == 1
        assert response.data["products"][0]["sku"] == "tb-gpu-4060"

    def test_unknown_slug_is_404(self, api, sample_data):
        response = api.get(reverse("catalog:entity-detail", kwargs={"slug": "nope"}))
        assert response.status_code == 404


# --- Facets ------------------------------------------------------------------


class TestFacets:
    def test_brand_list_counts_entities(self, api, sample_data):
        response = api.get(reverse("catalog:brand-list"))
        assert response.status_code == 200
        assert response.data[0]["name"] == "AMD"
        assert response.data[0]["entity_count"] == 3

    def test_category_list(self, api, sample_data):
        response = api.get(reverse("catalog:category-list"))
        assert response.status_code == 200
        assert response.data[0]["slug"] == "gpus"
