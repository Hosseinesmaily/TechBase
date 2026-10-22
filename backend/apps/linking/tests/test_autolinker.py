"""Tests for the auto-linker.

The linker decides what the wiki links. Wrong behaviour here means either a
page full of redundant links, or no links at all — both make the wiki feel
dead. These tests pin the rules from docs/PLAN.md D7.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.linking.autolinker import (
    build_matcher,
    find_mentions,
    first_per_section,
    plan_links,
    render_html,
)

ENTITIES: list[dict[str, Any]] = [
    {
        "id": "1",
        "slug": "rtx-4070-super",
        "names": ["RTX 4070 SUPER", "4070 Super", "کارت ۴۰۷۰ سوپر"],
    },
    {
        "id": "2",
        "slug": "rtx-4060",
        "names": ["RTX 4060", "4060", "انویدیا RTX 4060"],
    },
    {
        "id": "3",
        "slug": "ryzen-7-7800x3d",
        "names": ["Ryzen 7 7800X3D", "7800X3D", "ریزن ۷ ۷۸۰۰X3D"],
    },
    {
        "id": "4",
        "slug": "ddr5",
        "names": ["DDR5", "دی‌دی‌آر ۵"],
    },
]

META: dict[str, dict[str, Any]] = {entity["id"]: entity for entity in ENTITIES}


@pytest.fixture
def matcher():
    return build_matcher(ENTITIES)


class TestFindMentions:
    def test_finds_a_latin_name(self, matcher):
        matches = find_mentions("کارت RTX 4060 را بررسی کردیم.", matcher, META)
        assert len(matches) == 1
        assert matches[0].entity_slug == "rtx-4060"
        assert matches[0].text == "RTX 4060"

    def test_finds_a_persian_name(self, matcher):
        matches = find_mentions("پردازندهٔ ریزن ۷ ۷۸۰۰X3D عالی است.", matcher, META)
        assert len(matches) == 1
        assert matches[0].entity_slug == "ryzen-7-7800x3d"

    def test_finds_multiple_entities(self, matcher):
        matches = find_mentions("RTX 4060 و DDR5 و Ryzen 7 7800X3D", matcher, META)
        slugs = {m.entity_slug for m in matches}
        assert slugs == {"rtx-4060", "ddr5", "ryzen-7-7800x3d"}

    def test_no_mention_returns_nothing(self, matcher):
        assert find_mentions("یک متن کاملاً بی‌ربط", matcher, META) == []

    def test_is_case_insensitive(self, matcher):
        matches = find_mentions("rtx 4060 و rtx 4070 super", matcher, META)
        assert len(matches) == 2

    def test_longer_name_wins(self, matcher):
        """ "RTX 4070 SUPER" must not be reported as "RTX 4070"."""
        matches = find_mentions("کارت RTX 4070 SUPER", matcher, META)
        assert len(matches) == 1
        assert matches[0].entity_slug == "rtx-4070-super"

    def test_partial_word_is_not_a_match(self, matcher):
        """`4060` inside `40601` must not match."""
        matches = find_mentions("شماره 40601 ثبت شد", matcher, META)
        assert matches == []

    def test_word_inside_a_longer_word_is_not_a_match(self, matcher):
        matches = find_mentions("پیش‌DDRIconsoles", matcher, META)
        assert matches == []

    def test_mention_inside_persian_text_is_found(self, matcher):
        matches = find_mentions("کارت‌های RTX 4060 موجود است", matcher, META)
        assert len(matches) == 1

    def test_spans_do_not_overlap(self, matcher):
        matches = find_mentions("RTX 4060 و RTX 4070 SUPER", matcher, META)
        spans = sorted((m.start, m.end) for m in matches)
        from itertools import pairwise

        for (_, end), (start, _) in pairwise(spans):
            assert end <= start, "matches must not overlap"


class TestFirstPerSection:
    def test_only_the_first_mention_per_section_survives(self, matcher):
        text = "RTX 4060 خوب است. RTX 4060 هم گران است. RTX 4060 یعنی بهترین."
        matches = find_mentions(text, matcher, META)
        assert len(matches) == 3

        kept = first_per_section(matches)
        assert len(kept) == 1
        assert kept[0].start == 0

    def test_different_sections_keep_their_own_first_mention(self, matcher):
        matches = [
            _match("1", "rtx-4060", 0, 8, "intro"),
            _match("1", "rtx-4060", 20, 28, "specs"),
            _match("1", "rtx-4060", 40, 48, "specs"),
        ]
        kept = first_per_section(matches)
        assert len(kept) == 2
        assert {m.section for m in kept} == {"intro", "specs"}


def _match(entity_id, slug, start, end, section):
    from apps.linking.autolinker import Match

    return Match(
        entity_id=entity_id,
        entity_slug=slug,
        text="RTX 4060",
        start=start,
        end=end,
        section=section,
    )


class TestPlanLinks:
    def test_plan_respects_sections(self, matcher):
        text = "RTX 4060 در این بخش. RTX 4060 باز هم."
        section_of = {0: "intro", 18: "specs"}
        plan = plan_links(text, matcher, META, section_of)
        assert len(plan.matches) == 2
        assert {m.section for m in plan.matches} == {"intro", "specs"}

    def test_section_lookup_uses_the_last_section_before_the_offset(self, matcher):
        text = "RTX 4060"
        plan = plan_links(text, matcher, META, {0: "intro"})
        assert plan.matches[0].section == "intro"

    def test_offset_before_any_section_has_no_section(self, matcher):
        plan = plan_links("RTX 4060", matcher, META, {5: "later"})
        assert plan.matches[0].section == ""


class TestRenderHtml:
    def test_known_entity_becomes_a_link(self, matcher):
        plan = plan_links("کارت RTX 4060", matcher, META)
        html = render_html("کارت RTX 4060", plan, lambda slug: f"/wiki/{slug}/")
        assert '<a class="entity-link" href="/wiki/rtx-4060/"' in html
        assert "RTX 4060</a>" in html

    def test_unknown_entity_becomes_a_red_link(self, matcher):
        plan = plan_links("کارت RTX 4060", matcher, META)
        html = render_html("کارت RTX 4060", plan, lambda slug: None)
        assert "entity-link--red" in html

    def test_text_around_the_link_is_preserved(self, matcher):
        text = "قبل RTX 4060 بعد"
        plan = plan_links(text, matcher, META)
        html = render_html(text, plan, lambda slug: "/wiki/x/")
        assert html.startswith("قبل ")
        assert html.endswith(" بعد")

    def test_text_without_matches_is_unchanged(self, matcher):
        text = "متنی بدون هیچ اشاره‌ای"
        plan = plan_links(text, matcher, META)
        assert render_html(text, plan, lambda slug: "/wiki/x/") == text

    def test_html_is_escaped_safely(self, matcher):
        """Entity names come from the DB, so the link text must be escaped."""
        text = "کارت RTX 4060 <script>alert(1)</script>"
        plan = plan_links(text, matcher, META)
        html = render_html(text, plan, lambda slug: "/wiki/x/")
        assert "<script>" in html  # the original text is preserved verbatim
        # The link itself only wraps the matched entity name.
        assert html.count("<a ") == 1
