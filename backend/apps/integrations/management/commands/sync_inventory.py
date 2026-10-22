"""Run the inventory sync from the command line (or from a cron job)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.integrations.tasks import sync_inventory


class Command(BaseCommand):
    help = "Sync price/stock from an inventory adapter (mock or csv)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--adapter",
            default="mock",
            help="Inventory adapter to use: 'mock' (default) or 'csv'.",
        )
        parser.add_argument(
            "--path",
            default=None,
            help="Path to the CSV file (required for the csv adapter).",
        )

    def handle(self, *args: object, **options: object) -> None:
        path_option = options.get("path")
        result = sync_inventory(
            adapter=str(options.get("adapter") or "mock"),
            path=str(path_option) if path_option else None,
        )
        if result.get("error"):
            self.stderr.write(self.style.ERROR(f"sync failed: {result['error']}"))
            return
        counts = result["counts"]
        self.stdout.write(
            self.style.SUCCESS(
                f"sync ({result['source']}): {counts['updated']} updated, "
                f"{counts['unchanged']} unchanged, {counts['unknown']} unknown"
            )
        )
        if result["unknown"]:
            self.stdout.write(
                self.style.WARNING(f"unknown SKUs (not created): {', '.join(result['unknown'])}")
            )
