"""Catalog serializers.

Read models are intentionally shallow and denormalized for the product card UI:
a client renders a card without a second request.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import Brand, Category, ComponentSpec, Entity, Product


class BrandSerializer(serializers.ModelSerializer):
    entity_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Brand
        fields = ("id", "slug", "name", "name_fa", "country", "entity_count")
        read_only_fields = fields


class CategorySerializer(serializers.ModelSerializer):
    parent_slug: serializers.SlugRelatedField = serializers.SlugRelatedField(
        source="parent", slug_field="slug", read_only=True
    )

    class Meta:
        model = Category
        fields = ("id", "slug", "name", "name_fa", "parent", "parent_slug", "is_active")
        read_only_fields = fields


class ComponentSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentSpec
        fields = ("category", "common", "extra")
        read_only_fields = fields


class ProductSerializer(serializers.ModelSerializer):
    """Product card payload. `price` is a string to avoid float drift in JSON."""

    in_stock = serializers.BooleanField(read_only=True)
    display_title = serializers.CharField(read_only=True)
    entity_slug: serializers.SlugRelatedField = serializers.SlugRelatedField(
        source="entity", slug_field="slug", read_only=True
    )
    entity_type = serializers.CharField(source="entity.type", read_only=True)
    entity_title_fa = serializers.CharField(source="entity.title_fa", read_only=True)
    price_updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "title",
            "title_fa",
            "display_title",
            "entity_slug",
            "entity_type",
            "entity_title_fa",
            "price",
            "currency",
            "stock",
            "in_stock",
            "source",
            "is_active",
            "warranty_months",
            "image_url",
            "price_updated_at",
            "updated_at",
        )
        read_only_fields = fields


class EntityListSerializer(serializers.ModelSerializer):
    """Light payload for list views."""

    display_title = serializers.CharField(read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True, default=None)
    category_slug: serializers.SlugRelatedField = serializers.SlugRelatedField(
        source="category", slug_field="slug", read_only=True
    )
    price_min = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Entity
        fields = (
            "id",
            "type",
            "slug",
            "title",
            "title_fa",
            "display_title",
            "summary",
            "summary_fa",
            "status",
            "review_by",
            "brand_name",
            "category_slug",
            "price_min",
            "in_stock",
        )
        read_only_fields = fields

    def get_in_stock(self, obj: Entity) -> bool:
        return any(p.in_stock for p in obj.products.all() if p.is_active)

    def get_price_min(self, obj: Entity) -> str | None:
        """Cheapest active product price — `None` when the entity is not sold yet."""
        price = (
            obj.products.filter(is_active=True)
            .order_by("price")
            .values_list("price", flat=True)
            .first()
        )
        return str(price) if price is not None else None


class EntityDetailSerializer(EntityListSerializer):
    """Detail payload: specs + the product(s) that sell it."""

    spec = serializers.SerializerMethodField()
    products = ProductSerializer(many=True, read_only=True)

    class Meta(EntityListSerializer.Meta):
        # The base Meta declares a fixed-length tuple, so a widening assignment
        # is rejected by mypy. Declaring the fields explicitly avoids that.
        fields = (  # type: ignore[assignment]
            "id",
            "type",
            "slug",
            "title",
            "title_fa",
            "display_title",
            "summary",
            "summary_fa",
            "status",
            "review_by",
            "brand_name",
            "category_slug",
            "price_min",
            "in_stock",
            "spec",
            "products",
            "aliases",
        )
        read_only_fields = fields  # type: ignore[assignment]

    def get_spec(self, obj: Entity) -> dict | None:
        spec = getattr(obj, "spec", None)
        if spec is None:
            return None
        return {"category": spec.category, "common": spec.common, "extra": spec.extra}
