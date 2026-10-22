"""Benchmark API tests."""

from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.benchmarks.models import Benchmark
from apps.catalog.models import Entity, EntityType

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def data():
    gpu = Entity.objects.create(type=EntityType.GPU, slug="rtx-4060", title="RTX 4060")
    cpu = Entity.objects.create(type=EntityType.CPU, slug="ryzen-5-7600", title="Ryzen 5 7600")
    Benchmark.objects.create(
        component=gpu,
        game="Cyberpunk 2077",
        game_fa="سایبرپانک ۲۰۷۷",
        resolution="1080p",
        preset="high",
        avg_fps=78,
        p1_low=56,
        tested_at=date(2026, 1, 15),
    )
    Benchmark.objects.create(
        component=gpu,
        game="Cyberpunk 2077",
        game_fa="سایبرپانک ۲۰۷۷",
        resolution="1440p",
        preset="high",
        avg_fps=42,
        p1_low=31,
        tested_at=date(2026, 1, 15),
    )
    Benchmark.objects.create(
        component=cpu,
        game="Counter-Strike 2",
        game_fa="کانتر استرایک ۲",
        resolution="1080p",
        preset="high",
        avg_fps=245,
        p1_low=180,
        tested_at=date(2026, 1, 15),
    )
    return {"gpu": gpu, "cpu": cpu}


class TestBenchmarkList:
    def test_lists_all(self, api, data):
        response = api.get(reverse("benchmarks:benchmark-list"))
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_filters_by_component(self, api, data):
        response = api.get(reverse("benchmarks:benchmark-list"), {"component": "rtx-4060"})
        assert response.data["count"] == 2
        assert response.data["results"][0]["component_slug"] == "rtx-4060"

    def test_filters_by_resolution(self, api, data):
        response = api.get(reverse("benchmarks:benchmark-list"), {"resolution": "1440p"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["avg_fps"] == 42

    def test_filters_by_game(self, api, data):
        response = api.get(reverse("benchmarks:benchmark-list"), {"game": "counter-strike 2"})
        assert response.data["count"] == 1

    def test_combined_filters(self, api, data):
        response = api.get(
            reverse("benchmarks:benchmark-list"),
            {"component": "rtx-4060", "resolution": "1080p"},
        )
        assert response.data["count"] == 1
        row = response.data["results"][0]
        assert row["avg_fps"] == 78
        assert row["p1_low"] == 56

    def test_payload_carries_provenance(self, api, data):
        """A number without a rig and a date is not evidence."""
        response = api.get(reverse("benchmarks:benchmark-list"))
        row = response.data["results"][0]
        assert "test_rig" in row
        assert row["tested_at"] is not None
        assert row["game_fa"]
