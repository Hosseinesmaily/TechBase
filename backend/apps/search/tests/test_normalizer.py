"""Tests for the Persian normaliser.

The normaliser must be **symmetric**: whatever it does at index time, it does
at query time. Every test here is really a statement about that symmetry.
"""

from __future__ import annotations

import pytest

from apps.search.normalizer import normalize, normalize_for_index, normalize_for_query, tokens


class TestCharacterFolding:
    def test_arabic_yeh_folds_to_persian_yeh(self):
        assert normalize("ي") == "ی"

    def test_arabic_kaf_folds_to_persian_kaf(self):
        assert normalize("ك") == "ک"

    def test_persian_letters_are_unchanged(self):
        assert normalize("یک کتاب") == "یک کتاب"

    def test_latin_is_lowercased(self):
        assert normalize("RTX 4060") == "rtx 4060"

    def test_persian_is_not_cased(self):
        assert normalize("کتاب") == "کتاب"

    def test_zwnj_becomes_a_space(self):
        assert normalize("می‌شود") == "می شود"

    def test_half_space_and_plain_space_are_equivalent(self):
        assert normalize("می‌شود") == normalize("می شود")

    def test_diacritics_are_dropped(self):
        assert normalize("مُحَمَّد") == "محمد"

    def test_tatweel_is_dropped(self):
        assert normalize("کــتاب") == "کتاب"

    def test_arabic_punctuation_is_folded(self):
        assert normalize("سلام، خوب؟") == "سلام, خوب?"

    def test_guillemets_become_quotes(self):
        assert normalize("«تک‌بیس»") == '"تک بیس"'

    def test_arabic_digits_fold_to_latin(self):
        assert normalize("۱۴۰۵") == "1405"

    def test_extended_arabic_digits_fold_to_latin(self):
        assert normalize("١٤٠٥") == "1405"

    def test_mixed_digits_fold(self):
        assert normalize("۱۴0۵") == "1405"

    def test_whitespace_is_collapsed(self):
        assert normalize("  a   b  ") == "a b"

    def test_empty_string(self):
        assert normalize("") == ""


class TestSymmetry:
    @pytest.mark.parametrize(
        "text",
        [
            "می‌شود",
            "می شود",
            "می‌ شود",
            "کیک",
            "RTX 4070 SUPER",
            "نامبرد: رایزن ۷ ۸۰۰۰X3D",
            "قیمت: ۲۴,۵۰۰,۰۰۰ تومان",
        ],
    )
    def test_index_and_query_normalize_identically(self, text):
        assert normalize_for_index(text) == normalize_for_query(text)

    def test_zwnj_variants_match_each_other(self):
        assert normalize_for_index("می‌شود") == normalize_for_query("می شود")

    def test_digit_variants_match_each_other(self):
        assert normalize_for_index("۱۴۰۵") == normalize_for_query("1405")


class TestTokens:
    def test_splits_on_whitespace(self):
        assert tokens("کارت گرافیک RTX") == ["کارت", "گرافیک", "rtx"]

    def test_zwnj_produces_two_tokens(self):
        assert tokens("می‌شود") == ["می", "شود"]

    def test_empty_text_has_no_tokens(self):
        assert tokens("") == []
