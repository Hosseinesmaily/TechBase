"""Tests for the agentic layer: understanding, the tools and the orchestrator."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ai.llm import FakeLLM, LLMResponse, Message
from apps.ai.orchestrator import (
    build_context,
    cards_from,
    citations_from,
    plan_tools,
    run_agent,
    tool_facts,
)
from apps.ai.tools import (
    check_compatibility,
    get_benchmarks,
    search_products,
    search_wiki,
)
from apps.ai.understanding import understand, understand_with_heuristics

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def indexed():
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)
    call_command("seed_wiki", verbosity=0)
    call_command("index_content", verbosity=0)
    return True


class ScriptedLLM:
    """A model that answers from the context it was given."""

    name = "scripted"

    def __init__(self, answer: str = "پاسخ [1]") -> None:
        self.answer = answer
        self.seen: list[Message] = []

    def complete(self, messages: list[Message], *, max_tokens: int = 1024) -> LLMResponse:
        self.seen = list(messages)
        return LLMResponse(text=self.answer, model="scripted", provider="scripted")

    def stream(self, messages: list[Message], *, max_tokens: int = 1024):
        self.seen = list(messages)
        yield self.answer


# --- Understanding ------------------------------------------------------------


class TestQueryUnderstanding:
    def test_it_reads_the_resolution(self):
        understanding = understand_with_heuristics("سیستم گیمینگ ۱۴۴۰p می‌خواهم")
        assert understanding.resolution == "1440p"

    def test_it_reads_the_budget_in_millions(self):
        understanding = understand_with_heuristics("حدود ۴۰ میلیون بودجه دارم")
        assert understanding.budget_max == 40_000_000

    def test_it_reads_the_budget_in_tomans(self):
        understanding = understand_with_heuristics("بودجه ۶۰۰۰۰۰۰۰ تومان")
        assert understanding.budget_max == 60_000_000

    def test_it_reads_the_fps_target(self):
        understanding = understand_with_heuristics("می‌خواهم ۱۴۴ فریم بگیرم")
        assert understanding.fps_target == 144

    def test_it_reads_the_use_case(self):
        assert understand_with_heuristics("سیستم گیمینگ می‌خواهم").use_case == "gaming"
        assert understand_with_heuristics("سیستم اداری می‌خواهم").use_case == "office"

    def test_it_detects_the_language(self):
        assert understand_with_heuristics("سیستم گیمینگ").language == "fa"
        assert understand_with_heuristics("a gaming PC").language == "en"

    def test_it_reports_what_is_missing(self):
        understanding = understand_with_heuristics("یک سیستم خوب می‌خواهم")
        assert "budget_max" in understanding.missing_info

    def test_it_asks_one_clarifying_question(self):
        understanding = understand_with_heuristics("یک سیستم خوب می‌خواهم")
        assert understanding.clarifying_question
        assert understanding.needs_clarification

    def test_it_does_not_ask_when_everything_is_known(self):
        understanding = understand_with_heuristics("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون")
        assert understanding.missing_info == []
        assert not understanding.needs_clarification

    def test_understand_uses_the_heuristics_without_a_model(self):
        understanding = understand("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون")
        assert understanding.resolution == "1080p"
        assert understanding.budget_max == 50_000_000


# --- Tools -------------------------------------------------------------------


class TestSearchProducts:
    def test_it_returns_products_with_the_price_and_the_stock(self, indexed):
        result = search_products(entity_type="prebuilt", limit=5)
        assert result.ok
        assert result.data["count"] > 0
        item = result.data["items"][0]
        assert item["price"]
        assert item["stock"] is not None
        assert item["updated_at"]

    def test_it_filters_by_budget(self, indexed):
        result = search_products(max_price=40_000_000, limit=20)
        for item in result.data["items"]:
            assert int(float(item["price"])) <= 40_000_000

    def test_it_filters_by_stock(self, indexed):
        result = search_products(in_stock=True, limit=20)
        assert all(item["in_stock"] for item in result.data["items"])

    def test_gaming_gpu_results_are_ranked_by_measured_fps(self, indexed):
        result = search_products(entity_type="gpu", in_stock=True, resolution="1080p")
        assert result.ok and result.data["items"]
        scores = [
            item["recommendation_fps"]
            for item in result.data["items"]
            if item["recommendation_fps"] is not None
        ]
        assert scores == sorted(scores, reverse=True)
        assert all(item["recommendation_reason"] for item in result.data["items"])

    def test_the_facts_include_the_price(self, indexed):
        result = search_products(entity_type="prebuilt", limit=3)
        assert any("IRT" in fact for fact in result.facts())


class TestGetBenchmarks:
    def test_it_returns_the_frame_rates(self, indexed):
        result = get_benchmarks(component="rtx-4060", resolution="1080p")
        assert result.ok
        assert result.data["count"] > 0
        item = result.data["items"][0]
        assert item["avg_fps"] > 0
        assert item["game"]


class TestCheckCompatibility:
    def test_it_returns_the_rule_engine_verdict(self, indexed):
        result = check_compatibility(["ryzen-7-7800x3d", "gigabyte-b760m-ds3h"])
        assert result.ok
        assert result.data["verdict"] == "block"
        assert result.data["findings"][0]["rule_code"] == "SOCKET_MATCH"

    def test_a_valid_combination_is_ok(self, indexed):
        result = check_compatibility(
            ["ryzen-7-7800x3d", "asus-tuf-gaming-b650-plus", "corsair-vengeance-rgb-32gb-ddr5-6000"]
        )
        assert result.data["verdict"] == "ok"

    def test_the_verdict_is_never_invented(self, indexed):
        """The tool's verdict is the rule engine's, not a model's."""
        result = check_compatibility(["ryzen-7-7800x3d", "gigabyte-b760m-ds3h"])
        assert result.data["verdict"] in {"ok", "warn", "block"}


