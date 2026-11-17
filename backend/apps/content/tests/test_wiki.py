"""End-to-end tests for the wiki: seed → link → publish → read.

These cover the path the demo depends on: the seed command creates the
pages, the auto-linker fills in the links, and the API serves them.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Entity
from apps.content.models import BuyerGuidePage, ComponentPage, ConceptPage, WikiPage
from apps.linking.models import EntityLink
from apps.linking.services import check_integrity

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def seeded_catalog():
    call_command("seed_demo", verbosity=0)
    return True


@pytest.fixture
def seeded_wiki(seeded_catalog):
    call_command("seed_wiki", verbosity=0)
    return True


class TestSeedWiki:
    def test_creates_the_pages(self, seeded_wiki):
        assert WikiPage.objects.live().filter(first_published_at__isnull=False).count() >= 14

    def test_creates_all_three_page_types(self, seeded_wiki):
        assert ComponentPage.objects.live().count() > 0
        assert ConceptPage.objects.live().count() > 0
        assert BuyerGuidePage.objects.live().count() > 0

    def test_component_pages_are_bound_to_entities(self, seeded_wiki):
        page = ComponentPage.objects.live().filter(entity__isnull=False).first()
        assert page is not None
        assert page.entity is not None
        assert page.entity.slug

    def test_guides_reference_real_products(self, seeded_wiki):
        guide = BuyerGuidePage.objects.live().first()
        assert guide is not None
        products = guide.recommended_products.all()
        assert products.exists()
        for product in products:
            assert product.price > 0

    def test_pages_have_a_review_date(self, seeded_wiki):
        # The section page itself is not a content page and has no review date.
        content_pages = WikiPage.objects.live().exclude(slug="wiki")[:5]
        assert content_pages
        for page in content_pages:
            assert page.review_by is not None

    def test_seed_is_idempotent(self, seeded_wiki):
        count = WikiPage.objects.live().count()
        call_command("seed_wiki", verbosity=0)
        assert WikiPage.objects.live().count() == count

    def test_bodies_are_not_empty(self, seeded_wiki):
        for page in ComponentPage.objects.live()[:5]:
            assert len(page.body) > 0, f"{page.slug} has an empty body"


class TestAutoLinkedWiki:
    def test_pages_get_links(self, seeded_wiki):
        assert EntityLink.objects.filter(auto_created=True).count() > 0

    def test_links_point_at_real_entities(self, seeded_wiki):
        slugs = set(Entity.objects.values_list("slug", flat=True))
        for link in EntityLink.objects.all():
            assert link.target.slug in slugs

    def test_links_record_the_section(self, seeded_wiki):
        """A link must know which section it was found in, for citations."""
        with_section = EntityLink.objects.exclude(section_path="").count()
        assert with_section > 0

    def test_no_red_links_when_every_part_has_a_page(self, seeded_wiki):
        """A red link is an entity without a published page.

        The seed now gives every part a page (the generator fills the gaps), so
        the backlog is empty — and any red link that does exist must still point
        at a page-less entity.
        """
        red = EntityLink.objects.filter(target_exists=False)
        for link in red:
            assert not link.target.wiki_pages.live().exists()
        assert red.count() == 0

    def test_linked_entities_with_a_page_are_not_red(self, seeded_wiki):
        for link in EntityLink.objects.filter(target_exists=True):
            assert link.target.wiki_pages.live().exists()

    def test_integrity_check_passes(self, seeded_wiki):
        result = check_integrity()
        assert result.broken_links == 0
        assert result.total_links > 0
        assert result.orphan_pages == 0


class TestWikiApiAfterSeed:
    def test_pages_are_served(self, api, seeded_wiki):
        response = api.get(reverse("content:page-list"))
        assert response.status_code == 200
        assert response.data["count"] >= 14

    def test_a_page_detail_carries_its_body_and_links(self, api, seeded_wiki):
        response = api.get(reverse("content:page-detail", kwargs={"slug": "ryzen-7-7800x3d"}))
        assert response.status_code == 200
        assert response.data["body"]
        assert response.data["entity"]["slug"] == "ryzen-7-7800x3d"

    def test_ryzen_article_links_full_names_to_published_wiki_pages(self, seeded_wiki):
        page = WikiPage.objects.get(slug="ryzen-7-7800x3d")
        links = {
            (link.text, link.target.slug): link
            for link in EntityLink.objects.filter(page=page, auto_created=True)
        }

        for surface, slug in (
            ("ASUS TUF Gaming B650-PLUS", "asus-tuf-gaming-b650-plus"),
            ("Ryzen 5 7600", "ryzen-5-7600"),
            ("حافظهٔ DDR5", "ddr5"),
        ):
            link = links[(surface, slug)]
            assert link.target_exists is True
            assert link.target.wiki_pages.live().exists()

    def test_seeded_product_titles_follow_category_brand_model_format(self, seeded_wiki):
        cpu = Entity.objects.get(slug="ryzen-7-7800x3d")
        psu = Entity.objects.get(slug="corsair-rm650x")
        assert cpu.display_title == "پردازندهٔ کامپیوتر ای‌ام‌دی مدل Ryzen 7 7800X3D Tray"
        assert "پردازندهٔ کامپیوتر ای‌ام‌دی مدل Ryzen 7 7800X3D Tray" in cpu.aliases
        assert psu.display_title == "پاور ۶۵۰ وات Corsair مدل RM650x 80Plus Gold"
        assert "پاور ۶۵۰ وات Corsair مدل RM650x 80Plus Gold" in psu.aliases

    def test_entityless_guide_gets_internal_links(self, seeded_wiki):
        guide = WikiPage.objects.get(slug="how-to-choose-a-prebuilt-pc")
        links = EntityLink.objects.filter(page=guide, auto_created=True)
        assert links.filter(target__slug="ryzen-5-7600").exists()
        assert links.filter(target__slug="gigabyte-b760m-ds3h").exists()
        assert links.filter(target__slug="rtx-4070-super").exists()
        assert links.filter(target__slug="corsair-rm650x").exists()
        assert links.filter(target__slug="samsung-990-pro-2tb").exists()
        assert links.filter(source__isnull=True).count() == links.count()

    def test_guide_api_includes_its_auto_links(self, api, seeded_wiki):
        response = api.get(
            reverse("content:page-detail", kwargs={"slug": "how-to-choose-a-prebuilt-pc"})
        )
        assert response.status_code == 200
        assert any(link["target_slug"] == "rtx-4070-super" for link in response.data["links"])

    def test_ryzen_5_7600_has_a_published_article(self, api, seeded_wiki):
        response = api.get(reverse("content:page-detail", kwargs={"slug": "ryzen-5-7600"}))
        assert response.status_code == 200
        assert response.data["entity"]["slug"] == "ryzen-5-7600"
        assert len(response.data["body"]) >= 5

    def test_the_guide_lists_its_recommendations(self, api, seeded_wiki):
        response = api.get(
            reverse("content:page-detail", kwargs={"slug": "best-gaming-pcs-1080p-high-fps"})
        )
        assert response.status_code == 200
        assert response.data["recommended_products"]
        assert response.data["use_case"]

    def test_hovercard_works_for_a_seeded_entity(self, api, seeded_wiki):
        response = api.get(reverse("linking:hovercard"), {"entity": "rtx-4060"})
        assert response.status_code == 200
        assert response.data["product"]["price"]
        assert response.data["has_page"] is True

    def test_redlinks_endpoint_is_empty_for_a_complete_catalog(self, api, seeded_wiki):
        response = api.get(reverse("linking:redlinks"))
        assert response.status_code == 200
        # Every seeded part has a published page, so there is no backlog left.
        assert response.data["count"] == 0
