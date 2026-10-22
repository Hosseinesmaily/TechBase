"""Tests for the privacy scrubber and the tracing."""

from __future__ import annotations

import logging

import pytest

from apps.core.log_filters import ScrubFilter
from apps.core.observability import Trace, trace_middleware
from apps.core.privacy import scrub, scrub_dict


class TestScrub:
    def test_an_email_is_removed(self):
        assert "ali@example.com" not in scrub("سوال من به ali@example.com است")
        assert "[email]" in scrub("سوال من به ali@example.com است")

    def test_a_phone_number_is_removed(self):
        scrubbed = scrub("شمارهٔ من 09121234567 است")
        assert "09121234567" not in scrubbed
        assert "[phone]" in scrubbed

    def test_a_phone_number_with_separators(self):
        scrubbed = scrub("شماره 0912 123 4567")
        assert "0912 123 4567" not in scrubbed

    def test_a_card_number_is_removed(self):
        scrubbed = scrub("کارت 4111 1111 1111 1111 است")
        assert "4111 1111 1111 1111" not in scrubbed

    def test_an_ip_is_removed(self):
        scrubbed = scrub("از 192.168.1.1 آمده")
        assert "192.168.1.1" not in scrubbed

    def test_an_ordinary_question_is_untouched(self):
        text = "بهترین کارت گرافیک برای ۱۴۴۰p کدام است؟"
        assert scrub(text) == text

    def test_a_persian_number_is_not_a_phone(self):
        """A price like ۳۲۹۰۰۰۰۰۰ must survive."""
        text = "قیمت ۳۲۹۰۰۰۰۰۰ تومان است"
        assert "۳۲۹۰۰۰۰۰۰" in scrub(text)

    def test_empty_text(self):
        assert scrub("") == ""

    def test_a_dictionary_is_scrubbed(self):
        data = {"query": "به ali@example.com", "count": 3}
        scrubbed = scrub_dict(data)
        assert "ali@example.com" not in scrubbed["query"]
        assert scrubbed["count"] == 3


class TestScrubFilter:
    def test_it_scrubs_the_message(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="کاربر به ali@example.com نوشت",
            args=(),
            exc_info=None,
        )
        ScrubFilter().filter(record)
        assert "ali@example.com" not in record.getMessage()

    def test_it_keeps_the_arguments(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="کاربر %s نوشت",
            args=("ali@example.com",),
            exc_info=None,
        )
        ScrubFilter().filter(record)
        assert "ali@example.com" not in record.getMessage()


class TestTrace:
    def test_a_span_is_timed(self):
        trace = Trace("turn")
        with trace.span("retrieve", limit=6):
            pass
        assert trace.spans[0].name == "retrieve"
        assert trace.spans[0].duration_ms >= 0

    def test_a_span_records_the_attributes(self):
        trace = Trace("turn")
        with trace.span("retrieve", limit=6):
            pass
        assert trace.spans[0].attributes["limit"] == 6

    def test_a_failing_span_records_the_error(self):
        trace = Trace("turn")
        with pytest.raises(ValueError), trace.span("retrieve"):
            raise ValueError("boom")
        assert trace.spans[0].error == "boom"

    def test_the_trace_has_an_id(self):
        assert Trace("turn").id

    def test_the_trace_serialises(self):
        trace = Trace("turn")
        trace.set(cached=True)
        data = trace.as_dict()
        assert data["name"] == "turn"
        assert data["attributes"]["cached"] is True


class TestTraceMiddleware:
    def test_it_adds_a_trace_header(self, rf):
        middleware = trace_middleware(
            lambda request: __import__("django.http", fromlist=["HttpResponse"]).HttpResponse("ok")
        )
        request = rf.get("/api/v1/catalog/products/")
        response = middleware(request)
        assert response["X-Trace-Id"]

    def test_it_keeps_an_incoming_trace_id(self, rf):
        middleware = trace_middleware(
            lambda request: __import__("django.http", fromlist=["HttpResponse"]).HttpResponse("ok")
        )
        request = rf.get("/api/v1/catalog/products/", headers={"X-Trace-Id": "abc123"})
        response = middleware(request)
        assert response["X-Trace-Id"] == "abc123"
