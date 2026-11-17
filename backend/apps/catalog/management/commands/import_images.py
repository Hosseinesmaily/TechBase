"""Import the photos an operator saved in ``backend/seed_images/``.

The panel already has an upload endpoint and Wagtail has an image chooser, but
adding a few dozen product photos one dialog at a time is slow. This command is
the opposite workflow: the operator downloads the *real, model-matched* photos,
saves each one under the name of the SKU (or the entity / page slug) it belongs
to, and runs one command.

Nothing is invented and nothing is guessed. A file whose name matches no product,
entity or page is reported and left alone — one model's photo is never attached
to another. The accepted files are the same ones the panel accepts (JPEG, PNG,
WebP, at most 5 MB), verified with Pillow so a renamed text file fails.

The name says what the photo is: ``<sku>`` → the product, ``<entity-slug>`` → the
entity's products *and* its wiki page, ``<page-slug>`` → the page. A leading
``product-`` / ``sku-`` / ``entity-`` / ``page-`` / ``wiki-`` forces one of those
explicitly, which is how ``manage.py placeholder_images`` names its files.

    python manage.py image_audit --names     # what to download, and what to call it
    python manage.py import_images --dry-run # preview the matching
    python manage.py import_images           # attach
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Entity, Product
from apps.content.models import WikiPage
from apps.core.console import safe
from apps.core.images import ALLOWED_EXTENSIONS, validate_image_upload

#: Explicit prefixes: the operator can say *what* a file targets. A bare name is
#: auto-detected (SKU → entity → page).
PREFIX_TARGETS = {
    "product-": "product",
    "sku-": "product",
    "entity-": "entity",
    "page-": "page",
    "wiki-": "page",
}
#: Files that live in the folder but are not photos.
SKIP_NAMES = {"readme.md", ".gitkeep", ".gitignore", "readme.txt"}


def default_source_dir() -> Path:
    """The default drop zone: ``backend/seed_images/``."""
    return Path(settings.BASE_DIR) / "seed_images"


def _parse_name(path: Path) -> tuple[str, str]:
    """The (target hint, matching key) of a file. The hint is "" when auto."""
    stem = path.stem.lower()
    for prefix, target in PREFIX_TARGETS.items():
        if stem.startswith(prefix):
            return target, stem[len(prefix) :]
    return "", stem


def _store_image(path: Path, title: str):
    """Validate a file and store it as a Wagtail image (the panel's own path)."""
    from wagtail.images.forms import get_image_form
    from wagtail.images.models import Image

    with path.open("rb") as handle:
        django_file = File(handle, name=path.name)
        validate_image_upload(django_file)
        # Wagtail's form fills width, height and the file size, which a bare
        # `Image.objects.create` would leave empty and which renditions need.
        form = get_image_form(Image)({"title": title[:250]}, {"file": django_file})
        if not form.is_valid():
            message = " ".join(str(error) for errors in form.errors.values() for error in errors)
            raise ValidationError(message or "بارگذاری تصویر انجام نشد.")
        return form.save()


class Command(BaseCommand):
    help = (
        "Attach the images in backend/seed_images/ to the products and wiki pages "
        "whose SKU, entity slug or page slug matches the file name."
    )

    def write(self, text: str) -> None:
        """Write a line, replacing what the terminal cannot encode (cp1252)."""
        self.stdout.write(safe(text))

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--source",
            default="",
            help="the folder to read (default: backend/seed_images/).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="only report what would be attached; write nothing.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="replace an image that is already set (a photo is never overwritten otherwise).",
        )
        parser.add_argument(
            "--target",
            choices=["auto", "product", "page"],
            default="auto",
            help=(
                "what an *entity-slug* match attaches to: 'product', 'page', or "
                "'auto' for both (default). A SKU always targets the product and a "
                "page slug always targets the page."
            ),
        )

    def handle(self, *args: object, **options: object) -> None:
        source = Path(str(options["source"])) if options.get("source") else default_source_dir()
        if not source.is_dir():
            raise CommandError(
                f"folder not found: {source}\n"
                "put the photos in backend/seed_images/ or point --source at one."
            )

        dry_run = bool(options.get("dry_run"))
        force = bool(options.get("force"))
        target = str(options.get("target") or "auto")

        files = [
            path
            for path in sorted(source.iterdir())
            if path.is_file() and path.name.lower() not in SKIP_NAMES
        ]
        if not files:
            self.write(
                self.style.WARNING(
                    f"no images in {source}; run 'manage.py placeholder_images' to create them."
                )
            )
            return

        products_by_sku = {
            product.sku.lower(): product for product in Product.objects.select_related("entity")
        }
        entities_by_slug = {entity.slug.lower(): entity for entity in Entity.objects.all()}
        pages_by_slug = {page.slug.lower(): page for page in WikiPage.objects.all()}

        stored = attached = unmatched = failed = 0
        for path in files:
            extension = path.suffix.lower()
            if extension not in ALLOWED_EXTENSIONS:
                self.write(
                    self.style.WARNING(
                        f"[!!] {path.name} - not an allowed extension (jpg / jpeg / png / webp)."
                    )
                )
                unmatched += 1
                continue

            hint, key = _parse_name(path)
            targets = self._resolve(
                hint, key, products_by_sku, entities_by_slug, pages_by_slug, target
            )
            if not targets:
                self.write(
                    self.style.WARNING(f"[??] {path.name} - nothing matches the name '{key}'.")
                )
                unmatched += 1
                continue

            # Only the records that still need an image, unless --force replaces one.
            if force:
                pending = list(targets)
            else:
                pending = [
                    (kind, record)
                    for kind, record in targets
                    if (kind == "page" and not record.hero_image_id)  # type: ignore[attr-defined]
                    or (kind == "product" and not record.image_id)  # type: ignore[attr-defined]
                ]
            if not pending:
                self.write(
                    f"[= ] {path.name} -> {self._describe(targets)} "
                    "(already has an image; use --force to replace)"
                )
                continue

            if dry_run:
                self.write(
                    self.style.SUCCESS(f"[ok] {path.name} -> {self._describe(pending)} (dry run)")
                )
                attached += len(pending)
                continue

            try:
                image = _store_image(path, path.stem)
            except ValidationError as exc:
                self.write(self.style.ERROR(f"[!!] {path.name} - {' '.join(exc.messages)}"))
                failed += 1
                continue
            stored += 1

            for kind, record in pending:
                try:
                    if kind == "product":
                        record.image = image  # type: ignore[attr-defined]
                        record.save(update_fields=["image", "updated_at"])  # type: ignore[attr-defined]
                    else:
                        specific = record.specific  # type: ignore[attr-defined]
                        specific.hero_image = image
                        specific.save_revision().publish()
                    attached += 1
                except Exception as exc:  # a single bad record must not stop the batch
                    self.write(self.style.ERROR(f"[!!] {path.name} - attach failed: {exc}"))
                    failed += 1

            self.write(self.style.SUCCESS(f"[ok] {path.name} -> {self._describe(pending)}"))

        prefix = "dry run (nothing written): " if dry_run else ""
        self.write("")
        self.write(
            self.style.SUCCESS(
                f"{prefix}{len(files)} files - attached {attached}, stored {stored}, "
                f"unmatched {unmatched}, failed {failed}"
            )
        )
        if unmatched:
            self.write("for the exact file names run: manage.py image_audit --names")

    def _resolve(
        self,
        hint: str,
        key: str,
        products_by_sku: dict[str, Product],
        entities_by_slug: dict[str, Entity],
        pages_by_slug: dict[str, WikiPage],
        target: str,
    ) -> list[tuple[str, object]]:
        """The records a file name refers to.

        An explicit prefix (``hint``) fixes the kind; a bare name is auto-detected,
        most specific first (a SKU → an entity → a page).
        """
        if hint == "product":
            product = products_by_sku.get(key)
            return [("product", product)] if product is not None else []
        if hint == "page":
            page = pages_by_slug.get(key)
            return [("page", page)] if page is not None else []
        if hint == "entity":
            return self._entity_targets(key, entities_by_slug, target)

        product = products_by_sku.get(key)
        if product is not None:
            return [("product", product)]
        entity_matches = self._entity_targets(key, entities_by_slug, target)
        if entity_matches:
            return entity_matches
        page = pages_by_slug.get(key)
        if page is not None:
            return [("page", page)]
        return []

    @staticmethod
    def _entity_targets(
        key: str, entities_by_slug: dict[str, Entity], target: str
    ) -> list[tuple[str, object]]:
        """An entity's active products and its live wiki page (per ``target``)."""
        entity = entities_by_slug.get(key)
        if entity is None:
            return []
        matches: list[tuple[str, object]] = []
        if target in ("auto", "product"):
            matches.extend(("product", row) for row in entity.products.all() if row.is_active)
        if target in ("auto", "page"):
            page = WikiPage.objects.filter(entity=entity).live().first()
            if page is not None:
                matches.append(("page", page))
        return matches

    @staticmethod
    def _describe(targets: list[tuple[str, object]]) -> str:
        """A short, Persian label of what a file was attached to."""
        labels: list[str] = []
        for kind, record in targets:
            if kind == "product":
                labels.append(f"product {getattr(record, 'sku', '?')}")
            else:
                labels.append(f"page {getattr(record, 'slug', '?')}")
        return "، ".join(labels)
