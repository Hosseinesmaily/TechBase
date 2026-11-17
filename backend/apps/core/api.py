"""Staff-only utilities for the panel.

Today that is one thing: the validated image upload. The file itself is stored by
Wagtail (which owns validation, dimensions and renditions); this endpoint decides
what may become an image at all, with the checks in `apps/core/images.py`.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .images import validate_image_upload


class ImageUploadView(APIView):
    """`POST /api/v1/admin/images/` — upload one image (staff only).

    Multipart body: ``file`` is the image; ``page`` (a wiki page id) or ``sku`` (a
    product) optionally attaches it to that record in the same request, so the
    panel does not need a second call.

    Everything is checked on the server: the size, the real file type (Pillow, so
    a renamed file fails) and the staff permission.
    """

    permission_classes = [IsAdminUser]

    def post(self, request) -> Response:
        uploaded = request.FILES.get("file")
        try:
            validate_image_upload(uploaded)
        except ValidationError as exc:
            return Response({"error": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        title = str(request.data.get("title", "")).strip() or str(uploaded.name)[:250]

        from wagtail.images.forms import get_image_form
        from wagtail.images.models import Image

        # Wagtail's own form is used on purpose: it fills width, height and the
        # file size, which a bare `Image.objects.create` would leave empty and
        # which the renditions need.
        form = get_image_form(Image)({"title": title}, {"file": uploaded})
        if not form.is_valid():
            message = " ".join(str(error) for errors in form.errors.values() for error in errors)
            return Response(
                {"error": message or "بارگذاری تصویر انجام نشد."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        image = form.save()

        attached_to = ""
        try:
            attached_to = self._attach(request, image)
        except ValidationError as exc:
            # The image is stored either way; only the attachment failed.
            return Response(
                {
                    "error": " ".join(exc.messages),
                    "id": image.pk,
                    "url": image.file.url if image.file else "",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "id": image.pk,
                "title": image.title,
                "url": image.file.url if image.file else "",
                "thumbnail": image.get_rendition("max-400x300").url,
                "attached_to": attached_to,
            },
            status=status.HTTP_201_CREATED,
        )

    def _attach(self, request, image) -> str:
        """Attach the new image to a wiki page or a product, when one was named."""
        page_id = str(request.data.get("page", "")).strip()
        sku = str(request.data.get("sku", "")).strip()
        if not page_id and not sku:
            return ""

        if page_id:
            from apps.content.models import WikiPage

            page = WikiPage.objects.filter(pk=page_id).first() if page_id.isdigit() else None
            if page is None:
                raise ValidationError("صفحهٔ ویکی موردنظر پیدا نشد.")
            # The revision must be taken from the concrete page type, so the change
            # reaches the published revision the site serves.
            specific = page.specific
            specific.hero_image = image
            specific.save_revision().publish()
            return f"صفحهٔ «{page.title}»"

        from apps.catalog.models import Product

        product = Product.objects.filter(sku=sku).first()
        if product is None:
            raise ValidationError("محصولی با این شناسه پیدا نشد.")
        product.image = image
        product.save(update_fields=["image", "updated_at"])
        return f"محصول {product.sku}"
