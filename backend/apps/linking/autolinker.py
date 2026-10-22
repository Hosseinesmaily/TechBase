"""Auto-linker: find entity mentions in page text and turn them into links.

Design (docs/PLAN.md D7):
  * Aho-Corasick over every entity's names (title + Persian title + aliases),
    so matching is O(text) regardless of how many entities exist.
  * **First mention per section only** — a page that says "DDR5" ten times
    gets one link, not ten. This keeps link density readable and stops the
    auto-linker from swamping hand-written links.
  * Longer names win: "RTX 4070 SUPER" must beat "RTX 4070".
  * Word-boundary aware for Latin text; Persian text has no case folding, so
    the same boundary rule applies to the ZWNJ-joined forms.

The linker never rewrites the stored text. It produces *link candidates*;
the page renders them and the links are persisted as `EntityLink` rows.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# Characters that may sit between a word and a non-word. ZWNJ (U+200C) and
# the Arabic comma/zero-width marks are treated as word characters so that
# "نیم‌فاصله" inside a Persian name is not treated as a boundary.
_WORD_CHARS = r"\w‌‍ًٌ"
_LATIN_BOUNDARY = re.compile(rf"(?<![{_WORD_CHARS}])|(?![{_WORD_CHARS}])")
# A name may start/end with a non-word character; strip those for matching.
_TRIM_CHARS = " \t\n\r،؛.:!?()[]{}\"'«»…-"


@dataclass
class Match:
    """One entity mention found in a text."""

    entity_id: str
    entity_slug: str
    text: str  # the matched surface form
    start: int
    end: int
    section: str = ""  # the heading path the match occurred under

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class Section:
    """A heading and the text under it."""

    path: str  # "معرفی > مشخصات"
    level: int
    text: str


@dataclass
class LinkPlan:
    """The result of running the linker over a document."""

    matches: list[Match] = field(default_factory=list)
    # Characters that must not be linked again (already linked spans).
    linked_spans: list[tuple[int, int]] = field(default_factory=list)

    def in_section(self, section_path: str) -> list[Match]:
        return [m for m in self.matches if m.section == section_path]


def _normalise(name: str) -> str:
    """Fold a name for matching: case-insensitive, trimmed of edge punctuation."""
    return name.strip(_TRIM_CHARS).lower()


def _is_boundary_ok(text: str, start: int, end: int) -> bool:
    """Latin/Persian word-boundary check around a match."""
    before = text[start - 1] if start > 0 else " "
    after = text[end] if end < len(text) else " "
    before_ok = not re.match(rf"[{_WORD_CHARS}]", before, re.UNICODE)
    after_ok = not re.match(rf"[{_WORD_CHARS}]", after, re.UNICODE)
    return before_ok and after_ok


def build_matcher(entities: Iterable[dict[str, Any]]) -> tuple[Any, dict[str, str]]:
    """Build an Aho-Corasick automaton over the entity names.

    `entities` is an iterable of dicts with `id`, `slug` and `names`
    (the title, the Persian title and the aliases).

    Returns the automaton and a map from *normalised pattern* to the entity id.
    """
    try:
        import ahocorasick
    except ImportError:  # pragma: no cover - fallback for environments without it
        return _build_fallback_matcher(entities)

    automaton = ahocorasick.Automaton()
    pattern_to_entity: dict[str, str] = {}

    for entity in entities:
        names = entity.get("names") or []
        for name in names:
            cleaned = name.strip(_TRIM_CHARS)
            if len(cleaned) < 2:
                continue
            key = cleaned.lower()
            # Longest name wins: only register the first (longest) owner of a
            # given surface form, but never let a shorter name shadow a longer.
            if key in pattern_to_entity:
                continue
            pattern_to_entity[key] = entity["id"]
            automaton.add_word(key, (entity["id"], cleaned))

    automaton.make_automaton()
    return automaton, pattern_to_entity


def _build_fallback_matcher(entities: Iterable[dict[str, Any]]) -> tuple[Any, dict[str, str]]:
    """A regex-based fallback when `pyahocorasick` is not installed.

    Slower (O(entities × text)) but dependency-free, so the linker still
    works in a minimal environment.
    """
    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for entity in entities:
        for name in entity.get("names") or []:
            cleaned = name.strip(_TRIM_CHARS)
            key = cleaned.lower()
            if len(cleaned) < 2 or key in seen:
                continue
            seen.add(key)
            entries.append((key, entity["id"], cleaned))
    # Longest first so the regex alternation prefers the longer name.
    entries.sort(key=lambda item: len(item[0]), reverse=True)
    pattern = (
        "|".join(re.escape(name) for name, _, _ in entries) if entries else r"(?!)"  # never matches
    )
    regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
    mapping = {name: entity_id for name, entity_id, _ in entries}
    return regex, mapping


def find_mentions(
    text: str,
    matcher: tuple[Any, dict[str, str]],
    entity_meta: dict[str, dict[str, Any]],
    section_of: dict[int, str] | None = None,
) -> list[Match]:
    """Find all entity mentions in `text`.

    `matcher` is the tuple returned by `build_matcher`.
    `entity_meta` maps entity id → {slug, ...}.
    `section_of` optionally maps a character offset → section path; when it is
    not given, every match belongs to the empty section.

    When two names overlap ("RTX 4060" contains "4060"), the **longest** match
    wins and the shorter one is dropped — otherwise every mention of a full
    product name would also link its model number.
    """
    automaton, _ = matcher
    candidates: list[Match] = []

    if hasattr(automaton, "iter"):
        # pyahocorasick: yields (end_index, value)
        for end_index, (entity_id, surface) in automaton.iter(text.lower()):
            start = end_index - len(surface) + 1
            if not _is_boundary_ok(text, start, end_index + 1):
                continue
            candidates.append(
                Match(
                    entity_id=entity_id,
                    entity_slug=entity_meta.get(entity_id, {}).get("slug", ""),
                    text=text[start : end_index + 1],
                    start=start,
                    end=end_index + 1,
                    section=_section_for(section_of, start),
                )
            )
    else:
        for match in automaton.finditer(text):
            key = match.group(0).lower()
            entity_id = matcher[1].get(key)
            if entity_id is None:
                continue
            if not _is_boundary_ok(text, match.start(), match.end()):
                continue
            candidates.append(
                Match(
                    entity_id=entity_id,
                    entity_slug=entity_meta.get(entity_id, {}).get("slug", ""),
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    section=_section_for(section_of, match.start()),
                )
            )

    return _drop_shadowed(candidates)


def _drop_shadowed(candidates: list[Match]) -> list[Match]:
    """Remove matches that are contained in a longer match.

    "RTX 4060" (8 chars) contains "4060" (4 chars) — the shorter one is
    shadowed and must not produce a second link.
    """
    if not candidates:
        return []

    # Longest first, so a longer match claims its span before a shorter one.
    ordered = sorted(candidates, key=lambda m: (-m.length, m.start))
    kept: list[Match] = []
    claimed: list[tuple[int, int]] = []

    for match in ordered:
        if any(start <= match.start and match.end <= end for start, end in claimed):
            continue
        claimed.append((match.start, match.end))
        kept.append(match)

    return sorted(kept, key=lambda m: m.start)


def _section_for(section_of: dict[int, str] | None, offset: int) -> str:
    """The section path containing `offset` (the last section starting at or before it)."""
    if not section_of:
        return ""
    candidates = [start for start in section_of if start <= offset]
    if not candidates:
        return ""
    return section_of[max(candidates)]


def first_per_section(matches: list[Match]) -> list[Match]:
    """Keep only the first mention of each entity in each section."""
    seen: set[tuple[str, str]] = set()
    kept: list[Match] = []
    for match in matches:
        key = (match.entity_id, match.section)
        if key in seen:
            continue
        seen.add(key)
        kept.append(match)
    return kept


def plan_links(
    text: str,
    matcher: tuple[Any, dict[str, str]],
    entity_meta: dict[str, dict[str, Any]],
    section_of: dict[int, str] | None = None,
) -> LinkPlan:
    """Run the whole linker: find mentions, then keep the first per section."""
    matches = find_mentions(text, matcher, entity_meta, section_of)
    return LinkPlan(matches=first_per_section(matches))


def render_html(text: str, plan: LinkPlan, link_url: Any) -> str:
    """Wrap the planned matches in anchor tags.

    `link_url` maps an entity slug to the URL of its wiki page. Entities
    without a page become red links (a distinct class, no target).
    """
    if not plan.matches:
        return text

    pieces: list[str] = []
    cursor = 0
    for match in sorted(plan.matches, key=lambda m: m.start):
        if match.start < cursor:
            continue
        pieces.append(text[cursor : match.start])
        url = link_url(match.entity_slug)
        if url:
            pieces.append(
                f'<a class="entity-link" href="{url}" data-entity="{match.entity_slug}">'
                f"{match.text}</a>"
            )
        else:
            pieces.append(
                f'<a class="entity-link entity-link--red" data-entity="{match.entity_slug}">'
                f"{match.text}</a>"
            )
        cursor = match.end
    pieces.append(text[cursor:])
    return "".join(pieces)
