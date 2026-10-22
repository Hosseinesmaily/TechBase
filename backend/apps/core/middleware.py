"""The rate-limiting middleware.

It sits in front of the whole API: a request over its limit gets a 429 with
the standard headers, and the body says how long to wait.
"""

from __future__ import annotations

import logging

from django.http import JsonResponse

from .throttling import check

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """Limit the request rate per identity and scope.

    The scope comes from the path: the assistant (`/api/v1/ai/`) has its own,
    much tighter limit than the read-only endpoints.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        result = check(request)
        if not result.allowed:
            logger.warning("rate limit hit: scope=%s path=%s", result.scope, request.path)
            response = JsonResponse(
                {
                    "error": "too many requests",
                    "scope": result.scope,
                    "limit": result.limit,
                    "retry_after": result.retry_after,
                },
                status=429,
            )
        else:
            response = self.get_response(request)

        if result.limit:
            response["X-RateLimit-Limit"] = str(result.limit)
            response["X-RateLimit-Remaining"] = str(result.remaining)
            response["X-RateLimit-Reset"] = str(result.reset_after)
        if not result.allowed:
            response["Retry-After"] = str(result.retry_after)
        return response
