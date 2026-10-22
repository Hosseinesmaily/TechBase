"""Run the RAG evaluation against the golden set.

python manage.py run_evals               # the summary
python manage.py run_evals --verbose     # every case
python manage.py run_evals --json        # machine-readable
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.ai.evaluation import DEFAULT_GOLDEN_SET, evaluate
from apps.core.console import safe


class Command(BaseCommand):
    help = "Evaluate the retrieval and the answers against evals/golden_set.jsonl."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--path",
            default=None,
            help=f"Path to the golden set (default: {DEFAULT_GOLDEN_SET}).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print every case, not just the summary.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the raw report as JSON.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=8,
            help="How many chunks to retrieve per question (default: 8).",
        )
        parser.add_argument(
            "--min-retrieval",
            type=float,
            default=0.7,
            help="Fail the command if the retrieval hit-rate is below this (0 disables).",
        )
        parser.add_argument(
            "--min-answer",
            type=float,
            default=0.6,
            help="Fail the command if the answer quality is below this (0 disables).",
        )

    def write(self, text: str) -> None:
        """Write a line, replacing what the terminal cannot show."""
        self.stdout.write(safe(text))

    def handle(self, *args: object, **options: object) -> None:
        path: str | Path = str(options.get("path") or "")
        if not path:
            from django.conf import settings

            path = settings.GOLDEN_SET_PATH

        limit = int(str(options["limit"]))
        report = evaluate(path, limit=limit)

        if bool(options.get("json")):
            self.write(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            self._print_report(report, verbose=bool(options.get("verbose", False)))

        min_retrieval = options.get("min_retrieval") or 0
        min_answer = options.get("min_answer") or 0
        if report["retrieval_hit_rate"] < min_retrieval:
            raise SystemExit(
                f"retrieval hit-rate {report['retrieval_hit_rate']:.2%} is below "
                f"the required {min_retrieval:.2%}"
            )
        if report["answer_quality"] < min_answer:
            raise SystemExit(
                f"answer quality {report['answer_quality']:.2%} is below "
                f"the required {min_answer:.2%}"
            )

    def _print_report(self, report: dict, *, verbose: bool) -> None:
        self.write("")
        self.write("=" * 62)
        self.write("TechBase — RAG evaluation")
        self.write("=" * 62)
        self.write(f"cases              : {report['total']}")
        self.write(
            f"retrieval hit-rate : {report['retrieval_hit_rate']:.1%}  "
            f"(page {report['page_hit_rate']:.1%}, entity {report['entity_hit_rate']:.1%})"
        )
        self.write(f"answer quality     : {report['answer_quality']:.1%}")
        self.write(f"citation rate      : {report['citation_rate']:.1%}")
        self.write(f"guardrail pass     : {report['guardrail_pass_rate']:.1%}")

        if report["by_language"]:
            self.write("")
            self.write("per language:")
            for language, bucket in sorted(report["by_language"].items()):
                retrieval = bucket["retrieval"] / bucket["total"] if bucket["total"] else 0
                answer = bucket["answer"] / bucket["total"] if bucket["total"] else 0
                self.write(
                    f"  {language}: {bucket['total']:2} cases, "
                    f"retrieval {retrieval:.1%}, answer {answer:.1%}"
                )

        failures = [r for r in report["results"] if not (r["retrieval_ok"] and r["answer_ok"])]
        if failures:
            self.write("")
            self.write(f"failures ({len(failures)}):")
            for failure in failures:
                self.write(f"  {failure['id']}: {failure['query'][:52]}")
                for note in failure["notes"]:
                    self.write(f"      - {note}")
                if not failure["retrieval_ok"]:
                    self.write(f"      - expected page(s) {failure['retrieved_pages']}")

        if verbose:
            self.write("")
            self.write("every case:")
            for result in report["results"]:
                mark = "ok  " if result["retrieval_ok"] and result["answer_ok"] else "FAIL"
                self.write(
                    f"  [{mark}] {result['id']} ({result['language']}): {result['query'][:46]}"
                )

        self.write("")
