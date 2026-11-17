"""Tests for the compatibility rule engine.

The engine is pure Python, so these tests need no database for the rule logic
itself — only `PartContext` objects.
"""

from __future__ import annotations

import pytest

from apps.catalog.models import Entity, EntityType
from apps.compat.engine import (
    BLOCK,
    INFO,
    OK,
    WARN,
    ChipsetMatchRule,
    CoolerCapacityRule,
    CoolerFitRule,
    CoolerSocketSupportRule,
    CpuMemorySupportRule,
    GpuClearanceRule,
    GpuInterfaceRule,
    MemoryFitRule,
    PartContext,
    PsuConnectorRule,
    PsuFitRule,
    PsuWattageRule,
    RamTypeMatchRule,
    SocketMatchRule,
    StorageFitRule,
    build_context,
    overall_verdict,
    run_rules,
)

pytestmark = pytest.mark.django_db


def make_part(entity_type: str, title: str, slug: str, **specs) -> PartContext:
    entity = Entity(type=entity_type, title=title, slug=slug)
    return PartContext(entity=entity, specs=specs)


@pytest.fixture
def am5_cpu() -> PartContext:
    return make_part(
        EntityType.CPU, "AMD Ryzen 7 7800X3D", "ryzen-7-7800x3d", socket="AM5", tdp=120
    )


@pytest.fixture
def lga_cpu() -> PartContext:
    return make_part(
        EntityType.CPU, "Intel Core i5-13400F", "core-i5-13400f", socket="LGA1700", tdp=65
    )


@pytest.fixture
def am5_board() -> PartContext:
    return make_part(
        EntityType.MOTHERBOARD,
        "ASUS TUF B650-PLUS",
        "asus-tuf-gaming-b650-plus",
        socket="AM5",
        memory_type="DDR5",
    )


@pytest.fixture
def lga_board() -> PartContext:
    return make_part(
        EntityType.MOTHERBOARD,
        "Gigabyte B760M DS3H",
        "gigabyte-b760m-ds3h",
        socket="LGA1700",
        memory_type="DDR5",
    )


# --- Socket matching ---------------------------------------------------------


