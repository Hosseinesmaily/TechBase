"""Observability: request tracing and optional Langfuse integration.

Every request gets a trace id, which appears in the log lines and in the
`X-Trace-Id` response header — so a user can report "the answer was wrong" and
the log can be traced back to that exact turn.

Langfuse is optional: without the keys, the tracing is a no-op and the local
spans are still recorded in the log.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

#: The header the trace id is sent in.
TRACE_HEADER = "X-Trace-Id"


@dataclass
class Span:
    """One timed step of a request."""

    name: str
    duration_ms: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "error": self.error,
        }


class Trace:
    """A trace: a set of spans belonging to one request or one turn."""

    def __init__(self, name: str, trace_id: str | None = None) -> None:
        self.name = name
        self.id = trace_id or uuid.uuid4().hex
        self.spans: list[Span] = []
        self.attributes: dict[str, Any] = {}
        self.started = time.perf_counter()

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Span]:
        """Time a step of the trace."""
        span = Span(name=name, attributes=attributes)
        started = time.perf_counter()
        try:
            yield span
        except Exception as exc:
            span.error = str(exc)
            raise
        finally:
            span.duration_ms = int((time.perf_counter() - started) * 1000)
            self.spans.append(span)

    def set(self, **attributes: Any) -> None:
        """Add an attribute to the trace."""
        self.attributes.update(attributes)

    @property
    def duration_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "spans": [span.as_dict() for span in self.spans],
        }

    def log(self) -> None:
        """Write the trace to the log."""
        logger.info(
            "trace %s %s %dms %s",
            self.id,
            self.name,
            self.duration_ms,
            self.attributes,
        )


# --- Langfuse (optional) ------------------------------------------------------

_langfuse_client: Any = None
_langfuse_checked = False


def _langfuse():
    """The Langfuse client, or None when it is not configured."""
    global _langfuse_client, _langfuse_checked
    if _langfuse_checked:
        return _langfuse_client
    _langfuse_checked = True

    public_key = getattr(settings, "LANGFUSE_PUBLIC_KEY", "")
    secret_key = getattr(settings, "LANGFUSE_SECRET_KEY", "")
    host = getattr(settings, "LANGFUSE_HOST", "")
    if not (public_key and secret_key and host):
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    except Exception as exc:
        logger.info("langfuse is not available: %s", exc)
        _langfuse_client = None
    return _langfuse_client


def trace_turn(name: str, **attributes: Any) -> Trace:
    """Start a trace for a turn, and send it to Langfuse when configured."""
    trace = Trace(name, **attributes)
    client = _langfuse()
    if client is not None:
        try:
            client.trace(name=name, id=trace.id, metadata=attributes)
        except Exception as exc:
            logger.info("could not start the langfuse trace: %s", exc)
    return trace


def record_token_usage(trace: Trace, *, input_tokens: int, output_tokens: int) -> None:
    """Record what the turn cost."""
    trace.set(input_tokens=input_tokens, output_tokens=output_tokens)
    client = _langfuse()
    if client is not None:
        try:
            client.generation(
                name=trace.name,
                trace_id=trace.id,
                usage_details={"input": input_tokens, "output": output_tokens},
            )
        except Exception as exc:
            logger.info("could not record the langfuse usage: %s", exc)


def trace_middleware(get_response):
    """Add a trace id to every API response.

    The trace id is generated per request and echoed in the `X-Trace-Id`
    header, so a report can be matched to a log line.
    """

    def middleware(request):
        trace_id = request.headers.get(TRACE_HEADER) or uuid.uuid4().hex
        request.trace_id = trace_id
        response = get_response(request)
        response[TRACE_HEADER] = trace_id
        return response

    return middleware
