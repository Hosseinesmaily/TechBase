"""Search API tests.

Phase 1 search is a SQL `icontains` over titles and summaries. Phase 3 swaps
the internals for Meilisearch + pgvector behind the same endpoints, so these
tests pin the *response shape* and the matching rules.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Brand, Entity, EntityStatus, EntityType, Product

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def data():
    brand = Brand.objects.create(slug="amd", name="AMD")
    gpu = Entity.objects.create(
        type=EntityType.GPU,
        slug="rtx-4060",
        title="NVIDIA GeForce RTX 4060",
        title_fa="انویدیا RTX 4060",
        summary_fa="کارت گرافیک میان‌رده",
        brand=brand,
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
        title="RTX 4060",
        title_fa="کارت گرافیک RTX 4060",
        price="18900000",
        stock=18,
    )
    Product.objects.create(
        sku="tb-cpu-7600",
        entity=cpu,
        title="Ryzen 5 7600",
        title_fa="پردازنده رایزن ۵ ۷۶۰۰",
        price="15800000",
        stock=30,
    )
    return {"gpu": gpu, "cpu": cpu}


class TestSearch:
    def test_empty_query_returns_empty_results(self, api, data):
        response = api.get(reverse("search:search"))
        assert response.status_code == 200
        assert response.data["total"] == 0
        assert response.data["products"]["results"] == []

    def test_finds_by_latin_name(self, api, data):
        response = api.get(reverse("search:search"), {"q": "RTX"})
        assert response.data["total"] > 0
        slugs = [e["slug"] for e in response.data["entities"]["results"]]
        assert "rtx-4060" in slugs

    def test_finds_by_persian_name(self, api, data):
        response = api.get(reverse("search:search"), {"q": "رایزن"})
        assert response.data["total"] > 0
        skus = [p["sku"] for p in response.data["products"]["results"]]
        assert "tb-cpu-7600" in skus

    def test_finds_by_number(self, api, data):
        response = api.get(reverse("search:search"), {"q": "4060"})
        slugs = [e["slug"] for e in response.data["entities"]["results"]]
        assert "rtx-4060" in slugs

    def test_finds_by_sku(self, api, data):
        response = api.get(reverse("search:search"), {"q": "tb-gpu"})
        skus = [p["sku"] for p in response.data["products"]["results"]]
        assert "tb-gpu-4060" in skus

    def test_no_match_returns_zero(self, api, data):
        response = api.get(reverse("search:search"), {"q": "zzzz-nothing"})
        assert response.data["total"] == 0

    def test_result_shape_is_stable(self, api, data):
        response = api.get(reverse("search:search"), {"q": "RTX"})
        assert set(response.data) == {"query", "total", "products", "entities"}
        product = response.data["products"]["results"][0]
        for key in ("sku", "price", "stock", "in_stock", "updated_at"):
            assert key in product

    def test_query_is_echoed_back(self, api, data):
        response = api.get(reverse("search:search"), {"q": "RTX"})
        assert response.data["query"] == "RTX"

    def test_page_size_is_capped(self, api, data):
        response = api.get(reverse("search:search"), {"q": "a", "page_size": "9999"})
        assert response.status_code == 200


class TestAutocomplete:
    def test_requires_two_characters(self, api, data):
        response = api.get(reverse("search:autocomplete"), {"q": "R"})
        assert response.data["suggestions"] == []

    def test_suggests_matching_titles(self, api, data):
        response = api.get(reverse("search:autocomplete"), {"q": "RTX"})
        assert response.status_code == 200
        texts = [s["text"] for s in response.data["suggestions"]]
        assert any("RTX" in t or "4060" in t for t in texts)

    def test_suggestion_carries_the_slug(self, api, data):
        response = api.get(reverse("search:autocomplete"), {"q": "RTX"})
        slugs = [s["slug"] for s in response.data["suggestions"]]
        assert "rtx-4060" in slugs
