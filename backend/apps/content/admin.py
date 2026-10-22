"""Django admin registrations for the wiki models.

Wagtail has its own admin for pages; these registrations exist so the
linking models and the integrity reports are visible and manageable from
`/admin/` too.
"""

from django.contrib import admin

from apps.linking.models import EntityLink, LinkIntegrityReport


@admin.register(EntityLink)
class EntityLinkAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "target",
        "link_type",
        "section_path",
        "auto_created",
        "target_exists",
        "page",
    )
    list_filter = ("link_type", "auto_created", "target_exists")
    search_fields = ("source__title", "target__title", "text", "section_path")
    # `page` points at a Wagtail Page, which the Django admin cannot autocomplete.
    autocomplete_fields = ("source", "target")
    list_editable = ("link_type", "target_exists")

    @admin.display(description="red link")
    def is_red(self, obj: EntityLink) -> bool:
        return obj.is_red_link


@admin.register(LinkIntegrityReport)
class LinkIntegrityReportAdmin(admin.ModelAdmin):
    list_display = ("ran_at", "total_links", "red_links", "orphan_pages", "broken_links")
    readonly_fields = (
        "ran_at",
        "total_links",
        "red_links",
        "orphan_pages",
        "broken_links",
        "details",
    )
    list_filter = ("ran_at",)
