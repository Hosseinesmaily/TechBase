"""Catalog domain: the central linkable object (Entity) and its market faces.

Design (docs/PLAN.md §3, D4):
  * `Entity` — stable identity for a thing (a CPU, a concept). Wiki pages, specs,
    benchmarks and links all attach to it. Slugs are ASCII so URLs stay clean;
    the Persian display name lives in `title_fa`.
  * `Product` — a *market* SKU for an entity. Price and stock live here, never on
    the entity, because they change constantly.
  * `ComponentSpec` — machine-readable specs. Hot, rule-relevant fields go in
    `common` (JSONB, indexed); everything else goes in `extra` (JSONB) so a new
    component category never needs a migration.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel, UUIDModel


class EntityType(models.TextChoices):
    """What an entity is. Drives filters, facets and the auto-linker."""

    CPU = "cpu", "پردازنده"
    GPU = "gpu", "کارت گرافیک"
    RAM = "ram", "حافظه"
    MOTHERBOARD = "motherboard", "مادربرد"
    PSU = "psu", "منبع تغذیه"
    CASE = "case", "کیس"
    COOLER = "cooler", "خنک‌کننده"
    STORAGE = "storage", "حافظه ذخیره‌سازی"
    PREBUILT = "prebuilt", "سیستم آماده"
    CONCEPT = "concept", "مفهوم"
    GAME = "game", "بازی"


class EntityStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    RED = "red", "بدون صفحه"  # has no wiki page yet — editorial backlog
    PUBLISHED = "published", "منتشر شده"


class Category(UUIDModel, TimeStampedModel):
    """Hierarchical product category. Also used as the facet source in search."""

    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=120)
    name_fa = models.CharField(max_length=120, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.name_fa})" if self.name_fa else self.name


class Brand(UUIDModel, TimeStampedModel):
    """Manufacturer. Facet source; the auto-linker uses its name as an alias."""

    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=120, unique=True)
    name_fa = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=80, blank=True)

    class Meta:
        verbose_name = "برند"
        verbose_name_plural = "برندها"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Entity(UUIDModel, TimeStampedModel):
    """The central linkable object.

    An entity is a *concept with identity* ("Ryzen 7 7800X3D", "DDR5", "Ray
    tracing"). It is not a SKU: a SKU is a `Product` that sells it.
    """

    type = models.CharField(max_length=32, choices=EntityType.choices, db_index=True)
    slug = models.SlugField(max_length=160, unique=True)
    title = models.CharField(max_length=200)  # canonical (usually latin) name
    title_fa = models.CharField(max_length=200, blank=True)
    # Alternative names for the auto-linker: ["7800x3d", "ریزن ۷ ۷۸۰۰x3d", ...]
    aliases = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True)
    summary_fa = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=EntityStatus.choices,
        default=EntityStatus.DRAFT,
        db_index=True,
    )
    # Stale-content tracking: editorial review due date.
    review_by = models.DateField(null=True, blank=True, db_index=True)
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, null=True, blank=True, related_name="entities"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, null=True, blank=True, related_name="entities"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "موجودیت"
        verbose_name_plural = "موجودیت‌ها"
        ordering = ["title"]
        indexes = [
            models.Index(fields=["type", "status"], name="entity_type_status_idx"),
            models.Index(fields=["brand", "type"], name="entity_brand_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.title} [{self.type}]"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.title)[:160]
        super().save(*args, **kwargs)

    @property
    def display_title(self) -> str:
        """Persian title when available (the product language)."""
        return self.title_fa or self.title

    @property
    def search_terms(self) -> list[str]:
        """All names the auto-linker may match for this entity."""
        terms = [self.title, self.title_fa, *self.aliases]
        brand = self.brand
        if brand is not None:
            terms.append(brand.name)
            if brand.name_fa:
                terms.append(brand.name_fa)
        return [t for t in terms if t]


class Product(UUIDModel, TimeStampedModel):
    """A market SKU: something you can actually buy, with a price and a stock count."""

    sku = models.SlugField(max_length=120, unique=True)
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="products")
    title = models.CharField(max_length=200)
    title_fa = models.CharField(max_length=200, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=8, default="IRT")  # IRT = تومان
    stock = models.PositiveIntegerField(default=0)
    # Where this data came from: seed | mock_erp | csv | manual
    source = models.CharField(max_length=32, default="seed", db_index=True)
    is_active = models.BooleanField(default=True)
    # "last updated" shown on product cards — updated_at is the real timestamp,
    # this lets the catalog distinguish a price refresh from any other edit.
    price_updated_at = models.DateTimeField(null=True, blank=True)
    warranty_months = models.PositiveSmallIntegerField(default=0)
    image_url = models.URLField(blank=True)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["entity", "is_active"], name="product_entity_active_idx"),
            models.Index(fields=["price"], name="product_price_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.sku} — {self.title}"

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def display_title(self) -> str:
        return self.title_fa or self.title


class ComponentSpec(UUIDModel, TimeStampedModel):
    """Machine-readable specs for a component entity.

    `common` holds the fields the compatibility engine and filters need
    (socket, memory_type, tdp, wattage, length, ...). `extra` holds everything
    else. Both are JSONB so a new component type is seed data, not a migration.
    """

    entity = models.OneToOneField(Entity, on_delete=models.CASCADE, related_name="spec")
    category = models.CharField(max_length=64, blank=True)  # e.g. "gpu", "motherboard"
    common = models.JSONField(default=dict, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "مشخصات فنی"
        verbose_name_plural = "مشخصات فنی"

    def __str__(self) -> str:
        return f"spec({self.entity.title})"

    def get(self, key: str, default: object = None) -> object:
        """Read from `common` first, then `extra`."""
        value = self.common.get(key)
        if value is None:
            value = self.extra.get(key, default)
        return value
