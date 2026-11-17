"""The seed_images drop folder → catalog importer.

The rule under test: a photo is attached only to the record its *file name* names,
and a file that matches nothing (or is not a real image) is reported rather than
attached to the wrong product. Nothing is invented.
"""

from __future__ import annotations

from io import BytesIO, StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from wagtail.images.models import Image
from wagtail.models import Page

from apps.catalog.models import Entity, EntityStatus, EntityType, Product
from apps.content.models import ConceptPage

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def temporary_media(tmp_path, settings):
    """Keep the stored image files out of the repository during the tests."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def png_bytes() -> bytes:
    """A real (tiny) PNG, built with Pillow so the header is genuine."""
    from PIL import Image as PilImage

    buffer = BytesIO()
    PilImage.new("RGB", (32, 32), (18, 26, 49)).save(buffer, format="PNG")
    return buffer.getvalue()


def make_product(slug: str, sku: str) -> Product:
    entity = Entity.objects.create(
        type=EntityType.GPU, slug=slug, title=slug, status=EntityStatus.PUBLISHED
    )
    return Product.objects.create(sku=sku, entity=entity, title=slug, price="100")


def add_page(slug: str, entity: Entity) -> ConceptPage:
    root = Page.objects.filter(depth=1).first()
    page = ConceptPage(title=f"article {slug}", slug=slug, entity=entity)
    root.add_child(instance=page)
    page.save_revision().publish()
    return page


def run(source: Path, **options: object) -> str:
    out = StringIO()
    call_command("import_images", source=str(source), stdout=out, **options)
    return out.getvalue()


class TestMatchBySku:
    def test_a_file_named_after_the_sku_attaches_to_the_product(self, tmp_path):
        product = make_product("flash-gpu", "flash-gpu-sku")
        src = tmp_path / "src"
        src.mkdir()
        (src / "flash-gpu-sku.png").write_bytes(png_bytes())

        run(src)

        product.refresh_from_db()
        assert product.image_id is not None
        assert Image.objects.count() == 1

    def test_a_prefixed_name_also_matches(self, tmp_path):
        product = make_product("flash-prefixed", "flash-prefixed-sku")
        src = tmp_path / "src"
        src.mkdir()
        (src / "product-flash-prefixed-sku.png").write_bytes(png_bytes())

        run(src)

        product.refresh_from_db()
        assert product.image_id is not None


class TestMatchByEntitySlug:
    def test_an_entity_slug_attaches_to_the_product_and_the_page(self, tmp_path):
        product = make_product("flash-entity", "flash-entity-sku")
        page = add_page("flash-entity", product.entity)
        src = tmp_path / "src"
        src.mkdir()
        (src / "flash-entity.png").write_bytes(png_bytes())

        run(src)

        product.refresh_from_db()
        page.refresh_from_db()
        assert product.image_id is not None
        assert page.hero_image_id is not None

    def test_the_target_flag_can_limit_it_to_the_product(self, tmp_path):
        product = make_product("flash-target", "flash-target-sku")
        page = add_page("flash-target", product.entity)
        src = tmp_path / "src"
        src.mkdir()
        (src / "flash-target.png").write_bytes(png_bytes())

        run(src, target="product")

        product.refresh_from_db()
        page.refresh_from_db()
        assert product.image_id is not None
        assert page.hero_image_id is None


class TestMatchByPageSlug:
    def test_a_page_slug_attaches_to_the_page(self, tmp_path):
        product = make_product("flash-page", "flash-page-sku")
        page = add_page("flash-page-article", product.entity)
        src = tmp_path / "src"
        src.mkdir()
        (src / "flash-page-article.png").write_bytes(png_bytes())

        run(src)

        page.refresh_from_db()
        product.refresh_from_db()
        assert page.hero_image_id is not None
        assert product.image_id is None

    def test_a_page_prefix_targets_only_the_page(self, tmp_path):
        """``page-<slug>`` never falls through to an entity of the same name."""
        product = make_product("flash-prefixpage", "flash-prefixpage-sku")
        page = add_page("flash-prefixpage", product.entity)
        src = tmp_path / "src"
        src.mkdir()
        (src / "page-flash-prefixpage.png").write_bytes(png_bytes())

        run(src)

        page.refresh_from_db()
        product.refresh_from_db()
        assert page.hero_image_id is not None
        assert product.image_id is None


class TestSafety:
    def test_an_unmatched_file_is_reported_and_attaches_nothing(self, tmp_path):
        make_product("flash-safe", "flash-safe-sku")
        src = tmp_path / "src"
        src.mkdir()
        (src / "nothing-like-this.png").write_bytes(png_bytes())

        output = run(src)

        assert Image.objects.count() == 0
        assert "nothing matches" in output

    def test_a_renamed_text_file_is_refused(self, tmp_path):
        product = make_product("flash-fake", "flash-fake-sku")
        src = tmp_path / "src"
        src.mkdir()
        (src / "flash-fake-sku.png").write_text("this is not an image")

        run(src)

        product.refresh_from_db()
        assert product.image_id is None
        assert Image.objects.count() == 0

    def test_a_dry_run_writes_nothing(self, tmp_path):
        product = make_product("flash-dry", "flash-dry-sku")
        src = tmp_path / "src"
        src.mkdir()
        (src / "flash-dry-sku.png").write_bytes(png_bytes())

        output = run(src, dry_run=True)

        product.refresh_from_db()
        assert product.image_id is None
        assert Image.objects.count() == 0
        assert "dry run" in output

    def test_an_existing_image_is_kept_unless_forced(self, tmp_path):
        product = make_product("flash-keep", "flash-keep-sku")
        src = tmp_path / "src"
        src.mkdir()
        (src / "flash-keep-sku.png").write_bytes(png_bytes())

        run(src)
        product.refresh_from_db()
        first_image = product.image_id
        assert first_image is not None

        run(src)  # without --force nothing changes
        product.refresh_from_db()
        assert product.image_id == first_image
        assert Image.objects.count() == 1

        run(src, force=True)  # --force replaces it
        product.refresh_from_db()
        assert product.image_id != first_image
        assert Image.objects.count() == 2


class TestPlaceholders:
    def test_it_writes_one_named_file_and_links_it(self, tmp_path):
        """A part with a product and a page gets a single ``entity-`` file."""
        product = make_product("flash-ph", "flash-ph-sku")
        page = add_page("flash-ph", product.entity)
        src = tmp_path / "src"

        call_command("placeholder_images", source=str(src), stdout=StringIO())

        assert sorted(path.name for path in src.glob("*.png")) == ["entity-flash-ph.png"]

        call_command("import_images", source=str(src), stdout=StringIO())

        product.refresh_from_db()
        page.refresh_from_db()
        assert product.image_id is not None
        assert page.hero_image_id is not None

    def test_a_page_with_no_part_gets_a_page_file(self, tmp_path):
        root = Page.objects.filter(depth=1).first()
        page = ConceptPage(title="concept", slug="flash-concept")
        root.add_child(instance=page)
        page.save_revision().publish()
        src = tmp_path / "src"

        call_command("placeholder_images", source=str(src), stdout=StringIO())

        assert (src / "page-flash-concept.png").exists()

    def test_it_keeps_an_existing_file_unless_forced(self, tmp_path):
        make_product("flash-keepfile", "flash-keepfile-sku")
        src = tmp_path / "src"
        src.mkdir()
        existing = src / "entity-flash-keepfile.png"
        existing.write_bytes(b"the operator's own file")

        call_command("placeholder_images", source=str(src), stdout=StringIO())
        assert existing.read_bytes() == b"the operator's own file"

        call_command("placeholder_images", source=str(src), force=True, stdout=StringIO())
        assert existing.read_bytes() != b"the operator's own file"
