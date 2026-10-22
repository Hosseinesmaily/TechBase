"""Tests for the chunking and the retrieval."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from wagtail.models import Page

from apps.ai.chunking import chunk_page, estimate_tokens, split_long_text
from apps.ai.models import ContentChunk
from apps.content.models import ComponentPage, WikiPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def wiki_root():
    root = Page.get_first_root_node()
    assert root is not None
    return root.add_child(instance=WikiPage(title="ویکی", slug="wiki"))


def make_page(root, slug="p", title="صفحه", body=()):
    # A ComponentPage: the base WikiPage has no body field.
    page = ComponentPage(title=title, slug=slug, summary="خلاصه")
    root.add_child(instance=page)
    page = page.specific
    page.body = list(body)
    page.save_revision().publish()
    return page


class TestTokenEstimate:
    def test_counts_words(self):
        assert estimate_tokens("یک دو سه") == 3

    def test_empty_text(self):
        assert estimate_tokens("") == 0


class TestSplitLongText:
    def test_short_text_is_kept_whole(self):
        assert split_long_text("یک پاراگراف کوتاه") == ["یک پاراگراف کوتاه"]

    def test_long_text_is_split(self):
        text = "\n\n".join(["این یک پاراگراف نسبتاً طولانی است " * 20] * 5)
        pieces = split_long_text(text, target=100)
        assert len(pieces) > 1

    def test_the_pieces_keep_all_the_text(self):
        paragraphs = [f"پاراگراف {index} " * 10 for index in range(10)]
        pieces = split_long_text("\n\n".join(paragraphs), target=40)
        joined = " ".join(pieces)
        for index in range(10):
            assert f"پاراگراف {index}" in joined

    def test_a_very_long_paragraph_is_cut_on_sentences(self):
        text = ". ".join(["جملهٔ طولانی است" * 5 for _ in range(30)])
        pieces = split_long_text(text, target=50, maximum=100)
        assert len(pieces) > 1


class TestChunkPage:
    def test_a_page_with_headings_produces_one_chunk_per_section(self, wiki_root):
        page = make_page(
            wiki_root,
            body=[
                ("heading", {"level": "h2", "text": "معرفی"}),
                ("paragraph", "متن معرفی."),
                ("heading", {"level": "h2", "text": "سازگاری"}),
                ("paragraph", "متن سازگاری."),
            ],
        )
        chunks = chunk_page(page)
        assert len(chunks) == 2
        assert chunks[0].heading == "معرفی"
        assert chunks[1].heading == "سازگاری"

    def test_the_section_path_nests(self, wiki_root):
        page = make_page(
            wiki_root,
            body=[
                ("heading", {"level": "h2", "text": "معرفی"}),
                ("paragraph", "متن."),
                ("heading", {"level": "h3", "text": "جزئیات"}),
                ("paragraph", "متن جزئیات."),
            ],
        )
        chunks = chunk_page(page)
        assert chunks[0].section_path == "معرفی"
        assert chunks[1].section_path == "معرفی > جزئیات"

    def test_a_page_without_headings_produces_one_chunk(self, wiki_root):
        page = make_page(wiki_root, body=[("paragraph", "متن یکسره.")])
        chunks = chunk_page(page)
        assert len(chunks) == 1
        assert chunks[0].section_path == ""

    def test_an_empty_page_produces_nothing(self, wiki_root):
        page = make_page(wiki_root, body=[])
        assert chunk_page(page) == []

    def test_a_spec_table_becomes_text(self, wiki_root):
        page = make_page(
            wiki_root,
            body=[
                ("heading", {"level": "h2", "text": "مشخصات"}),
                (
                    "spec_table",
                    {"title": "", "rows": [{"label": "سوکت", "value": "AM5"}]},
                ),
            ],
        )
        chunks = chunk_page(page)
        assert "AM5" in chunks[0].text

    def test_every_chunk_has_a_hash_and_a_token_count(self, wiki_root):
        page = make_page(wiki_root, body=[("paragraph", "متن.")])
        chunk = chunk_page(page)[0]
        assert chunk.content_hash
        assert chunk.token_count > 0


class TestIndexContentCommand:
    def test_it_creates_the_chunks(self, wiki_root):
        make_page(
            wiki_root,
            body=[
                ("heading", {"level": "h2", "text": "معرفی"}),
                ("paragraph", "متن."),
            ],
        )
        call_command("index_content", verbosity=0)
        assert ContentChunk.objects.count() == 1

    def test_it_is_idempotent(self, wiki_root):
        make_page(wiki_root, body=[("paragraph", "متن.")])
        call_command("index_content", verbosity=0)
        call_command("index_content", verbosity=0)
        assert ContentChunk.objects.count() == 1

    def test_it_removes_the_chunks_of_deleted_text(self, wiki_root):
        page = make_page(wiki_root, body=[("paragraph", "متن اول.")])
        call_command("index_content", verbosity=0)
        assert ContentChunk.objects.count() == 1

        page.body = [("paragraph", "متن کاملاً متفاوت.")]
        page.save_revision().publish()
        call_command("index_content", verbosity=0)
        assert ContentChunk.objects.count() == 1
        chunk = ContentChunk.objects.first()
        assert chunk is not None
        assert "متفاوت" in chunk.text

    def test_the_chunks_are_embedded(self, wiki_root):
        make_page(wiki_root, body=[("paragraph", "متن.")])
        call_command("index_content", verbosity=0)
        chunk = ContentChunk.objects.first()
        assert chunk is not None
        assert chunk.embedding
        assert chunk.indexed_at is not None
