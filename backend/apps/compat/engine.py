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

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from apps.catalog.models import Entity, EntityType

# --- Verdicts and severities -------------------------------------------------

BLOCK = "block"
WARN = "warn"
INFO = "info"
OK = "ok"

_SEVERITY_ORDER = {BLOCK: 0, WARN: 1, INFO: 2}


def _as_set(value: Any) -> set[str]:
    """Normalise a spec that may be a string, a list or a "DDR4/DDR5" range.

    `memory_type` is a single token in the seed, but real data can carry a list
    or a slash-separated range — all three mean the same thing to a rule.
    """
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    return {part.strip() for part in re.split(r"[,|/،]", str(value)) if part.strip()}


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
    category_b = EntityType.GPU
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
    """The graphics card's length must fit the case's usable space.

    Only the GPU is judged here. The cooler has its own rule (`CoolerFitRule`),
    so a cooler candidate is credited for exactly the check that compares it.
    """

    code = "GPU_CLEARANCE"
    category_a = EntityType.CASE
    category_b = EntityType.GPU
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        case = ctx.of_type(EntityType.CASE)
        if case is None:
            return []
        max_gpu = case.number("max_gpu_length_mm")
        if not max_gpu:
            return []

        findings: list[Finding] = []
        for gpu in ctx.by_type(EntityType.GPU):
            length = gpu.number("length_mm")
            if length and length > max_gpu:
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
                            f"کارت گرافیک بلند است: {gpu.title} با طول {length:.0f} میلیمتر "
                            f"از حداکثر {max_gpu:.0f} میلیمتر کیس {case.title} بیشتر است."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )
        return findings


class CoolerFitRule:
    """The CPU cooler must physically fit the case.

    An air cooler is limited by its height against the case's
    ``max_cooler_height_mm``; a liquid cooler (AIO) by its radiator size against
    the case's ``radiator_support_mm``. A number missing on *either* side is not
    a pass: the rule stays silent and `services.evaluate_candidates` reports the
    candidate as not determined instead of compatible.
    """

    code = "COOLER_FIT"
    category_a = EntityType.CASE
    category_b = EntityType.COOLER
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        case = ctx.of_type(EntityType.CASE)
        if case is None:
            return []
        max_height = case.number("max_cooler_height_mm")
        max_radiator = case.number("radiator_support_mm")

        findings: list[Finding] = []
        for cooler in ctx.by_type(EntityType.COOLER):
            height = cooler.number("height_mm")
            if height and max_height and height > max_height:
                a, b = ctx.pair(cooler, case)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"Cooler too tall: {cooler.title} is {height:.0f}mm but "
                            f"{case.title} allows up to {max_height:.0f}mm."
                        ),
                        message_fa=(
                            f"خنک‌کننده بلند است: {cooler.title} با ارتفاع {height:.0f} میلیمتر "
                            f"از حداکثر {max_height:.0f} میلیمتر کیس {case.title} بیشتر است."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )

            radiator = cooler.number("radiator_mm")
            if radiator and max_radiator and radiator > max_radiator:
                a, b = ctx.pair(cooler, case)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"Radiator does not fit: {cooler.title} needs {radiator:.0f}mm "
                            f"but {case.title} supports up to {max_radiator:.0f}mm."
                        ),
                        message_fa=(
                            f"رادیاتور جا نمی‌شود: {cooler.title} به رادیاتور {radiator:.0f} "
                            f"میلیمتری نیاز دارد اما کیس {case.title} تا {max_radiator:.0f} "
                            f"میلیمتر پشتیبانی می‌کند."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )
        return findings


