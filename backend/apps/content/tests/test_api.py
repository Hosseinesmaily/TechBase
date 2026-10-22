"""Wiki API tests: the pages, their body, and the public read contract."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from wagtail.models import Page

from apps.catalog.models import Entity, EntityType
from apps.content.models import BuyerGuidePage, ComponentPage, ConceptPage, WikiPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def wiki_root():
    root = Page.get_first_root_node()
    assert root is not None
    return root.add_child(instance=WikiPage(title="ویکی", slug="wiki"))


@pytest.fixture
def entity():
    return Entity.objects.create(
        type=EntityType.CPU,
        slug="ryzen-7-7800x3d",
        title="AMD Ryzen 7 7800X3D",
        title_fa="رایزن ۷ ۷۸۰۰X3D",
    )


def publish(root, model, slug, title, **kwargs):
    page = model(title=title, slug=slug, **kwargs)
    root.add_child(instance=page)
    page = page.specific
    page.save_revision().publish()
    return page


class TestPageList:
    def test_lists_published_pages(self, api, wiki_root, entity):
        publish(wiki_root, ComponentPage, "cpu-page", "پردازنده", entity=entity)
        response = api.get(reverse("content:page-list"))
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["slug"] == "cpu-page"

    def test_draft_pages_are_not_listed(self, api, wiki_root, entity):
        page = ComponentPage(title="پیش‌نویس", slug="draft", entity=entity)
        wiki_root.add_child(instance=page)
        response = api.get(reverse("content:page-list"))
        assert response.data["count"] == 0

    def test_filters_by_type(self, api, wiki_root, entity):
        publish(wiki_root, ComponentPage, "c", "قطعه", entity=entity)
        publish(wiki_root, ConceptPage, "cc", "مفهوم")
        assert api.get(reverse("content:page-list"), {"type": "component"}).data["count"] == 1
        assert api.get(reverse("content:page-list"), {"type": "concept"}).data["count"] == 1

    def test_filters_by_entity(self, api, wiki_root, entity):
        publish(wiki_root, ComponentPage, "c", "قطعه", entity=entity)
        assert (
            api.get(reverse("content:page-list"), {"entity": "ryzen-7-7800x3d"}).data["count"] == 1
        )
        assert api.get(reverse("content:page-list"), {"entity": "other"}).data["count"] == 0

    def test_list_payload_has_no_body(self, api, wiki_root, entity):
        publish(wiki_root, ComponentPage, "c", "قطعه", entity=entity)
        row = api.get(reverse("content:page-list")).data["results"][0]
        assert "body" not in row
        assert row["entity"]["slug"] == "ryzen-7-7800x3d"
        assert row["page_type"] == "ComponentPage"

    def test_filters_stale_pages(self, api, wiki_root, entity):
        publish(
            wiki_root,
            ComponentPage,
            "old",
            "قدیمی",
            entity=entity,
            review_by=date.today() - timedelta(days=10),
        )
        publish(
            wiki_root,
            ComponentPage,
            "new",
            "تازه",
            entity=entity,
            review_by=date.today() + timedelta(days=10),
        )
        response = api.get(reverse("content:page-list"), {"stale": "true"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["slug"] == "old"


class TestPageDetail:
    def test_returns_the_page_with_its_body(self, api, wiki_root, entity):
        page = publish(wiki_root, ComponentPage, "c", "قطعه", entity=entity)
        page.body = [
            ("heading", {"level": "h2", "text": "معرفی"}),
            ("paragraph", "متن معرفی."),
        ]
        page.save_revision().publish()

        response = api.get(reverse("content:page-detail", kwargs={"slug": "c"}))
        assert response.status_code == 200
        assert response.data["title"] == "قطعه"
        types = [b["type"] for b in response.data["body"]]
        assert types == ["heading", "paragraph"]
        assert response.data["body"][0]["text"] == "معرفی"
        assert response.data["body"][0]["id"] == "معرفی"

    def test_unknown_slug_is_404(self, api, wiki_root):
        response = api.get(reverse("content:page-detail", kwargs={"slug": "nope"}))
        assert response.status_code == 404

    def test_draft_page_is_404(self, api, wiki_root, entity):
        page = ComponentPage(title="پیش‌نویس", slug="draft", entity=entity)
        wiki_root.add_child(instance=page)
        response = api.get(reverse("content:page-detail", kwargs={"slug": "draft"}))
        assert response.status_code == 404

    def test_buyer_guide_exposes_its_recommendations(self, api, wiki_root, entity):
        from apps.catalog.models import Product

        product = Product.objects.create(
            sku="tb-1", entity=entity, title="Ryzen", title_fa="رایزن", price="24500000", stock=3
        )
        page = publish(
            wiki_root,
            BuyerGuidePage,
            "guide",
            "راهنما",
            use_case="گیمینگ 1080p",
            resolution="1080p",
        )
        page.recommended_products.set([product])
        page.save_revision().publish()

        response = api.get(reverse("content:page-detail", kwargs={"slug": "guide"}))
        assert response.data["use_case"] == "گیمینگ 1080p"
        assert response.data["resolution"] == "1080p"
        assert len(response.data["recommended_products"]) == 1
        assert response.data["recommended_products"][0]["sku"] == "tb-1"


class TestPageModel:
    def test_is_stale_after_the_review_date(self, wiki_root, entity):
        page = publish(
            wiki_root,
            ComponentPage,
            "old",
            "قدیمی",
            entity=entity,
            review_by=date.today() - timedelta(days=1),
        )
        assert page.is_stale is True

    def test_is_not_stale_before_the_review_date(self, wiki_root, entity):
        page = publish(
            wiki_root,
            ComponentPage,
            "new",
            "تازه",
            entity=entity,
            review_by=date.today() + timedelta(days=1),
        )
        assert page.is_stale is False

    def test_a_page_without_a_review_date_is_never_stale(self, wiki_root, entity):
        page = publish(wiki_root, ComponentPage, "n", "بدون تاریخ", entity=entity)
        assert page.is_stale is False

    def test_language_defaults_to_persian(self, wiki_root, entity):
        page = publish(wiki_root, ComponentPage, "c", "قطعه", entity=entity)
        assert page.language == "fa"
