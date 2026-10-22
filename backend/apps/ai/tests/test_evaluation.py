"""Tests for the evaluation harness and the golden set."""

from __future__ import annotations

import json

import pytest
from django.conf import settings
from django.core.management import call_command

from apps.ai.evaluation import (
    GoldenCase,
    evaluate,
    evaluate_case,
    load_golden_set,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def indexed():
    from django.core.management import call_command as run

    run("seed_demo", verbosity=0)
    run("seed_wiki", verbosity=0)
    run("index_content", verbosity=0)
    return True


class TestGoldenSet:
    def test_the_file_exists(self):
        assert settings.GOLDEN_SET_PATH.exists()

    def test_it_has_forty_cases(self):
        cases = load_golden_set(settings.GOLDEN_SET_PATH)
        assert len(cases) == 40

    def test_thirty_persian_and_ten_english(self):
        cases = load_golden_set(settings.GOLDEN_SET_PATH)
        assert sum(1 for case in cases if case.language == "fa") == 30
        assert sum(1 for case in cases if case.language == "en") == 10

    def test_every_case_has_a_query_and_an_id(self):
        for case in load_golden_set(settings.GOLDEN_SET_PATH):
            assert case.id
            assert case.query

    def test_the_ids_are_unique(self):
        cases = load_golden_set(settings.GOLDEN_SET_PATH)
        assert len({case.id for case in cases}) == len(cases)

    def test_every_line_is_valid_json(self):
        with open(settings.GOLDEN_SET_PATH, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    assert isinstance(json.loads(line), dict)


class TestEvaluateCase:
    def test_a_case_that_should_hit_does(self, indexed):
        case = GoldenCase(
            id="t1",
            query="حافظه DDR5 چیست؟",
            expect_pages=["ddr5"],
        )
        result = evaluate_case(case)
        assert result.page_hit
        assert result.retrieval_ok

    def test_the_missing_mentions_are_reported(self, indexed):
        case = GoldenCase(
            id="t2",
            query="حافظه DDR5 چیست؟",
            must_mention=["یک عبارت ناموجود"],
        )
        result = evaluate_case(case)
        assert not result.mention_ok
        assert result.notes

    def test_a_forbidden_phrase_is_reported(self, indexed):
        case = GoldenCase(
            id="t3",
            query="حافظه DDR5 چیست؟",
            forbid=["DDR5"],
        )
        result = evaluate_case(case)
        assert not result.forbid_ok

    def test_a_case_with_no_expectations_passes_retrieval(self, indexed):
        case = GoldenCase(id="t4", query="حافظه DDR5 چیست؟")
        result = evaluate_case(case)
        assert result.retrieval_ok


class TestEvaluate:
    def test_the_report_has_the_documented_shape(self, indexed):
        report = evaluate(settings.GOLDEN_SET_PATH)
        for key in (
            "total",
            "retrieval_hit_rate",
            "answer_quality",
            "citation_rate",
            "guardrail_pass_rate",
            "by_language",
            "results",
        ):
            assert key in report

    def test_the_scores_are_in_range(self, indexed):
        report = evaluate(settings.GOLDEN_SET_PATH)
        for key in (
            "retrieval_hit_rate",
            "answer_quality",
            "citation_rate",
            "guardrail_pass_rate",
        ):
            assert 0.0 <= report[key] <= 1.0

    def test_the_citations_always_pass(self, indexed):
        """Every case that retrieves content must carry a citation."""
        report = evaluate(settings.GOLDEN_SET_PATH)
        assert report["citation_rate"] == 1.0

    def test_the_guardrails_always_pass(self, indexed):
        """The scripted model never fabricates, so the guardrails must pass."""
        report = evaluate(settings.GOLDEN_SET_PATH)
        assert report["guardrail_pass_rate"] == 1.0

    def test_the_per_language_breakdown(self, indexed):
        report = evaluate(settings.GOLDEN_SET_PATH)
        assert report["by_language"]["fa"]["total"] == 30
        assert report["by_language"]["en"]["total"] == 10


class TestRunEvalsCommand:
    def test_it_runs(self, indexed):
        call_command("run_evals", verbosity=0)

    def test_it_reports_json(self, indexed, capsys):
        call_command("run_evals", json=True, verbosity=0)
        out = capsys.readouterr().out
        report = json.loads(out)
        assert report["total"] == 40

    def test_it_fails_below_the_threshold(self, indexed):
        """A deliberately impossible threshold must fail the command."""
        with pytest.raises(SystemExit):
            call_command("run_evals", min_retrieval=1.1, verbosity=0)
