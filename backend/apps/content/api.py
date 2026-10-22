"""Wiki API for the Nuxt frontend.

The Nuxt app renders all public pages, so it reads the wiki through these
endpoints rather than rendering Wagtail templates. Wagtail keeps the editorial
side (revisions, workflow, preview) and the database.

Only **live** (published) pages are exposed here.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.linking.models import EntityLink

from .models import BuyerGuidePage, ComponentPage, ConceptPage, WikiPage


class WikiPageSerializer:
    """Plain serialisation of a page (no DRF ModelSerializer — the shape is
    ours and the frontend depends on it)."""

    @staticmethod
    def to_dict(page: WikiPage, *, include_body: bool = True) -> dict:
        entity = page.entity
        data = {
            "id": page.id,
            "title": page.title,
            "slug": page.slug,
            "path": page.url_path,
            "page_type": page.specific_class.__name__ if page.specific_class else "WikiPage",
            "summary": page.summary,
            "review_by": page.review_by.isoformat() if page.review_by else None,
            "is_stale": page.is_stale,
            "tags": page.tags,
            "language": page.language,
            "entity": (
                {
                    "slug": entity.slug,
                    "title": entity.display_title,
                    "type": entity.type,
                }
                if entity is not None
                else None
            ),
            "last_updated": page.last_published_at.isoformat() if page.last_published_at else None,
        }

        if include_body:
            data["body"] = _render_body(page)

        if isinstance(page, BuyerGuidePage):
            data["use_case"] = page.use_case
            data["resolution"] = page.resolution
            data["budget_max"] = str(page.budget_max) if page.budget_max else None
            data["recommended_products"] = [
                {
                    "sku": product.sku,
                    "title": product.display_title,
                    "price": str(product.price),
                    "currency": product.currency,
                    "in_stock": product.in_stock,
                    "stock": product.stock,
                    "entity_slug": product.entity.slug,
                }
                for product in page.recommended_products.all()
            ]

        return data


def _render_body(page: WikiPage) -> list[dict]:
    """The StreamField body as a list of block dicts, ready for the frontend."""
    blocks: list[dict] = []
    # The body lives on the concrete page type, not on the WikiPage base.
    specific = page.specific if hasattr(page, "specific") else page
    body = getattr(specific, "body", None)
    if body is None:
        return blocks

    for block in body:
        block_type = block.block_type
        value = block.value
        if block_type == "heading":
            blocks.append(
                {
                    "type": "heading",
                    "level": value.get("level", "h2"),
                    "text": value.get("text", ""),
                    "id": _slugify(value.get("text", "")),
                }
            )
        elif block_type == "paragraph":
            blocks.append({"type": "paragraph", "text": value})
        elif block_type == "rich_text":
            blocks.append({"type": "rich_text", "html": str(value)})
        elif block_type == "list":
            blocks.append(
                {
                    "type": "list",
                    "style": value.get("style", "ul"),
                    "items": list(value.get("items", [])),
                }
            )
        elif block_type == "quote":
            blocks.append(
                {
                    "type": "quote",
                    "text": value.get("text", ""),
                    "source": value.get("source", ""),
                }
            )
        elif block_type == "callout":
            blocks.append(
                {
                    "type": "callout",
                    "kind": value.get("kind", "info"),
                    "title": value.get("title", ""),
                    "text": value.get("text", ""),
                }
            )
        elif block_type == "spec_table":
            blocks.append(
                {
                    "type": "spec_table",
                    "title": value.get("title", ""),
                    "rows": [
                        {"label": row.get("label", ""), "value": row.get("value", "")}
                        for row in value.get("rows", [])
                    ],
                }
            )
        elif block_type == "image":
            image = value.get("image")
            blocks.append(
                {
                    "type": "image",
                    "url": image.file.url if image else "",
                    "caption": value.get("caption", ""),
                }
            )
        elif block_type == "related_entity":
            blocks.append(
                {
                    "type": "related_entity",
                    "entity_slug": value.get("entity_slug", ""),
                    "note": value.get("note", ""),
                }
            )
    return blocks


def _slugify(text: str) -> str:
    from django.utils.text import slugify

    return slugify(text, allow_unicode=True)


def published_pages():
    """The pages that are actually published.

    Wagtail's `live()` flag is True for a freshly created page that has never
    been published, so `first_published_at` is the reliable signal: a draft
    has it as None.
    """
    return (
        WikiPage.objects.live()
        .filter(first_published_at__isnull=False)
        .select_related("entity")
        .exclude(slug="wiki")
    )


class WikiPageListView(generics.ListAPIView):
    """List published wiki pages.

    Filters: `type` (component|guide|concept), `entity` (slug), `q` (search),
    `stale` (only pages past their review date).
    """

    def get_queryset(self):
        qs = published_pages()
        params = self.request.query_params

        page_type = params.get("type", "")
        model = {
            "component": ComponentPage,
            "guide": BuyerGuidePage,
            "concept": ConceptPage,
        }.get(page_type)
        if model is not None:
            qs = qs.filter(
                content_type__model=model._meta.model_name,
            )

        entity = params.get("entity")
        if entity:
            qs = qs.filter(entity__slug=entity)

        if params.get("stale") in {"1", "true", "yes"}:
            from django.utils import timezone

            qs = qs.filter(review_by__lt=timezone.now().date())

        query = params.get("q", "").strip()
        if query:
            from django.db.models import Q

            qs = qs.filter(Q(title__icontains=query) | Q(summary__icontains=query))

        return qs.order_by("path")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        rows = [WikiPageSerializer.to_dict(item, include_body=False) for item in (page or queryset)]
        if page is not None:
            return self.get_paginated_response(rows)
        return Response({"count": len(rows), "next": None, "previous": None, "results": rows})


class WikiPageDetailView(APIView):
    """One published page by its slug, with its body and its links."""

    def get(self, request, slug: str) -> Response:
        page = get_object_or_404(published_pages(), slug=slug)
        # The concrete page type holds the body and the guide fields.
        page = page.specific
        data = WikiPageSerializer.to_dict(page)
        data["links"] = [
            {
                "type": link.link_type,
                "text": link.text,
                "target_slug": link.target.slug,
                "target_title": link.target.display_title,
                "target_exists": link.target_exists,
                "section_path": link.section_path,
            }
            for link in EntityLink.objects.filter(page=page, source=page.entity).select_related(
                "target"
            )
        ]
        return Response(data)
