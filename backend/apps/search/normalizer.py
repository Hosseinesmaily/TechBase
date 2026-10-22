"""Persian text normalisation.

The normaliser is used at **both** ends of the search pipeline: when indexing
and when querying. If it is not symmetric, recall collapses — a document
indexed as "می‌شود" would not match a query for "می شود".

Rules (docs/PLAN.md D14):
  * ی (U+06CC) ↔ ي (U+064A) — the Arabic yeh
  * ک (U+06A9) ↔ ك (U+0643) — the Arabic kaf
  * ZWNJ (U+200C) → space, so "می‌شود" and "می شود" are the same
  * Arabic-Indic (٠١٢…) and Extended Arabic-Indic (۰۱۲…) ↔ Latin digits
  * Arabic percent sign and thousands separator → ASCII
  * Diacritics (harakat) and tatweel are dropped
  * Zero-width non-joiner (U+200D) and other invisible marks are dropped
  * Arabic comma/semicolon/question mark → ASCII equivalents
  * Latin and Persian letters are NOT case-folded: Persian has no case, and
    folding Latin to lower case is what makes the search case-insensitive.
"""

from __future__ import annotations

import re
import unicodedata

#: Arabic yeh → Persian yeh
_YEH_ARABIC = "ي"
_YEH_PERSIAN = "ی"
#: Arabic kaf → Persian kaf
_KEHEH_ARABIC = "ك"
_KEHEH_PERSIAN = "ک"

#: Arabic-Indic digits (٠-٩) and Extended Arabic-Indic digits (۰-۹) → Latin.
_DIGIT_MAP = {ord("٠") + i: str(i) for i in range(10)}
_DIGIT_MAP.update({ord("۰") + i: str(i) for i in range(10)})

#: Invisible and formatting characters that carry no meaning for search.
_INVISIBLE = "‌‍⁠﻿"

#: Punctuation that differs between the Arabic and Latin keyboards.
_PUNCT_MAP = {
    ord("،"): ",",  # Arabic comma
    ord("؛"): ";",  # Arabic semicolon
    ord("؟"): "?",  # Arabic question mark
    ord("٪"): "%",  # Arabic percent sign
    ord("٬"): ",",  # Arabic thousands separator
    ord("٫"): ".",  # Arabic decimal separator
    ord("«"): '"',  # «
    ord("»"): '"',  # »
    ord("‘"): "'",
    ord("’"): "'",
    ord("“"): '"',
    ord("”"): '"',
    ord("–"): "-",  # en dash
    ord("—"): "-",  # em dash
    ord("…"): "...",  # ellipsis
}

#: Harakat (short vowels) and tatweel — decorative, dropped.
_DIACRITICS = re.compile(r"[ً-ْٰـ]")

#: Runs of whitespace.
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Normalise a text for indexing or querying.

    The output is lowercase, whitespace-collapsed, and free of the characters
    that differ only in encoding between the Persian and Arabic keyboards.
    """
    if not text:
        return ""

    # 1. Unicode composition, so "ي" written as yā' + hamza folds correctly.
    text = unicodedata.normalize("NFC", text)

    # 2. Character-level folding.
    text = text.translate(_DIGIT_MAP)
    text = text.translate(_PUNCT_MAP)
    for char in _INVISIBLE:
        text = text.replace(char, " " if char == "‌" else "")
    text = text.replace(_YEH_ARABIC, _YEH_PERSIAN)
    text = text.replace(_KEHEH_ARABIC, _KEHEH_PERSIAN)

    # 3. Drop the decorative diacritics.
    text = _DIACRITICS.sub("", text)

    # 4. Lower case (Latin only; Persian letters are unaffected).
    text = text.lower()

    # 5. Collapse the whitespace.
    return _SPACES.sub(" ", text).strip()


def normalize_for_index(text: str) -> str:
    """Normalise a text for indexing.

    Same as `normalize`, but ZWNJ becomes a space rather than being dropped:
    "می‌شود" → "می شود", so a query for "می شود" matches.
    """
    return normalize(text)


def normalize_for_query(text: str) -> str:
    """Normalise a query.

    Identical to `normalize` — the two must stay symmetric or recall breaks.
    The separate name exists so the intent is explicit at the call site.
    """
    return normalize(text)


def tokens(text: str) -> list[str]:
    """The normalised tokens of a text, in order."""
    return normalize(text).split()


def token_set(text: str) -> set[str]:
    """The normalised token set of a text."""
    return set(tokens(text))


def fold_digits(text: str) -> str:
    """Only the digit folding, for display purposes."""
    return text.translate(_DIGIT_MAP)
