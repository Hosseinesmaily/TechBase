"""Integration tests for the whole v1 API surface.

These run against the seeded catalog and check that the endpoints the spec
promises actually exist, return the documented shape, and that the OpenAPI
schema builds without errors.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def seeded() -> bool:
    call_command("seed_demo", verbosity=0)
    return True


class TestApiSurface:
    def test_catalog_endpoints_respond(self, api, seeded):
        for name in (
            "catalog:entity-list",
            "catalog:product-list",
            "catalog:brand-list",
            "catalog:category-list",
        ):
            response = api.get(reverse(name))
            assert response.status_code == 200, name

    def test_benchmarks_endpoint_responds(self, api, seeded):
        response = api.get(reverse("benchmarks:benchmark-list"))
        assert response.status_code == 200
        assert response.data["count"] > 0

    def test_compat_check_endpoint_responds(self, api, seeded):
        response = api.post(
            reverse("compat:check"),
            {"parts": ["ryzen-7-7800x3d", "asus-tuf-gaming-b650-plus"]},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["verdict"] == "ok"

    def test_health_endpoints_respond(self, api):
        assert api.get(reverse("core:health")).status_code == 200
        assert api.get(reverse("core:ready")).status_code in (200, 503)


class TestSeededCatalogOverApi:
    def test_there_are_prebuilt_products_with_prices(self, api, seeded):
        response = api.get(
            reverse("catalog:product-list"), {"category": "prebuilt", "page_size": 50}
        )
        assert response.data["count"] == 10
        for row in response.data["results"]:
            assert Decimal(row["price"]) > 0
            assert row["updated_at"]

    def test_price_filter_finds_a_budget_build(self, api, seeded):
        response = api.get(
            reverse("catalog:product-list"), {"max_price": "40000000", "category": "prebuilt"}
        )
        assert response.data["count"] > 0
        for row in response.data["results"]:
            assert Decimal(row["price"]) <= Decimal("40000000")

    def test_in_stock_filter_only_returns_available(self, api, seeded):
        response = api.get(reverse("catalog:product-list"), {"in_stock": "true", "page_size": 100})
        assert response.data["count"] > 0
        assert all(row["stock"] > 0 for row in response.data["results"])


class TestOpenApiSchema:
    def test_schema_generates_without_errors(self):
        """drf-spectacular must not find broken views."""
        from drf_spectacular.generators import SchemaGenerator

        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)
        assert schema is not None
        paths = schema["paths"]
        for expected in (
            "/api/v1/catalog/entities/",
            "/api/v1/catalog/products/",
            "/api/v1/compat/check/",
            "/api/v1/benchmarks/",
        ):
            assert expected in paths, f"{expected} missing from the schema"

    def test_schema_view_responds(self, api):
        response = api.get("/api/schema/?format=json")
        assert response.status_code == 200
