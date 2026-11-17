"""Short social messages: a greeting is not a product query.

Every factual answer comes from a tool, so a turn is normally driven by the tool
plan. A greeting, a thank-you or a goodbye carries no question at all — running
the catalog over it would answer "سلام" with a product list, which is exactly the
robotic behaviour this module removes.

A message that mixes a social word with a real request ("سلام، یک سیستم گیمینگ
میخواهم") is *not* social: the topic/aspect cues are checked first, and only a
message that carries no request at all is classified here.
"""

from __future__ import annotations

import hashlib

from apps.search.normalizer import normalize

from .intent import aspects_of, topic_of

GREETING = "greeting"
THANKS = "thanks"
FAREWELL = "farewell"

#: The longest a message may be and still count as small talk.
MAX_TOKENS = 6

_GREETINGS = (
    "سلام",
    "درود",
    "صبح بخیر",
    "روز بخیر",
    "شب بخیر",
    "وقت بخیر",
    "hi",
    "hello",
    "hey",
    "good morning",
)
_THANKS = (
    "ممنون",
    "مرسی",
    "سپاس",
    "تشکر",
    "دستت درد نکنه",
    "لطف کردی",
    "لطفا کمک",
    "thanks",
    "thank you",
    "thx",
)
_FAREWELLS = ("خداحافظ", "خدانگهدار", "خدافظ", "بدرود", "فعلا", "bye", "goodbye", "see you")

_CUE_SETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (GREETING, _GREETINGS),
    (THANKS, _THANKS),
    (FAREWELL, _FAREWELLS),
)

#: A short, human reply per kind. More than one variant per kind keeps the
#: assistant from repeating the same sentence turn after turn.
_REPLIES: dict[str, tuple[str, ...]] = {
    GREETING: (
        "سلام! من دستیار تکبیس هستم؛ دربارهٔ قطعات، قیمت، موجودی یا سازگاری هر سؤالی داری بپرس.",
        "سلام و وقت بخیر. هر چیزی دربارهٔ سختافزار یا انتخاب سیستم لازم داری، همینجا بپرس.",
        "درود! برای انتخاب قطعه یا راهنمایی خرید در خدمتم؛ بگو دنبال چه چیزی هستی.",
    ),
    THANKS: (
        "خواهش میکنم! اگر پرسش دیگری داری، در خدمتم.",
        "کاری نکردم؛ هر وقت لازم داشتی همینجا بپرس.",
        "خوشحالم که به کار آمد. سؤال دیگری داری؟",
    ),
    FAREWELL: (
        "خداحافظ! هر وقت سؤالی داشتی همینجا هستم.",
        "موفق باشی؛ هر وقت لازم شد برگرد.",
        "خدانگهدار! انتخاب خوبی داشته باشی.",
    ),
}

#: The acknowledgement a social message never needs a question for.
_PUNCTUATION = "!؟?.،,؛:…«»"


def classify_social(text: str) -> str:
    """The social kind of a short message, or ``""`` when it is a real request."""
    normalized = normalize(text)
    tokens = [token for token in normalized.strip(_PUNCTUATION).split() if token]
    if not tokens or len(tokens) > MAX_TOKENS:
        return ""

    # A request hides in the same sentence? Then it is a request.
    if topic_of(normalized) or aspects_of(normalized):
        return ""

    for kind, cues in _CUE_SETS:
        if any(cue in normalized for cue in cues):
            return kind
    return ""


def social_reply(kind: str, text: str) -> str:
    """A short reply for a social message.

    The variant is picked from the message itself, so the same greeting always
    gets the same answer (testable) while different messages do not all read
    alike.
    """
    options = _REPLIES.get(kind) or _REPLIES[GREETING]
    digest = hashlib.sha256(normalize(text).encode("utf-8")).digest()
    return options[digest[0] % len(options)]
