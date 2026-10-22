from django.contrib import admin

from .models import CompatibilityRule


@admin.register(CompatibilityRule)
class CompatibilityRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "category_a", "category_b", "severity", "enabled", "order")
    list_filter = ("enabled", "severity", "category_a", "category_b")
    search_fields = ("code", "description", "description_fa")
    list_editable = ("enabled", "severity", "order")
    fieldsets = (
        (None, {"fields": ("code", "description", "description_fa")}),
        ("Scope", {"fields": ("category_a", "category_b", "enabled", "severity", "order")}),
        ("Parameters", {"fields": ("params",)}),
    )
