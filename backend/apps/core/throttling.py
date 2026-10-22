"""Rate limiting.

The assistant costs money per turn, so it needs a tighter limit than the
read-only catalog endpoints. The limiter is a fixed-window counter in Redis
when Redis is up, and a database-backed one when it is not — the limit must
hold even in a degraded deployment.

Scopes:
  * `anon`  — the general API (catalog, search, wiki).
  * `chat`  — the assistant. Deliberately much tighter.
  * `staff` — no limit; the editorial team is not a customer.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import cast

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Whether the request is allowed, and what the caller should be told."""

    allowed: bool
    limit: int
    remaining: int
    reset_after: int
    scope: str = "anon"

    @property
    def retry_after(self) -> int:
        return max(1, self.reset_after)


def _client():
    """The Redis client, or None when Redis is unreachable."""
    try:
        import redis

        return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
    except Exception as exc:  # not installed, bad URL, …
        logger.warning("redis is unavailable for rate limiting: %s", exc)
        return None


def _identity(request) -> str:
    """Who the request is from: the user id, or the IP address."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"user:{user.pk}"
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def _scope_for(request) -> str:
    """The scope the request falls into."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff:
        return "staff"
    path = request.path or ""
    if path.startswith("/api/v1/ai/"):
        return "chat"
    return "anon"


def _rate_for(scope: str) -> int:
    """The number of requests allowed per minute for a scope."""
    rates = cast(dict, settings.REST_FRAMEWORK).get("DEFAULT_THROTTLE_RATES", {})
    if scope == "staff":
        return 0  # unlimited
    return _parse_rate(str(rates.get(scope, rates.get("anon", "60/min"))))


def _parse_rate(rate: str) -> int:
    """Turn "20/min" into 20.

    Only the per-minute form is supported: a window other than a minute would
    need a second counter and buys nothing here.
    """
    text = rate.strip().lower()
    if "/" in text:
        number, _, period = text.partition("/")
        if period not in {"min", "minute", "m"}:
            logger.warning("unsupported rate window %r — using per minute", rate)
        try:
            return max(1, int(number))
        except ValueError:
            return 60
    try:
        return max(1, int(text))
    except ValueError:
        return 60


def check(request, scope: str | None = None) -> RateLimitResult:
    """Whether this request is within its limit."""
    scope = scope or _scope_for(request)
    limit = _rate_for(scope)
    if limit <= 0:
        return RateLimitResult(allowed=True, limit=0, remaining=0, reset_after=0, scope=scope)

    identity = _identity(request)
    window = int(time.time() // 60)
    key = f"ratelimit:{scope}:{identity}:{window}"
    reset_after = 60 - int(time.time() % 60)

    client = _client()
    if client is not None:
        try:
            pipeline = client.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, 120)
            count = pipeline.execute()[0]
            return RateLimitResult(
                allowed=count <= limit,
                limit=limit,
                remaining=max(0, limit - count),
                reset_after=reset_after,
                scope=scope,
            )
        except Exception as exc:
            logger.warning("redis rate limiting failed, falling back to the database: %s", exc)

    return _database_check(identity, scope, limit, reset_after)


def _database_check(identity: str, scope: str, limit: int, reset_after: int) -> RateLimitResult:
    """The database-backed fallback — slower, but it always works."""
    from .models import RateLimitCounter

    key = f"{scope}:{identity}"
    counter = RateLimitCounter.objects.get_or_create(
        key=key,
        defaults={"count": 0, "window": int(time.time() // 60)},
    )[0]
    now_window = int(time.time() // 60)
    if counter.window != now_window:
        counter.window = now_window
        counter.count = 0

    counter.count += 1
    counter.save(update_fields=["window", "count"])
    return RateLimitResult(
        allowed=counter.count <= limit,
        limit=limit,
        remaining=max(0, limit - counter.count),
        reset_after=reset_after,
        scope=scope,
    )


def reset(request) -> None:
    """Clear the counters of an identity (used by the tests)."""
    scope = _scope_for(request)
    identity = _identity(request)
    client = _client()
    if client is not None:
        try:
            keys = list(client.scan_iter(f"ratelimit:{scope}:{identity}:*"))
            if keys:
                client.delete(*keys)
            return
        except Exception as exc:
            logger.warning("could not reset the redis rate limit: %s", exc)

    from .models import RateLimitCounter

    RateLimitCounter.objects.filter(key=f"{scope}:{identity}").delete()