class TestSearchWiki:
    def test_it_returns_sections_with_urls(self, indexed):
        result = search_wiki("حافظه DDR5 چیست؟", limit=5)
        assert result.ok
        assert result.data["count"] > 0
        item = result.data["items"][0]
        assert item["url"].startswith("/wiki/")
        assert item["page_title"]


# --- The plan ----------------------------------------------------------------


class TestPlanTools:
    def test_the_wiki_is_always_searched(self):
        understanding = understand_with_heuristics("یک سؤال")
        plan = plan_tools("یک سؤال", understanding)
        assert plan[0][0] == "search_wiki"

    def test_a_price_question_searches_the_products(self, indexed):
        understanding = understand_with_heuristics("قیمت کارت گرافیک چقدر است؟")
        plan = plan_tools("قیمت کارت گرافیک چقدر است؟", understanding)
        assert any(name == "search_products" for name, _ in plan)

    def test_a_gaming_intent_searches_the_prebuilts(self):
        understanding = understand_with_heuristics("سیستم گیمینگ ۱۰۸۰p می‌خواهم")
        plan = plan_tools("سیستم گیمینگ", understanding)
        products = [args for name, args in plan if name == "search_products"]
        assert products and products[0].get("entity_type") == "prebuilt"

    def test_a_gaming_gpu_query_searches_gpu_products_directly(self):
        understanding = understand_with_heuristics("کارت گرافیک مخصوص گیم")
        plan = plan_tools("کارت گرافیک مخصوص گیم", understanding)
        product_calls = [args for name, args in plan if name == "search_products"]
        assert product_calls and product_calls[0]["entity_type"] == "gpu"

    def test_compatibility_query_routes_two_named_parts_to_the_rule_engine(self, indexed):
        query = "Is Ryzen 7 7800X3D compatible with Gigabyte B760M DS3H?"
        understanding = understand_with_heuristics(query)
        plan = plan_tools(query, understanding)
        checks = [args for name, args in plan if name == "check_compatibility"]
        assert checks and len(checks[0]["parts"]) >= 2

    def test_a_specific_part_query_does_not_block_on_missing_budget(self, indexed):
        result = run_agent("کارت گرافیک مخصوص گیم", llm=FakeLLM(), use_cache=False)
        assert not result.clarifying_question
        assert result.cards
        assert "گزینه" in result.answer

    def test_compatibility_answer_uses_the_rule_engine(self, indexed):
        query = "Is Ryzen 7 7800X3D compatible with Gigabyte B760M DS3H?"
        result = run_agent(query, llm=FakeLLM(), use_cache=False)
        assert not result.clarifying_question
        assert any(call["tool"] == "check_compatibility" for call in result.tool_calls)
        assert result.cards == []
        assert "ناسازگار" in result.answer

    def test_the_budget_becomes_a_filter(self):
        understanding = understand_with_heuristics("سیستم گیمینگ با بودجه ۵۰ میلیون")
        plan = plan_tools("سیستم گیمینگ", understanding)
        products = [args for name, args in plan if name == "search_products"]
        assert products and products[0].get("max_price") == 50_000_000

    def test_a_frame_rate_question_reads_the_benchmarks(self):
        understanding = understand_with_heuristics("۱۴۴ فریم در ۱۰۸۰p می‌خواهم")
        plan = plan_tools("۱۴۴ فریم", understanding)
        assert any(name == "get_benchmarks" for name, _ in plan)


# --- The orchestrator --------------------------------------------------------


