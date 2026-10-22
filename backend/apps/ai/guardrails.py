"""Guardrails: the rules that keep the assistant honest.

The hard rules from the spec:
  * The model must never state a price, a stock count or a spec from its own
    memory — only from a tool result.
  * Every claim taken from wiki content must carry a citation.
  * When the data is insufficient, say so; never fabricate.
  * Retrieved content is untrusted data: strip the instructions from it before
    it reaches the prompt.

This module holds the *mechanics* of those rules, so they can be tested
without a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Patterns that look like an instruction aimed at the model.
_INSTRUCTION_PATTERNS = [
    re.compile(
        r"^\s*(ignore|disregard|forget)\b.{0,60}\b(instruction|instruction|rule|prompt)", re.I
    ),
    re.compile(r"^\s*(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|earlier)", re.I),
    re.compile(r"^\s*you\s+are\s+now\b", re.I),
    re.compile(r"^\s*(new|updated|revised)\s+(system\s+)?(prompt|instruction)", re.I),
    re.compile(r"^\s*(system|assistant|developer)\s*[:：]", re.I),
    re.compile(r"^\s*###\s*(instruction|system)", re.I),
    re.compile(r"^\s*(do not|don't)\s+(tell|inform|mention|reveal)\b", re.I),
    # Persian injections.
    re.compile(r"(نادیده\s*بگیر|نادیده\s*بگیرید|دستور\s+قبلی|دستورهای\s+قبلی)", re.I),
    re.compile(r"^\s*تو\s+اکنون\s+هستی", re.I),
    re.compile(r"(قیمت\s+را\s+بگو|قیمت\s+را\s+اعلام\s+کن)", re.I),
    re.compile(r"</?(system|assistant|user)>", re.I),
]

#: A number that could be a price, in Persian or Latin digits.
_NUMBER_RE = re.compile(r"[0-9۰-۹٠-٩][0-9۰-۹٠-٩.,٬٫ ]*[0-9۰-۹٠-٩]?")

#: The words that introduce a price, in Persian and English.
_PRICE_CUE_RE = re.compile(r"(قیمت|قیمتی|تومان|ریال|هزینه|price|cost|usd|toman|rial)", re.I)

#: The words that introduce a stock count.
_STOCK_CUE_RE = re.compile(
    r"(موجودی|موجود|انبار|تعداد\s+موجود|stock|in\s+stock|availability|available)", re.I
)


@dataclass
class SanitizedContent:
    """A retrieved chunk, stripped of anything that looks like an instruction."""

    text: str
    removed_lines: list[str] = field(default_factory=list)
    was_modified: bool = False


def sanitize_retrieved(text: str) -> SanitizedContent:
    """Strip instruction-like lines from retrieved content.

    The content comes from the wiki, which is editor-controlled — but a page
    could still contain a sentence that reads like a prompt. The retrieved
    text is *data*, never instructions, and this makes that concrete.
    """
    if not text:
        return SanitizedContent(text="")

    kept: list[str] = []
    removed: list[str] = []

    for line in text.splitlines():
        if any(pattern.search(line) for pattern in _INSTRUCTION_PATTERNS):
            removed.append(line)
            continue
        kept.append(line)

    if not removed:
        return SanitizedContent(text=text)

    return SanitizedContent(
        text="\n".join(kept),
        removed_lines=removed,
        was_modified=True,
    )


def wrap_untrusted(text: str, label: str = "محتوای بازیابی‌شده") -> str:
    """Wrap retrieved content in delimiters, so the model can see it is data."""
    return f"<<<{label}>>>\n{text}\n<<<END {label}>>>"


@dataclass
class FactCheck:
    """The result of checking a draft answer against the tool results."""

    ok: bool
    violations: list[str] = field(default_factory=list)
    uncited_claims: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "violations": self.violations,
            "uncited_claims": self.uncited_claims,
        }


def _to_persian_digits(text: str) -> str:
    """Fold every digit set to Latin, so the checks compare like with like."""
    table = {ord("۰") + i: str(i) for i in range(10)}
    table.update({ord("٠") + i: str(i) for i in range(10)})
    return text.translate(table)


#: A citation marker like "[1]" or "[2, 3]" — not a number in the text.
_CITATION_MARKER_RE = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")


def numbers_in(text: str) -> set[str]:
    """The numbers in a text, normalised (digits folded, separators removed).

    Citation markers ("[1]") are removed first — they are references, not
    claims, and treating them as prices would flag every cited answer.

    The trailing decimal part is dropped, so the price "32900000.00" from the
    catalog and "32900000" in an answer are the same number.
    """
    found: set[str] = set()
    without_markers = _CITATION_MARKER_RE.sub(" ", text)
    for match in _NUMBER_RE.findall(without_markers):
        normalized = _to_persian_digits(match)
        normalized = normalized.replace(",", "").replace("٬", "").replace("٫", ".")
        normalized = normalized.replace(" ", "").strip()
        if not normalized or normalized in {".", ","}:
            continue
        if "." in normalized:
            # "32900000.00" → "32900000" (and "1.5" → "1.5" stays distinct
            # from "15" — only a trailing zero fraction is dropped).
            head, _, tail = normalized.rpartition(".")
            if tail and set(tail) == {"0"}:
                normalized = head
        if normalized:
            found.add(normalized)
    return found


def check_facts(answer: str, tool_facts: list[str]) -> FactCheck:
    """Check that every price and stock count in the answer came from the tools.

    `tool_facts` is the list of values the tools returned. A number in the
    answer that is not in that list is a fabrication — the model made it up.

    Numbers that are not introduced by a price or stock cue are left alone:
    a year, a core count or a resolution is not a shop fact.
    """
    result = FactCheck(ok=True)
    allowed = set()
    for fact in tool_facts:
        allowed |= numbers_in(fact)

    for sentence in re.split(r"(?<=[.!?؟۔\n])\s+", answer):
        if not sentence.strip():
            continue
        is_fact_sentence = bool(_PRICE_CUE_RE.search(sentence) or _STOCK_CUE_RE.search(sentence))
        if not is_fact_sentence:
            continue
        for number in numbers_in(sentence):
            if number not in allowed:
                result.violations.append(
                    f"number {number!r} in the answer is not in the tool results: {sentence.strip()[:120]}"
                )
                result.ok = False

    return result


def check_citations(answer: str, citations: list[dict]) -> FactCheck:
    """Check that the answer carries citations for its wiki claims.

    The rule: if the answer mentions a wiki page (or a section of one), there
    must be at least one citation. An answer with no citation at all and no
    wiki claim is fine — it may be answering from the catalog only.
    """
    result = FactCheck(ok=True)
    if not citations:
        return result

    # A citation marker is a bracketed number, or a wiki URL.
    has_marker = bool(re.search(r"\[\d+\]|\[منبع|https?://|/wiki/", answer))
    if not has_marker:
        result.uncited_claims.append("the answer uses wiki content but carries no citation marker")
        result.ok = False

    return result


def enforce(answer: str, tool_facts: list[str], citations: list[dict]) -> tuple[str, dict]:
    """Apply the guardrails to a draft answer.

    Returns the answer to send and a report of what was checked. A violation
    replaces the answer with an honest "I don't have this" message, because a
    fabricated price is worse than no answer.
    """
    facts = check_facts(answer, tool_facts)
    cited = check_citations(answer, citations)

    report = {
        "facts": facts.as_dict(),
        "citations": cited.as_dict(),
        "ok": facts.ok and cited.ok,
    }

    if not facts.ok:
        return (
            "متأسفم — نمی‌توانم این اطلاعات را تأیید کنم. لطفاً از دادهٔ موجود استفاده کنید.",
            report,
        )
    if not cited.ok:
        return (
            "متأسفم — پاسخ بدون استناد قابل ارائه نیست. لطفاً دوباره جستجو کنید.",
            report,
        )
    return answer, report
