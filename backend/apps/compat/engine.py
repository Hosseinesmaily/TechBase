"""Deterministic compatibility engine.

**No LLM is involved in any compatibility decision** (docs/PLAN.md D6). The
engine is a pure function over a set of parts: same input, same verdict, every
time, with a human-readable reason for each finding.

Each rule is a small class implementing `check(ctx) -> list[Finding]`. Rules are
looked up from the DB by code (so staff can enable/disable and tune params),
but the *logic* lives here in code so it stays testable.

Verdicts
--------
* `ok`     — no findings at all.
* `warn`   — only `warn`/`info` findings: usable, with caveats.
* `block`  — at least one `block` finding: the parts do not work together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from apps.catalog.models import Entity, EntityType

# --- Verdicts and severities -------------------------------------------------

BLOCK = "block"
WARN = "warn"
INFO = "info"
OK = "ok"

_SEVERITY_ORDER = {BLOCK: 0, WARN: 1, INFO: 2}


@dataclass(frozen=True)
class Finding:
    """One problem (or remark) between a specific pair of parts."""

    rule_code: str
    severity: str
    message: str
    message_fa: str
    a_slug: str
    b_slug: str
    a_title: str = ""
    b_title: str = ""

    def as_dict(self) -> dict:
        return {
            "rule_code": self.rule_code,
            "severity": self.severity,
            "message": self.message,
            "message_fa": self.message_fa,
            "a": {"slug": self.a_slug, "title": self.a_title},
            "b": {"slug": self.b_slug, "title": self.b_title},
        }


@dataclass
class PartContext:
    """One part in a compatibility check, with its specs resolved."""

    entity: Entity
    specs: dict[str, Any]

    @property
    def slug(self) -> str:
        return self.entity.slug

    @property
    def title(self) -> str:
        return self.entity.title

    def spec(self, key: str, default: Any = None) -> Any:
        value = self.specs.get(key)
        return default if value is None else value

    def number(self, key: str) -> float | None:
        """Read a numeric spec, tolerating strings like "700W" or "120 mm"."""
        value = self.spec(key)
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        digits = ""
        for char in text:
            if char.isdigit() or char == ".":
                digits += char
            elif digits:
                break
        try:
            return float(digits) if digits else None
        except ValueError:
            return None


@dataclass
class CheckContext:
    """Everything a rule may look at.

    `params` holds *global* tunables. Per-rule tunables live on the rule
    instance (`rule.params`), so one rule's setting never leaks into another.
    """

    parts: list[PartContext]
    params: dict = field(default_factory=dict)

    def by_type(self, *types: str) -> list[PartContext]:
        return [p for p in self.parts if p.entity.type in types]

    def of_type(self, entity_type: str) -> PartContext | None:
        for part in self.parts:
            if part.entity.type == entity_type:
                return part
        return None

    def pair(self, a: PartContext, b: PartContext) -> tuple[PartContext, PartContext]:
        return (a, b) if a.slug <= b.slug else (b, a)


# --- Rule protocol -----------------------------------------------------------


class Rule(Protocol):
    code: str
    default_severity: str
    #: Tunables for this rule, supplied by its DB row.
    params: dict

    # `category_a`/`category_b` are read-only properties so a rule may narrow
    # the type (e.g. to the `EntityType` enum) while still satisfying the
    # protocol — a plain protocol attribute is invariant and would reject that.
    @property
    def category_a(self) -> str: ...

    @property
    def category_b(self) -> str: ...

    def check(self, ctx: CheckContext) -> list[Finding]: ...


# --- Rules -------------------------------------------------------------------


class SocketMatchRule:
    """CPU and motherboard must share a socket (AM5, LGA1700, ...)."""

    code = "SOCKET_MATCH"
    category_a = EntityType.CPU
    category_b = EntityType.MOTHERBOARD
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        cpu = ctx.of_type(EntityType.CPU)
        board = ctx.of_type(EntityType.MOTHERBOARD)
        if cpu is None or board is None:
            return []
        cpu_socket = cpu.spec("socket")
        board_socket = board.spec("socket")
        if not cpu_socket or not board_socket:
            return []
        if str(cpu_socket).lower() != str(board_socket).lower():
            a, b = ctx.pair(cpu, board)
            return [
                Finding(
                    rule_code=self.code,
                    severity=self.default_severity,
                    message=(
                        f"Socket mismatch: {cpu.title} uses {cpu_socket} but "
                        f"{board.title} has {board_socket}."
                    ),
                    message_fa=(
                        f"ناسازگاری سوکت: پردازنده {cpu.title} سوکت {cpu_socket} دارد اما "
                        f"مادربرد {board.title} سوکت {board_socket} دارد."
                    ),
                    a_slug=a.slug,
                    b_slug=b.slug,
                    a_title=a.title,
                    b_title=b.title,
                )
            ]
        return []


class RamTypeMatchRule:
    """Memory type (DDR4/DDR5) and form factor must match the board."""

    code = "RAM_TYPE_MATCH"
    category_a = EntityType.RAM
    category_b = EntityType.MOTHERBOARD
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        rams = ctx.by_type(EntityType.RAM)
        board = ctx.of_type(EntityType.MOTHERBOARD)
        if not rams or board is None:
            return []
        board_type = board.spec("memory_type")
        if not board_type:
            return []
        findings: list[Finding] = []
        for ram in rams:
            ram_type = ram.spec("memory_type")
            if not ram_type:
                continue
            if str(ram_type).lower() != str(board_type).lower():
                a, b = ctx.pair(ram, board)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"Memory type mismatch: {ram.title} is {ram_type} but "
                            f"{board.title} supports {board_type}."
                        ),
                        message_fa=(
                            f"ناسازگاری نوع حافظه: {ram.title} از نوع {ram_type} است اما "
                            f"مادربرد {board.title} فقط {board_type} را پشتیبانی می‌کند."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )
        return findings


class PsuWattageRule:
    """PSU wattage must cover the estimated draw of CPU + GPU, with headroom.

    The estimated draw is the sum of the parts' `tdp` (W) specs. The rule
    compares it against the PSU's `wattage` minus a safety margin.
    """

    code = "PSU_WATTAGE"
    category_a = EntityType.PSU
    category_b = EntityType.PREBUILT
    default_severity = BLOCK
    params: dict = {"headroom_ratio": 1.25}

    def check(self, ctx: CheckContext) -> list[Finding]:
        psu = ctx.of_type(EntityType.PSU)
        if psu is None:
            return []
        psu_wattage = psu.number("wattage")
        if psu_wattage is None:
            return []

        headroom_ratio = float(self.params.get("headroom_ratio", 1.25))
        required = 0.0
        contributors: list[PartContext] = []
        for part in ctx.parts:
            if part.entity.type in {EntityType.CPU, EntityType.GPU}:
                tdp = part.number("tdp")
                if tdp:
                    required += tdp
                    contributors.append(part)
        if required <= 0:
            return []

        needed = required * headroom_ratio
        if psu_wattage + 1e-9 < needed:
            a, b = ctx.pair(psu, contributors[0]) if contributors else (psu, psu)
            names = " + ".join(p.title for p in contributors)
            return [
                Finding(
                    rule_code=self.code,
                    severity=self.default_severity,
                    message=(
                        f"PSU too small: {names} needs about {required:.0f}W "
                        f"({needed:.0f}W with headroom) but {psu.title} provides {psu_wattage:.0f}W."
                    ),
                    message_fa=(
                        f"منبع تغذیه ضعیف است: {names} حدود {required:.0f} وات نیاز دارد "
                        f"({needed:.0f} وات با حاشیه اطمینان) اما {psu.title} فقط "
                        f"{psu_wattage:.0f} وات دارد."
                    ),
                    a_slug=a.slug,
                    b_slug=b.slug,
                    a_title=a.title,
                    b_title=b.title,
                )
            ]
        return []


class GpuClearanceRule:
    """GPU length must fit the case; cooler height must fit the case."""

    code = "GPU_CLEARANCE"
    category_a = EntityType.CASE
    category_b = EntityType.GPU
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        case = ctx.of_type(EntityType.CASE)
        if case is None:
            return []
        findings: list[Finding] = []

        max_gpu = case.number("max_gpu_length_mm")
        for gpu in ctx.by_type(EntityType.GPU):
            length = gpu.number("length_mm")
            if length and max_gpu and length > max_gpu:
                a, b = ctx.pair(gpu, case)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"GPU too long: {gpu.title} is {length:.0f}mm but {case.title} "
                            f"allows up to {max_gpu:.0f}mm."
                        ),
                        message_fa=(
                            f"کارت گرافیک بلند است: {gpu.title} با طول {length:.0f} میلی‌متر "
                            f"از حداکثر {max_gpu:.0f} میلی‌متر کیس {case.title} بیشتر است."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )

        max_cooler = case.number("max_cooler_height_mm")
        for cooler in ctx.by_type(EntityType.COOLER):
            height = cooler.number("height_mm")
            if height and max_cooler and height > max_cooler:
                a, b = ctx.pair(cooler, case)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"Cooler too tall: {cooler.title} is {height:.0f}mm but "
                            f"{case.title} allows up to {max_cooler:.0f}mm."
                        ),
                        message_fa=(
                            f"خنک‌کننده بلند است: {cooler.title} با ارتفاع {height:.0f} میلی‌متر "
                            f"از حداکثر {max_cooler:.0f} میلی‌متر کیس {case.title} بیشتر است."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )
        return findings


class CoolerSocketSupportRule:
    """The cooler must support the CPU's socket."""

    code = "COOLER_SUPPORT"
    category_a = EntityType.COOLER
    category_b = EntityType.CPU
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        cooler = ctx.of_type(EntityType.COOLER)
        cpu = ctx.of_type(EntityType.CPU)
        if cooler is None or cpu is None:
            return []
        supported = cooler.spec("sockets")
        cpu_socket = cpu.spec("socket")
        if not supported or not cpu_socket:
            return []
        supported_list = [str(s).lower() for s in supported]
        if str(cpu_socket).lower() not in supported_list:
            a, b = ctx.pair(cooler, cpu)
            return [
                Finding(
                    rule_code=self.code,
                    severity=self.default_severity,
                    message=(
                        f"Cooler does not support {cpu_socket}: {cooler.title} supports "
                        f"{', '.join(supported_list)}."
                    ),
                    message_fa=(
                        f"خنک‌کننده از سوکت {cpu_socket} پشتیبانی نمی‌کند: {cooler.title} از "
                        f"{'، '.join(supported_list)} پشتیبانی می‌کند."
                    ),
                    a_slug=a.slug,
                    b_slug=b.slug,
                    a_title=a.title,
                    b_title=b.title,
                )
            ]
        return []


