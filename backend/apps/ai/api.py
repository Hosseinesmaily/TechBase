"""The chat API.

`POST /api/v1/ai/chat/` streams the answer as Server-Sent Events. The event
types are `citations`, `token`, `replace`, `guardrails`, `done` and `error`.
"""

from __future__ import annotations

import json

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .chat import answer_query, stream_answer
from .models import Feedback, QueryLog


class ChatView(APIView):
    """`POST /api/v1/ai/chat/`

    Body: `{"query": "...", "language": "fa", "stream": true}`

    With `stream: true` (the default) the response is an SSE stream; with
    `stream: false` it is a single JSON object.
    """

    def post(self, request) -> Response | StreamingHttpResponse:
        query = str(request.data.get("query", "")).strip()
        if not query:
            return Response({"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST)

        language = str(request.data.get("language", "fa"))[:8]
        limit = int(request.data.get("limit", 6))
        should_stream = request.data.get("stream", True)
        should_stream = should_stream not in (False, "false", "0", 0)

        if not should_stream:
            result = answer_query(query, limit=limit, language=language)
            return Response(result.as_dict())

        def event_stream():
            try:
                for event in stream_answer(query, limit=limit, language=language):
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"event: {event['type']}\ndata: {payload}\n\n"
            except Exception as exc:  # the stream must not die silently
                payload = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
                yield f"event: error\ndata: {payload}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


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
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ]
        )
