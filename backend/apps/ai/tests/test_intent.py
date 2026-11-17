"""The assistant's intent analysis and its clarification policy.

The bug this pins down: every message that lacked a budget and a use case was
answered with the same canned question — including "حافظه DDR4", which asks about a
part rather than asking for a whole PC to be specified. These tests fix the policy:
ask only when the request genuinely needs it, and then ask for exactly what is
missing, never for what the user already said.
"""

from __future__ import annotations

import pytest

from apps.ai.intent import (
    BUILD,
    COMPATIBILITY,
    COMPONENT,
    UNCLEAR,
    analyse_request,
    decide_clarification,
)
from apps.ai.llm import FakeLLM
from apps.ai.orchestrator import run_agent
from apps.ai.understanding import understand_with_heuristics

pytestmark = pytest.mark.django_db


def intent_of(query: str, *, entities=()):
    """The intent of a query, as the orchestrator computes it."""
    return analyse_request(
        query,
        understanding=understand_with_heuristics(query),
        entities=entities,
    )


class TestRequestKind:
    def test_a_part_question_is_a_component_request(self):
        intent = intent_of("حافظه DDR4")
        assert intent.kind == COMPONENT
        assert intent.topic == "ram"
        assert intent.keywords == ("ddr4",)

    def test_a_price_question_is_a_component_request(self):
        intent = intent_of("قیمت کارت گرافیک RTX 4070 SUPER چقدر است؟")
        assert intent.kind == COMPONENT
        assert intent.topic == "gpu"
        assert intent.mentions("price")
        assert "rtx" in intent.keywords
        assert "4070" in intent.keywords

    def test_a_resolution_and_a_budget_are_not_treated_as_models(self):
        """`1080p` and `50` are not identities: using them as search terms finds nothing."""
        intent = intent_of("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون")
        assert intent.keywords == ()

    def test_storage_is_not_confused_with_memory(self):
        assert intent_of("حافظه ذخیره‌سازی یک ترابایتی").topic == "storage"

    def test_a_compatibility_question_is_recognised(self):
        assert intent_of("آیا این رم با مادربرد سازگار است؟", entities=("a", "b")).kind == (
            COMPATIBILITY
        )

    def test_a_build_request_is_recognised(self):
        assert intent_of("یک سیستم گیمینگ می‌خواهم").kind == BUILD
        assert intent_of("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون").kind == BUILD

    def test_a_build_that_mentions_compatibility_stays_a_build(self):
        """One part named plus «سازگار» is not a two-part check."""
        intent = intent_of("یک سیستم با قطعات سازگار می‌خواهم", entities=("ryzen-7-7800x3d",))
        assert intent.kind == BUILD

    def test_nothing_recognisable_is_unclear(self):
        assert intent_of("asdasd").kind == UNCLEAR


class TestClarificationPolicy:
    def test_a_named_part_is_never_interrupted(self):
        assert decide_clarification(intent_of("حافظه DDR4")) == ""

    def test_a_price_question_is_never_interrupted(self):
        assert decide_clarification(intent_of("قیمت RTX 4070 SUPER چقدر است؟")) == ""

    def test_a_broad_build_asks_for_the_missing_essentials(self):
        question = decide_clarification(intent_of("یک سیستم خوب می‌خواهم"))
        assert question
        assert "بودجه" in question

    def test_a_build_that_already_gave_a_budget_does_not_ask_for_it_again(self):
        question = decide_clarification(intent_of("سیستم با بودجه ۵۰ میلیون می‌خواهم"))
        assert question
        assert "بودجه" not in question

    def test_a_build_with_a_resolution_is_not_interrupted(self):
        assert decide_clarification(intent_of("بهترین سیستم گیمینگ برای 1080p کدام است؟")) == ""

    def test_an_incomplete_compatibility_check_asks_for_two_parts(self):
        question = decide_clarification(
            intent_of("این رم با مادربرد سازگار است؟", entities=("only-one",))
        )
        assert "دو قطعه" in question

    def test_an_under_specified_ram_recommendation_names_what_is_missing(self):
        question = decide_clarification(intent_of("یک رم خوب پیشنهاد بده"))
        assert "مادربرد" in question

    def test_an_unclear_message_gets_a_specific_request_for_clarity(self):
        question = decide_clarification(intent_of("asdasd"))
        assert question
        assert "بودجه" not in question

    def test_the_question_can_be_turned_off(self):
        assert decide_clarification(intent_of("یک سیستم خوب می‌خواهم"), ask=False) == ""


@pytest.fixture
def indexed():
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)
    call_command("seed_wiki", verbosity=0)
    call_command("index_content", verbosity=0)
    return True


def ask(query: str, **kwargs):
    """One turn, with the deterministic local model (no API key involved)."""
    return run_agent(query, llm=FakeLLM(), use_cache=False, **kwargs)


class TestAssistantRegressions:
    """The six cases the request named, end to end."""

    def test_a_memory_question_is_answered_not_deferred(self, indexed):
        result = ask("حافظه DDR4")
        assert result.clarifying_question == ""
        assert result.answer
        products = next(call for call in result.tool_calls if call["tool"] == "search_products")
        assert products["arguments"]["query"] == "ddr4"
        assert products["data"]["items"]
        assert all("ddr4" in item["entity_slug"] for item in products["data"]["items"])
        assert result.guardrails.get("ok") is True

    def test_a_memory_compatibility_question_uses_the_rule_engine(self, indexed):
        result = ask(
            "آیا Kingston FURY Beast 32GB DDR4-3200 با مادربرد ASUS TUF Gaming B650-PLUS "
            "سازگار است؟"
        )
        assert result.clarifying_question == ""
        compatibility = next(
            call for call in result.tool_calls if call["tool"] == "check_compatibility"
        )
        assert compatibility["data"]["verdict"] == "block"
        assert compatibility["data"]["findings"][0]["rule_code"] == "RAM_TYPE_MATCH"
        assert "ناسازگار" in result.answer

    def test_a_price_question_is_grounded_in_the_tools(self, indexed):
        result = ask("قیمت کارت گرافیک RTX 4070 SUPER چقدر است؟")
        assert result.clarifying_question == ""
        assert any(call["tool"] == "search_products" for call in result.tool_calls)
        assert result.cards
        assert result.cards[0].price
        assert result.guardrails["ok"] is True

    def test_a_build_without_essentials_asks_exactly_once(self, indexed):
        result = ask("یک سیستم خوب می‌خواهم")
        assert result.clarifying_question
        assert result.answer == ""
        assert result.tool_calls == []

    def test_a_build_with_a_budget_answers_with_cards(self, indexed):
        result = ask("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون")
        assert result.clarifying_question == ""
        assert result.cards

    def test_an_unclear_message_asks_for_clarity_not_a_budget(self, indexed):
        result = ask("asdasd")
        assert result.clarifying_question
        assert "بودجه" not in result.clarifying_question
        assert result.tool_calls == []

    def test_context_the_user_already_gave_is_not_asked_again(self, indexed):
        """The client sends the earlier turn along with the follow-up answer."""
        result = ask("سیستم گیمینگ با بودجه ۵۰ میلیون می‌خواهم\nپاسخ تکمیلی کاربر: برای بازی")
        assert result.clarifying_question == ""

    def test_the_intent_is_recorded_with_the_understanding(self, indexed):
        result = ask("حافظه DDR4")
        assert result.understanding["request"]["kind"] == COMPONENT
        assert result.understanding["request"]["topic"] == "ram"
