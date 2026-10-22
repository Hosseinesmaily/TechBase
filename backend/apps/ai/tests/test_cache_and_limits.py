"""Tests for the semantic cache and the rate limiter."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.ai.cache import find_similar, invalidate, stats
from apps.ai.orchestrator import run_agent
from apps.core.models import RateLimitCounter
from apps.core.throttling import _parse_rate, check, reset

pytestmark = pytest.mark.django_db


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def indexed():
    call_command("seed_demo", verbosity=0)
    call_command("seed_wiki", verbosity=0)
    call_command("index_content", verbosity=0)
    return True


class TestParseRate:
    def test_it_reads_the_per_minute_form(self):
        assert _parse_rate("20/min") == 20
        assert _parse_rate("120/minute") == 120
        assert _parse_rate("60/m") == 60

    def test_a_bare_number_works(self):
        assert _parse_rate("30") == 30

    def test_a_nonsense_value_falls_back(self):
        assert _parse_rate("abc") == 60

    def test_it_never_returns_zero(self):
        assert _parse_rate("0/min") == 1


class TestRateLimiting:
    def test_a_request_within_the_limit_is_allowed(self, api):
        from django.test import RequestFactory

        request = RequestFactory().get("/api/v1/catalog/products/")
        result = check(request)
        assert result.allowed
        assert result.remaining >= 0

    def test_the_chat_scope_is_tighter(self, api):
        from django.test import RequestFactory

        catalog = check(RequestFactory().get("/api/v1/catalog/products/"))
        chat = check(RequestFactory().post("/api/v1/ai/chat/"))
        assert chat.limit < catalog.limit

    def test_the_limit_is_eventually_enforced(self, api, settings):
        from django.test import RequestFactory

        settings.REST_FRAMEWORK = {
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {"anon": "3/min", "chat": "2/min"},
        }
        request = RequestFactory().get("/api/v1/catalog/products/")
        reset(request)
        # Redis is usually unavailable in the tests → the database fallback.
        allowed = [check(request).allowed for _ in range(5)]
        assert allowed.count(False) >= 1
        reset(request)

    def test_the_counter_is_kept(self, api, settings):
        from django.test import RequestFactory

        settings.REST_FRAMEWORK = {
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {"anon": "3/min", "chat": "2/min"},
        }
        request = RequestFactory().get("/api/v1/catalog/products/")
        reset(request)
        check(request)
        assert RateLimitCounter.objects.filter(key__contains="anon").exists()
        reset(request)

    def test_an_over_limit_request_gets_a_429(self, api, settings):
        from django.test import RequestFactory

        settings.REST_FRAMEWORK = {
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {"anon": "1/min", "chat": "1/min"},
        }
        request = RequestFactory().get("/api/v1/catalog/products/")
        reset(request)
        check(request)
        response = api.get("/api/v1/catalog/products/")
        assert response.status_code == 429
        assert response["Retry-After"]
        reset(request)

    def test_the_headers_are_set(self, api):
        response = api.get("/api/v1/catalog/products/")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response
        assert "X-RateLimit-Remaining" in response


class TestSemanticCache:
    def test_a_repeated_question_is_served_from_the_cache(self, indexed):
        from apps.ai.tests.test_agentic import ScriptedLLM

        query = "سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون"
        first = run_agent(query, llm=ScriptedLLM("پاسخ اول [1]."))
        second = run_agent(query, llm=ScriptedLLM("پاسخ اول [1]."))
        assert second.guardrails.get("cached") is True
        assert second.answer == first.answer

    def test_a_different_question_is_not_cached(self, indexed):
        from apps.ai.tests.test_agentic import ScriptedLLM

        run_agent("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون", llm=ScriptedLLM("پاسخ [1]."))
        other = run_agent("سیستم گیمینگ ۱۴۴۰p با بودجه ۹۰ میلیون", llm=ScriptedLLM("پاسخ [1]."))
        assert other.guardrails.get("cached") is not True

    def test_a_clarifying_turn_is_not_cached(self, indexed):
        from apps.ai.tests.test_agentic import ScriptedLLM

        result = run_agent("یک سیستم خوب می‌خواهم", llm=ScriptedLLM())
        assert result.clarifying_question
        # The same question again must ask again, not serve a cached question.
        again = run_agent("یک سیستم خوب می‌خواهم", llm=ScriptedLLM())
        assert again.clarifying_question

    def test_a_failed_guardrail_is_not_cached(self, indexed):
        from apps.ai.tests.test_agentic import ScriptedLLM

        query = "قیمت سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون چقدر است؟"
        run_agent(query, llm=ScriptedLLM("قیمت ۹۹۹۹۹۹۹۹۹۹ تومان [1]."))
        again = run_agent(query, llm=ScriptedLLM("قیمت ۹۹۹۹۹۹۹۹۹۹ تومان [1]."))
        assert again.guardrails.get("cached") is not True

    def test_the_cache_can_be_invalidated(self, indexed):
        from apps.ai.tests.test_agentic import ScriptedLLM

        query = "سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون"
        run_agent(query, llm=ScriptedLLM("پاسخ [1]."))
        invalidate()
        again = run_agent(query, llm=ScriptedLLM("پاسخ [1]."))
        assert again.guardrails.get("cached") is not True

    def test_the_stats_report_the_cache_size(self, indexed):
        from apps.ai.tests.test_agentic import ScriptedLLM

        run_agent("سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون", llm=ScriptedLLM("پاسخ [1]."))
        report = stats()
        assert report["total_turns"] > 0
        assert report["cached_turns"] > 0

    def test_find_similar_returns_none_for_an_unknown_question(self, indexed):
        assert find_similar("یک سؤال کاملاً بی‌ربط") is None
