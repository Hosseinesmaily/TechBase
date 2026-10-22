"""Shared abstract models and helpers for all apps."""

from __future__ import annotations

import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """created_at / updated_at mixin."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """UUID primary key mixin."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class RateLimitCounter(TimeStampedModel):
    """The database fallback for the rate limiter.

    Only used when Redis is unreachable — it is slower, but the limit still
    holds.
    """

    key = models.CharField(max_length=255, unique=True)
    count = models.PositiveIntegerField(default=0)
    # The minute the counter belongs to.
    window = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "rate limit counter"
        verbose_name_plural = "rate limit counters"

    def __str__(self) -> str:
        return f"{self.key}={self.count}"
