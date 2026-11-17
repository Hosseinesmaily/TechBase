"""Image upload: one validated door for the files the editors add.

Wagtail stores the file and produces the renditions; this module only decides
what may become an image in the first place. The rule is deliberately strict:

* the size is checked against a single limit (``WAGTAILIMAGES_MAX_UPLOAD_SIZE``
  is set from the same constant), and
* the *content* is verified with Pillow — a text file renamed to ``.png`` is
  refused, because the extension is never trusted,
* only JPEG, PNG and WebP are accepted; SVG is not (it can carry script).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

#: 5 MB — a product photo or an article illustration, not a print master.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(uploaded_file: Any) -> None:
    """Raise ``ValidationError`` unless this upload is an allowed image.

    The checks run in a fixed order (size, extension, real content) so the
    message a user sees names the first thing that is wrong.
    """
    if uploaded_file is None:
        raise ValidationError("فایلی برای بارگذاری انتخاب نشده است.")

    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size <= 0:
        raise ValidationError("فایل خالی است.")
    if size > MAX_UPLOAD_BYTES:
        megabytes = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValidationError(f"حجم تصویر باید کمتر از {megabytes} مگابایت باشد.")

    name = str(getattr(uploaded_file, "name", "")).lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise ValidationError("فقط تصویرهای JPEG، PNG و WebP پذیرفته میشوند.")

    # The extension is a claim; the content is the fact. Pillow parses the real
    # header, so a renamed file fails here.
    from PIL import Image

    position = None
    if hasattr(uploaded_file, "tell") and hasattr(uploaded_file, "seek"):
        position = uploaded_file.tell()
    try:
        image = Image.open(uploaded_file, formats=tuple(ALLOWED_FORMATS))
        image_format = (image.format or "").upper()
        if image_format and image_format not in ALLOWED_FORMATS:
            raise ValidationError("قالب تصویر پشتیبانی نمیشود؛ JPEG، PNG یا WebP بفرستید.")
        image.verify()
    except ValidationError:
        raise
    except Exception as exc:  # Pillow raises its own error types
        raise ValidationError("فایل ارسالشده یک تصویر معتبر نیست.") from exc
    finally:
        if position is not None:
            uploaded_file.seek(position)
