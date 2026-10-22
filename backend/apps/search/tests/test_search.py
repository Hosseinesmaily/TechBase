"""Tests for the search service: RRF fusion, the PostgreSQL backend and the API."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Brand, Entity, EntityStatus, EntityType, Product
from apps.search import postgres, service
from apps.search.meili import SearchResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def catalog():
    brand = Brand.objects.create(slug="amd", name="AMD", name_fa="ای‌ام‌دی")
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
        title_fa="کارت RTX 4060",
        price="18900000",
        stock=18,
    )
    Product.objects.create(
        sku="tb-cpu-7600",
        entity=cpu,
        title="Ryzen 5 7600",
        title_fa="پردازنده رایزن ۵",
        price="15800000",
        stock=0,
    )
    return {"gpu": gpu, "cpu": cpu, "brand": brand}


def hit(slug: str, kind: str = "entity", score: float = 0.0) -> SearchResult:
    return SearchResult(
        id=slug,
        slug=slug,
        title=slug,
        kind=kind,
        score=score,
    )


class TestReciprocalRankFusion:
    def test_a_document_in_both_lists_scores_higher(self):
        meili = [hit("a"), hit("b"), hit("c")]
        pg = [hit("a"), hit("d")]
        fused = service.reciprocal_rank_fusion([meili, pg])
        assert fused[0].slug == "a"

    def test_a_document_in_one_list_still_appears(self):
        fused = service.reciprocal_rank_fusion([[hit("a")], [hit("b")]])
        slugs = {h.slug for h in fused}
        assert slugs == {"a", "b"}

    def test_ordering_follows_the_fused_score(self):
        fused = service.reciprocal_rank_fusion([[hit("a"), hit("b")], [hit("b"), hit("a")]])
        # Symmetric input → symmetric output.
        assert {h.slug for h in fused} == {"a", "b"}
        assert fused[0].score == pytest.approx(fused[1].score)

    def test_the_same_kind_and_slug_is_merged(self):
        fused = service.reciprocal_rank_fusion([[hit("x", "entity")], [hit("x", "entity")]])
        assert len(fused) == 1

    def test_different_kinds_with_the_same_slug_stay_separate(self):
        fused = service.reciprocal_rank_fusion([[hit("x", "entity")], [hit("x", "product")]])
        assert len(fused) == 2

    def test_empty_input_gives_empty_output(self):
        assert service.reciprocal_rank_fusion([[], []]) == []

    def test_the_fused_score_is_positive(self):
        fused = service.reciprocal_rank_fusion([[hit("a")]])
        assert fused[0].score > 0


class TestPostgresSearch:
    def test_finds_by_latin_name(self, catalog):
        response = postgres.search("RTX 4060")
        slugs = {h.slug for h in response.hits}
        assert "rtx-4060" in slugs

    def test_finds_by_persian_name(self, catalog):
        response = postgres.search("رایزن")
        slugs = {h.slug for h in response.hits}
        assert "ryzen-5-7600" in slugs

    def test_finds_by_number(self, catalog):
        response = postgres.search("4060")
        assert response.total > 0

    def test_search_is_case_insensitive(self, catalog):
        assert postgres.search("rtx").total == postgres.search("RTX").total

    def test_all_query_tokens_must_match(self, catalog):
        # "RTX" is present, "zzz" is not → no hit.
        assert postgres.search("RTX zzz").total == 0

    def test_filters_by_type(self, catalog):
        response = postgres.search("a", entity_type="cpu")
        kinds = {h.extra["entity_type"] for h in response.hits if h.kind == "entity" and h.extra}
        assert kinds <= {"cpu"}

    def test_filters_by_brand(self, catalog):
        response = postgres.search("a", brand="amd")
        assert response.total > 0
        response = postgres.search("a", brand="nvidia")
        assert response.total == 0

    def test_filters_by_stock(self, catalog):
        response = postgres.search("a", in_stock=True)
        assert all(h.in_stock for h in response.hits if h.kind == "product")
        response = postgres.search("a", in_stock=False)
        assert all(not h.in_stock for h in response.hits if h.kind == "product")

    def test_empty_query_gives_nothing(self, catalog):
        assert postgres.search("").total == 0

    def test_facets_count_the_hits(self, catalog):
        response = postgres.search("a")
        assert response.facets is not None
        assert "type" in response.facets

    def test_the_backend_is_reported(self, catalog):
        assert postgres.search("RTX").backend == "postgres"


class TestAutocomplete:
    def test_requires_two_characters(self, catalog):
        assert postgres.autocomplete("R") == []

    def test_suggests_matching_titles(self, catalog):
        suggestions = postgres.autocomplete("RTX")
        assert suggestions
        assert suggestions[0]["slug"] == "rtx-4060"

    def test_suggestion_has_text_and_slug(self, catalog):
        suggestion = postgres.autocomplete("RTX")[0]
        assert suggestion["text"]
        assert suggestion["slug"]
        assert suggestion["kind"] == "entity"


class TestSearchApi:
    def test_returns_the_documented_shape(self, api, catalog):
        response = api.get(reverse("search:search"), {"q": "RTX"})
        assert response.status_code == 200
        for key in ("query", "total", "hits", "facets", "took_ms", "backend"):
            assert key in response.data

    def test_empty_query_returns_an_empty_result(self, api, catalog):
        response = api.get(reverse("search:search"))
        assert response.data["total"] == 0
        assert response.data["hits"] == []

    def test_hits_carry_the_expected_fields(self, api, catalog):
        response = api.get(reverse("search:search"), {"q": "RTX"})
        first = response.data["hits"][0]
        for key in ("id", "slug", "title", "kind", "score"):
            assert key in first

    def test_facets_endpoint_lists_brands_and_types(self, api, catalog):
        response = api.get(reverse("search:facets"))
        assert response.status_code == 200
        assert response.data["brands"]
        assert response.data["types"]
        assert "in_stock" in response.data

    def test_autocomplete_endpoint(self, api, catalog):
        response = api.get(reverse("search:autocomplete"), {"q": "RTX"})
        assert response.status_code == 200
        assert response.data["suggestions"]

    def test_autocomplete_needs_two_characters(self, api, catalog):
        response = api.get(reverse("search:autocomplete"), {"q": "R"})
        assert response.data["suggestions"] == []


class TestIndexing:
    def test_builds_a_document_for_every_entity(self, catalog):
        from apps.search.indexer import build_documents

        documents = build_documents()
        assert len(documents["entities"]) == 2
        assert len(documents["products"]) == 2

    def test_the_entity_document_has_the_searchable_fields(self, catalog):
        from apps.search.indexer import entity_document

        document = entity_document(catalog["gpu"])
        assert document["slug"] == "rtx-4060"
        assert document["title_fa"]
        assert document["entity_type"] == "gpu"
        assert document["brand"] == "AMD"

    def test_the_product_document_carries_the_price(self, catalog):
        from apps.search.indexer import product_document

        product = catalog["gpu"].products.first()
        document = product_document(product)
        assert document["price"] == "18900000.00"
        assert document["in_stock"] is True

    def test_reindex_reports_when_meilisearch_is_down(self, catalog):
        """The reindex must not crash when the search container is not up."""
        from apps.search.indexer import reindex_all

        report = reindex_all()
        assert "meilisearch" in report
        assert "indexes" in report
        if not report["meilisearch"]:
            assert report["errors"]


class TestSearchWithWikiContent:
    def test_finds_a_wiki_page(self, api):
        from wagtail.models import Page

        from apps.content.models import WikiPage

        call_command("seed_demo", verbosity=0)
        root = Page.get_first_root_node()
        assert root is not None
        wiki = root.add_child(instance=WikiPage(title="ویکی", slug="wiki"))
        page = wiki.add_child(
            instance=WikiPage(
                title="حافظهٔ DDR5 چیست؟",
                slug="ddr5",
                summary="نسل پنجم حافظهٔ DDR",
            )
        )
        # A page is only searchable once it has been published.
        page.save_revision().publish()

        response = api.get(reverse("search:search"), {"q": "DDR5"})
        slugs = {hit["slug"] for hit in response.data["hits"]}
        assert "ddr5" in slugs
