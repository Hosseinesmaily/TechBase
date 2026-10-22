"""StreamField blocks for wiki page bodies.

The body is a *structured* document, not free HTML, so that:
  * headings can be indexed for heading-based chunking (Phase 4),
  * the auto-linker knows the section a mention occurred in,
  * the renderer can produce a table of contents and anchor ids.

Blocks are deliberately small and boring: a heading, paragraphs, a list, a
quote, a spec table, a callout and an image.
"""

from __future__ import annotations

from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class HeadingBlock(blocks.StructBlock):
    """A section heading. Its text becomes part of the section path."""

    level = blocks.ChoiceBlock(
        choices=[
            ("h2", "عنوان اصلی (h2)"),
            ("h3", "زیرعنوان (h3)"),
            ("h4", "زیرعنوان (h4)"),
        ],
        default="h2",
        label="سطح",
    )
    text = blocks.CharBlock(max_length=200, label="متن عنوان")

    class Meta:
        icon = "title"
        label = "عنوان"
        template = "content/blocks/heading.html"


class ParagraphBlock(blocks.TextBlock):
    class Meta:
        icon = "pilcrow"
        label = "پاراگراف"


class RichTextBlock(blocks.RichTextBlock):
    class Meta:
        icon = "doc-full"
        label = "متن غنی"


class ListBlock(blocks.StructBlock):
    """A bullet or numbered list."""

    style = blocks.ChoiceBlock(
        choices=[("ul", "فهرست نقطه‌ای"), ("ol", "فهرست شماره‌دار")],
        default="ul",
        label="سبک",
    )
    items = blocks.ListBlock(blocks.CharBlock(max_length=300), label="موارد")

    class Meta:
        icon = "list-ul"
        label = "فهرست"
        template = "content/blocks/list.html"


class QuoteBlock(blocks.StructBlock):
    text = blocks.TextBlock(label="نقل‌قول")
    source = blocks.CharBlock(max_length=200, required=False, label="منبع")

    class Meta:
        icon = "openquote"
        label = "نقل‌قول"
        template = "content/blocks/quote.html"


class CalloutBlock(blocks.StructBlock):
    """A highlighted note — the wiki's equivalent of an aside."""

    kind = blocks.ChoiceBlock(
        choices=[
            ("info", "اطلاع"),
            ("warning", "هشدار"),
            ("tip", "نکته"),
            ("danger", "خطر"),
        ],
        default="info",
        label="نوع",
    )
    title = blocks.CharBlock(max_length=200, required=False, label="عنوان")
    text = blocks.TextBlock(label="متن")

    class Meta:
        icon = "help"
        label = "کادر توضیح"
        template = "content/blocks/callout.html"


class SpecTableBlock(blocks.StructBlock):
    """A key/value spec table, e.g. socket, TDP, memory type."""

    title = blocks.CharBlock(max_length=200, required=False, label="عنوان جدول")
    rows = blocks.ListBlock(
        blocks.StructBlock(
            [
                ("label", blocks.CharBlock(max_length=120, label="مشخصه")),
                ("value", blocks.CharBlock(max_length=300, label="مقدار")),
            ]
        ),
        label="ردیف‌ها",
    )

    class Meta:
        icon = "table"
        label = "جدول مشخصات"
        template = "content/blocks/spec_table.html"


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(label="تصویر")
    caption = blocks.CharBlock(max_length=300, required=False, label="توضیح")

    class Meta:
        icon = "image"
        label = "تصویر"
        template = "content/blocks/image.html"


class RelatedEntityBlock(blocks.StructBlock):
    """A hand-picked link to another entity (the curated counterpart of auto-links)."""

    entity_slug = blocks.CharBlock(max_length=160, label="شناسهٔ موجودیت")
    note = blocks.CharBlock(max_length=300, required=False, label="توضیح")

    class Meta:
        icon = "link"
        label = "موجودیت مرتبط"
        template = "content/blocks/related_entity.html"


class BodyBlock(blocks.StreamBlock):
    """The body of a wiki page."""

    heading = HeadingBlock()
    paragraph = ParagraphBlock()
    rich_text = RichTextBlock()
    list = ListBlock()
    quote = QuoteBlock()
    callout = CalloutBlock()
    spec_table = SpecTableBlock()
    image = ImageBlock()
    related_entity = RelatedEntityBlock()

    class Meta:
        icon = "doc-full"
        label = "محتوا"


#: Blocks that count as a section boundary for the auto-linker and the chunker.
HEADING_BLOCKS = ("heading",)
