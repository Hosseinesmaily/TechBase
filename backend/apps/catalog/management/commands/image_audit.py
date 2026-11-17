"""Audit media coverage: which parts and wiki pages still have no image.

Nothing is invented here. The command reports exactly what is missing so a real,
model-matched photo can be added through the existing panel (`/admin-panel`
upload or Wagtail's image chooser) or through the drop-folder workflow
(`backend/seed_images/` + `manage.py import_images`). It never copies one model's
picture onto another, and it never writes a placeholder as if it were the product
photo.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.content.models import WikiPage
from apps.core.console import safe


class Command(BaseCommand):
    help = "Report the products and wiki pages that still lack an image."

    def write(self, text: str) -> None:
        """Write a line, replacing what the terminal cannot encode (cp1252)."""
        self.stdout.write(safe(text))

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--names",
            action="store_true",
            help="print the file name to save in backend/seed_images/ for each missing image.",
        )

    def handle(self, *args: object, **options: object) -> None:
        show_names = bool(options.get("names"))
        products = list(Product.objects.select_related("entity").order_by("entity__type", "sku"))
        missing_products = [product for product in products if not product.image_id]
        pages = list(WikiPage.objects.live().select_related("entity"))
        missing_pages = [page for page in pages if not page.hero_image_id]

        self.write(
            self.style.SUCCESS(
                f"products: {len(products)} - without image: {len(missing_products)} | "
                f"live wiki pages: {len(pages)} - without image: {len(missing_pages)}"
            )
        )

        if show_names:
            self.write(
                "\nsave each photo in backend/seed_images/ with one of these names "
                "(jpg / png / webp), then run: manage.py import_images"
            )

        if missing_products:
            self.write("\nproducts still needing a model-accurate image:")
            for product in missing_products:
                if show_names:
                    self.write(f"  product-{product.sku}.png")
                else:
                    self.write(f"  product-{product.sku:<28} {product.entity.type}")

        if missing_pages:
            self.write("\nwiki pages still needing an image:")
            for page in missing_pages:
                if show_names:
                    self.write(f"  page-{page.slug}.png")
                else:
                    self.write(f"  page-{page.slug}")

        if not missing_products and not missing_pages:
            self.write(self.style.SUCCESS("every product and page has an image."))
