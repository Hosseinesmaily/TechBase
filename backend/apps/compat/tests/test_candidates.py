"""Candidate badges: one verdict per identifier, driven by the real selection.

These pin the contract the configurator relies on:

* the answer is a **map keyed by the candidate identifier** (never a list whose
  order has to line up with the cards),
* a different earlier choice produces a different verdict (the engine is re-run,
  not cached by the step),
* "no rule could compare anything" is reported as `checked_rules == 0` — which the
  UI shows as *neutral*, never as compatible,
* a finding between two *other* parts is not attributed to the candidate.
"""

from __future__ import annotations

import itertools

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Brand, ComponentSpec, Entity, EntityStatus, EntityType
from apps.compat.models import CompatibilityRule, RuleSeverity
from apps.compat.services import check_parts

pytestmark = pytest.mark.django_db

CHECK = "/api/v1/compat/check/"


def make_entity(slug: str, kind: str, specs: dict) -> Entity:
    entity = Entity.objects.create(type=kind, slug=slug, title=slug, status=EntityStatus.PUBLISHED)
    ComponentSpec.objects.create(entity=entity, category=kind, common=specs)
    return entity


@pytest.fixture
def parts():
    brand = Brand.objects.create(slug="test-brand", name="Test")
    assert brand  # the brand is not required by the rules; created for realism

    board_am5 = make_entity(
        "test-board-am5", EntityType.MOTHERBOARD, {"socket": "AM5", "memory_type": "DDR5"}
    )
    board_lga = make_entity(
        "test-board-lga", EntityType.MOTHERBOARD, {"socket": "LGA1700", "memory_type": "DDR4"}
    )
    cpu_am5 = make_entity("test-cpu-am5", EntityType.CPU, {"socket": "AM5", "tdp": 120})
    cpu_lga = make_entity("test-cpu-lga", EntityType.CPU, {"socket": "LGA1700", "tdp": 65})
    ram_ddr5 = make_entity("test-ram-ddr5", EntityType.RAM, {"memory_type": "DDR5"})
    ram_ddr4 = make_entity("test-ram-ddr4", EntityType.RAM, {"memory_type": "DDR4"})
    ssd = make_entity("test-ssd", EntityType.STORAGE, {"interface": "NVMe"})

    CompatibilityRule.objects.create(
        code="SOCKET_MATCH",
        category_a=EntityType.CPU,
        category_b=EntityType.MOTHERBOARD,
        severity=RuleSeverity.BLOCK,
    )
    CompatibilityRule.objects.create(
        code="RAM_TYPE_MATCH",
        category_a=EntityType.RAM,
        category_b=EntityType.MOTHERBOARD,
        severity=RuleSeverity.BLOCK,
    )
    return {
        "board_am5": board_am5,
        "board_lga": board_lga,
        "cpu_am5": cpu_am5,
        "cpu_lga": cpu_lga,
        "ram_ddr5": ram_ddr5,
        "ram_ddr4": ram_ddr4,
        "ssd": ssd,
    }


def check(parts: list[str], candidates: list[str]) -> dict:
    response = APIClient().post(CHECK, {"parts": parts, "candidates": candidates}, format="json")
    assert response.status_code == 200, response.data
    return response.data["candidate_results"]


class TestCandidateMapping:
    def test_every_candidate_has_its_own_verdict(self, parts):
        results = check([parts["board_am5"].slug], [parts["cpu_am5"].slug, parts["cpu_lga"].slug])

        assert set(results) == {parts["cpu_am5"].slug, parts["cpu_lga"].slug}
        assert results[parts["cpu_am5"].slug]["verdict"] == "ok"
        assert results[parts["cpu_lga"].slug]["verdict"] == "block"

    def test_the_mapping_does_not_depend_on_the_request_order(self, parts):
        forward = check([parts["board_am5"].slug], [parts["cpu_am5"].slug, parts["cpu_lga"].slug])
        backward = check([parts["board_am5"].slug], [parts["cpu_lga"].slug, parts["cpu_am5"].slug])

        for slug in (parts["cpu_am5"].slug, parts["cpu_lga"].slug):
            assert forward[slug]["verdict"] == backward[slug]["verdict"]

    def test_the_verdict_follows_the_selection(self, parts):
        am5 = check([parts["board_am5"].slug], [parts["cpu_am5"].slug])
        lga = check([parts["board_lga"].slug], [parts["cpu_am5"].slug])

        assert am5[parts["cpu_am5"].slug]["verdict"] == "ok"
        assert lga[parts["cpu_am5"].slug]["verdict"] == "block"

    def test_the_memory_type_is_checked_against_the_board(self, parts):
        results = check(
            [parts["board_am5"].slug, parts["cpu_am5"].slug],
            [parts["ram_ddr5"].slug, parts["ram_ddr4"].slug],
        )

        assert results[parts["ram_ddr5"].slug]["verdict"] == "ok"
        assert results[parts["ram_ddr4"].slug]["verdict"] == "block"


