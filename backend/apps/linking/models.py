"""Typed links between entities, and the pages that mention them.

`EntityLink` is the precomputed edge list behind the wiki's internal
hyperlinking. It is written by the auto-linker (mentions) and by editors
(the typed edges), and it backs the backlinks and hover-card features.

A link whose target has no page yet is a **red link** — the editorial backlog
of "entities we should write about".
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.catalog.models import Entity
from apps.core.models import TimeStampedModel, UUIDModel


class LinkType(models.TextChoices):
    MENTIONS = "mentions", "ذکر می‌کند"
    COMPATIBLE_WITH = "compatible_with", "سازگار با"
    ALTERNATIVE_TO = "alternative_to", "جایگزین"
    BENCHMARKED_IN = "benchmarked_in", "بنچمارک‌شده در"
    PART_OF = "part_of", "بخشی از"
    BUY_GUIDE = "buy_guide", "راهنمای خرید"


class EntityLink(UUIDModel, TimeStampedModel):
    """A typed edge between two entities, optionally anchored to a page section.

    `section_path` is the heading path the mention occurred under
    ("روش‌های ارتقا > حافظه"), which lets the wiki link only the first
    mention per section and lets citations point at a specific heading.
    """

    source = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="outgoing_links")
    target = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="incoming_links")
    link_type = models.CharField(
        max_length=32, choices=LinkType.choices, default=LinkType.MENTIONS, db_index=True
    )
    # The heading path of the mention, e.g. "معرفی > مشخصات".
    section_path = models.CharField(max_length=400, blank=True)
    # The page the link was found on (if any).
    page = models.ForeignKey(
        "content.WikiPage",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="links",
    )
    # The text that was linked, for context and for redisplay.
    text = models.CharField(max_length=300, blank=True)
    # True when the auto-linker created it (editors' links are curated).
    auto_created = models.BooleanField(default=True, db_index=True)
    # False when the target has no wiki page yet → a red link.
    target_exists = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="entity_links"
    )

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target", "link_type", "page", "section_path"],
                name="uniq_entity_link",
            )
        ]
        indexes = [
            models.Index(fields=["target", "link_type"], name="link_target_type_idx"),
            models.Index(fields=["target_exists"], name="link_target_exists_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.source_id} → {self.target_id} ({self.link_type})"

    @property
    def is_red_link(self) -> bool:
        """A link to an entity that has no page yet."""
        return not self.target_exists


class LinkIntegrityReport(UUIDModel, TimeStampedModel):
    """The result of one nightly link-integrity run.

    Keeps the editorial backlog auditable: how many red links and orphan pages
    existed at a point in time, and what was fixed.
    """

    broken_links = models.PositiveIntegerField(default=0)
    red_links = models.PositiveIntegerField(default=0)
    orphan_pages = models.PositiveIntegerField(default=0)
    total_links = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)
    ran_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-ran_at"]
        verbose_name = "link integrity report"

    def __str__(self) -> str:
        return f"integrity {self.ran_at:%Y-%m-%d %H:%M} — {self.red_links} red, {self.orphan_pages} orphan"
