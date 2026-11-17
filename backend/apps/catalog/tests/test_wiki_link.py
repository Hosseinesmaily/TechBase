"""The catalog → wiki link behind the product card's double click.

The address must come from the **entity binding in the database**, never from the
product's name, and an article that was not published must not be offered — a
dead link is worse than no link.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from wagtail.models import Page

from apps.catalog.models import Entity, EntityStatus, EntityType, Product
from apps.content.models import ConceptPage

pytestmark = pytest.mark.django_db

PRODUCTS = "/api/v1/catalog/products/"
ENTITIES = "/api/v1/catalog/entities/"


def make_product(slug: str, sku: str) -> Product:
    entity = Entity.objects.create(
        type=EntityType.CPU, slug=slug, title=slug, status=EntityStatus.PUBLISHED
    )
    return Product.objects.create(sku=sku, entity=entity, title=slug, price="100")


def add_page(slug: str, *, publish: bool, entity: Entity | None = None) -> ConceptPage:
    root = Page.objects.filter(depth=1).first()
    page = ConceptPage(title=f"article {slug}", slug=slug, summary="summary", entity=entity)
    root.add_child(instance=page)
    if publish:
        page.save_revision().publish()
    return page


def product_row(sku: str) -> dict:
    response = APIClient().get(PRODUCTS)
    assert response.status_code == 200
    return next(item for item in response.data["results"] if item["sku"] == sku)


class TestProductWikiLink:
    def test_a_published_article_is_exposed_on_the_product(self):
        product = make_product("cpu-with-article", "sku-with-article")
        add_page("cpu-with-article", publish=True, entity=product.entity)

        assert product_row(product.sku)["wiki_slug"] == "cpu-with-article"

    def test_a_product_without_an_article_gets_an_empty_slug(self):
        product = make_product("cpu-without-article", "sku-without-article")

        assert product_row(product.sku)["wiki_slug"] == ""

    def test_an_unpublished_article_is_not_offered(self):
        product = make_product("cpu-draft-article", "sku-draft-article")
        add_page("cpu-draft-article", publish=False, entity=product.entity)

        # The page exists (and is live) but has never been published: it has no
        # public address yet, so the card must not link to it.
        assert product_row(product.sku)["wiki_slug"] == ""

    def test_the_entity_endpoint_carries_the_same_address(self):
        product = make_product("cpu-entity-link", "sku-entity-link")
        add_page("cpu-entity-link", publish=True, entity=product.entity)

        response = APIClient().get(ENTITIES)
        row = next(item for item in response.data["results"] if item["slug"] == product.entity.slug)
        assert row["wiki_slug"] == "cpu-entity-link"

    def test_another_entitys_article_is_not_borrowed(self):
        first = make_product("cpu-with-own-article", "sku-own")
        make_product("cpu-without-own-article", "sku-without")
        add_page("cpu-with-own-article", publish=True, entity=first.entity)

        assert product_row("sku-without")["wiki_slug"] == ""
        assert product_row("sku-own")["wiki_slug"] == "cpu-with-own-article"
