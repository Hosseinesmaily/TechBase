"""Benchmark results: measured FPS for a component in a game at a resolution.

Benchmarks are *evidence*, not marketing: each row records the rig it was
measured on and when, so a recommendation can cite the number and the user can
see its provenance.
"""

from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class Resolution(models.TextChoices):
    HD = "720p", "720p"
    FHD = "1080p", "1080p"
    QHD = "1440p", "1440p"
    UHD = "4k", "4K"


class Benchmark(UUIDModel, TimeStampedModel):
    """avg_fps / p1_low for one component in one game at one resolution."""

    component = models.ForeignKey(
        "catalog.Entity", on_delete=models.CASCADE, related_name="benchmarks"
    )
    game = models.CharField(max_length=120, db_index=True)
    game_fa = models.CharField(max_length=120, blank=True)
    resolution = models.CharField(max_length=16, choices=Resolution.choices, db_index=True)
    preset = models.CharField(max_length=64, default="high")  # low | medium | high | ultra
    avg_fps = models.PositiveSmallIntegerField()
    p1_low = models.PositiveSmallIntegerField(null=True, blank=True)
    # The machine the numbers came from: {"cpu": "...", "gpu": "...", "ram": "..."}
    test_rig = models.JSONField(default=dict, blank=True)
    tested_at = models.DateField(db_index=True)
    source = models.CharField(max_length=64, default="seed")

    class Meta:
        ordering = ["-tested_at", "game"]
        constraints = [
            models.UniqueConstraint(
                fields=["component", "game", "resolution", "preset", "tested_at"],
                name="uniq_benchmark_measurement",
            )
        ]
        indexes = [
            models.Index(fields=["component", "resolution"], name="bench_comp_res_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.component.title} / {self.game} @ {self.resolution} = {self.avg_fps}fps"
