"""Write a named placeholder image for every product and wiki page that has none.

The site should not show empty frames while the real, model-matched photos are
still being collected. This command generates one placeholder per slot and names
it so ``import_images`` knows exactly what it stands in for — so the operator can
see which slot is which, drop the real photo in its place, and re-run the import
with ``--force``.

    python manage.py placeholder_images   # write the files into seed_images/
    python manage.py import_images        # attach them

File names (each resolves to exactly one target, thanks to the explicit prefix):

  * ``entity-<slug>.png`` — a part's active products *and* its wiki page (the same
    photo belongs on both, so one file covers both).
  * ``product-<sku>.png`` — a product whose part has no wiki page.
  * ``page-<slug>.png``   — a wiki page with no part (a guide, a concept).

An existing file is kept unless ``--force`` is given, and a slot that already has
a real image is skipped, so running it again never clobbers downloaded photos.
The image itself is generated with Pillow: a dark tile carrying the record's name
(the ASCII slug, which the default font can draw) and the word PLACEHOLDER.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

from apps.catalog.management.commands.import_images import default_source_dir
from apps.catalog.models import Entity
from apps.content.models import WikiPage
from apps.core.console import safe

# --- the tile -----------------------------------------------------------------
TILE = (1200, 800)
BG = (17, 26, 45)  # --color-surface
BORDER = (41, 54, 79)  # --color-border
TEXT = (241, 245, 251)  # --color-foreground
MUTED = (165, 176, 198)  # --color-muted
ACCENT = (52, 121, 255)  # --color-accent


def _font(size: int) -> Any:
    from PIL import ImageFont

    return ImageFont.load_default(size=size)


def _fit_font(text: str, max_width: int, start: int = 72, minimum: int = 26) -> Any:
    """The largest font (starting at ``start``) that keeps ``text`` inside the tile."""
    from PIL import Image, ImageDraw

    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    size = start
    while size > minimum:
        font = _font(size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return _font(minimum)


def _render(path: Path, *, headline: str, subline: str) -> None:
    """Draw one placeholder tile and save it as PNG."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", TILE, BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([2, 2, TILE[0] - 3, TILE[1] - 3], outline=BORDER, width=4)
    draw.rectangle([0, 0, TILE[0], 12], fill=ACCENT)

    tag_font = _font(30)
    tag = "PLACEHOLDER"
    draw.text(
        ((TILE[0] - draw.textlength(tag, font=tag_font)) / 2, 150), tag, font=tag_font, fill=ACCENT
    )

    head_font = _fit_font(headline, TILE[0] - 140)
    draw.text(
        ((TILE[0] - draw.textlength(headline, font=head_font)) / 2, TILE[1] / 2 - 70),
        headline,
        font=head_font,
        fill=TEXT,
    )

    sub_font = _font(34)
    draw.text(
        ((TILE[0] - draw.textlength(subline, font=sub_font)) / 2, TILE[1] / 2 + 40),
        subline,
        font=sub_font,
        fill=MUTED,
    )

    image.save(path, format="PNG")


class Command(BaseCommand):
    help = (
        "Write a named placeholder image into seed_images/ for every product and "
        "wiki page that still has none."
    )

    def write(self, text: str) -> None:
        """Write a line, replacing what the terminal cannot encode (cp1252)."""
        self.stdout.write(safe(text))

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--source",
            default="",
            help="the folder to write (default: backend/seed_images/).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="overwrite a placeholder file that already exists.",
        )

    def handle(self, *args: object, **options: object) -> None:
        source = Path(str(options["source"])) if options.get("source") else default_source_dir()
        force = bool(options.get("force"))
        source.mkdir(parents=True, exist_ok=True)

        slots = self._slots()
        if not slots:
            self.write(
                self.style.SUCCESS("every product and page already has an image; nothing to write.")
            )
            return

        written = kept = 0
        for name, (headline, subline) in sorted(slots.items()):
            path = source / f"{name}.png"
            if path.exists() and not force:
                kept += 1
                continue
            _render(path, headline=headline, subline=subline)
            written += 1
            self.write(self.style.SUCCESS(f"  +  {path.name}"))

        self.write("")
        self.write(
            self.style.SUCCESS(f"{written} placeholders written, {kept} existing files kept.")
        )
        self.write("now run: manage.py import_images")

    def _slots(self) -> dict[str, tuple[str, str]]:
        """The placeholder files to write, as ``{stem: (headline, subline)}``.

        Grouped by entity, so a part's product photo and its wiki hero image stay
        one file; a page with no part (a guide, a concept) gets its own.
        """
        slots: dict[str, tuple[str, str]] = {}
        used_pages: set[int] = set()

        for entity in Entity.objects.order_by("slug"):
            products = [row for row in entity.products.all() if row.is_active and not row.image_id]
            primary = WikiPage.objects.filter(entity=entity).live().first()
            if primary is not None:
                used_pages.add(primary.pk)
            page_needs_one = primary is not None and not primary.hero_image_id
            if products or page_needs_one:
                slots[f"entity-{entity.slug}"] = (str(entity.slug), f"part · {entity.type}")

        for page in WikiPage.objects.live().order_by("slug"):
            if page.pk in used_pages or page.hero_image_id:
                continue
            slots[f"page-{page.slug}"] = (str(page.slug), "wiki page")

        return slots
