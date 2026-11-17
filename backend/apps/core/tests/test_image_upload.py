"""The image upload: what is accepted, what is refused, and who may upload.

The rule under test is that the *content* decides — a text file renamed to ``.png``
is not an image — and that the endpoint is staff-only, because it writes files and
can attach them to a wiki page or a product.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient
from wagtail.images.models import Image

from apps.catalog.models import Entity, EntityStatus, EntityType, Product
from apps.core.images import validate_image_upload

pytestmark = pytest.mark.django_db

PASSWORD = "Test-Password-8291!"


@pytest.fixture(autouse=True)
def temporary_media(settings, tmp_path):
    """Keep the uploaded files out of the repository during the tests."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def make_user(email: str, *, staff: bool = False):
    return get_user_model().objects.create_user(
        username=email, email=email, password=PASSWORD, is_staff=staff
    )


@pytest.fixture
def staff_client():
    client = APIClient()
    client.force_login(make_user("editor@example.com", staff=True))
    return client


@pytest.fixture
def customer_client():
    client = APIClient()
    client.force_login(make_user("customer@example.com"))
    return client


@pytest.fixture
def product():
    entity = Entity.objects.create(
        type=EntityType.GPU,
        slug="upload-gpu",
        title="Upload GPU",
        title_fa="کارت گرافیک بارگذاری",
        status=EntityStatus.PUBLISHED,
    )
    return Product.objects.create(sku="upload-gpu-sku", entity=entity, title="Upload GPU")


def png_file(name: str = "photo.png") -> SimpleUploadedFile:
    """A real (tiny) PNG, built with Pillow so the header is genuine."""
    buffer = BytesIO()
    from PIL import Image as PilImage

    PilImage.new("RGB", (32, 32), (18, 26, 49)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class TestUploadPermissions:
    def test_only_staff_may_upload(self, customer_client):
        anonymous = APIClient()
        assert anonymous.post(reverse("core:image-upload"), {"file": png_file()}).status_code == 403
        assert (
            customer_client.post(reverse("core:image-upload"), {"file": png_file()}).status_code
            == 403
        )
        assert Image.objects.count() == 0

    def test_a_valid_png_is_stored_with_its_rendition(self, staff_client):
        response = staff_client.post(
            reverse("core:image-upload"), {"file": png_file(), "title": "کارت گرافیک"}
        )

        assert response.status_code == 201
        assert response.data["thumbnail"]
        assert response.data["attached_to"] == ""
        image = Image.objects.get(pk=response.data["id"])
        assert image.title == "کارت گرافیک"
        # The dimensions were filled in by Wagtail's own form, so renditions work.
        assert image.width == 32 and image.height == 32


class TestUploadValidation:
    def test_a_renamed_text_file_is_refused(self, staff_client):
        fake = SimpleUploadedFile(
            "photo.png", b"this is definitely not an image", content_type="image/png"
        )
        response = staff_client.post(reverse("core:image-upload"), {"file": fake})

        assert response.status_code == 400
        assert "تصویر معتبر" in response.data["error"]
        assert Image.objects.count() == 0

    def test_an_unsupported_extension_is_refused(self, staff_client):
        svg = SimpleUploadedFile(
            "drawing.svg",
            b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            content_type="image/svg+xml",
        )
        response = staff_client.post(reverse("core:image-upload"), {"file": svg})

        assert response.status_code == 400
        assert "JPEG" in response.data["error"]
        assert Image.objects.count() == 0

    def test_an_oversized_file_is_refused(self, staff_client, monkeypatch):
        # The limit is read from one constant, so it can be lowered for the test
        # instead of building a five-megabyte file.
        monkeypatch.setattr("apps.core.images.MAX_UPLOAD_BYTES", 16)
        response = staff_client.post(reverse("core:image-upload"), {"file": png_file()})

        assert response.status_code == 400
        assert "مگابایت" in response.data["error"]
        assert Image.objects.count() == 0

    def test_a_missing_file_is_refused(self, staff_client):
        response = staff_client.post(reverse("core:image-upload"), {})

        assert response.status_code == 400
        assert response.data["error"]

    def test_the_validator_rejects_an_empty_upload(self):
        with pytest.raises(ValidationError):
            validate_image_upload(None)
        with pytest.raises(ValidationError):
            validate_image_upload(SimpleUploadedFile("empty.png", b""))


class TestUploadAttachment:
    def test_the_image_can_be_attached_to_a_product(self, staff_client, product):
        response = staff_client.post(
            reverse("core:image-upload"), {"file": png_file(), "sku": product.sku}
        )

        assert response.status_code == 201
        assert product.sku in response.data["attached_to"]
        product.refresh_from_db()
        assert product.image_id == response.data["id"]

        listing = APIClient().get("/api/v1/catalog/products/")
        row = next(item for item in listing.data["results"] if item["sku"] == product.sku)
        assert row["image_thumbnail"]  # the card gets a rendition
        assert row["image_full"]

    def test_the_image_can_be_attached_to_a_wiki_page(self, staff_client):
        from wagtail.models import Page

        from apps.content.models import ConceptPage

        root = Page.objects.filter(depth=1).first()
        page = ConceptPage(title="مقالهٔ آزمایشی تصویر", slug="upload-attach-test", summary="خلاصه")
        root.add_child(instance=page)
        page.save_revision().publish()

        response = staff_client.post(
            reverse("core:image-upload"), {"file": png_file(), "page": str(page.pk)}
        )

        assert response.status_code == 201
        page.refresh_from_db()
        assert page.hero_image_id == response.data["id"]

        detail = APIClient().get(f"/api/v1/wiki/pages/{page.slug}/")
        assert detail.status_code == 200
        assert detail.data["hero_image"]
        assert detail.data["hero_thumbnail"]

    def test_attaching_to_an_unknown_record_fails_without_losing_the_image(self, staff_client):
        response = staff_client.post(
            reverse("core:image-upload"), {"file": png_file(), "sku": "no-such-sku"}
        )

        assert response.status_code == 404
        assert "پیدا نشد" in response.data["error"]
        # The upload itself succeeded, so the editor does not have to send it again.
        assert Image.objects.count() == 1

    def test_an_upload_without_a_target_is_just_stored(self, staff_client):
        response = staff_client.post(reverse("core:image-upload"), {"file": png_file()})

        assert response.status_code == 201
        assert Image.objects.count() == 1
