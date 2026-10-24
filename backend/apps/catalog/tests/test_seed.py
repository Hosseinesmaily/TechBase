"""Tests for the demo seed command.

The seed data is the substrate of every demo and of the Phase 4 evaluation
set, so it must be internally consistent: every prebuilt's parts must exist
and be compatible with each other.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.benchmarks.models import Benchmark
from apps.catalog.models import ComponentSpec, Entity, EntityType, Product
from apps.compat.models import CompatibilityRule
from apps.compat.services import check_parts

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_demo", verbosity=0)
    return True


class TestSeedCreatesData:
    def test_creates_brands_categories_entities_products(self, seeded):
        assert Entity.objects.count() > 20
        assert Product.objects.count() > 20
        assert CompatibilityRule.objects.count() == 7
        assert Benchmark.objects.count() > 20

    def test_creates_ten_prebuilt_pcs(self, seeded):
        prebuilts = Entity.objects.filter(type=EntityType.PREBUILT)
        assert prebuilts.count() == 10

    def test_every_product_points_at_an_entity(self, seeded):
        for product in Product.objects.all():
            assert product.entity_id is not None
            assert product.price > 0

    def test_seed_is_idempotent(self, seeded):
        entity_count = Entity.objects.count()
        product_count = Product.objects.count()
        call_command("seed_demo", verbosity=0)
        assert Entity.objects.count() == entity_count
        assert Product.objects.count() == product_count

    def test_specs_exist_for_components(self, seeded):
        gpu = Entity.objects.get(slug="rtx-4060")
        spec = ComponentSpec.objects.get(entity=gpu)
        assert spec.common["vram_gb"] == 8
        assert spec.common.get("tdp") == 115

    def test_products_carry_persian_titles(self, seeded):
        product = Product.objects.get(sku="tb-gpu-4070s")
        assert product.title_fa
        assert product.currency == "IRT"

    def test_component_product_titles_follow_a_consistent_persian_format(self, seeded):
        gpu = Product.objects.get(sku="tb-gpu-4070s")
        motherboard = Product.objects.get(sku="tb-mb-b650plus")
        memory = Product.objects.get(sku="tb-ram-32-6000")

        assert gpu.display_title.startswith("کارت گرافیک انویدیا مدل ")
        assert "حافظهٔ ۱۲ گیگابایت" in gpu.display_title
        assert motherboard.display_title.startswith("مادربرد ایسوس مدل ")
        assert "مدل Vengeance RGB" in memory.display_title
        assert "ظرفیت ۳۲ گیگابایت" in memory.display_title

    def test_prebuilt_titles_identify_the_category_and_model(self, seeded):
        gaming_pc = Product.objects.get(sku="tb-sku-striker-1080")
        office_pc = Product.objects.get(sku="tb-sku-nomad-office")

        assert gaming_pc.display_title.startswith("سیستم گیمینگ تک‌بیس مدل Striker 1080")
        assert office_pc.display_title.startswith("سیستم اداری تک‌بیس مدل Nomad Office")


class TestSeedIsInternallyConsistent:
    """The demo data must survive its own compatibility engine."""

    def test_every_prebuilt_is_compatible(self, seeded):
        for prebuilt in Entity.objects.filter(type=EntityType.PREBUILT):
            spec = ComponentSpec.objects.get(entity=prebuilt)
            parts = spec.common["components"]
            report = check_parts(parts)
            assert report.verdict != "block", f"{prebuilt.slug} is blocked: {report.findings}"

    def test_prebuilt_specs_reference_real_entities(self, seeded):
        slugs = set(Entity.objects.values_list("slug", flat=True))
        for prebuilt in Entity.objects.filter(type=EntityType.PREBUILT):
            spec = ComponentSpec.objects.get(entity=prebuilt)
            for part in spec.common["components"]:
                assert part in slugs, f"{prebuilt.slug} references unknown {part}"

    def test_benchmarks_reference_real_components(self, seeded):
        for benchmark in Benchmark.objects.all():
            assert benchmark.component_id is not None
            assert benchmark.avg_fps > 0
            assert benchmark.p1_low is None or benchmark.p1_low <= benchmark.avg_fps


class TestKnownIncompatibilities:
    """The engine must actually catch a bad pairing in the seeded catalog."""

    def test_ryzen_with_intel_board_is_blocked(self, seeded):
        report = check_parts(["ryzen-7-7800x3d", "gigabyte-b760m-ds3h"])
        assert report.verdict == "block"
        assert any(f.rule_code == "SOCKET_MATCH" for f in report.findings)

    def test_ddr4_on_ddr5_board_is_blocked(self, seeded):
        report = check_parts(["kingston-fury-beast-32gb-ddr4-3200", "asus-tuf-gaming-b650-plus"])
        assert report.verdict == "block"
        assert any(f.rule_code == "RAM_TYPE_MATCH" for f in report.findings)

    def test_long_gpu_in_small_case_is_blocked(self, seeded):
        # The RTX 4080 SUPER reference design is 304mm; the seeded H5 Flow takes
        # 365mm, so it fits. Shrink the case to 280mm and it must be rejected.
        report = check_parts(["rtx-4080-super", "nzxt-h5-flow"])
        assert report.verdict == "ok"

        case = Entity.objects.get(slug="nzxt-h5-flow")
        spec = ComponentSpec.objects.get(entity=case)
        spec.common["max_gpu_length_mm"] = 280
        spec.save()

        report = check_parts(["rtx-4080-super", "nzxt-h5-flow"])
        assert report.verdict == "block"
        assert any(f.rule_code == "GPU_CLEARANCE" for f in report.findings)

    def test_matching_build_is_ok(self, seeded):
        report = check_parts(
            [
                "ryzen-7-7800x3d",
                "rtx-4070-super",
                "corsair-vengeance-rgb-32gb-ddr5-6000",
                "asus-tuf-gaming-b650-plus",
                "corsair-rm650x",
                "lian-li-lancool-216",
                "cooler-master-hyper-212",
            ]
        )
        assert report.verdict == "ok", [f.message for f in report.findings]

    def test_unknown_slug_is_reported_not_silently_dropped(self, seeded):
        report = check_parts(["rtx-4060", "not-a-real-part"])
        assert any(f.rule_code == "UNKNOWN_PART" for f in report.findings)
