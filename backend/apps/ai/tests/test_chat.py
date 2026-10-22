"""End-to-end chat tests: retrieval → prompt → answer → guardrails → citations.

The model is replaced by a scripted one, so the tests are deterministic and
assert the *behaviour* the spec demands rather than the wording of a model.
"""

from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ai.chat import answer_query, stream_answer
from apps.ai.llm import LLMResponse, Message, parse_json_response
from apps.ai.models import QueryLog

pytestmark = pytest.mark.django_db


class ScriptedLLM:
    """An LLM that returns a fixed answer — the test controls the model."""

    name = "scripted"

    def __init__(self, answer: str = "پاسخ آزمایشی [1]") -> None:
        self.answer = answer
        self.seen_messages: list[Message] = []

    def complete(self, messages: list[Message], *, max_tokens: int = 1024) -> LLMResponse:
        self.seen_messages = list(messages)
        return LLMResponse(text=self.answer, model="scripted", provider="scripted")

    def stream(self, messages: list[Message], *, max_tokens: int = 1024):
        self.seen_messages = list(messages)
        for index in range(0, len(self.answer), 10):
            yield self.answer[index : index + 10]


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def indexed():
    """A seeded catalog and wiki, chunked and embedded."""
    call_command("seed_demo", verbosity=0)
    call_command("seed_wiki", verbosity=0)
    call_command("index_content", verbosity=0)
    return True


class TestAnswerQuery:
    def test_it_answers_with_citations(self, indexed):
        result = answer_query("حافظه DDR5 چیست؟", llm=ScriptedLLM("حافظه DDR5 نسل پنجم است [1]."))
        assert result.answer
        assert result.citations
        assert result.citations[0]["page_slug"]
        assert result.citations[0]["url"].startswith("/wiki/")

    def test_a_question_with_no_answer_says_so(self, indexed):
        """A question the knowledge base cannot answer gets an honest reply."""
        result = answer_query("قیمت چای در تهران چند است؟", llm=ScriptedLLM("..."))
        # Either the retrieval found nothing (so the service says so), or it
        # found something and the guardrail replaced the uncited answer.
        assert result.citations == [] or result.guardrails["ok"] is False
        assert "متأسفم" in result.answer or "اطلاعات کافی" in result.answer

    def test_a_question_nothing_matches_gets_no_citation(self, indexed):
        result = answer_query(
            "دربارهٔ قوانین مهاجرت خودرو در ژاپن چه می‌دانید؟",
            llm=ScriptedLLM("..."),
        )
        assert "اطلاعات کافی" in result.answer
        assert result.citations == []

    def test_a_fabricated_price_is_blocked(self, indexed):
        """The model invents a price that is not in the tool results."""
        result = answer_query(
            "قیمت RTX 4070 SUPER چقدر است؟",
            llm=ScriptedLLM("قیمت این کارت ۹۹۹۹۹۹۹۹۹ تومان است [1]."),
        )
        assert "۹۹۹۹۹۹۹۹۹" not in result.answer
        assert result.guardrails["ok"] is False
        assert result.guardrails["facts"]["violations"]

    def test_a_price_from_the_tool_results_passes(self, indexed):
        result = answer_query(
            "قیمت RTX 4070 SUPER چقدر است؟",
            llm=ScriptedLLM("قیمت این کارت ۳۲۹۰۰۰۰۰ تومان است [1]."),
        )
        assert result.guardrails["facts"]["ok"] is True

    def test_the_prompt_tells_the_model_what_not_to_do(self, indexed):
        llm = ScriptedLLM("پاسخ [1].")
        answer_query("حافظه DDR5 چیست؟", llm=llm)
        system = next(m for m in llm.seen_messages if m.role == "system")
        assert "فقط" in system.content
        assert "CONTEXT" in system.content
        assert "<<<CONTEXT>>>" in system.content

    def test_the_query_is_logged(self, indexed):
        result = answer_query("حافظه DDR5 چیست؟", llm=ScriptedLLM("پاسخ [1]."))
        log = QueryLog.objects.get(id=result.query_log_id)
        assert log.raw_query == "حافظه DDR5 چیست؟"
        assert log.citations

    def test_the_language_is_recorded(self, indexed):
        result = answer_query("حافظه DDR5 چیست؟", llm=ScriptedLLM("پاسخ [1]."), language="fa")
        log = QueryLog.objects.get(id=result.query_log_id)
        assert log.language == "fa"


