from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Rebuild Meilisearch + pgvector indexes for catalog and wiki content."

    def handle(self, *args: object, **options: object) -> None:
        self.stdout.write(
            self.style.WARNING(
                "reindex is a Phase 0 stub — search indexing lands in Phase 3 and "
                "embeddings in Phase 4 (docs/PLAN.md). Nothing was indexed."
            )
        )
