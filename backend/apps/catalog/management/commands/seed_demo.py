from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed realistic demo data (CPUs, GPUs, RAM, boards, PSUs, cases, prebuilt PCs)."

    def handle(self, *args: object, **options: object) -> None:
        self.stdout.write(
            self.style.WARNING(
                "seed_demo is a Phase 0 stub — real demo data lands in Phase 1 "
                "(docs/PLAN.md). Nothing was written to the database."
            )
        )
