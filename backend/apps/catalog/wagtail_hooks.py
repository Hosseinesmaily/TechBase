"""Wagtail admin integration for the catalog: the product snippet.

A product is editable in the Wagtail admin as a snippet for one concrete reason:
the **image chooser**. Wagtail's chooser is the upload path the project already
has — it validates the file, records its dimensions and produces renditions — so
products get upload / replace / remove without a second upload system of our own.
The Django admin keeps its own ProductAdmin for price and stock work.
"""

from __future__ import annotations

from wagtail.admin.panels import FieldPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Product


class ProductSnippetViewSet(SnippetViewSet):
    """Products in the Wagtail admin, with the image chooser on the form."""

    model = Product
    menu_label = "محصولات"
    menu_icon = "cube"
    list_display = ("sku", "title", "price", "stock", "is_active", "updated_at")
    list_filter = ("is_active", "source")
    search_fields = ("sku", "title", "title_fa")
    ordering = ("-updated_at",)
    panels = [
        FieldPanel("sku"),
        FieldPanel("entity"),
        FieldPanel("title"),
        FieldPanel("title_fa"),
        FieldPanel("image"),
        FieldPanel("image_url"),
        FieldPanel("price"),
        FieldPanel("currency"),
        FieldPanel("stock"),
        FieldPanel("warranty_months"),
        FieldPanel("source"),
        FieldPanel("is_active"),
    ]


register_snippet(ProductSnippetViewSet)