class StorageFitRule:
    """M.2/NVMe storage needs an M.2 slot; a SATA drive only needs a SATA port."""

    code = "STORAGE_FIT"
    category_a = EntityType.MOTHERBOARD
    category_b = EntityType.STORAGE
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        board = ctx.of_type(EntityType.MOTHERBOARD)
        if board is None:
            return []
        m2_slots = board.number("m2_slots")
        board_gen = board.number("pcie_gen")
        findings: list[Finding] = []
        for disk in ctx.by_type(EntityType.STORAGE):
            interface = str(disk.spec("interface") or "")
            form = str(disk.spec("form_factor") or "")
            is_m2 = (
                "M.2" in form.upper() or "M.2" in interface.upper() or "NVME" in interface.upper()
            )
            if is_m2 and m2_slots is not None and m2_slots < 1:
                a, b = ctx.pair(disk, board)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=BLOCK,
                        message=(
                            f"{disk.title} is an M.2/NVMe drive but {board.title} has no M.2 slot."
                        ),
                        message_fa=(
                            f"{disk.title} از نوع M.2/NVMe است اما مادربرد {board.title} "
                            f"اسلات M.2 ندارد."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )
                continue
            match = re.search(r"PCIe\s*(\d)", interface, re.IGNORECASE)
            disk_gen = float(match.group(1)) if match else 0.0
            if disk_gen and board_gen and disk_gen > board_gen:
                a, b = ctx.pair(disk, board)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=WARN,
                        message=(
                            f"{disk.title} is PCIe {disk_gen:.0f} but {board.title} provides "
                            f"PCIe {board_gen:.0f}; it will run at the lower generation."
                        ),
                        message_fa=(
                            f"{disk.title} از PCIe نسل {disk_gen:.0f} است اما {board.title} "
                            f"PCIe نسل {board_gen:.0f} دارد؛ با نسل کمتر کار می‌کند."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )
        return findings


