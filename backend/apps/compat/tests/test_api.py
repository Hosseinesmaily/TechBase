"""Compatibility API tests: the HTTP contract the assistant's tool layer uses."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Brand, ComponentSpec, Entity, EntityStatus, EntityType
from apps.compat.models import CompatibilityRule, RuleSeverity

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def catalog():
    brand = Brand.objects.create(slug="amd", name="AMD")

    cpu = Entity.objects.create(
        type=EntityType.CPU,
        slug="ryzen-7-7800x3d",
        title="Ryzen 7 7800X3D",
        brand=brand,
        status=EntityStatus.PUBLISHED,
    )
    ComponentSpec.objects.create(entity=cpu, category="cpu", common={"socket": "AM5", "tdp": 120})

    board = Entity.objects.create(
        type=EntityType.MOTHERBOARD,
        slug="asus-b650",
        title="ASUS B650",
        brand=brand,
        status=EntityStatus.PUBLISHED,
    )
    ComponentSpec.objects.create(
        entity=board, category="motherboard", common={"socket": "AM5", "memory_type": "DDR5"}
    )

    lga_board = Entity.objects.create(
        type=EntityType.MOTHERBOARD,
        slug="gigabyte-b760m",
        title="Gigabyte B760M",
        brand=brand,
        status=EntityStatus.PUBLISHED,
    )
    ComponentSpec.objects.create(
        entity=lga_board,
        category="motherboard",
        common={"socket": "LGA1700", "memory_type": "DDR5"},
    )

    CompatibilityRule.objects.create(
        code="SOCKET_MATCH", category_a="cpu", category_b="motherboard", severity=RuleSeverity.BLOCK
    )
    return {"cpu": cpu, "board": board, "lga_board": lga_board}


class TestCheckEndpoint:
    def test_compatible_parts_are_ok(self, api, catalog):
        response = api.post(
            reverse("compat:check"),
            {"parts": ["ryzen-7-7800x3d", "asus-b650"]},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["verdict"] == "ok"
        assert response.data["findings"] == []
        assert response.data["checked"] == ["ryzen-7-7800x3d", "asus-b650"]

    def test_incompatible_parts_are_blocked_with_reason(self, api, catalog):
        response = api.post(
            reverse("compat:check"),
            {"parts": ["ryzen-7-7800x3d", "gigabyte-b760m"]},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["verdict"] == "block"
        finding = response.data["findings"][0]
        assert finding["rule_code"] == "SOCKET_MATCH"
        assert finding["severity"] == "block"
        assert "AM5" in finding["message"]
        assert finding["message_fa"]

    def test_empty_parts_is_a_bad_request(self, api, catalog):
        response = api.post(reverse("compat:check"), {"parts": []}, format="json")
        assert response.status_code == 400

    def test_missing_body_is_a_bad_request(self, api, catalog):
        response = api.post(reverse("compat:check"), {}, format="json")
        assert response.status_code == 400

    def test_unknown_part_is_reported_not_hidden(self, api, catalog):
        response = api.post(
            reverse("compat:check"),
            {"parts": ["ryzen-7-7800x3d", "not-a-real-part"]},
            format="json",
        )
        assert response.status_code == 200
        codes = [f["rule_code"] for f in response.data["findings"]]
        assert "UNKNOWN_PART" in codes

    def test_duplicate_slugs_are_deduped(self, api, catalog):
        response = api.post(
            reverse("compat:check"),
            {"parts": ["ryzen-7-7800x3d", "ryzen-7-7800x3d"]},
            format="json",
        )
        assert response.data["checked"] == ["ryzen-7-7800x3d"]

    def test_disabled_rule_is_not_applied(self, api, catalog):
        CompatibilityRule.objects.filter(code="SOCKET_MATCH").update(enabled=False)
        response = api.post(
            reverse("compat:check"),
            {"parts": ["ryzen-7-7800x3d", "gigabyte-b760m"]},
            format="json",
        )
        assert response.data["verdict"] == "ok"

    def test_severity_from_db_row_is_used(self, api, catalog):
        CompatibilityRule.objects.filter(code="SOCKET_MATCH").update(severity=RuleSeverity.WARN)
        response = api.post(
            reverse("compat:check"),
            {"parts": ["ryzen-7-7800x3d", "gigabyte-b760m"]},
            format="json",
        )
        assert response.data["verdict"] == "warn"
        assert response.data["findings"][0]["severity"] == "warn"


class TestRuleListEndpoint:
    def test_rules_are_staff_only(self, api, catalog):
        response = api.get(reverse("compat:rule-list"))
        assert response.status_code in (401, 403)

    def test_staff_can_list_rules(self, api, catalog):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username="editor", password="pw")
        user.is_staff = True
        user.save()
        api.force_authenticate(user=user)
        response = api.get(reverse("compat:rule-list"))
        assert response.status_code == 200
        assert response.data[0]["code"] == "SOCKET_MATCH"
