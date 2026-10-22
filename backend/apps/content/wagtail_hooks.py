"""Wagtail admin customisation for the editorial team.

The admin is the *only* way content is created, so it should present the
editorial model clearly: pages, their linked entity, when they need review,
and the backlog of entities that still need a page.
"""

from __future__ import annotations

from django.utils import timezone
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from .models import BuyerGuidePage, ComponentPage, ConceptPage, WikiPage


@hooks.register("register_admin_menu_item")
def register_wiki_menu_item() -> MenuItem:
    return MenuItem(
        "ویکی",
        "/cms/pages/",
        icon_name="doc-full",
        order=200,
    )


@hooks.register("register_admin_menu_item")
def register_stale_pages_menu_item() -> MenuItem:
    """A direct link to the pages that are past their review date."""
    return MenuItem(
        "صفحات نیازمند بازبینی",
        "/cms/pages/?stale=1",
        icon_name="warning",
        order=201,
    )


@hooks.register("construct_page_action_menu")
def add_entity_link_to_page_menu(items, request, page):
    """Add a shortcut to the entity a page is about."""
    if not isinstance(page, (ComponentPage, ConceptPage, BuyerGuidePage)):
        return items

    entity = page.entity
    if entity is not None:
        items.append(
            (
                "entity",
                format_html(
                    '<a href="/admin/catalog/entity/{}/change/" target="_blank">'
                    "مشاهدهٔ موجودیت «{}» در کاتالوگ</a>",
                    entity.pk,
                    entity.display_title,
                ),
            )
        )
    else:
        items.append(
            (
                "entity",
                format_html(
                    '<a href="/admin/catalog/entity/?q={}">این صفحه به موجودیتی وصل نیست</a>',
                    "—",
                ),
            )
        )
    return items


@hooks.register("before_edit_page")
def warn_about_stale_review_date(request, page):
    """Tell the editor when a page is overdue for review."""
    if isinstance(page, WikiPage) and page.is_stale:
        from django.contrib import messages

        messages.warning(
            request,
            f"این صفحه از {page.review_by:%Y-%m-%d} بازبینی نشده و قدیمی محسوب می‌شود.",
        )


@hooks.register("register_permissions")
def register_editor_permissions():
    """Register the wiki permissions Wagtail offers to the editor groups.

    The default "Editors" group already has the standard Wagtail page
    permissions; these make the *wiki* permission explicit and named.
    """
    from wagtail.permission_policies.base import Permission  # type: ignore[attr-defined]

    return [
        Permission(
            "Can publish wiki pages",
            content=True,
            publish=True,
            locales=["fa", "en"],
        ),
    ]


def stale_pages_queryset():
    """Pages past their review date — used by the menu item and the report."""
    return WikiPage.objects.live().filter(review_by__lt=timezone.now().date())
