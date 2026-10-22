"""Query understanding: turn a question into a structured request.

The model returns **strict JSON** (docs/PLAN.md, the agentic flow):

    {
      "use_case": "gaming" | "office" | "content_creation" | "",
      "resolution": "1080p" | "1440p" | "4k" | "",
      "fps_target": 144 | 0,
      "budget_max": 60000000 | 0,
      "language": "fa" | "en",
      "missing_info": ["budget_max"],
      "clarifying_question": "..."
    }

The parse is defensive: a malformed or partial response falls back to the
heuristics below rather than failing the turn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .llm import Message, get_llm, parse_json_response

#: The resolutions the catalog knows about.
RESOLUTIONS = ("1080p", "1440p", "4k", "720p")

#: The use cases the assistant can route.
USE_CASES = ("gaming", "office", "content_creation", "streaming", "programming")

UNDERSTAND_PROMPT = """تو یک تحلیل‌گر پرسش هستی. پرسش کاربر را تحلیل کن و **فقط JSON** برگردان.

قالب دقیق:
{
  "use_case": "gaming|office|content_creation|streaming|programming|",
  "resolution": "1080p|1440p|4k|720p|",
  "fps_target": 0,
  "budget_max": 0,
  "language": "fa|en",
  "missing_info": [],
  "clarifying_question": ""
}

قواعد:
- اعداد را به رقم لاتین بنویس. budget_max به **تومان** است.
- اگر چیزی در پرسش نیامده، مقدار را خالی یا صفر بگذار.
- missing_info فهرست فیلدهای حیاتیِ ناموجود است: "budget_max" و "use_case".
- اگر بودجه یا کاربرد نامعلوم است، یک clarifying_question کوتاه فارسی بنویس.
- هیچ توضیحی بیرون از JSON ننویس.