class TestUnknownAndUnchecked:
    def test_a_part_no_rule_can_compare_is_flagged_as_unchecked(self, parts):
        results = check([parts["board_am5"].slug, parts["cpu_am5"].slug], [parts["ssd"].slug])

        row = results[parts["ssd"].slug]
        # The verdict is "nothing blocked it", but nothing was *checked* either: the
        # UI must show neutral, and it keys that on `checked_rules`.
        assert row["verdict"] == "ok"
        assert row["checked_rules"] == 0
        assert row["has_specs"] is True
        assert row["known"] is True

    def test_an_unknown_candidate_is_not_reported_as_compatible(self):
        results = check(["does-not-exist"], ["also-missing"])

        row = results["also-missing"]
        assert row["known"] is False
        assert row["checked_rules"] == 0
        assert row["verdict"] == "unknown"

    def test_a_conflict_between_two_other_parts_is_not_borrowed(self, parts):
        # The CPU and the board disagree with each other; the SSD is only a
        # bystander and must not inherit their finding.
        results = check([parts["cpu_lga"].slug, parts["board_am5"].slug], [parts["ssd"].slug])

        row = results[parts["ssd"].slug]
        assert row["findings"] == []
        assert row["verdict"] == "ok"


class TestGpuAndCoolerVerdicts:
    """The GPU and the cooler must be judged decisively once their counterpart
    is chosen, and must *say why* when they cannot be judged yet."""

    @pytest.fixture
    def rig(self):
        cpu = make_entity("t-cpu", EntityType.CPU, {"socket": "AM5", "tdp": 120})
        board = make_entity("t-board", EntityType.MOTHERBOARD, {"socket": "AM5"})
        ram = make_entity("t-ram", EntityType.RAM, {"memory_type": "DDR5"})
        big_gpu = make_entity("t-gpu-big", EntityType.GPU, {"length_mm": 304, "tdp": 320})
        psu = make_entity(
            "t-psu",
            EntityType.PSU,
            {"wattage": 650, "connectors": ["8-pin CPU", "2x 8-pin PCIe"]},
        )
        small_case = make_entity(
            "t-case-small",
            EntityType.CASE,
            {"max_gpu_length_mm": 245, "max_cooler_height_mm": 165, "radiator_support_mm": 240},
        )
        air = make_entity("t-air", EntityType.COOLER, {"height_mm": 159, "sockets": ["AM5"]})
        aio = make_entity(
            "t-aio", EntityType.COOLER, {"height_mm": 55, "sockets": ["AM5"], "radiator_mm": 360}
        )
        for code, a, b in (
            ("PSU_WATTAGE", EntityType.PSU, EntityType.GPU),
            ("GPU_CLEARANCE", EntityType.CASE, EntityType.GPU),
            ("COOLER_FIT", EntityType.CASE, EntityType.COOLER),
            ("COOLER_SUPPORT", EntityType.COOLER, EntityType.CPU),
            ("PSU_CONNECTORS", EntityType.PSU, EntityType.GPU),
        ):
            CompatibilityRule.objects.create(
                code=code, category_a=a, category_b=b, severity=RuleSeverity.BLOCK
            )
        return {
            "cpu": cpu,
            "board": board,
            "ram": ram,
            "big_gpu": big_gpu,
            "psu": psu,
            "small_case": small_case,
            "air": air,
            "aio": aio,
        }

    def test_gpu_without_case_or_psu_is_not_determined_but_says_why(self, rig):
        results = check(
            [rig["cpu"].slug, rig["board"].slug, rig["ram"].slug], [rig["big_gpu"].slug]
        )
        row = results[rig["big_gpu"].slug]
        assert row["checked_rules"] == 0
        assert row["verdict"] == "ok"  # nothing blocked it, but nothing checked it either
        assert "کیس" in row["reason"]
        assert "منبع تغذیه" in row["reason"]

    def test_gpu_against_a_case_is_decided(self, rig):
        results = check([rig["small_case"].slug], [rig["big_gpu"].slug])
        row = results[rig["big_gpu"].slug]
        assert row["checked_rules"] >= 1
        assert row["verdict"] == "block"  # 304mm card in a 245mm case
        assert row["findings"][0]["rule_code"] == "GPU_CLEARANCE"
        assert row["reason"] == ""

    def test_aio_radiator_against_a_case_is_decided(self, rig):
        results = check(
            [rig["cpu"].slug, rig["small_case"].slug], [rig["aio"].slug, rig["air"].slug]
        )
        aio = results[rig["aio"].slug]
        assert aio["checked_rules"] >= 2  # COOLER_FIT + COOLER_SUPPORT were both credited
        assert aio["verdict"] == "block"  # a 360mm radiator in a 240mm case
        assert any(f["rule_code"] == "COOLER_FIT" for f in aio["findings"])

        air = results[rig["air"].slug]
        assert air["verdict"] == "ok"  # fits the case and supports the socket
        assert air["checked_rules"] >= 1

    def test_the_engine_is_order_independent(self, rig):
        """The display order must not decide the verdict.

        The same set of parts, checked in every possible order, has to produce
        the same verdict and the same findings — otherwise the stepper's order
        would be a hidden compatibility rule.
        """
        slugs = [
            rig["cpu"].slug,
            rig["board"].slug,
            rig["ram"].slug,
            rig["big_gpu"].slug,
            rig["small_case"].slug,
            rig["psu"].slug,
        ]
        baseline: tuple | None = None
        for order in itertools.permutations(slugs):
            report = check_parts(list(order))
            signature = (report.verdict, sorted(finding.rule_code for finding in report.findings))
            if baseline is None:
                baseline = signature
            else:
                assert signature == baseline, f"{order} differs from {baseline}"
        assert baseline is not None
        assert baseline[0] == "block"  # the 304mm card in the 245mm case
        assert "GPU_CLEARANCE" in baseline[1]
