"""Health and readiness endpoints."""

from __future__ import annotations

import logging

import redis as redis_lib
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health(_request) -> JsonResponse:
    """Liveness: process is up. No dependency checks."""
    return JsonResponse({"status": "ok"})


@require_GET
def ready(_request) -> JsonResponse:
    """Readiness: database + Redis reachable. Returns 503 with per-check detail."""
    checks: dict[str, str] = {}

    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception as exc:  # report any driver error
        logger.warning("readiness: database failed: %s", exc)
        checks["database"] = f"error: {exc.__class__.__name__}"

    if not settings.REDIS_URL:
        checks["redis"] = "not configured"
    else:
        try:
            client = redis_lib.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
            client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            logger.warning("readiness: redis failed: %s", exc)
            checks["redis"] = f"error: {exc.__class__.__name__}"

    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )
