"""Rebuild the search indexes.

python manage.py reindex            # rebuild the Meilisearch indexes
python manage.py reindex --stats    # just show what is indexed
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.search.indexer import build_documents, reindex_all
from apps.search.meili import get_client


class Command(BaseCommand):
    help = "Rebuild the search indexes (Meilisearch) from the database."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Only show what would be indexed; do not write to Meilisearch.",
        )
        parser.add_argument(
            "--no-reset",
            action="store_true",
            help="Merge with the existing index instead of replacing it.",
        )

    def handle(self, *args: object, **options: object) -> None:
        if options.get("stats"):
            documents = build_documents()
            for index, docs in documents.items():
                self.stdout.write(f"{index}: {len(docs)} documents")
            self.stdout.write(f"total: {sum(len(d) for d in documents.values())} documents")
            self.stdout.write(f"meilisearch reachable: {get_client().available()}")
            return

        report = reindex_all(reset=not options.get("no_reset"))
        self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False))

        if report["meilisearch"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Indexed {report['total_documents']} documents across "
                    f"{len(report['indexes'])} indexes."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Meilisearch is not reachable — the search falls back to "
                    "PostgreSQL. Start it with `docker compose up meilisearch` "
                    "and run this again."
                )
            )
            for error in report["errors"]:
                self.stdout.write(self.style.WARNING(f"  {error}"))
