"""Admin for the catalog. Editorial staff use this to curate the data the
assistant is allowed to state as fact."""

from django.contrib import admin

from .models import Brand, Category, ComponentSpec, Entity, Product


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "name_fa", "country", "entity_count")
    search_fields = ("name", "name_fa")
    list_filter = ("country",)

    @admin.display(description="entities")
    def entity_count(self, obj: Brand) -> int:
        return obj.entities.count()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "name_fa", "parent", "is_active")
    search_fields = ("name", "name_fa")
    list_filter = ("is_active",)


class ComponentSpecInline(admin.StackedInline):
    model = ComponentSpec
    can_delete = False
    extra = 0


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("title", "title_fa", "type", "brand", "status", "review_by", "is_active")
    list_filter = ("type", "status", "is_active", "brand")
    search_fields = ("title", "title_fa", "aliases", "summary", "summary_fa")
    list_editable = ("status",)
    autocomplete_fields = ("brand", "category")
    inlines = [ComponentSpecInline]
    fieldsets = (
        (
            None,
            {"fields": ("type", "title", "title_fa", "slug", "aliases", "summary", "summary_fa")},
        ),
        ("Classification", {"fields": ("brand", "category", "status")}),
        ("Editorial", {"fields": ("review_by", "is_active")}),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "title", "entity", "price", "currency", "stock", "source", "is_active")
    list_filter = ("is_active", "source", "currency")
    search_fields = ("sku", "title", "title_fa")
    autocomplete_fields = ("entity",)
    readonly_fields = ("created_at", "updated_at", "price_updated_at")
    fieldsets = (
        (None, {"fields": ("sku", "entity", "title", "title_fa", "image_url")}),
        ("Commerce", {"fields": ("price", "currency", "stock", "warranty_months", "source")}),
        ("Status", {"fields": ("is_active", "created_at", "updated_at", "price_updated_at")}),
    )


@admin.register(ComponentSpec)
class ComponentSpecAdmin(admin.ModelAdmin):
    list_display = ("entity", "category", "updated_at")
    search_fields = ("entity__title", "entity__title_fa")
    autocomplete_fields = ("entity",)