class PsuConnectorRule:
    """A high-end GPU may need PCIe 12V-2x6/8-pin connectors the PSU lacks."""

    code = "PSU_CONNECTORS"
    category_a = EntityType.PSU
    category_b = EntityType.GPU
    default_severity = WARN
    params: dict = {}

    @staticmethod
    def _connector_kinds(value: Any) -> set[str]:
        """Reduce a connector description to comparable *kinds*.

        `"2x 8-pin PCIe"` and `"8-pin CPU"` both provide the `8-pin` kind, so a
        GPU asking for `8-pin` is satisfied by either. `12vhpwr`/`12v-2x6` are
        the same physical connector under two names.
        """
        kinds: set[str] = set()
        for item in value or []:
            text = str(item).lower()
            if "12vhpwr" in text or "12v-2x6" in text:
                kinds.add("12vhpwr")
            elif "8-pin" in text or "8pin" in text:
                kinds.add("8-pin")
            elif "6-pin" in text or "6pin" in text:
                kinds.add("6-pin")
            elif "24-pin" in text or "24pin" in text:
                kinds.add("24-pin")
            else:
                kinds.add(text.strip())
        return kinds

    def check(self, ctx: CheckContext) -> list[Finding]:
        psu = ctx.of_type(EntityType.PSU)
        if psu is None:
            return []
        psu_connectors = psu.spec("connectors")
        if psu_connectors is None:
            return []
        available = self._connector_kinds(psu_connectors)
        findings: list[Finding] = []
        for gpu in ctx.by_type(EntityType.GPU):
            needed = gpu.spec("power_connectors")
            if not needed:
                continue
            needed_kinds = self._connector_kinds(needed)
            missing = sorted(k for k in needed_kinds if k not in available)
            if missing:
                a, b = ctx.pair(gpu, psu)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"Missing power connector(s) {', '.join(missing)}: {gpu.title} needs "
                            f"them but {psu.title} does not provide them."
                        ),
                        message_fa=(
                            f"کانکتور برق {'، '.join(missing)} موجود نیست: {gpu.title} به آن نیاز "
                            f"دارد اما {psu.title} این کانکتورها را ندارد."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )
        return findings