class TestSocketMatch:
    def test_matching_sockets_pass(self, am5_cpu, am5_board):
        findings = SocketMatchRule().check(build_context([am5_cpu, am5_board]))
        assert findings == []

    def test_mismatched_sockets_block(self, am5_cpu, lga_board):
        findings = SocketMatchRule().check(build_context([am5_cpu, lga_board]))
        assert len(findings) == 1
        finding = findings[0]
        assert finding.severity == BLOCK
        assert finding.rule_code == "SOCKET_MATCH"
        assert "AM5" in finding.message
        assert "AM5" in finding.message_fa

    def test_missing_spec_is_not_a_finding(self, am5_cpu):
        board = make_part(
            EntityType.MOTHERBOARD, "Unknown board", "unknown-board", memory_type="DDR5"
        )
        assert SocketMatchRule().check(build_context([am5_cpu, board])) == []

    def test_socket_comparison_is_case_insensitive(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", socket="am5")
        board = make_part(EntityType.MOTHERBOARD, "Board", "board", socket="AM5")
        assert SocketMatchRule().check(build_context([cpu, board])) == []

    def test_no_cpu_means_no_finding(self, am5_board):
        assert SocketMatchRule().check(build_context([am5_board])) == []


# --- RAM type ----------------------------------------------------------------


class TestRamTypeMatch:
    def test_matching_memory_type_passes(self, am5_board):
        ram = make_part(EntityType.RAM, "Vengeance 32GB", "veng-32", memory_type="DDR5")
        assert RamTypeMatchRule().check(build_context([ram, am5_board])) == []

    def test_ddr4_on_ddr5_board_blocks(self, am5_board):
        ram = make_part(EntityType.RAM, "Fury Beast 32GB", "fury-32", memory_type="DDR4")
        findings = RamTypeMatchRule().check(build_context([ram, am5_board]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK
        assert "DDR4" in findings[0].message

    def test_every_ram_module_is_checked(self, am5_board):
        good = make_part(EntityType.RAM, "Good", "good-ram", memory_type="DDR5")
        bad = make_part(EntityType.RAM, "Bad", "bad-ram", memory_type="DDR4")
        findings = RamTypeMatchRule().check(build_context([good, bad, am5_board]))
        assert len(findings) == 1
        assert findings[0].a_slug == "bad-ram" or findings[0].b_slug == "bad-ram"


# --- PSU wattage -------------------------------------------------------------


class TestPsuWattage:
    def test_enough_wattage_passes(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", tdp=120)
        gpu = make_part(EntityType.GPU, "GPU", "gpu", tdp=220)
        psu = make_part(EntityType.PSU, "RM850x", "rm850x", wattage=850)
        assert PsuWattageRule().check(build_context([cpu, gpu, psu])) == []

    def test_insufficient_wattage_blocks(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", tdp=120)
        gpu = make_part(EntityType.GPU, "GPU", "gpu", tdp=220)
        psu = make_part(EntityType.PSU, "RM450", "rm450", wattage=450)
        # 340W draw * 1.25 headroom = 425W needed, PSU gives 450W → fits.
        assert PsuWattageRule().check(build_context([cpu, gpu, psu])) == []

        # A 400W PSU does not.
        small = make_part(EntityType.PSU, "Small PSU", "small-psu", wattage=400)
        findings = PsuWattageRule().check(build_context([cpu, gpu, small]))
        assert len(findings) == 1
        finding = findings[0]
        assert finding.severity == BLOCK
        assert "340W" in finding.message  # 120 + 220
        assert "425W" in finding.message  # with 1.25 headroom

    def test_headroom_ratio_is_configurable(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", tdp=200)
        psu = make_part(EntityType.PSU, "PSU", "psu", wattage=300)
        rule = PsuWattageRule()
        # 200 * 1.0 = 200 <= 300 → fine
        rule.params = {"headroom_ratio": 1.0}
        assert rule.check(build_context([cpu, psu])) == []
        # 200 * 1.6 = 320 > 300 → blocks
        rule.params = {"headroom_ratio": 1.6}
        assert len(rule.check(build_context([cpu, psu]))) == 1

    def test_no_psu_means_no_finding(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", tdp=120)
        assert PsuWattageRule().check(build_context([cpu])) == []

    def test_numeric_specs_with_units_are_parsed(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", tdp="120 W")
        psu = make_part(EntityType.PSU, "PSU", "psu", wattage="650W")
        assert PsuWattageRule().check(build_context([cpu, psu])) == []

    def test_draw_below_headroom_boundary_is_allowed(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", tdp=100)
        psu = make_part(EntityType.PSU, "PSU", "psu", wattage=125)
        # 100 * 1.25 = 125 → exactly equal → allowed
        assert PsuWattageRule().check(build_context([cpu, psu])) == []


# --- Clearance ---------------------------------------------------------------


class TestGpuClearance:
    def test_fitting_gpu_passes(self):
        gpu = make_part(EntityType.GPU, "RTX 4060", "rtx-4060", length_mm=245)
        case = make_part(EntityType.CASE, "H5 Flow", "nzxt-h5-flow", max_gpu_length_mm=365)
        assert GpuClearanceRule().check(build_context([gpu, case])) == []

    def test_too_long_gpu_blocks(self):
        gpu = make_part(EntityType.GPU, "RTX 4080 SUPER", "rtx-4080-super", length_mm=304)
        case = make_part(EntityType.CASE, "H5 Flow", "nzxt-h5-flow", max_gpu_length_mm=245)
        findings = GpuClearanceRule().check(build_context([gpu, case]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK
        assert "304mm" in findings[0].message

    def test_no_case_means_no_finding(self):
        gpu = make_part(EntityType.GPU, "RTX 4080 SUPER", "rtx-4080-super", length_mm=304)
        assert GpuClearanceRule().check(build_context([gpu])) == []


# --- Cooler fit --------------------------------------------------------------


class TestCoolerFit:
    def test_tall_air_cooler_blocks(self):
        cooler = make_part(EntityType.COOLER, "Kraken 360", "nzxt-kraken-360", height_mm=200)
        case = make_part(EntityType.CASE, "H5 Flow", "nzxt-h5-flow", max_cooler_height_mm=165)
        findings = CoolerFitRule().check(build_context([cooler, case]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK
        assert findings[0].rule_code == "COOLER_FIT"
        assert "200mm" in findings[0].message

    def test_fitting_air_cooler_passes(self):
        cooler = make_part(EntityType.COOLER, "Hyper 212", "hyper-212", height_mm=159)
        case = make_part(EntityType.CASE, "H5 Flow", "nzxt-h5-flow", max_cooler_height_mm=165)
        assert CoolerFitRule().check(build_context([cooler, case])) == []

    def test_oversized_radiator_blocks(self):
        cooler = make_part(EntityType.COOLER, "Kraken 360", "nzxt-kraken-360", radiator_mm=360)
        case = make_part(EntityType.CASE, "Compact", "compact", radiator_support_mm=240)
        findings = CoolerFitRule().check(build_context([cooler, case]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK
        assert "360mm" in findings[0].message

    def test_unknown_radiator_support_stays_silent(self):
        # The case records no radiator support: the rule must not invent a pass.
        # `evaluate_candidates` reports such a candidate as *not determined*.
        cooler = make_part(EntityType.COOLER, "Kraken 360", "nzxt-kraken-360", radiator_mm=360)
        case = make_part(EntityType.CASE, "Compact", "compact", max_cooler_height_mm=165)
        assert CoolerFitRule().check(build_context([cooler, case])) == []

    def test_no_case_means_no_finding(self):
        cooler = make_part(EntityType.COOLER, "Kraken 360", "nzxt-kraken-360", radiator_mm=360)
        assert CoolerFitRule().check(build_context([cooler])) == []


# --- Cooler socket -----------------------------------------------------------


class TestCoolerSocketSupport:
    def test_supported_socket_passes(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", socket="AM5")
        cooler = make_part(
            EntityType.COOLER, "Hyper 212", "hyper-212", sockets=["AM4", "AM5", "LGA1700"]
        )
        assert CoolerSocketSupportRule().check(build_context([cpu, cooler])) == []

    def test_unsupported_socket_blocks(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", socket="AM5")
        cooler = make_part(EntityType.COOLER, "Old cooler", "old-cooler", sockets=["LGA1151"])
        findings = CoolerSocketSupportRule().check(build_context([cpu, cooler]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK


# --- PSU connectors ----------------------------------------------------------


class TestPsuConnectors:
    def test_missing_connector_warns(self):
        gpu = make_part(
            EntityType.GPU,
            "RTX 4080 SUPER",
            "rtx-4080-super",
            power_connectors=["8-pin", "12vhpwr"],
        )
        psu = make_part(
            EntityType.PSU, "RM650x", "rm650x", connectors=["24-pin", "8-pin CPU", "2x 8-pin PCIe"]
        )
        findings = PsuConnectorRule().check(build_context([gpu, psu]))
        assert len(findings) == 1
        assert findings[0].severity == WARN
        assert "12vhpwr" in findings[0].message

    def test_present_connector_passes(self):
        gpu = make_part(EntityType.GPU, "RTX 4060", "rtx-4060", power_connectors=["8-pin"])
        psu = make_part(
            EntityType.PSU, "RM650x", "rm650x", connectors=["24-pin", "8-pin CPU", "2x 8-pin PCIe"]
        )
        assert PsuConnectorRule().check(build_context([gpu, psu])) == []

    def test_no_gpu_means_no_finding(self):
        psu = make_part(EntityType.PSU, "RM650x", "rm650x", connectors=["24-pin"])
        assert PsuConnectorRule().check(build_context([psu])) == []


# --- Verdict -----------------------------------------------------------------


class TestVerdict:
    def test_ok_when_no_findings(self):
        assert overall_verdict([]) == OK

    def test_warn_when_only_warnings(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", tdp=120)
        psu = make_part(EntityType.PSU, "RM450", "rm450", wattage=450)
        gpu = make_part(EntityType.GPU, "GPU", "gpu", tdp=220, power_connectors=["12vhpwr"])
        psu.specs["connectors"] = ["24-pin"]
        findings = run_rules(build_context([cpu, gpu, psu]), [PsuConnectorRule()])
        assert overall_verdict(findings) == WARN

    def test_block_wins_over_warn(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", socket="AM5", tdp=120)
        board = make_part(EntityType.MOTHERBOARD, "Board", "board", socket="LGA1700")
        findings = run_rules(build_context([cpu, board]), [SocketMatchRule()])
        assert overall_verdict(findings) == BLOCK

    def test_broken_rule_does_not_crash(self):
        class ExplodingRule:
            code = "BOOM"
            category_a = ""
            category_b = ""
            default_severity = BLOCK
            params: dict = {}

            def check(self, ctx):
                raise RuntimeError("kaboom")

        findings = run_rules(build_context([]), [ExplodingRule()])
        assert len(findings) == 1
        assert findings[0].severity == INFO


# --- Chipset / CPU ↔ board ---------------------------------------------------


class TestChipsetMatch:
    def test_a_chipset_from_another_socket_blocks(self):
        cpu = make_part(EntityType.CPU, "7800X3D", "cpu", socket="AM5")
        board = make_part(EntityType.MOTHERBOARD, "B760M", "board", chipset="B760")
        findings = ChipsetMatchRule().check(build_context([cpu, board]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK

    def test_the_matching_chipset_passes(self):
        cpu = make_part(EntityType.CPU, "7800X3D", "cpu", socket="AM5")
        board = make_part(EntityType.MOTHERBOARD, "B650", "board", chipset="B650")
        assert ChipsetMatchRule().check(build_context([cpu, board])) == []

    def test_a_missing_chipset_is_not_guessed(self):
        cpu = make_part(EntityType.CPU, "7800X3D", "cpu", socket="AM5")
        board = make_part(EntityType.MOTHERBOARD, "Board", "board")
        assert ChipsetMatchRule().check(build_context([cpu, board])) == []


# --- CPU ↔ RAM ---------------------------------------------------------------


class TestCpuMemorySupport:
    def test_a_ddr4_kit_on_a_ddr5_cpu_blocks(self):
        cpu = make_part(EntityType.CPU, "7800X3D", "cpu", memory_type="DDR5")
        ram = make_part(EntityType.RAM, "DDR4 kit", "ram", memory_type="DDR4")
        findings = CpuMemorySupportRule().check(build_context([cpu, ram]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK

    def test_a_range_on_the_cpu_accepts_both_kinds(self):
        cpu = make_part(EntityType.CPU, "i5", "cpu", memory_type="DDR4/DDR5")
        ram = make_part(EntityType.RAM, "DDR5 kit", "ram", memory_type="DDR5")
        assert CpuMemorySupportRule().check(build_context([cpu, ram])) == []


# --- Board ↔ RAM -------------------------------------------------------------


class TestMemoryFit:
    def test_more_modules_than_slots_blocks(self):
        board = make_part(EntityType.MOTHERBOARD, "Board", "board", memory_slots=2)
        ram = make_part(EntityType.RAM, "4 modules", "ram", modules=4, capacity_gb=64)
        findings = MemoryFitRule().check(build_context([board, ram]))
        assert any(finding.severity == BLOCK for finding in findings)

    def test_capacity_over_the_board_ceiling_blocks(self):
        board = make_part(
            EntityType.MOTHERBOARD, "Board", "board", memory_slots=4, max_memory_gb=64
        )
        ram = make_part(EntityType.RAM, "128GB kit", "ram", modules=2, capacity_gb=128)
        findings = MemoryFitRule().check(build_context([board, ram]))
        assert any(finding.severity == BLOCK for finding in findings)

    def test_a_speed_above_the_rated_rate_only_warns(self):
        board = make_part(
            EntityType.MOTHERBOARD,
            "Board",
            "board",
            memory_slots=4,
            max_memory_gb=128,
            max_memory_speed=5333,
        )
        ram = make_part(
            EntityType.RAM, "DDR5-6000", "ram", modules=2, capacity_gb=32, speed_mhz=6000
        )
        findings = MemoryFitRule().check(build_context([board, ram]))
        assert len(findings) == 1
        assert findings[0].severity == WARN

    def test_a_kit_inside_every_limit_passes(self):
        board = make_part(
            EntityType.MOTHERBOARD,
            "Board",
            "board",
            memory_slots=4,
            max_memory_gb=256,
            max_memory_speed=6400,
        )
        ram = make_part(
            EntityType.RAM, "DDR5-6000", "ram", modules=2, capacity_gb=32, speed_mhz=6000
        )
        assert MemoryFitRule().check(build_context([board, ram])) == []


# --- Board ↔ GPU / storage ---------------------------------------------------


class TestGpuInterface:
    def test_an_older_board_slot_warns(self):
        board = make_part(EntityType.MOTHERBOARD, "Board", "board", pcie_gen=3)
        gpu = make_part(EntityType.GPU, "Card", "gpu", pcie_gen=4)
        findings = GpuInterfaceRule().check(build_context([board, gpu]))
        assert len(findings) == 1
        assert findings[0].severity == WARN

    def test_matching_generations_pass(self):
        board = make_part(EntityType.MOTHERBOARD, "Board", "board", pcie_gen=4)
        gpu = make_part(EntityType.GPU, "Card", "gpu", pcie_gen=4)
        assert GpuInterfaceRule().check(build_context([board, gpu])) == []


class TestStorageFit:
    def test_nvme_without_an_m2_slot_blocks(self):
        board = make_part(EntityType.MOTHERBOARD, "Board", "board", m2_slots=0)
        disk = make_part(
            EntityType.STORAGE, "990 Pro", "disk", interface="PCIe 4.0 x4", form_factor="M.2 2280"
        )
        findings = StorageFitRule().check(build_context([board, disk]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK

    def test_an_m2_slot_present_passes(self):
        board = make_part(EntityType.MOTHERBOARD, "Board", "board", m2_slots=2, pcie_gen=4)
        disk = make_part(
            EntityType.STORAGE, "990 Pro", "disk", interface="PCIe 4.0 x4", form_factor="M.2 2280"
        )
        assert StorageFitRule().check(build_context([board, disk])) == []


# --- Cooler ↔ CPU / PSU ↔ case -----------------------------------------------


class TestCoolerCapacity:
    def test_an_undersized_cooler_warns(self):
        cpu = make_part(EntityType.CPU, "Hot CPU", "cpu", tdp=170)
        cooler = make_part(EntityType.COOLER, "Small cooler", "cooler", tdp_rating=150)
        findings = CoolerCapacityRule().check(build_context([cpu, cooler]))
        assert len(findings) == 1
        assert findings[0].severity == WARN

    def test_an_adequate_cooler_passes(self):
        cpu = make_part(EntityType.CPU, "CPU", "cpu", tdp=120)
        cooler = make_part(EntityType.COOLER, "Big cooler", "cooler", tdp_rating=300)
        assert CoolerCapacityRule().check(build_context([cpu, cooler])) == []


class TestPsuFit:
    def test_a_too_long_psu_blocks(self):
        case = make_part(EntityType.CASE, "H5", "case", max_psu_length_mm=200)
        psu = make_part(EntityType.PSU, "Big PSU", "psu", length_mm=210)
        findings = PsuFitRule().check(build_context([case, psu]))
        assert len(findings) == 1
        assert findings[0].severity == BLOCK

    def test_a_fitting_psu_passes(self):
        case = make_part(EntityType.CASE, "H5", "case", max_psu_length_mm=200)
        psu = make_part(EntityType.PSU, "PSU", "psu", length_mm=160)
        assert PsuFitRule().check(build_context([case, psu])) == []
