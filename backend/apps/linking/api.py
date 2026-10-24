"""Linking API: hover cards, backlinks and the red-link backlog.

The hover card is what makes a wiki feel dense: hovering a linked name shows
the price, the key specs and whether the entity has its own page — all from
the catalog, so it can never contradict the shop.
"""

from __future__ import annotations

from django.db.models import Count
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Entity, Product

from .models import EntityLink

#: The specs shown on a hover card, in order. Kept short on purpose.
HOVER_SPEC_KEYS = [
    "socket",
    "memory_type",
    "cores",
    "threads",
    "tdp",
    "wattage",
    "vram_gb",
    "length_mm",
    "capacity_gb",
    "speed_mhz",
]

#: Persian labels for the spec keys, so the card reads in the product language.
SPEC_LABELS = {
    "socket": "سوکت",
    "memory_type": "نوع حافظه",
    "cores": "هسته",
    "threads": "رشته",
    "tdp": "توان (وات)",
    "wattage": "توان منبع (وات)",
    "vram_gb": "حافظهٔ گرافیک (GB)",
    "length_mm": "طول (میلی‌متر)",
    "capacity_gb": "ظرفیت (GB)",
    "speed_mhz": "سرعت (MHz)",
    "recommended_psu": "منبع پیشنهادی (وات)",
}


class HoverCardView(APIView):
    """`GET /linking/hovercard/?entity=<slug>`

    Returns the title, the price, the stock, a few key specs and the URL of
    the entity's wiki page (or `has_page: false`, which is how the frontend
    renders a red link).
    """

    def get(self, request) -> Response:
        slug = request.query_params.get("entity", "").strip()
        if not slug:
            return Response({"error": "entity query parameter is required"}, status=400)

        entity = (
            Entity.objects.filter(slug=slug).select_related("brand", "category", "spec").first()
        )
        if entity is None:
            return Response({"error": f"no entity with slug {slug!r}"}, status=404)

        product = Product.objects.filter(entity=entity, is_active=True).order_by("price").first()

        specs: list[dict] = []
        spec = getattr(entity, "spec", None)
        if spec is not None:
            merged = {**(spec.common or {}), **(spec.extra or {})}
            for key in HOVER_SPEC_KEYS:
                if key in merged and merged[key] is not None:
                    specs.append(
                        {
                            "key": key,
                            "label": SPEC_LABELS.get(key, key),
                            "value": merged[key],
                        }
                    )

        page = entity.wiki_pages.live().first() if entity.pk is not None else None

        return Response(
            {
                "entity": {
                    "slug": entity.slug,
                    "title": entity.display_title,
                    "type": entity.type,
                    "brand": entity.brand.name if entity.brand is not None else None,
                    "summary": entity.summary_fa or entity.summary,
                },
                "product": (
                    {
                        "sku": product.sku,
                        "price": str(product.price),
                        "currency": product.currency,
                        "stock": product.stock,
                        "in_stock": product.in_stock,
                        "price_updated_at": product.price_updated_at.isoformat()
                        if product.price_updated_at
                        else None,
                    }
                    if product
                    else None
                ),
                "specs": specs,
                "has_page": page is not None,
                "page_url": f"/wiki/{page.slug}/" if page else None,
            }
        )


class BacklinkListView(APIView):
    """`GET /linking/backlinks/<slug>/` — pages that link to this entity."""

    def get(self, request, slug: str) -> Response:
        entity = Entity.objects.filter(slug=slug).first()
        if entity is None:
            return Response({"error": f"no entity with slug {slug!r}"}, status=404)

        links = (
            EntityLink.objects.filter(target=entity)
            .select_related("source", "page")
            .order_by("-updated_at")
        )

        return Response(
            {
                "entity": entity.slug,
                "count": links.count(),
                "backlinks": [
                    {
                        "source_slug": link.source.slug if link.source_id else None,
                        "source_title": link.source.display_title if link.source_id else None,
                        "link_type": link.link_type,
                        "text": link.text,
                        "section_path": link.section_path,
                        "page_slug": link.page.slug if link.page is not None else None,
                        "page_title": link.page.title if link.page is not None else None,
                    }
                    for link in links
                ],
            }
        )


class RedLinkListView(APIView):
    """`GET /linking/redlinks/` — entities mentioned but without a page.

    This is the editorial backlog: what the wiki should write next.
    """

    def get(self, request) -> Response:
        limit = min(int(request.query_params.get("limit", 100)), 500)

        red = (
            EntityLink.objects.filter(target_exists=False)
            .values("target__slug", "target__title_fa", "target__title", "target__type")
            .annotate(mentions=Count("id"))
            .order_by("-mentions")
        )

        rows = [
            {
                "slug": row["target__slug"],
                "title": row["target__title_fa"] or row["target__title"],
                "type": row["target__type"],
                "mentions": row["mentions"],
            }
            for row in red[:limit]
        ]

        return Response({"count": len(rows), "results": rows})


class OrphanPageListView(APIView):
    """`GET /linking/orphans/` — published pages nothing links to."""

    def get(self, request) -> Response:
        from apps.content.models import WikiPage

        orphans = WikiPage.objects.live().filter(links__isnull=True).distinct().order_by("path")
        rows = [
            {
                "slug": page.slug,
                "title": page.title,
                "entity_slug": page.entity.slug if page.entity is not None else None,
            }
            for page in orphans
        ]
        return Response({"count": len(rows), "results": rows})
