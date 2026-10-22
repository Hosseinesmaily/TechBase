"""Drop the semantic cache.

    python manage.py invalidate_cache

Run it after a catalog change (a price sync, a new product): the cached
answers quote the old prices.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.ai.cache import invalidate, stats


class Command(BaseCommand):
    help = "Empty the semantic cache (the cached answers may quote old prices)."

    def handle(self, *args: object, **options: object) -> None:
        before = stats()
        deleted = invalidate()
        after = stats()
        self.stdout.write(
            self.style.SUCCESS(
                f"cache cleared: {deleted} entries dropped, "
                f"{before['cached_turns']} → {after['cached_turns']} cached turns"
            )
        )