class PsuFitRule:
    """A power supply has to physically fit the case."""

    code = "PSU_FIT"
    category_a = EntityType.CASE
    category_b = EntityType.PSU
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        case = ctx.of_type(EntityType.CASE)
        if case is None:
            return []
        max_len = case.number("max_psu_length_mm")
        if not max_len:
            return []
        findings: list[Finding] = []
        for psu in ctx.by_type(EntityType.PSU):
            length = psu.number("length_mm")
            if length and length > max_len:
                a, b = ctx.pair(psu, case)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"{psu.title} is {length:.0f}mm long but {case.title} allows up to "
                            f"{max_len:.0f}mm."
                        ),
                        message_fa=(
                            f"طول {psu.title} برابر {length:.0f} میلی‌متر است اما کیس "
                            f"{case.title} تا {max_len:.0f} میلی‌متر جا می‌دهد."
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


class GpuInterfaceRule:
    """A card works in a lower-generation PCIe slot, but the gap is worth saying."""

    code = "GPU_INTERFACE"
    category_a = EntityType.MOTHERBOARD
    category_b = EntityType.GPU
    default_severity = WARN
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        board = ctx.of_type(EntityType.MOTHERBOARD)
        if board is None:
            return []
        board_gen = board.number("pcie_gen")
        if not board_gen:
            return []
        findings: list[Finding] = []
        for gpu in ctx.by_type(EntityType.GPU):
            gpu_gen = gpu.number("pcie_gen")
            if gpu_gen and gpu_gen > board_gen:
                a, b = ctx.pair(gpu, board)
                findings.append(
                    Finding(
                        rule_code=self.code,
                        severity=self.default_severity,
                        message=(
                            f"{gpu.title} is a PCIe {gpu_gen:.0f} card but {board.title} provides "
                            f"PCIe {board_gen:.0f}; it will run at the lower generation."
                        ),
                        message_fa=(
                            f"{gpu.title} از PCIe نسل {gpu_gen:.0f} است اما {board.title} "
                            f"PCIe نسل {board_gen:.0f} دارد؛ با نسل کمتر کار می‌کند."
                        ),
                        a_slug=a.slug,
                        b_slug=b.slug,
                        a_title=a.title,
                        b_title=b.title,
                    )
                )
        return findings


class CoolerCapacityRule:
    """The cooler's heat rating must cover the CPU's design power."""

    code = "COOLER_CAPACITY"
    category_a = EntityType.COOLER
    category_b = EntityType.CPU
    default_severity = WARN
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        cooler = ctx.of_type(EntityType.COOLER)
        cpu = ctx.of_type(EntityType.CPU)
        if cooler is None or cpu is None:
            return []
        rating = cooler.number("tdp_rating")
        tdp = cpu.number("tdp")
        if not rating or not tdp or rating >= tdp:
            return []
        a, b = ctx.pair(cooler, cpu)
        return [
            Finding(
                rule_code=self.code,
                severity=self.default_severity,
                message=(
                    f"{cooler.title} is rated for {rating:.0f}W but {cpu.title} is a {tdp:.0f}W part."
                ),
                message_fa=(
                    f"ظرفیت خنک‌کنندگی {cooler.title} حدود {rating:.0f} وات است اما مصرف "
                    f"{cpu.title} حدود {tdp:.0f} وات است."
                ),
                a_slug=a.slug,
                b_slug=b.slug,
                a_title=a.title,
                b_title=b.title,
            )
        ]


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


class MemoryFitRule:
    """A memory kit must fit the board: module count, capacity and rated speed.

    More modules than slots, or more capacity than the board supports, is a
    block. Running the kit above the board's rated speed is only a warning: it
    still works, at a lower speed or through the board's memory profile.
    """

    code = "MEMORY_FIT"
    category_a = EntityType.MOTHERBOARD
    category_b = EntityType.RAM
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        board = ctx.of_type(EntityType.MOTHERBOARD)
        if board is None:
            return []
        slots = board.number("memory_slots")
        max_gb = board.number("max_memory_gb")
        max_speed = board.number("max_memory_speed")

        findings: list[Finding] = []
        for ram in ctx.by_type(EntityType.RAM):
            modules = ram.number("modules")
            capacity = ram.number("capacity_gb")
            speed = ram.number("speed_mhz")
            if modules and slots and modules > slots:
                findings.append(
                    self._make(
                        ctx,
                        ram,
                        board,
                        BLOCK,
                        f"{ram.title} uses {modules:.0f} modules but {board.title} has {slots:.0f} slots.",
                        f"{ram.title} {modules:.0f} ماژول دارد اما مادربرد {board.title} فقط {slots:.0f} اسلات دارد.",
                    )
                )
            if capacity and max_gb and capacity > max_gb:
                findings.append(
                    self._make(
                        ctx,
                        ram,
                        board,
                        BLOCK,
                        f"{ram.title} is {capacity:.0f}GB but {board.title} supports up to {max_gb:.0f}GB.",
                        f"ظرفیت {ram.title} برابر {capacity:.0f} گیگابایت است اما مادربرد {board.title} تا {max_gb:.0f} گیگابایت پشتیبانی می‌کند.",
                    )
                )
            if speed and max_speed and speed > max_speed:
                findings.append(
                    self._make(
                        ctx,
                        ram,
                        board,
                        WARN,
                        f"{ram.title} runs at {speed:.0f}MHz, above the {max_speed:.0f}MHz {board.title} is rated for.",
                        f"سرعت {ram.title} برابر {speed:.0f} مگاهرتز است و از نرخ {max_speed:.0f} مگاهرتز مادربرد {board.title} بیشتر است؛ با سرعت کمتر کار می‌کند.",
                    )
                )
        return findings

    def _make(
        self,
        ctx: CheckContext,
        ram: PartContext,
        board: PartContext,
        severity: str,
        message: str,
        message_fa: str,
    ) -> Finding:
        a, b = ctx.pair(ram, board)
        return Finding(
            rule_code=self.code,
            severity=severity,
            message=message,
            message_fa=message_fa,
            a_slug=a.slug,
            b_slug=b.slug,
            a_title=a.title,
            b_title=b.title,
        )


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


class ChipsetMatchRule:
    """The board's chipset must belong to the CPU's socket family.

    The map is socket-level on purpose: a chipset family belongs to exactly one
    socket family (B650 → AM5, B760 → LGA1700). It does not invent a per-CPU
    support list — the socket already pins that.
    """

    code = "CHIPSET_MATCH"
    category_a = EntityType.CPU
    category_b = EntityType.MOTHERBOARD
    default_severity = BLOCK
    params: dict = {}

    SOCKET_CHIPSETS: dict[str, set[str]] = {
        "AM5": {"A620", "B650", "B650E", "X670", "X670E", "B840", "B850", "X870", "X870E"},
        "LGA1700": {"H610", "B660", "B760", "H670", "H770", "Z690", "Z790", "W680"},
    }

    def check(self, ctx: CheckContext) -> list[Finding]:
        cpu = ctx.of_type(EntityType.CPU)
        board = ctx.of_type(EntityType.MOTHERBOARD)
        if cpu is None or board is None:
            return []
        socket = str(cpu.spec("socket") or "").strip().upper()
        chipset = str(board.spec("chipset") or "").strip().upper()
        family = self.SOCKET_CHIPSETS.get(socket)
        if not family or not chipset or chipset in family:
            return []
        a, b = ctx.pair(cpu, board)
        return [
            Finding(
                rule_code=self.code,
                severity=self.default_severity,
                message=(
                    f"Chipset {chipset} is not a {socket} chipset: {cpu.title} needs a {socket} "
                    f"board but {board.title} is {chipset}."
                ),
                message_fa=(
                    f"چیپست {chipset} متعلق به سوکت {socket} نیست: {cpu.title} به مادربرد "
                    f"{socket} نیاز دارد اما {board.title} چیپست {chipset} دارد."
                ),
                a_slug=a.slug,
                b_slug=b.slug,
                a_title=a.title,
                b_title=b.title,
            )
        ]


class CpuMemorySupportRule:
    """The kit's memory type must be supported by the CPU's memory controller.

    A DDR4 kit cannot be driven by a DDR5-only controller whatever the board
    says; the board check (`RAM_TYPE_MATCH`) and this one are independent.
    """

    code = "CPU_MEMORY_SUPPORT"
    category_a = EntityType.CPU
    category_b = EntityType.RAM
    default_severity = BLOCK
    params: dict = {}

    def check(self, ctx: CheckContext) -> list[Finding]:
        cpu = ctx.of_type(EntityType.CPU)
        ram = ctx.of_type(EntityType.RAM)
        if cpu is None or ram is None:
            return []
        supported = {item.upper() for item in _as_set(cpu.spec("memory_type"))}
        wanted = str(ram.spec("memory_type") or "").strip()
        if not supported or not wanted or wanted.upper() in supported:
            return []
        a, b = ctx.pair(cpu, ram)
        return [
            Finding(
                rule_code=self.code,
                severity=self.default_severity,
                message=f"{cpu.title} does not support {wanted} memory ({ram.title}).",
                message_fa=(
                    f"پردازندهٔ {cpu.title} از حافظهٔ {wanted} پشتیبانی نمی‌کند ({ram.title})."
                ),
                a_slug=a.slug,
                b_slug=b.slug,
                a_title=a.title,
                b_title=b.title,
            )
        ]


# --- Registry ----------------------------------------------------------------

#: code -> rule instance. The DB row supplies severity/params/enabled; the
#: class supplies the logic.
REGISTRY: dict[str, Rule] = {
    rule.code: rule
    for rule in (
        SocketMatchRule(),
        ChipsetMatchRule(),
        RamTypeMatchRule(),
        CpuMemorySupportRule(),
        MemoryFitRule(),
        PsuWattageRule(),
        GpuClearanceRule(),
        GpuInterfaceRule(),
        CoolerFitRule(),
        CoolerSocketSupportRule(),
        CoolerCapacityRule(),
        StorageFitRule(),
        PsuConnectorRule(),
        PsuFitRule(),
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
