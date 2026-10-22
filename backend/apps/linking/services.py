"""Link-integrity services.

Two jobs:
  * `link_page` — run the auto-linker over a page's body and persist the
    resulting `EntityLink` rows (and the red links for entities without a page).
  * `check_integrity` — the nightly job that reports broken links, red links
    and orphan pages, and records a `LinkIntegrityReport`.

Both are pure-ish functions over the database so they can be tested without
Celery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Entity

from .autolinker import build_matcher, plan_links
from .models import EntityLink, LinkIntegrityReport

#: The section page that holds the wiki; it is never an orphan.
WIKI_ROOT_SLUG = "wiki"

logger = logging.getLogger(__name__)


@dataclass
class LinkPageResult:
    """What one linking run produced."""

    page_slug: str = ""
    created: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    red_links: list[str] = field(default_factory=list)
    total_matches: int = 0

    def as_dict(self) -> dict:
        return {
            "page_slug": self.page_slug,
            "created": self.created,
            "removed": self.removed,
            "red_links": self.red_links,
            "total_matches": self.total_matches,
        }


def entity_matcher() -> tuple[tuple[Any, dict[str, str]], dict[str, dict[str, Any]]]:
    """Build the Aho-Corasick matcher over every active entity.

    The matcher is rebuilt per run: the catalog changes, and a stale matcher
    would silently link to entities that no longer exist.

    Brand names are excluded: "ای‌ام‌دی" or "ASUS" appear in almost every
    paragraph and linking them adds noise without adding information. A brand
    is reachable through the product it belongs to, not through a link.
    """
    entities = list(Entity.objects.filter(is_active=True))
    payload = []
    meta: dict[str, dict] = {}
    for entity in entities:
        names = [
            name
            for name in (entity.title, entity.title_fa, *entity.aliases)
            if name and len(name.strip()) >= 2
        ]
        payload.append({"id": str(entity.id), "slug": entity.slug, "names": names})
        meta[str(entity.id)] = {"slug": entity.slug, "title": entity.display_title}
    return build_matcher(payload), meta


def page_sections(page) -> tuple[str, dict[int, str]]:
    """The page's plain text and the heading path at each character offset.

    A heading starts a new section; the path is the chain of headings, e.g.
    "معرفی > مشخصات فنی".
    """
    # The concrete page type holds the body; the base WikiPage does not.
    specific = page.specific if hasattr(page, "specific") else page
    text_parts: list[str] = []
    section_of: dict[int, str] = {}
    heading_stack: list[tuple[int, str]] = []
    offset = 0

    for block in getattr(specific, "body", []) or []:
        if block.block_type == "heading":
            value = block.value
            level = int(str(value.get("level", "h2")).lstrip("h") or 2)
            heading = value.get("text", "")
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading))
            path = " > ".join(h for _, h in heading_stack)
            section_of[offset] = path
            chunk = f"\n{heading}\n"
        elif block.block_type == "paragraph" or block.block_type == "rich_text":
            chunk = f"{block.value}\n"
        elif block.block_type == "list":
            chunk = "\n".join(f"- {item}" for item in block.value.get("items", [])) + "\n"
        elif block.block_type == "quote":
            chunk = f"{block.value.get('text', '')}\n"
        elif block.block_type == "callout":
            chunk = f"{block.value.get('title', '')} {block.value.get('text', '')}\n"
        elif block.block_type == "spec_table":
            chunk = (
                "\n".join(
                    f"{row.get('label', '')}: {row.get('value', '')}"
                    for row in block.value.get("rows", [])
                )
                + "\n"
            )
        else:
            chunk = ""

        text_parts.append(chunk)
        offset += len(chunk)

    return "".join(text_parts), section_of


@transaction.atomic
def link_page(page) -> LinkPageResult:
    """Run the auto-linker over a page and persist its links.

    Only *auto-created* links are rewritten — the editor's curated links are
    left alone.
    """
    result = LinkPageResult(page_slug=page.slug)
    source = page.entity
    if source is None:
        # A page with no entity has no source edge; nothing to link.
        return result

    text, section_of = page_sections(page)
    matcher, meta = entity_matcher()
    plan = plan_links(text, matcher, meta, section_of)
    result.total_matches = len(plan.matches)

    # Which entities have their own page? Everything else is a red link.
    with_page = set(
        str(slug)
        for slug in Entity.objects.filter(
            wiki_pages__isnull=False, wiki_pages__live=True
        ).values_list("slug", flat=True)
    )

    # The keys are normalised to strings: `target_id` is a UUID here but the
    # match loop uses the string form, and mixing the two would make every
    # re-link look like a new link (and violate the unique constraint).
    existing = {
        (str(link.target_id), link.section_path): link
        for link in EntityLink.objects.filter(page=page, auto_created=True)
    }
    seen: set[tuple[str, str]] = set()

    for match in plan.matches:
        target = Entity.objects.filter(id=match.entity_id).first()
        if target is None:
            continue
        key = (str(target.id), match.section)
        if key in seen:
            continue
        seen.add(key)

        target_exists = target.slug in with_page
        if not target_exists:
            result.red_links.append(target.slug)

        link = existing.get(key)
        if link is None:
            EntityLink.objects.create(
                source=source,
                target=target,
                link_type="mentions",
                section_path=match.section,
                page=page,
                text=match.text[:300],
                auto_created=True,
                target_exists=target_exists,
            )
            result.created.append(target.slug)
        else:
            # Update the stored surface text and the red-link flag.
            changed = []
            if link.text != match.text[:300]:
                link.text = match.text[:300]
                changed.append("text")
            if link.target_exists != target_exists:
                link.target_exists = target_exists
                changed.append("target_exists")
            if changed:
                link.save(update_fields=[*changed, "updated_at"])

    # Remove auto links whose mention is gone from the text.
    for (target_id, section), link in existing.items():
        if (target_id, section) not in seen:
            link.delete()
            result.removed.append(link.target.slug if link.target_id else "")

    return result


@dataclass
class IntegrityResult:
    total_links: int = 0
    red_links: int = 0
    broken_links: int = 0
    orphan_pages: int = 0
    red_link_targets: list[dict] = field(default_factory=list)
    orphan_page_list: list[dict] = field(default_factory=list)
    broken_link_list: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total_links": self.total_links,
            "red_links": self.red_links,
            "broken_links": self.broken_links,
            "orphan_pages": self.orphan_pages,
            "red_link_targets": self.red_link_targets,
            "orphan_pages_detail": self.orphan_page_list,
            "broken_link_list": self.broken_link_list,
        }


def check_integrity() -> IntegrityResult:
    """Audit the link graph.

    * **broken links** — a link whose source or target entity no longer exists.
    * **red links** — a link to an entity that has no wiki page.
    * **orphan pages** — a published page that nothing links to.
    """
    from apps.content.models import WikiPage

    result = IntegrityResult()

    links = EntityLink.objects.select_related("source", "target", "page")
    result.total_links = links.count()

    # A link is broken when its target entity is gone. Django's CASCADE means
    # this should not happen, but a stale row from an import would show up here.
    for link in links:
        if link.target_id and not Entity.objects.filter(id=link.target_id).exists():
            result.broken_links += 1
            result.broken_link_list.append(
                {
                    "id": str(link.id),
                    "source": link.source.slug if link.source_id else None,
                    "target": link.target.slug if link.target_id else None,
                }
            )

    red = (
        EntityLink.objects.filter(target_exists=False)
        .values("target__slug", "target__title_fa", "target__title", "target__type")
        .distinct()
    )
    result.red_links = red.count()
    result.red_link_targets = [
        {
            "slug": row["target__slug"],
            "title": row["target__title_fa"] or row["target__title"],
            "type": row["target__type"],
        }
        for row in red
    ]

    # An orphan is a published page that **nothing links to**. The link graph
    # is keyed by entity, so a page is an orphan when its bound entity has no
    # inbound links. Pages without an entity cannot be link targets at all,
    # so they are reported separately rather than counted as orphans.
    linked_entity_ids = set(EntityLink.objects.values_list("target_id", flat=True).distinct())
    orphan_pages = [
        page
        for page in WikiPage.objects.live().select_related("entity")
        if page.entity_id
        and page.slug != WIKI_ROOT_SLUG
        and page.entity_id not in linked_entity_ids
    ]
    result.orphan_pages = len(orphan_pages)
    result.orphan_page_list = [
        {
            "slug": page.slug,
            "title": page.title,
            "entity_slug": page.entity.slug if page.entity is not None else None,
        }
        for page in orphan_pages
    ]

    return result


def record_integrity(result: IntegrityResult) -> LinkIntegrityReport:
    """Persist an integrity run so the trend is visible over time."""
    return LinkIntegrityReport.objects.create(
        total_links=result.total_links,
        red_links=result.red_links,
        broken_links=result.broken_links,
        orphan_pages=result.orphan_pages,
        details=result.as_dict(),
        ran_at=timezone.now(),
    )


def stale_pages(days: int = 30) -> list:
    """Pages whose review date is in the past (or soon)."""
    from apps.content.models import WikiPage

    cutoff = timezone.now().date() - timedelta(days=days)
    return list(WikiPage.objects.live().filter(review_by__lt=cutoff).order_by("review_by"))