پرسش: {query}
"""


@dataclass
class QueryUnderstanding:
    """What the assistant understood from the question."""

    use_case: str = ""
    resolution: str = ""
    fps_target: int = 0
    budget_max: int = 0
    language: str = "fa"
    missing_info: list[str] = field(default_factory=list)
    clarifying_question: str = ""
    # The raw model output, for the log.
    raw: dict[str, Any] = field(default_factory=dict)
    # True when the heuristics filled in the answer instead of the model.
    used_heuristics: bool = False

    def as_dict(self) -> dict:
        return {
            "use_case": self.use_case,
            "resolution": self.resolution,
            "fps_target": self.fps_target,
            "budget_max": self.budget_max,
            "language": self.language,
            "missing_info": self.missing_info,
            "clarifying_question": self.clarifying_question,
            "used_heuristics": self.used_heuristics,
        }

    @property
    def needs_clarification(self) -> bool:
        """Whether one question should be asked before answering.

        The spec allows **one** clarifying question, and only when something
        critical is missing.
        """
        return bool(self.clarifying_question) and bool(self.missing_info)


# --- Heuristics --------------------------------------------------------------

# Persian and Arabic digits, folded to Latin before matching.
_DIGIT_MAP = {ord("۰") + i: str(i) for i in range(10)}
_DIGIT_MAP.update({ord("٠") + i: str(i) for i in range(10)})


def _fold_digits(text: str) -> str:
    """Persian/Arabic digits → Latin."""
    return text.translate(_DIGIT_MAP)


_RESOLUTION_RE = re.compile(r"\b(720p|1080p|1440p|4k|2160p)\b", re.IGNORECASE)
_FPS_RE = re.compile(r"(\d{2,3})\s*(?:fps|فریم)", re.IGNORECASE)
_BUDGET_RE = re.compile(r"(\d[\d,٬]*(?:\.\d+)?)\s*(?:میلیون|تومان|تومن)", re.IGNORECASE)
_MILLION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*میلیون", re.IGNORECASE)

#: Words that signal the use case.
_USE_CASE_CUES = {
    "gaming": ("گیم", "بازی", "game", "games", "fps", "فریم"),
    "office": ("اداری", "تایپ", "برنامه", "office", "word", "excel"),
    "content_creation": ("رندر", "ادیت", "ویدیو", "استریم", "render", "edit", "stream"),
    "programming": ("برنامه‌نویسی", "کدنویسی", "compile", "programming"),
}


def _normalise_resolution(text: str) -> str:
    match = _RESOLUTION_RE.search(_fold_digits(text))
    if not match:
        return ""
    value = match.group(1).lower()
    return {"2160p": "4k"}.get(value, value)


def _normalise_budget(text: str) -> int:
    """The budget in tomans."""
    folded = _fold_digits(text)
    million = _MILLION_RE.search(folded)
    if million:
        return int(float(million.group(1)) * 1_000_000)

    match = _BUDGET_RE.search(folded)
    if not match:
        return 0
    raw = match.group(1).replace(",", "").replace("٬", "")
    try:
        value = float(raw)
    except ValueError:
        return 0
    # "۴۰ میلیون" is caught above; a bare "40000000 تومان" is here.
    return int(value)


def _normalise_use_case(text: str) -> str:
    lowered = text.lower()
    for use_case, cues in _USE_CASE_CUES.items():
        if any(cue in lowered for cue in cues):
            return use_case
    return ""


def _detect_language(text: str) -> str:
    """Persian if it has Persian letters, English otherwise."""
    if re.search(r"[؀-ۿ]", text):
        return "fa"
    return "en"


def understand_with_heuristics(query: str) -> QueryUnderstanding:
    """Understand the question without a model.

    This is the fallback when no LLM is configured, and the safety net when
    the model's JSON is unusable.
    """
    fps_match = _FPS_RE.search(_fold_digits(query))
    understanding = QueryUnderstanding(
        resolution=_normalise_resolution(query),
        fps_target=int(fps_match.group(1)) if fps_match else 0,
        budget_max=_normalise_budget(query),
        use_case=_normalise_use_case(query),
        language=_detect_language(query),
        used_heuristics=True,
    )
    understanding.missing_info = _missing_info(understanding)
    if understanding.missing_info:
        understanding.clarifying_question = _clarifying_question(understanding)
    return understanding


def _missing_info(understanding: QueryUnderstanding) -> list[str]:
    """The critical fields that are missing."""
    missing: list[str] = []
    if not understanding.budget_max:
        missing.append("budget_max")
    if not understanding.use_case:
        missing.append("use_case")
    return missing


def _clarifying_question(understanding: QueryUnderstanding) -> str:
    """One question — never more (the spec allows one)."""
    if "budget_max" in understanding.missing_info and "use_case" in understanding.missing_info:
        return "برای چه کاری و با چه بودجه‌ای سیستم می‌خواهید؟"
    if "budget_max" in understanding.missing_info:
        return "حداکثر بودجهٔ شما چقدر است؟"
    if "use_case" in understanding.missing_info:
        return "این سیستم را برای چه کاری می‌خواهید — گیم، کار اداری یا تولید محتوا؟"
    return ""


def understand(query: str, *, llm=None) -> QueryUnderstanding:
    """Understand a question, with the model when there is one."""
    fallback = understand_with_heuristics(query)

    model = llm or get_llm("understand")
    if getattr(model, "name", "") == "fake":
        return fallback

    prompt = UNDERSTAND_PROMPT.replace("{query}", query)
    try:
        response = model.complete([Message(role="user", content=prompt)], max_tokens=512)
    except Exception:
        return fallback

    parsed = parse_json_response(response.text)
    if not parsed:
        return fallback

    understanding = _from_parsed(parsed, fallback)
    if not understanding.missing_info:
        understanding.clarifying_question = ""
    elif not understanding.clarifying_question:
        understanding.clarifying_question = _clarifying_question(understanding)
    return understanding


def _from_parsed(parsed: dict, fallback: QueryUnderstanding) -> QueryUnderstanding:
    """Build the understanding from the model's JSON, keeping the heuristics
    for anything the model left out."""
    understanding = QueryUnderstanding(
        use_case=str(parsed.get("use_case") or fallback.use_case),
        resolution=str(parsed.get("resolution") or fallback.resolution),
        fps_target=int(parsed.get("fps_target") or fallback.fps_target),
        budget_max=int(parsed.get("budget_max") or fallback.budget_max),
        language=str(parsed.get("language") or fallback.language),
        clarifying_question=str(parsed.get("clarifying_question") or ""),
        raw=parsed,
    )
    if understanding.resolution.lower() not in RESOLUTIONS:
        understanding.resolution = fallback.resolution
    if understanding.use_case and understanding.use_case not in USE_CASES:
        understanding.use_case = fallback.use_case

    missing = parsed.get("missing_info")
    if isinstance(missing, list):
        understanding.missing_info = [str(item) for item in missing]
    else:
        understanding.missing_info = _missing_info(understanding)
    return understanding
