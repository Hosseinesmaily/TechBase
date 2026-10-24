"""Small, deterministic intent parser for Persian and English catalog search."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .normalizer import normalize


@dataclass(frozen=True)
class SearchIntent:
    entity_type: str = ""
    use_case: str = ""
    resolution: str = ""
    query: str = ""


_TYPE_CUES = {
    "gpu": ("کارت گرافیک", "گرافیک", "graphics card", "video card", "gpu"),
    "cpu": ("پردازنده", "processor", "cpu"),
    # DDR generation is a precise search term and should remain searchable in
    # wiki titles (e.g. “DDR5 چیست؟”), so do not consume it as a category cue.
    "ram": ("حافظه رم", "رم", "memory", "ram"),
    "motherboard": ("مادربرد", "motherboard", "mainboard"),
    "psu": ("منبع تغذیه", "پاور", "power supply", "psu"),
    "case": ("کیس کامپیوتر", "کیس", "computer case", "case"),
    "cooler": ("خنک کننده", "خنک‌کننده", "cpu cooler", "cooler"),
    "storage": ("حافظه ذخیره سازی", "حافظه ذخیره‌سازی", "ssd", "nvme", "hard drive"),
    "prebuilt": ("سیستم آماده", "کامپیوتر گیمینگ", "سیستم گیمینگ", "gaming pc", "prebuilt"),
}

_USE_CASE_CUES = {
    "gaming": ("گیمینگ", "گیم", "بازی", "gaming", "game", "games"),
    "office": ("اداری", "office", "excel", "word"),
    "content_creation": ("تولید محتوا", "رندر", "تدوین", "ادیت", "render", "editing"),
    "programming": ("برنامه نویسی", "برنامه‌نویسی", "کدنویسی", "programming", "coding"),
}

_RESOLUTION_RE = re.compile(r"\b(720p|1080p|1440p|2160p|4k)\b", re.IGNORECASE)
_BUDGET_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:میلیون|تومان|تومن|ریال|million|toman)\b")
_GENERIC_CUES = {
    "مخصوص",
    "مناسب",
    "برای",
    "بهترین",
    "پیشنهاد",
    "چی",
    "چیه",
    "کدام",
    "کدوم",
    "بخرم",
    "میخوام",
    "میخواهم",
    "لطفا",
    "لطفاً",
    "گیمینگ",
    "گیم",
    "بازی",
    "gaming",
    "game",
    "games",
    "اداری",
    "رندر",
    "تولید",
    "محتوا",
    "تدوین",
    "ادیت",
    "office",
    "render",
    "editing",
    "programming",
    "for",
    "the",
    "a",
    "an",
    "best",
    "suitable",
    "specifically",
    "with",
    "in",
    "at",
}


def understand_search(query: str) -> SearchIntent:
    """Extract the product class and use case, leaving model-specific terms."""
    normalized = normalize(query)
    entity_type = next(
        (
            kind
            for kind, cues in _TYPE_CUES.items()
            if any(normalize(cue) in normalized for cue in cues)
        ),
        "",
    )
    use_case = next(
        (
            case
            for case, cues in _USE_CASE_CUES.items()
            if any(normalize(cue) in normalized for cue in cues)
        ),
        "",
    )
    resolution_match = _RESOLUTION_RE.search(normalized)
    resolution = resolution_match.group(1).lower() if resolution_match else ""
    if resolution == "2160p":
        resolution = "4k"

    cleaned = normalized
    phrases = [phrase for cues in _TYPE_CUES.values() for phrase in cues]
    phrases += [phrase for cues in _USE_CASE_CUES.values() for phrase in cues]
    for phrase in sorted(phrases, key=len, reverse=True):
        cleaned = re.sub(r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)", " ", cleaned)
    cleaned = _RESOLUTION_RE.sub(" ", cleaned)
    cleaned = _BUDGET_RE.sub(" ", cleaned)
    tokens = [token for token in cleaned.split() if token not in _GENERIC_CUES]
    return SearchIntent(
        entity_type=entity_type,
        use_case=use_case,
        resolution=resolution,
        query=" ".join(tokens),
    )
