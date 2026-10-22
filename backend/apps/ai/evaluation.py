"""The evaluation harness.

Measures the two things the spec asks for:

  * **retrieval hit-rate** — did the right chunk come back for the question?
  * **answer quality** — does the answer mention what it should, avoid what it
    should not, and carry citations?

The golden set lives in `evals/golden_set.jsonl`: one JSON object per line, each
with a query and what the answer should (and should not) contain.

The harness runs against the *retrieval* and the *guardrails*, not against a
live model: the model is scripted, so the score measures the pipeline rather
than the wording. That is what makes the number comparable between runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .chat import answer_query
from .guardrails import check_citations
from .llm import LLMResponse, Message
from .retrieval import retrieve

#: The default golden set location, relative to the repository root.
DEFAULT_GOLDEN_SET = "evals/golden_set.jsonl"


@dataclass
class GoldenCase:
    """One evaluation case."""

    id: str
    query: str
    language: str = "fa"
    expect_pages: list[str] = field(default_factory=list)
    expect_entities: list[str] = field(default_factory=list)
    must_mention: list[str] = field(default_factory=list)
    forbid: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> GoldenCase:
        return cls(
            id=str(data.get("id", "")),
            query=str(data.get("query", "")),
            language=str(data.get("language", "fa")),
            expect_pages=list(data.get("expect_pages", [])),
            expect_entities=list(data.get("expect_entities", [])),
            must_mention=list(data.get("must_mention", [])),
            forbid=list(data.get("forbid", [])),
        )


@dataclass
class CaseResult:
    """The outcome of one case."""

    case: GoldenCase
    retrieved_pages: list[str] = field(default_factory=list)
    retrieved_entities: list[str] = field(default_factory=list)
    page_hit: bool = False
    entity_hit: bool = False
    mention_ok: bool = True
    forbid_ok: bool = True
    cited: bool = False
    guarded: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def retrieval_ok(self) -> bool:
        """Did the retrieval find what the case expects?

        A case with no expectation is not judged on retrieval.
        """
        if not self.case.expect_pages and not self.case.expect_entities:
            return True
        return self.page_hit or self.entity_hit

    @property
    def answer_ok(self) -> bool:
        """Did the answer meet the content expectations?"""
        return self.mention_ok and self.forbid_ok and self.cited and self.guarded

    def as_dict(self) -> dict:
        return {
            "id": self.case.id,
            "query": self.case.query,
            "language": self.case.language,
            "retrieval_ok": self.retrieval_ok,
            "page_hit": self.page_hit,
            "entity_hit": self.entity_hit,
            "answer_ok": self.answer_ok,
            "mention_ok": self.mention_ok,
            "forbid_ok": self.forbid_ok,
            "cited": self.cited,
            "guarded": self.guarded,
            "retrieved_pages": self.retrieved_pages,
            "notes": self.notes,
        }


class ScriptedLLM:
    """A model that answers from the context it was given.

    It quotes the retrieved lines with their citation markers — the same shape
    a well-behaved model produces — so the guardrails and the citation check
    are exercised realistically.
    """

    name = "scripted"

    def complete(self, messages: list[Message], *, max_tokens: int = 1024) -> LLMResponse:
        text = self._respond(messages)
        return LLMResponse(text=text, model="scripted", provider="scripted")

    def stream(self, messages: list[Message], *, max_tokens: int = 1024):
        text = self._respond(messages)
        for index in range(0, len(text), 40):
            yield text[index : index + 40]

    def _respond(self, messages: list[Message]) -> str:
        system = next((m.content for m in messages if m.role == "system"), "")
        if "CONTEXT" not in system:
            return "پاسخی بدون زمینه."
        body = system.split("CONTEXT", 1)[1]
        quoted: list[str] = []
        current_index = ""
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("<<<") or line.startswith("==="):
                continue
            if line.startswith("["):
                # A new context entry: "[3] عنوان › بخش"
                current_index = line.split("]", 1)[0] + "]"
                continue
            if current_index and len(line) > 10:
                quoted.append(f"{line} {current_index}")
        if not quoted:
            return "اطلاعات کافی برای پاسخ پیدا نشد."
        return "بر اساس مستندات:\n" + "\n".join(quoted[:12])


def load_golden_set(path: str | Path) -> list[GoldenCase]:
    """Read the golden set file."""
    cases: list[GoldenCase] = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON: {exc}") from exc
            cases.append(GoldenCase.from_dict(data))
    return cases


def evaluate_case(case: GoldenCase, *, limit: int = 8) -> CaseResult:
    """Evaluate one case."""
    result = CaseResult(case=case)

    retrieval = retrieve(case.query, limit=limit)
    result.retrieved_pages = [chunk.chunk.page.slug for chunk in retrieval.chunks]
    result.retrieved_entities = [
        chunk.chunk.entity.slug for chunk in retrieval.chunks if chunk.chunk.entity is not None
    ]

    result.page_hit = any(expected in result.retrieved_pages for expected in case.expect_pages)
    result.entity_hit = any(
        expected in result.retrieved_entities for expected in case.expect_entities
    )

    # The answer, from the scripted model.
    answer = answer_query(case.query, llm=ScriptedLLM(), limit=limit, log=False)

    # The content expectations.
    lowered = answer.answer.lower()
    missing = [term for term in case.must_mention if term.lower() not in lowered]
    if missing:
        result.mention_ok = False
        result.notes.append(f"missing: {', '.join(missing)}")

    forbidden = [term for term in case.forbid if term.lower() in lowered]
    if forbidden:
        result.forbid_ok = False
        result.notes.append(f"forbidden present: {', '.join(forbidden)}")

    # The citations.
    if answer.citations:
        citation_check = check_citations(answer.answer, answer.citations)
        result.cited = citation_check.ok
    else:
        result.cited = True  # nothing to cite

    # The guardrails.
    result.guarded = answer.guardrails.get("ok", True)

    return result


def evaluate(path: str | Path | None = None, *, limit: int = 8) -> dict:
    """Run the whole golden set and report the scores."""
    if path is None:
        from django.conf import settings

        path = settings.GOLDEN_SET_PATH
    cases = load_golden_set(path)
    results = [evaluate_case(case, limit=limit) for case in cases]

    total = len(results)
    retrieval_hits = sum(1 for r in results if r.retrieval_ok)
    answer_ok = sum(1 for r in results if r.answer_ok)
    page_hits = sum(1 for r in results if r.page_hit)
    entity_hits = sum(1 for r in results if r.entity_hit)
    cited = sum(1 for r in results if r.cited)
    guarded = sum(1 for r in results if r.guarded)

    by_language: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_language.setdefault(
            result.case.language, {"total": 0, "retrieval": 0, "answer": 0}
        )
        bucket["total"] += 1
        bucket["retrieval"] += 1 if result.retrieval_ok else 0
        bucket["answer"] += 1 if result.answer_ok else 0

    return {
        "total": total,
        "retrieval_hit_rate": round(retrieval_hits / total, 4) if total else 0.0,
        "answer_quality": round(answer_ok / total, 4) if total else 0.0,
        "page_hit_rate": round(page_hits / total, 4) if total else 0.0,
        "entity_hit_rate": round(entity_hits / total, 4) if total else 0.0,
        "citation_rate": round(cited / total, 4) if total else 0.0,
        "guardrail_pass_rate": round(guarded / total, 4) if total else 0.0,
        "by_language": by_language,
        "results": [result.as_dict() for result in results],
    }
