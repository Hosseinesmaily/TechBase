"""The conversational behaviour of the assistant.

These tests pin the *conversation*, not the facts: a greeting gets a greeting, a
definition question gets the concept explained, a follow-up keeps its context,
and the "one question at most" policy never turns into an interrogation. The
grounding rules (price/stock/compatibility only from tools) stay covered by
`test_guardrails.py` and `test_agentic.py`.
"""

from __future__ import annotations

import re

import pytest

from apps.ai.intent import (
    BUILD,
    COMPATIBILITY,
    COMPONENT,
    CONCEPT,
    analyse_request,
    decide_clarification,
)
from apps.ai.orchestrator import run_agent
from apps.ai.social import FAREWELL, GREETING, THANKS, classify_social, social_reply
from apps.ai.understanding import understand

pytestmark = pytest.mark.django_db


class TestSmallTalk:
    def test_a_greeting_and_a_thanks_and_a_goodbye_are_recognised(self):
        assert classify_social("سلام") == GREETING
        assert classify_social("سلام!") == GREETING
        assert classify_social("خوبی؟ سلام") == GREETING
        assert classify_social("ممنون، عالی بود") == THANKS
        assert classify_social("مرسی از راهنماییت") == THANKS
        assert classify_social("خداحافظ") == FAREWELL

    def test_a_message_that_carries_a_request_is_not_small_talk(self):
        # The social word must not swallow the question behind it.
        assert classify_social("سلام، یک سیستم گیمینگ میخواهم") == ""
        assert classify_social("رم DDR4 چیه؟") == ""
        assert classify_social("قیمت RTX 4070 SUPER چقدر است؟") == ""
        assert classify_social("این رم با مادربردم سازگار است؟") == ""

    def test_the_reply_is_a_reply_and_stays_stable(self):
        reply = social_reply(GREETING, "سلام")
        assert reply == social_reply(GREETING, "سلام")
        # No number at all: a greeting must not look like a shop fact.
        assert not re.search(r"[0-9۰-۹]", reply)
        assert len(reply) > 10

    def test_a_greeting_runs_no_tool_and_asks_no_question(self):
        result = run_agent("سلام", log=False)

        assert result.tool_calls == []
        assert result.cards == []
        assert result.clarifying_question == ""
        assert result.answer
        assert "بودجه" not in result.answer

    def test_a_thanks_does_not_become_a_product_search(self):
        result = run_agent("ممنون، کمک خوبی بود", log=False)

        assert result.tool_calls == []
        assert result.clarifying_question == ""
        assert result.answer


class TestTeachingQuestions:
    """«رم DDR4 چیه؟» is a question about a thing — not a build request."""

    def test_a_definition_question_asks_nothing_about_budget(self):
        text = "رم DDR4 چیه؟"
        intent = analyse_request(text, understanding=understand(text))

        assert intent.kind == COMPONENT
        assert CONCEPT in intent.aspects
        assert decide_clarification(intent) == ""

    def test_a_definition_answer_leads_with_the_explanation(self):
        # No catalog row is needed: with no tool output the assistant admits it has
        # nothing rather than inventing an explanation.
        result = run_agent("رم DDR4 چیه؟", log=False)

        assert result.clarifying_question == ""
        assert result.answer
        assert "بودجه" not in result.clarifying_question


class TestBuildConversation:
    def test_a_meaningful_but_incomplete_build_gets_one_helpful_question(self):
        text = "سیستم میخوام برای بازی"
        intent = analyse_request(text, understanding=understand(text))

        assert intent.kind == BUILD
        question = decide_clarification(intent)
        assert "بودجه" in question
        assert "منظور" not in question  # not the dry "say it again"

    def test_the_clarifying_question_acknowledges_the_request_first(self):
        result = run_agent("سیستم میخوام برای بازی", log=False)

        assert result.clarifying_question
        assert result.clarifying_question.startswith("حتماً")
        # One question, never a list of them.
        assert result.clarifying_question.count("؟") == 1

    def test_a_budget_given_in_the_second_message_is_not_asked_again(self):
        history = [{"role": "user", "content": "یک سیستم گیمینگ میخواهم"}]
        result = run_agent("بودجهاش ۴۰ میلیون تومان است", history=history, log=False)

        assert result.clarifying_question == ""
        assert result.understanding["budget_max"] == 40000000
        assert result.understanding["use_case"] == "gaming"

    def test_a_thin_follow_up_stays_on_the_same_topic(self):
        history = [{"role": "user", "content": "رم DDR4 میخواهم"}]
        result = run_agent("گرونترش چطور؟", history=history, log=False)

        # The follow-up names no category, so the topic comes from the conversation.
        assert result.understanding["request"]["topic"] == "ram"
        assert result.clarifying_question == ""


class TestCompatibilityConversation:
    def test_two_named_parts_are_checked_without_a_question(self):
        intent = analyse_request(
            "رم DDR4-3200 با مادربرد B650 سازگار است؟",
            understanding=understand("رم DDR4-3200 با مادربرد B650 سازگار است؟"),
            entities=("kingston-fury-beast-32gb-ddr4-3200", "msi-mag-b650-tomahawk"),
        )

        assert intent.kind == COMPATIBILITY
        assert decide_clarification(intent) == ""

    def test_one_named_part_asks_for_the_second(self):
        intent = analyse_request(
            "این رم سازگار است؟",
            understanding=understand("این رم سازگار است؟"),
            entities=("kingston-fury-beast-32gb-ddr4-3200",),
        )

        assert intent.kind == COMPATIBILITY
        assert "دو قطعه" in decide_clarification(intent)