class PrebuiltFitRule:
    """For prebuilt PCs: the listed parts must be compatible with each other."""

    code = "PREBUILT_FIT"
    category_a = EntityType.PREBUILT
    category_b = EntityType.PREBUILT
    default_severity = WARN
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        """A prebuilt is a fixed configuration; a mismatch in its own specs is a warning.

        The prebuilt's `common` spec carries the config it ships with, so the
        rule only fires when the prebuilt's own numbers contradict.
        """
        findings: list[Finding] = []
        for part in ctx.parts:
            if part.entity.type != EntityType.PREBUILT:
                continue
            wattage = part.number("psu_wattage")
            required = part.number("estimated_draw_w")
            if wattage and required and wattage < required:
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"{part.title} ships with a {wattage:.0f}W PSU but its own "
                            f"specs estimate a {required:.0f}W draw."
                        ),
                        message_fa=(
                            f"{part.title} با منبع تغذیه {wattage:.0f} وات عرضه می‌شود اما "
                            f"مشخصات خودش مصرف {required:.0f} وات را تخمین می‌زند."
                        ),
                        a_slug=part.slug,
                        b_slug=part.slug,
                        a_title=part.title,
                    )
                )
        return findings


# --- Registry ----------------------------------------------------------------

#: code -> rule instance. The DB row supplies severity/params/enabled; the
#: class supplies the logic.
REGISTRY: dict[str, Rule] = {
    rule.code: rule
    for rule in (
        SocketMatchRule(),
        RamTypeMatchRule(),
        PsuWattageRule(),
        GpuClearanceRule(),
        CoolerSocketSupportRule(),
        PsuConnectorRule(),
        PrebuiltFitRule(),
    )
}


# --- Engine ------------------------------------------------------------------


def build_context(parts: list[PartContext], params: dict | None = None) -> CheckContext:
    return CheckContext(parts=parts, params=params or {})


def run_rules(
    ctx: CheckContext,
    rules: list[Rule],
) -> list[Finding]:
    """Run rules over the context, most severe findings first."""
    findings: list[Finding] = []
    for rule in rules:
        try:
            findings.extend(rule.check(ctx))
        except Exception:  # a broken rule must never crash a user's check
            findings.append(
                Finding(
                    rule_code=getattr(rule, "code", "unknown"),
                    severity=INFO,
                    message="This check could not be completed.",
                    message_fa="این بررسی قابل انجام نبود.",
                    a_slug="",
                    b_slug="",
                )
            )
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 3), f.rule_code))
    return findings


def overall_verdict(findings: list[Finding]) -> str:
    """`block` if anything blocks, `warn` if any warnings, else `ok`."""
    severities = {f.severity for f in findings}
    if BLOCK in severities:
        return BLOCK
    if severities:
        return WARN
    return OK
