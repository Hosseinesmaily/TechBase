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
        # Rules see both halves: the hot keys live in `common`, the rest (PCIe
        # generation, PSU length, the board's memory ceiling) in `extra`.
        specs = {**(spec.common or {}), **(spec.extra or {})} if spec else {}
        parts.append(PartContext(entity=entity, specs=specs))
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


#: Persian labels for the entity types, so "not determined" can name the part the
#: user still has to choose instead of a vague "not enough data".
CATEGORY_LABELS = {
    "cpu": "پردازنده",
    "motherboard": "مادربرد",
    "ram": "حافظه",
    "gpu": "کارت گرافیک",
    "psu": "منبع تغذیه",
    "case": "کیس",
    "cooler": "خنک‌کننده",
    "storage": "ذخیره‌سازی",
    "prebuilt": "سیستم آماده",
}


def _missing_counterparts(entity_type: str, base_types: set[str], rules: list[Rule]) -> list[str]:
    """The parts a rule needs to judge this candidate but that are not chosen yet."""
    missing: list[str] = []
    for rule in rules:
        if entity_type not in {rule.category_a, rule.category_b}:
            continue
        counterpart = rule.category_b if rule.category_a == entity_type else rule.category_a
        if counterpart == entity_type or counterpart in base_types:
            continue
        label = CATEGORY_LABELS.get(counterpart, counterpart)
        if label not in missing:
            missing.append(label)
    return missing


def _unknown_reason(entity_type: str, base_types: set[str], rules: list[Rule]) -> str:
    """A specific Persian reason for "not determined" ('' when not applicable)."""
    if not any(entity_type in {rule.category_a, rule.category_b} for rule in rules):
        return "برای این دسته هنوز قاعدهٔ سازگاری ثبت نشده است."
    missing = _missing_counterparts(entity_type, base_types, rules)
    if not missing:
        return ""
    return "برای بررسی سازگاری، ابتدا این قطعات را انتخاب کنید: " + "، ".join(missing) + "."


def evaluate_candidates(base_slugs: list[str], candidate_slugs: list[str]) -> dict[str, dict]:
    """Evaluate every candidate against the parts that are already chosen.

    The configurator uses this to badge each card. The verdict comes from the
    same deterministic engine — the candidate is simply added to the current
    selection and the rules are run again; no display-only rule exists here.

    Only the findings that involve the candidate are reported: a problem between
    two *other* parts is not what the card in front of the user is about.

    `checked_rules` is the number of enabled rules that could actually compare the
    candidate with something already selected. Zero means "not enough information
    yet" (a PSU candidate while no GPU or prebuilt is chosen, for example), which
    is a different statement from "compatible" and must not be shown as one.
    """
    base_slugs = [slug for slug in dict.fromkeys(base_slugs) if slug]
    candidate_slugs = [slug for slug in dict.fromkeys(candidate_slugs) if slug]
    if not candidate_slugs:
        return {}

    base_parts, _ = _load_parts(base_slugs)
    base_types = {part.entity.type for part in base_parts}

    rules = active_rules()
    params = rule_params()

    entities = {
        entity.slug: entity
        for entity in Entity.objects.filter(slug__in=candidate_slugs).select_related("spec")
    }

    results: dict[str, dict] = {}
    for slug in candidate_slugs:
        entity = entities.get(slug)
        if entity is None:
            results[slug] = {
                "verdict": "unknown",
                "findings": [],
                "has_specs": False,
                "checked_rules": 0,
                "known": False,
                "reason": "این قطعه در کاتالوگ پیدا نشد.",
            }
            continue

        spec = getattr(entity, "spec", None)
        specs = {**(spec.common or {}), **(spec.extra or {})} if spec is not None else {}
        candidate = PartContext(entity=entity, specs=specs)

        findings = run_rules(
            build_context([*base_parts, candidate], params=params),
            rules,
        )
        relevant = [finding for finding in findings if slug in {finding.a_slug, finding.b_slug}]

        checked_rules = 0
        for rule in rules:
            if entity.type not in {rule.category_a, rule.category_b}:
                continue
            counterpart = rule.category_b if rule.category_a == entity.type else rule.category_a
            if counterpart in base_types:
                checked_rules += 1

        results[slug] = {
            "verdict": overall_verdict(relevant),
            "findings": [finding.as_dict() for finding in relevant],
            "has_specs": bool(specs),
            "checked_rules": checked_rules,
            "known": True,
            # An empty reason means "a decisive verdict was reached". A non-empty
            # one names the parts still missing, so the UI never dresses a
            # "not determined yet" card up as "compatible".
            "reason": _unknown_reason(entity.type, base_types, rules) if checked_rules == 0 else "",
        }

    return results
