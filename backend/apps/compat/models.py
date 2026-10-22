"""Compatibility rules: DB rows for enable/disable + parameters, code for logic.

The engine itself lives in `apps.compat.engine` and is pure Python with no LLM
involvement (docs/PLAN.md D6). Rules are data so they can be tuned without a
deploy, but the *decision logic* is code so it stays testable and explainable.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class RuleSeverity(models.TextChoices):
    """How bad it is when the rule fails."""

    BLOCK = "block", "ناسازگار"
    WARN = "warn", "هشدار"
    INFO = "info", "اطلاع"


class CompatibilityRule(UUIDModel, TimeStampedModel):
    """A single compatibility rule, e.g. SOCKET_MATCH between cpu and motherboard."""

    code = models.CharField(max_length=64, unique=True)
    category_a = models.CharField(max_length=64)  # entity type on the left
    category_b = models.CharField(max_length=64)  # entity type on the right
    description = models.CharField(max_length=255, blank=True)
    description_fa = models.CharField(max_length=255, blank=True)
    # Tunables: socket allow-lists, wattage headroom, length margins, ...
    params = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True, db_index=True)
    severity = models.CharField(
        max_length=16, choices=RuleSeverity.choices, default=RuleSeverity.BLOCK
    )
    # Rules run in this order; lower first.
    order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["order", "code"]
        verbose_name = "قاعدهٔ سازگاری"
        verbose_name_plural = "قواعد سازگاری"

    def __str__(self) -> str:
        return f"{self.code} [{self.category_a}×{self.category_b}]"
