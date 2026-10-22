"""Service layer: bridge between the DB (rules) and the pure engine.

This is the only place that knows both worlds. The engine stays pure so it can
be unit-tested without a database.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Entity

from .engine import (
    REGISTRY,
    CheckContext,
    Finding,
    PartContext,
    Rule,
    build_context,
    overall_verdict,
    run_rules,
)


@dataclass
class CompatibilityReport:
    verdict: str
    findings: list[Finding]
    checked: list[str]  # slugs that were actually evaluated

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "findings": [f.as_dict() for f in self.findings],
            "checked": self.checked,
        }


def _load_parts(slugs: list[str]) -> tuple[list[PartContext], list[str]]:
    """Load parts by slug, keeping the caller's order; report unknown slugs."""
    entities = {e.slug: e for e in Entity.objects.filter(slug__in=slugs).select_related("spec")}
    parts: list[PartContext] = []
    missing: list[str] = []
    for slug in slugs:
        entity = entities.get(slug)
        if entity is None:
            missing.append(slug)
            continue
        spec = getattr(entity, "spec", None)
        parts.append(
            PartContext(
                entity=entity,
                specs=dict(spec.common or {}) if spec else {},
            )
        )
    return parts, missing


def active_rules() -> list[Rule]:
    """Enabled rules from the DB, in order, mapped to their code implementations."""
    from .models import CompatibilityRule

    rules: list[Rule] = []
    for row in CompatibilityRule.objects.filter(enabled=True).order_by("order", "code"):
        implementation = REGISTRY.get(row.code)
        if implementation is None:
            continue
        # The DB row wins over the class defaults for severity and params.
        instance = type(implementation)()
        instance.default_severity = row.severity
        instance.params = {**getattr(implementation, "params", {}), **(row.params or {})}
        rules.append(instance)
    return rules


def rule_params() -> dict:
    """Global tunables only. Per-rule params live on the rule instance."""
    from .models import CompatibilityRule

    params: dict = {}
    for row in CompatibilityRule.objects.filter(enabled=True).order_by("order", "code"):
        if row.code == "PSU_WATTAGE":
            params.update(row.params or {})
    return params


def check_parts(slugs: list[str]) -> CompatibilityReport:
    """Check a set of parts for compatibility.

    `slugs` are entity slugs (e.g. `["ryzen-7-7800x3d", "b650-motherboard"]`).
    Unknown slugs are reported, not silently dropped.
    """
    slugs = [s for s in dict.fromkeys(slugs) if s]  # de-dupe, keep order
    parts, missing = _load_parts(slugs)

    ctx: CheckContext = build_context(parts, params=rule_params())
    findings = run_rules(ctx, active_rules())

    # Unknown slugs are a finding of their own — a silent drop would be a lie.
    for slug in missing:
        findings.append(
            Finding(
                rule_code="UNKNOWN_PART",
                severity="info",
                message=f"No catalog entry found for '{slug}'.",
                message_fa=f"برای «{slug}» هیچ موردی در کاتالوگ پیدا نشد.",
                a_slug=slug,
                b_slug="",
            )
        )

    return CompatibilityReport(
        verdict=overall_verdict(findings),
        findings=findings,
        checked=[p.slug for p in parts],
    )
