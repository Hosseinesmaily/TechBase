from __future__ import annotations

from rest_framework import serializers

from .models import Benchmark


class BenchmarkSerializer(serializers.ModelSerializer):
    component_slug: serializers.SlugRelatedField = serializers.SlugRelatedField(
        source="component", slug_field="slug", read_only=True
    )
    component_title = serializers.CharField(source="component.title", read_only=True)
    component_title_fa = serializers.CharField(source="component.title_fa", read_only=True)

    class Meta:
        model = Benchmark
        fields = (
            "id",
            "component_slug",
            "component_title",
            "component_title_fa",
            "game",
            "game_fa",
            "resolution",
            "preset",
            "avg_fps",
            "p1_low",
            "test_rig",
            "tested_at",
            "source",
        )
        read_only_fields = fields
