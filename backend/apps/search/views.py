"""Search API.

Phase 3 (this file): the hybrid pipeline — Meilisearch for lexical matching
and facets, PostgreSQL as the always-available baseline, fused with RRF.
"""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from . import service


class SearchView(APIView):
    """`GET /api/v1/search/?q=<query>`

    Query parameters:
      * `q`          — the search text (Persian or English)
      * `type`       — filter by entity type (gpu, cpu, prebuilt, …)
      * `brand`      — filter by brand slug
      * `in_stock`   — `true` / `false`
      * `kind`       — restrict to `entity`, `product` or `page`
      * `page_size`  — how many hits (default 24, max 100)

    The response carries the hits, the facet counts and how long the search
    took, plus which backend answered (`hybrid`, `meilisearch` or `postgres`).
    """

    def get(self, request) -> Response:
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response(
                {
                    "query": "",
                    "total": 0,
                    "hits": [],
                    "facets": {},
                    "took_ms": 0,
                    "backend": "postgres",
                }
            )

        limit = min(int(request.query_params.get("page_size", 24)), 100)
        in_stock_param = request.query_params.get("in_stock")
        in_stock = None
        if in_stock_param in {"true", "1", "yes"}:
            in_stock = True
        elif in_stock_param in {"false", "0", "no"}:
            in_stock = False

        response = service.search(
            query,
            limit=limit,
            entity_type=request.query_params.get("type") or None,
            brand=request.query_params.get("brand") or None,
            in_stock=in_stock,
            kind=request.query_params.get("kind") or None,
        )
        return Response(response.as_dict())


class SearchAutocompleteView(APIView):
    """`GET /api/v1/search/autocomplete/?q=<prefix>`

    Minimum two characters.
    """

    def get(self, request) -> Response:
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response({"query": query, "suggestions": []})
        suggestions = service.autocomplete(query)
        return Response({"query": query, "suggestions": suggestions})


class FacetView(APIView):
    """`GET /api/v1/search/facets/` — the facet sources for the filter UI.

    Returned independently of a query so the filter panel can be rendered
    before the user types anything.
    """

    def get(self, request) -> Response:
        from apps.catalog.models import Brand, Entity, Product

        # Every brand that has at least one active entity, with its count.
        brands = [
            {
                "slug": brand.slug,
                "name": brand.name,
                "name_fa": brand.name_fa,
                "count": brand.entities.filter(is_active=True).count(),
            }
            for brand in Brand.objects.filter(entities__is_active=True).distinct().order_by("name")
        ]

        return Response(
            {
                "brands": brands,
                "types": [
                    {
                        "value": value,
                        "label": label,
                        "count": Entity.objects.filter(type=value, is_active=True).count(),
                    }
                    for value, label in _type_choices()
                ],
                "in_stock": {
                    "yes": Product.objects.filter(is_active=True, stock__gt=0).count(),
                    "no": Product.objects.filter(is_active=True, stock=0).count(),
                },
            }
        )


def _type_choices() -> list[tuple[str, str]]:
    """The entity types and their Persian labels."""
    from apps.catalog.models import EntityType

    return [(value, label) for value, label in EntityType.choices]
