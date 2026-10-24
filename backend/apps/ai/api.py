"""The chat and comparison API.

`POST /api/v1/ai/chat/` — the agentic turn.

  * `stream: false` → one JSON object with the answer, the product cards and
    the citations.
  * `stream: true` (the default) → an SSE stream of the same events as the
    RAG MVP, plus a `cards` event.

`POST /api/v1/ai/chat/feedback/` — a thumbs up/down.
`POST /api/v1/ai/compare/` — two products side by side.
`GET /api/v1/ai/logs/` — the recent questions (staff).
"""

from __future__ import annotations

import json

from django.http import StreamingHttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.benchmarks.models import Benchmark
from apps.catalog.models import Product

from .models import Feedback, QueryLog
from .orchestrator import run_agent


class ChatView(APIView):
    """`POST /api/v1/ai/chat/`

    Body: `{"query": "...", "language": "fa", "stream": true, "ask_clarifying": true}`
    """

    # Chat is intentionally public and rate-limited by IP. Ignore Django admin
    # session cookies: SessionAuthentication would require a CSRF token that
    # the same-origin SSE client does not need to send for this public endpoint.
    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]

    def post(self, request) -> Response | StreamingHttpResponse:
        query = str(request.data.get("query", "")).strip()
        if not query:
            return Response({"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST)

        language = str(request.data.get("language", "fa"))[:8]
        limit = int(request.data.get("limit", 6))
        ask_clarifying = request.data.get("ask_clarifying", True)
        ask_clarifying = ask_clarifying not in (False, "false", 0, "0")
        should_stream = request.data.get("stream", True)
        should_stream = should_stream not in (False, "false", 0, "0")

        if not should_stream:
            result = run_agent(
                query,
                limit=limit,
                language=language,
                ask_clarifying=ask_clarifying,
            )
            return Response(result.as_dict())

        def event_stream():
            # The agentic turn is computed first (the tools are fast), then the
            # answer is streamed. The clarification path short-circuits.
            result = run_agent(
                query,
                limit=limit,
                language=language,
                ask_clarifying=ask_clarifying,
            )
            yield _event(
                {
                    "type": "citations",
                    "citations": result.citations,
                    "cards": [card.as_dict() for card in result.cards],
                    "understanding": result.understanding,
                }
            )
            if result.clarifying_question:
                yield _event(
                    {
                        "type": "clarifying_question",
                        "question": result.clarifying_question,
                    }
                )
            else:
                # The answer arrives in one piece; the token events let the
                # client render it progressively.
                for index in range(0, len(result.answer), 40):
                    yield _event({"type": "token", "text": result.answer[index : index + 40]})
            yield _event({"type": "guardrails", "guardrails": result.guardrails})
            yield _event(
                {
                    "type": "done",
                    "latency_ms": result.latency_ms,
                    "query_log_id": result.query_log_id,
                }
            )

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


def _event(payload: dict) -> str:
    """One SSE frame."""
    return f"event: {payload['type']}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ChatFeedbackView(APIView):
    """`POST /api/v1/ai/chat/feedback/` — a thumbs up/down on an answer."""

    def post(self, request) -> Response:
        query_log_id = request.data.get("query_log_id")
        thumbs = request.data.get("thumbs")
        comment = str(request.data.get("comment", ""))

        try:
            thumbs = int(thumbs)
        except (TypeError, ValueError):
            return Response({"error": "thumbs must be 1 or -1"}, status=status.HTTP_400_BAD_REQUEST)
        if thumbs not in (1, -1):
            return Response({"error": "thumbs must be 1 or -1"}, status=status.HTTP_400_BAD_REQUEST)

        query_log = None
        if query_log_id:
            query_log = QueryLog.objects.filter(id=query_log_id).first()

        feedback = Feedback.objects.create(
            query_log=query_log,
            thumbs=thumbs,
            comment=comment,
            language=str(request.data.get("language", "fa"))[:8],
        )
        return Response(
            {"id": str(feedback.id), "thumbs": feedback.thumbs}, status=status.HTTP_201_CREATED
        )


class QueryLogListView(APIView):
    """`GET /api/v1/ai/logs/` — the recent questions. Staff only."""

    def get(self, request) -> Response:
        if not (request.user.is_authenticated and request.user.is_staff):
            return Response({"error": "staff only"}, status=status.HTTP_403_FORBIDDEN)

        logs = QueryLog.objects.all()[:50]
        return Response(
            [
                {
                    "id": str(log.id),
                    "query": log.raw_query,
                    "language": log.language,
                    "latency_ms": log.latency_ms,
                    "citations": len(log.citations or []),
                    "understood": log.understood,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ]
        )


class CompareView(APIView):
    """`POST /api/v1/ai/compare/`

    Body: `{"skus": ["tb-sku-vanguard-1080", "tb-sku-striker-1080"]}`

    Compares two (or more) products side by side: the price, the stock, the
    specs and the measured frame rates — everything from the catalog and the
    benchmark table, never from a model.
    """

    def post(self, request) -> Response:
        skus = [str(sku) for sku in request.data.get("skus", [])][:4]
        if len(skus) < 2:
            return Response(
                {"error": "give at least two SKUs to compare"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = {
            product.sku: product
            for product in Product.objects.filter(sku__in=skus, is_active=True).select_related(
                "entity", "entity__brand"
            )
        }
        missing = [sku for sku in skus if sku not in products]
        if missing:
            return Response(
                {"error": f"unknown SKUs: {', '.join(missing)}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        rows = [self._product_row(products[sku]) for sku in skus]

        # The specs to compare: the union of the entities' spec keys.
        spec_keys: list[str] = []
        for sku in skus:
            spec = getattr(products[sku].entity, "spec", None)
            if spec is None:
                continue
            for key in spec.common or {}:
                if key not in spec_keys:
                    spec_keys.append(key)

        comparison = []
        for key in spec_keys:
            values = []
            for sku in skus:
                spec = getattr(products[sku].entity, "spec", None)
                value = None
                if spec is not None:
                    merged = {**(spec.common or {}), **(spec.extra or {})}
                    value = merged.get(key)
                values.append(value)
            comparison.append({"key": key, "values": values})

        return Response(
            {
                "products": rows,
                "specs": comparison,
                "benchmarks": self._benchmarks(skus),
            }
        )

    def _product_row(self, product: Product) -> dict:
        entity = product.entity
        return {
            "sku": product.sku,
            "title": product.display_title,
            "entity_slug": entity.slug,
            "entity_type": entity.type,
            "brand": entity.brand.name if entity.brand is not None else "",
            "price": str(product.price),
            "currency": product.currency,
            "stock": product.stock,
            "in_stock": product.in_stock,
            "updated_at": product.updated_at.isoformat(),
        }

    def _benchmarks(self, skus: list[str]) -> list[dict]:
        """The frame rates of the compared components, side by side."""
        entities = list(Product.objects.filter(sku__in=skus).values_list("entity", flat=True))
        rows = (
            Benchmark.objects.filter(component__in=entities)
            .select_related("component")
            .order_by("game", "resolution")
        )
        return [
            {
                "component": row.component.slug,
                "game": row.game,
                "game_fa": row.game_fa,
                "resolution": row.resolution,
                "avg_fps": row.avg_fps,
                "p1_low": row.p1_low,
            }
            for row in rows
        ]
