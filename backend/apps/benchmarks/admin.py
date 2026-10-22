from django.contrib import admin

from .models import Benchmark


@admin.register(Benchmark)
class BenchmarkAdmin(admin.ModelAdmin):
    list_display = ("component", "game", "resolution", "preset", "avg_fps", "p1_low", "tested_at")
    list_filter = ("resolution", "preset", "game", "tested_at")
    search_fields = ("game", "game_fa", "component__title", "component__title_fa")
    autocomplete_fields = ("component",)
    date_hierarchy = "tested_at"
