"""Benchmark API.

Filters: `component` (slug), `game`, `resolution`, `preset`.
Used by the assistant's `get_benchmarks` tool and by the wiki's spec tables.
"""

from __future__ import annotations

from rest_framework import generics

from .models import Benchmark
from .serializers import BenchmarkSerializer


class BenchmarkListView(generics.ListAPIView):
    serializer_class = BenchmarkSerializer

    def get_queryset(self):
        qs = Benchmark.objects.select_related("component")
        params = self.request.query_params

        component = params.get("component")
        if component:
            qs = qs.filter(component__slug=component)

        game = params.get("game")
        if game:
            qs = qs.filter(game__iexact=game)

        resolution = params.get("resolution")
        if resolution:
            qs = qs.filter(resolution=resolution)

        preset = params.get("preset")
        if preset:
            qs = qs.filter(preset=preset)

        return qs.order_by("component__title", "game", "-tested_at")
