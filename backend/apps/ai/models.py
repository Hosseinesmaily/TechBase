"""RAG models: the chunk store and the query log.

`ContentChunk` is a piece of a wiki page, cut along its heading structure so
a citation can point at a specific section rather than at a whole page. The
embedding is a pgvector column; its dimension is a setting, so switching
between bge-m3 and multilingual-e5 is a configuration change, not a migration.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.catalog.models import Entity
from apps.core.models import TimeStampedModel, UUIDModel


class ContentChunk(UUIDModel, TimeStampedModel):
    """One section of a wiki page, with its embedding.

    The chunk text is the section's own text; `section_path` is the heading
    path ("معرفی > سازگاری") and `heading_level` its depth. Together they let
    the answer cite "the compatibility section of the 7800X3D page".
    """

    page = models.ForeignKey("content.WikiPage", on_delete=models.CASCADE, related_name="chunks")
    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chunks",
    )
    # The heading path of the chunk.
    section_path = models.CharField(max_length=400, blank=True, db_index=True)
    heading_level = models.PositiveSmallIntegerField(default=0)
    # The chunk's own text, without the heading.
    text = models.TextField()
    # The heading itself, so the chunk can be shown with its title.
    heading = models.CharField(max_length=300, blank=True)
    # A stable hash of the text, used to skip re-embedding unchanged chunks.
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    # The token count, for the retrieval budget.
    token_count = models.PositiveIntegerField(default=0)
    # pgvector column. Its dimension comes from settings.EMBEDDING_DIM.
    embedding = models.JSONField(null=True, blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["page", "heading_level", "id"]
        indexes = [
            models.Index(fields=["page", "heading_level"], name="chunk_page_level_idx"),
            models.Index(fields=["entity"], name="chunk_entity_idx"),
        ]

    def __str__(self) -> str:
        title = self.heading or self.section_path or self.page.slug
        return f"{self.page.slug}: {title} ({self.token_count} tokens)"

    @property
    def citation_label(self) -> str:
        """The human label of this chunk's section, for a citation."""
        if self.section_path:
            return self.section_path
        return self.heading or self.page.title

    @property
    def citation_url(self) -> str:
        """The URL of the chunk, including the heading anchor when there is one."""
        if self.heading:
            from django.utils.text import slugify

            return f"/wiki/{self.page.slug}/#{slugify(self.heading, allow_unicode=True)}"
        return f"/wiki/{self.page.slug}/"

    def set_embedding(self, vector: list[float]) -> None:
        """Store an embedding, checking the configured dimension."""
        expected = settings.EMBEDDING_DIM
        if expected and len(vector) != expected:
            raise ValueError(
                f"embedding has {len(vector)} dimensions, but EMBEDDING_DIM is {expected}"
            )
        self.embedding = vector


class QueryLog(UUIDModel, TimeStampedModel):
    """One conversation turn: what was asked, what was understood, what was used.

    This is the raw material of the analytics app (unanswered questions) and
    of the Phase 4 evaluation harness.
    """

    raw_query = models.TextField()
    # The parsed query understanding (Phase 5 fills this in).
    understood = models.JSONField(default=dict, blank=True)
    # The tool calls and their results.
    tool_calls = models.JSONField(default=list, blank=True)
    # The chunks that were retrieved.
    retrieved = models.JSONField(default=list, blank=True)
    # The answer text and the citations it carries.
    answer = models.TextField(blank=True)
    citations = models.JSONField(default=list, blank=True)
    language = models.CharField(max_length=8, default="fa")
    # How long the whole turn took.
    latency_ms = models.PositiveIntegerField(default=0)
    # Cache hit, token counts, retrieval scores.
    metrics = models.JSONField(default=dict, blank=True)
    # A hash of the normalised query, for the semantic cache.
    query_hash = models.CharField(max_length=64, blank=True, db_index=True)
    # The embedding of the query, for the semantic cache lookup.
    query_embedding = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="querylog_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.language}: {self.raw_query[:50]}"


class Feedback(UUIDModel, TimeStampedModel):
    """A thumbs-up / thumbs-down on an answer."""

    query_log = models.ForeignKey(
        QueryLog, on_delete=models.CASCADE, related_name="feedback", null=True, blank=True
    )
    # 1 = up, -1 = down.
    thumbs = models.SmallIntegerField()
    comment = models.TextField(blank=True)
    language = models.CharField(max_length=8, default="fa")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.thumbs:+d}"
