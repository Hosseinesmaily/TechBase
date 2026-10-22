"""Catalog API: entities, products, brands, categories.

All reads are public. Writes happen in Django admin (editorial staff) or via
the inventory sync job — never through this API in v1.
"""

from __future__ import annotations

from django.db.models import Count, Prefetch, Q
from django.http import Http404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Brand, Category, Entity, Product
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    EntityDetailSerializer,
    EntityListSerializer,
    ProductSerializer,
)


class BrandListView(generics.ListAPIView):
    """Facet source: all brands that have at least one active entity."""

    serializer_class = BrandSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Brand.objects.filter(entities__is_active=True)
            .distinct()
            .annotate(entity_count=Count("entities"))
            .order_by("name")
        )


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by("name")


class EntityListView(generics.ListAPIView):
    """List/filter entities.

    Filters: `type`, `brand` (slug), `category` (slug), `status`, `q` (search),
    `in_stock`.
    """

    serializer_class = EntityListSerializer

    def get_queryset(self):
        qs = Entity.objects.filter(is_active=True).select_related("brand", "category")
        params = self.request.query_params

        entity_type = params.get("type")
        if entity_type:
            qs = qs.filter(type=entity_type)

        brand = params.get("brand")
        if brand:
            qs = qs.filter(brand__slug=brand)

        category = params.get("category")
        if category:
            qs = qs.filter(category__slug=category)

        status = params.get("status")
        if status:
            qs = qs.filter(status=status)

        query = params.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(title_fa__icontains=query)
                | Q(summary__icontains=query)
                | Q(summary_fa__icontains=query)
            )

        if params.get("in_stock") in {"1", "true", "yes"}:
            qs = qs.filter(products__stock__gt=0, products__is_active=True)

        return qs.distinct().order_by("title")


class EntityDetailView(generics.RetrieveAPIView):
    """Entity by slug, with specs and the products that sell it."""

    serializer_class = EntityDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Entity.objects.filter(is_active=True)
            .select_related("brand", "category", "spec")
            .prefetch_related(Prefetch("products", queryset=Product.objects.filter(is_active=True)))
        )


class ProductListView(generics.ListAPIView):
    """List/filter products.

    Filters: `category` (entity type), `brand` (slug), `min_price`, `max_price`,
    `in_stock`, `q`, `entity` (slug).
    """

    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related(
            "entity", "entity__brand", "entity__category"
        )
        params = self.request.query_params

        entity_type = params.get("category")
        if entity_type:
            qs = qs.filter(entity__type=entity_type)

        brand = params.get("brand")
        if brand:
            qs = qs.filter(entity__brand__slug=brand)

        entity = params.get("entity")
        if entity:
            qs = qs.filter(entity__slug=entity)

        min_price = params.get("min_price")
        if min_price:
            qs = qs.filter(price__gte=min_price)

        max_price = params.get("max_price")
        if max_price:
            qs = qs.filter(price__lte=max_price)

        if params.get("in_stock") in {"1", "true", "yes"}:
            qs = qs.filter(stock__gt=0)

        query = params.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(title_fa__icontains=query)
                | Q(sku__icontains=query)
                | Q(entity__title__icontains=query)
                | Q(entity__title_fa__icontains=query)
            )

        return qs.order_by("price")


class ProductDetailView(generics.RetrieveAPIView):
    """Product by SKU — includes `updated_at` so the UI can show "last updated"."""

    serializer_class = ProductSerializer
    lookup_field = "sku"
    lookup_url_kwarg = "sku"

    def get_queryset(self):
        return Product.objects.filter(is_active=True).select_related("entity", "entity__brand")


class EntityBySlugView(APIView):
    """Resolve a slug to an entity, or 404. Used by the wiki's link layer."""

    def get(self, request, slug: str) -> Response:
        try:
            entity = Entity.objects.select_related("brand", "category").get(slug=slug)
        except Entity.DoesNotExist as exc:
            raise Http404 from exc
        return Response(EntityListSerializer(entity).data)
