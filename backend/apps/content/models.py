"""Wagtail page types for the editorial wiki.

Three page types, per the spec:
  * `ComponentPage` — a page about one component (a CPU, a GPU). Bound to an
    `Entity`, so the catalog and the wiki share one identity.
  * `BuyerGuidePage` — a "best X for Y" guide. May list many products.
  * `ConceptPage` — a topic explained (DDR5, ray tracing, PSU sizing).

Every page carries:
  * a Persian title and slug,
  * `review_by` — the date the content goes stale (the spec's stale-content
    tracking),
  * an optional bound `Entity`.

Content is editor-controlled: the public site reads published pages only.
"""

from __future__ import annotations

from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page

from apps.catalog.models import Entity

from .blocks import BodyBlock


class WikiPage(Page):
    """Base class for every wiki page.

    Kept concrete (not abstract) so a generic "article" type exists and
    generic queries can rely on it.
    """

    #: The catalog entity this page is about (null for standalone guides).
    entity = models.ForeignKey(
        Entity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiki_pages",
        help_text="اگر این صفحه دربارهٔ یک قطعه است، موجودیت مرتبط را انتخاب کنید.",
    )
    summary = models.TextField(blank=True, help_text="خلاصهٔ یک تا دو جمله‌ای.")
    review_by = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="تاریخ بازبینی محتوا — پس از این تاریخ محتوا قدیمی تلقی می‌شود.",
    )
    #: Tags for the "related pages" rail and for the editorial backlog.
    tags = models.JSONField(default=list, blank=True, help_text="برچسب‌ها به‌صورت فهرست JSON.")

    content_panels = [
        *Page.content_panels,
        FieldPanel("entity"),
        FieldPanel("summary"),
        FieldPanel("review_by"),
        FieldPanel("tags"),
    ]

    class Meta:
        verbose_name = "صفحهٔ ویکی"
        verbose_name_plural = "صفحات ویکی"

    def __str__(self) -> str:
        return self.title

    @property
    def is_stale(self) -> bool:
        """True when the page is past its review date."""
        if self.review_by is None:
            return False
        from django.utils import timezone

        return self.review_by < timezone.now().date()

    @property
    def language(self) -> str:
        """The page's language — Persian first, English secondary."""
        return "en" if self.slug.startswith("en/") else "fa"


class ComponentPage(WikiPage):
    """A page about a single component in the catalog."""

    body = StreamField(BodyBlock(), blank=True, verbose_name="محتوا")

    content_panels = [*WikiPage.content_panels, FieldPanel("body")]

    class Meta:
        verbose_name = "صفحهٔ قطعه"
        verbose_name_plural = "صفحات قطعات"


class BuyerGuidePage(WikiPage):
    """A buying guide: "the best gaming PCs for 1080p high-FPS"."""

    body = StreamField(BodyBlock(), blank=True, verbose_name="محتوا")
    #: Products this guide recommends, in the editor's order.
    recommended_products = models.ManyToManyField(
        "catalog.Product",
        blank=True,
        related_name="buyer_guides",
        help_text="محصولات پیشنهادی این راهنما به ترتیب اولویت.",
    )
    #: The use case the guide targets, e.g. "1080p high-FPS gaming".
    use_case = models.CharField(max_length=120, blank=True, help_text="کاربرد هدف.")
    resolution = models.CharField(max_length=16, blank=True, help_text="رزولوشن هدف.")
    budget_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, help_text="حداکثر بودجه (تومان)."
    )

    content_panels = [
        *WikiPage.content_panels,
        FieldPanel("use_case"),
        FieldPanel("resolution"),
        FieldPanel("budget_max"),
        FieldPanel("recommended_products", widget=None),
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "راهنمای خرید"
        verbose_name_plural = "راهنماهای خرید"


class ConceptPage(WikiPage):
    """A concept explained: DDR5, ray tracing, PSU sizing."""

    body = StreamField(BodyBlock(), blank=True, verbose_name="محتوا")

    content_panels = [*WikiPage.content_panels, FieldPanel("body")]

    class Meta:
        verbose_name = "صفحهٔ مفهوم"
        verbose_name_plural = "صفحات مفاهیم"
