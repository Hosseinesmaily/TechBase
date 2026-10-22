"""Search API.

Phase 1 ships a simple SQL search over the catalog (title/summary contains).
Phase 3 replaces the internals with a hybrid Meilisearch + pgvector pipeline
fused with RRF, behind this same endpoint — the response shape stays the same
so the frontend does not change.
"""

from __future__ import annotations

from django.db.models import Q
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Entity, Product
from apps.catalog.serializers import EntityListSerializer, ProductSerializer
from apps.core.pagination import DefaultPagination


class SearchView(APIView):
    """Search products and entities.

    `GET /api/v1/search/?q=<query>&page_size=24`

    Returns both result sets in one response so the UI renders one page.
    """

    def get(self, request) -> Response:
        query = request.query_params.get("q", "").strip()
        page_size = min(int(request.query_params.get("page_size", 24)), 100)

        if not query:
            return Response(
                {
                    "query": "",
                    "total": 0,
                    "products": {"count": 0, "results": []},
                    "entities": {"count": 0, "results": []},
                }
            )

        products = (
            Product.objects.filter(is_active=True)
            .select_related("entity", "entity__brand")
            .filter(
                Q(title__icontains=query)
                | Q(title_fa__icontains=query)
                | Q(sku__icontains=query)
                | Q(entity__title__icontains=query)
                | Q(entity__title_fa__icontains=query)
            )
            .distinct()
            .order_by("price")[:page_size]
        )

        entities = (
            Entity.objects.filter(is_active=True)
            .select_related("brand", "category")
            .filter(
                Q(title__icontains=query)
                | Q(title_fa__icontains=query)
                | Q(summary__icontains=query)
                | Q(summary_fa__icontains=query)
                | Q(aliases__icontains=query)
            )
            .distinct()
            .order_by("title")[:page_size]
        )

        product_rows = list(products)
        entity_rows = list(entities)

        return Response(
            {
                "query": query,
                "total": len(product_rows) + len(entity_rows),
                "products": {
                    "count": len(product_rows),
                    "results": ProductSerializer(product_rows, many=True).data,
                },
                "entities": {
                    "count": len(entity_rows),
                    "results": EntityListSerializer(entity_rows, many=True).data,
                },
            }
        )


class SearchAutocompleteView(APIView):
    """Prefix suggestions for the search box.

    Phase 3 replaces this with the Meilisearch autocomplete endpoint; the
    response shape is kept stable.
    """

    def get(self, request) -> Response:
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response({"query": query, "suggestions": []})

        titles = (
            Entity.objects.filter(is_active=True)
            .filter(Q(title__icontains=query) | Q(title_fa__icontains=query))
            .values_list("title_fa", "title", "slug")
            .distinct()[:10]
        )
        suggestions = [
            {"text": fa or title, "slug": slug} for fa, title, slug in titles if (fa or title)
        ]
        return Response({"query": query, "suggestions": suggestions})


class CatalogSearchListView(generics.ListAPIView):
    """A paginated products-only variant, for callers that want DRF pagination."""

    serializer_class = ProductSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip()
        qs = Product.objects.filter(is_active=True).select_related("entity")
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(title_fa__icontains=query)
                | Q(sku__icontains=query)
                | Q(entity__title__icontains=query)
            )
        return qs.distinct().order_by("price")