class TestRunAgent:
    def test_it_asks_one_clarifying_question_and_stops(self, indexed):
        result = run_agent("یک سیستم خوب می‌خواهم", llm=ScriptedLLM())
        assert result.clarifying_question
        assert result.answer == ""
        assert result.tool_calls == []

    def test_it_answers_when_everything_is_known(self, indexed):
        result = run_agent(
            "قیمت سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون چقدر است؟",
            llm=ScriptedLLM("پاسخ [1]"),
        )
        assert not result.clarifying_question
        assert result.answer
        assert result.tool_calls

    def test_it_returns_product_cards(self, indexed):
        result = run_agent(
            "سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون",
            llm=ScriptedLLM("پاسخ [1]"),
        )
        assert result.cards
        card = result.cards[0]
        assert card.sku
        assert card.price
        assert card.entity_slug

    def test_it_returns_citations(self, indexed):
        result = run_agent(
            "سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون",
            llm=ScriptedLLM("پاسخ [1]"),
        )
        assert result.citations
        assert result.citations[0]["url"].startswith("/wiki/")

    def test_a_fabricated_price_is_blocked(self, indexed):
        result = run_agent(
            "قیمت سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون چقدر است؟",
            llm=ScriptedLLM("قیمت ۹۹۹۹۹۹۹۹۹۹ تومان [1]."),
        )
        assert "۹۹۹۹۹۹۹۹۹۹" not in result.answer
        assert result.guardrails["ok"] is False

    def test_a_price_from_the_tools_passes(self, indexed):
        result = run_agent(
            "قیمت سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون چقدر است؟",
            llm=ScriptedLLM("قیمت ۳۹۵۰۰۰۰۰ تومان [1]."),
        )
        assert result.guardrails["facts"]["ok"] is True

    def test_the_turn_is_logged(self, indexed):
        result = run_agent("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون", llm=ScriptedLLM("پاسخ [1]"))
        assert result.query_log_id

    def test_the_log_records_the_understanding(self, indexed):
        from apps.ai.models import QueryLog

        result = run_agent("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون", llm=ScriptedLLM("پاسخ [1]"))
        log = QueryLog.objects.get(id=result.query_log_id)
        assert log.understood["resolution"] == "1080p"
        assert log.understood["budget_max"] == 50_000_000

    def test_the_prompt_lists_the_tools(self, indexed):
        llm = ScriptedLLM("پاسخ [1]")
        run_agent("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون", llm=llm)
        system = next(m for m in llm.seen if m.role == "system")
        assert "search_products" in system.content
        assert "check_compatibility" in system.content
        assert "<<<CONTEXT>>>" in system.content


class TestHelpers:
    def test_the_context_holds_the_tool_output(self, indexed):
        results = [search_wiki("حافظه DDR5 چیست؟", limit=3)]
        context = build_context(results)
        assert "search_wiki" in context
        assert len(context) > 50

    def test_the_facts_come_from_the_tools(self, indexed):
        results = [search_products(entity_type="prebuilt", limit=3)]
        facts = tool_facts(results)
        assert facts
        assert any("IRT" in fact for fact in facts)

    def test_the_cards_are_built_from_the_products(self, indexed):
        results = [search_products(entity_type="prebuilt", limit=3)]
        cards = cards_from(results)
        assert cards
        assert cards[0].sku

    def test_the_citations_are_built_from_the_wiki(self, indexed):
        results = [search_wiki("حافظه DDR5 چیست؟", limit=3)]
        citations = citations_from(results)
        assert citations
        assert citations[0]["index"] == 1


class TestChatApi:
    def test_the_json_answer_carries_the_cards(self, api, indexed):
        response = api.post(
            reverse("ai:chat"),
            {"query": "سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون", "stream": False},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["cards"]
        assert response.data["citations"]
        assert response.data["understanding"]["resolution"] == "1080p"

    def test_the_clarifying_question_short_circuits(self, api, indexed):
        response = api.post(
            reverse("ai:chat"),
            {"query": "یک سیستم خوب می‌خواهم", "stream": False},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["clarifying_question"]
        assert response.data["tool_calls"] == []

    def test_the_stream_emits_the_events(self, api, indexed):
        response = api.post(
            reverse("ai:chat"),
            {"query": "سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون", "stream": True},
            format="json",
        )
        assert response.status_code == 200
        body = b"".join(response.streaming_content).decode("utf-8")
        assert "event: citations" in body
        assert "event: token" in body
        assert "event: done" in body


class TestCompare:
    def test_it_compares_two_products(self, api, indexed):
        response = api.post(
            reverse("ai:compare"),
            {"skus": ["tb-sku-vanguard-1080", "tb-sku-striker-1080"]},
            format="json",
        )
        assert response.status_code == 200
        assert len(response.data["products"]) == 2
        assert response.data["specs"]
        assert response.data["products"][0]["price"]

    def test_it_needs_two_skus(self, api, indexed):
        response = api.post(
            reverse("ai:compare"), {"skus": ["tb-sku-vanguard-1080"]}, format="json"
        )
        assert response.status_code == 400

    def test_an_unknown_sku_is_a_404(self, api, indexed):
        response = api.post(
            reverse("ai:compare"),
            {"skus": ["tb-sku-vanguard-1080", "not-a-sku"]},
            format="json",
        )
        assert response.status_code == 404

    def test_it_carries_the_benchmarks(self, api, indexed):
        response = api.post(
            reverse("ai:compare"),
            {"skus": ["tb-sku-vanguard-1080", "tb-sku-striker-1080"]},
            format="json",
        )
        assert "benchmarks" in response.data
