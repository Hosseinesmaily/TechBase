"""Chunk the wiki pages and embed the chunks.

python manage.py index_content              # chunk + embed every page
python manage.py index_content --no-embed   # chunk only
python manage.py index_content --stats      # what would be indexed
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.ai.chunking import chunk_page
from apps.ai.embeddings import embed_texts
from apps.ai.models import ContentChunk
from apps.content.models import WikiPage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Chunk the published wiki pages and embed the chunks."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--no-embed",
            action="store_true",
            help="Only create the chunks; do not compute the embeddings.",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Only show what would be indexed.",
        )
        parser.add_argument(
            "--page",
            default="",
            help="Only re-index the page with this slug.",
        )

    def handle(self, *args: object, **options: object) -> None:
        pages = (
            WikiPage.objects.live()
            .filter(first_published_at__isnull=False)
            .select_related("entity")
        )
        if options.get("page"):
            pages = pages.filter(slug=options["page"])

        if options.get("stats"):
            total_chunks = 0
            total_tokens = 0
            for page in pages:
                chunks = chunk_page(page)
                total_chunks += len(chunks)
                total_tokens += sum(chunk.token_count for chunk in chunks)
            self.stdout.write(
                f"{pages.count()} pages, {total_chunks} chunks, {total_tokens} tokens"
            )
            return

        created = 0
        updated = 0
        skipped = 0
        embedded = 0

        for page in pages:
            chunks = chunk_page(page)
            if not chunks:
                continue

            seen_hashes = {chunk.content_hash for chunk in chunks}
            # Chunks whose text is unchanged keep their embedding.
            existing = {
                chunk.content_hash: chunk for chunk in ContentChunk.objects.filter(page=page)
            }
            stale = ContentChunk.objects.filter(page=page).exclude(content_hash__in=seen_hashes)
            stale_count = stale.count()
            stale.delete()

            for chunk in chunks:
                current = existing.get(chunk.content_hash)
                if current is None:
                    current = ContentChunk(page=page, content_hash=chunk.content_hash)
                    created += 1
                else:
                    updated += 1
                current.entity = page.entity
                current.section_path = chunk.section_path
                current.heading_level = chunk.heading_level
                current.heading = chunk.heading
                current.text = chunk.text
                current.token_count = chunk.token_count
                current.save()

            if not options.get("no_embed"):
                embedded += _embed_page(page, chunks)

            skipped += stale_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {created + updated} chunks "
                f"({created} new, {updated} updated, {skipped} removed), "
                f"{embedded} embedded."
            )
        )


def _embed_page(page, chunks) -> int:
    """Compute and store the embeddings of a page's chunks."""
    from django.utils import timezone

    pending = [chunk for chunk in ContentChunk.objects.filter(page=page) if not chunk.embedding]
    if not pending:
        return 0

    vectors = embed_texts([chunk.text for chunk in pending])
    now = timezone.now()
    for chunk, vector in zip(pending, vectors, strict=True):
        try:
            chunk.set_embedding(vector)
        except ValueError as exc:
            # The dimension does not match EMBEDDING_DIM — leave the chunk
            # unembedded rather than storing a wrong-shaped vector.
            logger.warning("could not embed chunk %s: %s", chunk.pk, exc)
            chunk.embedding = None
        else:
            chunk.indexed_at = now
        chunk.save(update_fields=["embedding", "indexed_at"])

    return len(pending)