class TestStreamAnswer:
    def test_it_yields_the_citations_first(self, indexed):
        events = list(stream_answer("حافظه DDR5 چیست؟", llm=ScriptedLLM("پاسخ [1].")))
        assert events[0]["type"] == "citations"

    def test_it_yields_the_tokens(self, indexed):
        events = list(stream_answer("حافظه DDR5 چیست؟", llm=ScriptedLLM("پاسخ آزمایشی [1].")))
        tokens = [e for e in events if e["type"] == "token"]
        assert tokens
        assert "".join(t["text"] for t in tokens) == "پاسخ آزمایشی [1]."

    def test_it_ends_with_done(self, indexed):
        events = list(stream_answer("حافظه DDR5 چیست؟", llm=ScriptedLLM("پاسخ [1].")))
        assert events[-1]["type"] == "done"
        assert events[-1]["query_log_id"]

    def test_a_fabrication_triggers_a_replace_event(self, indexed):
        events = list(
            stream_answer(
                "قیمت RTX 4070 SUPER چقدر است؟",
                llm=ScriptedLLM("قیمت ۹۹۹۹۹۹۹۹۹ تومان [1]."),
            )
        )
        replaces = [e for e in events if e["type"] == "replace"]
        assert replaces
        assert "۹۹۹۹۹۹۹۹۹" not in replaces[0]["text"]

    def test_a_failing_model_produces_an_error_event(self, indexed):
        class BrokenLLM(ScriptedLLM):
            def stream(self, messages, *, max_tokens=1024):
                raise RuntimeError("model down")
                yield ""  # pragma: no cover

        events = list(stream_answer("حافظه DDR5 چیست؟", llm=BrokenLLM()))
        assert events[-1]["type"] == "error"
        assert "model down" in events[-1]["message"]


class TestChatApi:
    def test_a_json_answer(self, api, indexed, monkeypatch):
        monkeypatch.setattr(
            "apps.ai.chat.get_llm", lambda task="chat": ScriptedLLM("پاسخ آزمایشی [1].")
        )
        response = api.post(
            reverse("ai:chat"),
            {"query": "حافظه DDR5 چیست؟", "stream": False},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["answer"]
        assert response.data["citations"]

    def test_a_missing_query_is_a_bad_request(self, api, indexed):
        response = api.post(reverse("ai:chat"), {}, format="json")
        assert response.status_code == 400

    def test_the_stream_returns_sse_events(self, api, indexed, monkeypatch):
        monkeypatch.setattr(
            "apps.ai.chat.get_llm", lambda task="chat": ScriptedLLM("پاسخ آزمایشی [1].")
        )
        response = api.post(
            reverse("ai:chat"),
            {"query": "حافظه DDR5 چیست؟", "stream": True},
            format="json",
        )
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/event-stream")
        body = b"".join(response.streaming_content).decode("utf-8")
        assert "event: citations" in body
        assert "event: token" in body
        assert "event: done" in body
        # Every event carries valid JSON.
        for line in body.splitlines():
            if line.startswith("data: "):
                json.loads(line[6:])

    def test_feedback_is_recorded(self, api, indexed):
        response = api.post(
            reverse("ai:feedback"),
            {"query_log_id": "", "thumbs": 1, "comment": "خوب بود"},
            format="json",
        )
        assert response.status_code == 201
        assert response.data["thumbs"] == 1

    def test_feedback_rejects_an_invalid_thumb(self, api, indexed):
        response = api.post(reverse("ai:feedback"), {"thumbs": 5}, format="json")
        assert response.status_code == 400


class TestParseJsonResponse:
    def test_plain_json(self):
        assert parse_json_response('{"a": 1}') == {"a": 1}

    def test_json_in_a_code_fence(self):
        assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}

    def test_json_with_surrounding_text(self):
        assert parse_json_response('این است: {"a": 1} پایان') == {"a": 1}

    def test_invalid_json_returns_none(self):
        assert parse_json_response("no json here") is None

    def test_empty_text(self):
        assert parse_json_response("") is None
