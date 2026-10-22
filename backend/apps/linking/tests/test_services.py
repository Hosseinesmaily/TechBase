"""Tests for the linking services and the linking API.

These cover the parts that decide what the wiki shows: which links are made,
which entities are red links, and what the editorial backlog looks like.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from wagtail.models import Page

from apps.catalog.models import Brand, ComponentSpec, Entity, EntityStatus, EntityType, Product
from apps.content.models import ComponentPage, WikiPage
from apps.linking.models import EntityLink
from apps.linking.services import check_integrity, link_page, record_integrity

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
def catalog():
    brand = Brand.objects.create(slug="amd", name="AMD", name_fa="ای‌ام‌دی")
    cpu = Entity.objects.create(
        type=EntityType.CPU,
        slug="ryzen-7-7800x3d",
        title="AMD Ryzen 7 7800X3D",
        title_fa="رایزن ۷ ۷۸۰۰X3D",
        brand=brand,
        status=EntityStatus.PUBLISHED,
    )
    ComponentSpec.objects.create(entity=cpu, category="cpu", common={"socket": "AM5", "tdp": 120})
    board = Entity.objects.create(
        type=EntityType.MOTHERBOARD,
        slug="asus-b650",
        title="ASUS TUF Gaming B650-PLUS",
        title_fa="ایسوس TUF B650",
        brand=brand,
        status=EntityStatus.PUBLISHED,
    )
    ComponentSpec.objects.create(entity=board, category="motherboard", common={"socket": "AM5"})
    return {"cpu": cpu, "board": board, "brand": brand}


def make_page(root, catalog, *, slug="cpu-page", title="پردازنده", entity=None, body_blocks=()):
    page = ComponentPage(
        title=title,
        slug=slug,
        summary="خلاصهٔ تست",
        entity=entity,
    )
    root.add_child(instance=page)
    page = page.specific
    page.body = body_blocks
    page.save_revision().publish()
    return page


def paragraph(text):
    return [("paragraph", text)]


class TestLinkPage:
    def test_creates_a_link_for_a_mentioned_entity(self, wiki_root, catalog):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=paragraph("این پردازنده با مادربرد ASUS TUF Gaming B650-PLUS کار می‌کند."),
        )
        result = link_page(page)
        assert "asus-b650" in result.created
        assert EntityLink.objects.filter(page=page, target__slug="asus-b650").count() == 1

    def test_no_entity_means_no_links(self, wiki_root, catalog):
        page = make_page(
            wiki_root,
            catalog,
            entity=None,
            body_blocks=paragraph("متنی بدون موجودیت."),
        )
        result = link_page(page)
        assert result.created == []
        assert EntityLink.objects.filter(page=page).count() == 0

    def test_brand_names_are_not_linked(self, wiki_root, catalog):
        """Linking every "ای‌ام‌دی" would be noise, not information."""
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=paragraph("ای‌ام‌دی و AMD در این بازار پیشرو هستند."),
        )
        link_page(page)
        assert EntityLink.objects.filter(page=page).count() == 0

    def test_only_the_first_mention_per_section_is_linked(self, wiki_root, catalog):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=[
                ("heading", {"level": "h2", "text": "بخش اول"}),
                ("paragraph", "مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
                ("paragraph", "دوباره ASUS TUF Gaming B650-PLUS و ASUS TUF Gaming B650-PLUS."),
            ],
        )
        link_page(page)
        assert EntityLink.objects.filter(page=page, target__slug="asus-b650").count() == 1

    def test_a_mention_in_a_new_section_gets_its_own_link(self, wiki_root, catalog):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=[
                ("heading", {"level": "h2", "text": "بخش اول"}),
                ("paragraph", "مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
                ("heading", {"level": "h2", "text": "بخش دوم"}),
                ("paragraph", "همان مادربرد ASUS TUF Gaming B650-PLUS را بخرید."),
            ],
        )
        link_page(page)
        assert EntityLink.objects.filter(page=page, target__slug="asus-b650").count() == 2

    def test_target_without_a_page_is_a_red_link(self, wiki_root, catalog):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=paragraph("مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
        )
        link_page(page)
        link = EntityLink.objects.get(page=page, target__slug="asus-b650")
        assert link.target_exists is False
        assert link.is_red_link

    def test_target_with_a_page_is_not_a_red_link(self, wiki_root, catalog):
        make_page(
            wiki_root,
            catalog,
            slug="board-page",
            title="مادربرد",
            entity=catalog["board"],
        )
        page = make_page(
            wiki_root,
            catalog,
            slug="cpu-page-2",
            entity=catalog["cpu"],
            body_blocks=paragraph("مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
        )
        link_page(page)
        link = EntityLink.objects.get(page=page, target__slug="asus-b650")
        assert link.target_exists is True
        assert not link.is_red_link

    def test_relinking_removes_links_whose_mention_is_gone(self, wiki_root, catalog):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=paragraph("مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
        )
        link_page(page)
        assert EntityLink.objects.filter(page=page).count() == 1

        page.body = paragraph("حالا دیگر هیچ اشاره‌ای وجود ندارد.")
        page.save_revision().publish()
        result = link_page(page.specific)
        assert "asus-b650" in result.removed
        assert EntityLink.objects.filter(page=page).count() == 0

    def test_relinking_is_idempotent(self, wiki_root, catalog):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=paragraph("مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
        )
        link_page(page)
        second = link_page(page.specific)
        assert second.created == []
        assert EntityLink.objects.filter(page=page).count() == 1


class TestIntegrity:
    def test_reports_red_links(self, wiki_root, catalog):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=paragraph("مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
        )
        link_page(page)
        result = check_integrity()
        assert result.total_links == 1
        assert result.red_links == 1
        assert result.broken_links == 0

    def test_reports_orphan_pages(self, wiki_root, catalog):
        make_page(wiki_root, catalog, slug="lonely", title="تنها", entity=catalog["cpu"])
        result = check_integrity()
        assert result.orphan_pages >= 1
        slugs = {page["slug"] for page in result.orphan_page_list}
        assert "lonely" in slugs

    def test_a_linked_page_is_not_an_orphan(self, wiki_root, catalog):
        make_page(
            wiki_root,
            catalog,
            slug="source",
            entity=catalog["cpu"],
            body_blocks=paragraph("مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
        )
        make_page(wiki_root, catalog, slug="target", title="مادربرد", entity=catalog["board"])
        link_page(WikiPage.objects.get(slug="source").specific)
        result = check_integrity()
        slugs = {page["slug"] for page in result.orphan_page_list}
        assert "target" not in slugs

    def test_report_is_recorded(self, wiki_root, catalog):
        result = check_integrity()
        report = record_integrity(result)
        assert report.ran_at is not None
        assert report.total_links == result.total_links


class TestLinkingApi:
    def test_hovercard_returns_price_and_specs(self, api, catalog):
        Product.objects.create(
            sku="tb-cpu-1",
            entity=catalog["cpu"],
            title="Ryzen 7 7800X3D",
            title_fa="رایزن ۷ ۷۸۰۰X3D",
            price="24500000",
            stock=12,
        )
        response = api.get(reverse("linking:hovercard"), {"entity": "ryzen-7-7800x3d"})
        assert response.status_code == 200
        # Money is a decimal string — never a float.
        assert response.data["product"]["price"] == "24500000.00"
        assert response.data["product"]["in_stock"] is True
        spec_keys = [s["key"] for s in response.data["specs"]]
        assert "socket" in spec_keys
        assert response.data["has_page"] is False

    def test_hovercard_needs_an_entity(self, api, catalog):
        response = api.get(reverse("linking:hovercard"))
        assert response.status_code == 400

    def test_hovercard_404_for_unknown_entity(self, api, catalog):
        response = api.get(reverse("linking:hovercard"), {"entity": "nope"})
        assert response.status_code == 404

    def test_hovercard_reports_the_page_url_when_it_exists(self, api, catalog, wiki_root):
        make_page(wiki_root, catalog, slug="cpu-page", entity=catalog["cpu"])
        response = api.get(reverse("linking:hovercard"), {"entity": "ryzen-7-7800x3d"})
        assert response.data["has_page"] is True
        assert response.data["page_url"] == "/wiki/cpu-page/"

    def test_backlinks_list_the_sources(self, api, catalog, wiki_root):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=paragraph("مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
        )
        link_page(page)
        response = api.get(reverse("linking:backlinks", kwargs={"slug": "asus-b650"}))
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["backlinks"][0]["source_slug"] == "ryzen-7-7800x3d"

    def test_backlinks_404_for_unknown_entity(self, api, catalog):
        response = api.get(reverse("linking:backlinks", kwargs={"slug": "nope"}))
        assert response.status_code == 404

    def test_redlinks_are_the_editorial_backlog(self, api, catalog, wiki_root):
        page = make_page(
            wiki_root,
            catalog,
            entity=catalog["cpu"],
            body_blocks=paragraph("مادربرد ASUS TUF Gaming B650-PLUS مناسب است."),
        )
        link_page(page)
        response = api.get(reverse("linking:redlinks"))
        assert response.status_code == 200
        slugs = {row["slug"] for row in response.data["results"]}
        assert "asus-b650" in slugs

    def test_orphans_are_listed(self, api, catalog, wiki_root):
        make_page(wiki_root, catalog, slug="lonely", title="تنها", entity=catalog["cpu"])
        response = api.get(reverse("linking:orphans"))
        assert response.status_code == 200
        slugs = {row["slug"] for row in response.data["results"]}
        assert "lonely" in slugs
