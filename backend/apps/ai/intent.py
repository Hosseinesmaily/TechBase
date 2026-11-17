"""What the user is asking *for*.

`apps.search.intent` classifies a catalog search; this module classifies the
request itself, because the two answer different questions. The one that matters
here is narrow: **should the assistant ask a clarifying question, and if so,
which one?**

The decision is deterministic (no model), for two reasons: the stack has to work
with no API key at all, and a policy that decides when to interrupt the user must
be testable.

The kinds:

  * `build`         — "یک سیستم گیمینگ مناسب می‌خواهم": the essentials decide.
  * `component`     — "حافظه DDR4"، "قیمت RTX 4070 SUPER چقدر است؟": the user named
                      a thing, so answer *that thing*.
  * `compatibility` — "آیا این رم با این مادربرد سازگار است؟": the rule engine answers.
  * `compare`       — "تفاوت Ryzen 5 7600 و 7800X3D چیست؟": both sides are named.
  * `unclear`       — "سلام": ask what they mean, never a canned build question.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.search.normalizer import normalize

#: The kinds of request the assistant distinguishes.
BUILD = "build"
COMPONENT = "component"
COMPATIBILITY = "compatibility"
COMPARE = "compare"
UNCLEAR = "unclear"

#: The aspects of a request that make it answerable without more information.
PRICE = "price"
STOCK = "stock"
SPEC = "spec"
BENCHMARK = "benchmark"
CONCEPT = "concept"

# --- Cues (normalised once: ZWNJ → space, Latin lower-cased) ------------------

_TOPIC_CUES: dict[str, tuple[str, ...]] = {
    # The more specific cue sets come first: "حافظه ذخیره‌سازی" is storage, not RAM.
    "storage": ("حافظه ذخیره", "اس اس د", "اس‌اس‌دی", "ssd", "nvme", "هارد", "990 pro", "sn580"),
    "prebuilt": ("سیستم آماده", "سیستم گیمینگ", "کامپیوتر گیمینگ", "سیستم اداری", "prebuilt"),
    "gpu": ("کارت گرافیک", "گرافیک", "rtx", "gtx", "radeon", "geforce", "gpu"),
    "cpu": ("پردازنده", "سی پی یو", "cpu", "ryzen", "رایزن", "core i", "اینتل"),
    "motherboard": ("مادربرد", "b650", "b760", "x670", "z790", "mainboard", "motherboard"),
    "psu": ("منبع تغذیه", "پاور", "psu", "وات", "watt"),
    "cooler": ("خنک کننده", "کولر", "cooler", "هایپر", "hyper"),
    "case": ("کیس", "case"),
    "ram": ("ddr3", "ddr4", "ddr5", "رم", "حافظه", "memory"),
}

_ASPECT_CUES: dict[str, tuple[str, ...]] = {
    PRICE: ("قیمت", "چند", "چقدر", "هزینه", "تومان", "price", "cost", "how much"),
    STOCK: ("موجود", "موجودی", "انبار", "stock", "available", "in stock"),
    BENCHMARK: ("فریم", "fps", "بنچمارک", "benchmark"),
    SPEC: ("سوکت", "مشخصات", "چند هسته", "tdp", "ظرفیت", "سرعت", "spec", "socket"),
    CONCEPT: ("چیست", "چیه", "یعنی چه", "what is", "explain"),
}

_COMPATIBILITY_CUES = ("سازگار", "سازگاری", "با هم کار", "می خوره", "compatible", "compatibility")
_COMPARE_CUES = ("تفاوت", "مقایسه", "compare", "difference", "کدوم بهتر", "کدام بهتر")
_BUILD_CUES = ("سیستم", "کامپیوتر", "اسمبل", "build", "pc", "rig", "تجهیز")
_RECOMMEND_CUES = (
    "می خوام",
    "می خواهم",
    "میخواستم",
    "پیشنهاد",
    "بده",
    "لازم دارم",
    "مناسب",
    "بخرم",
    "انتخاب کن",
    "راهنمایی",
    "want",
    "need",
    "recommend",
    "suggest",
    # The ZWNJ-free spellings are what people usually type — "میخوام" is written
    # without the half-space far more often than with it. The normaliser folds a
    # ZWNJ into a space, so the spaced spellings above cover that form and these
    # cover the other one.
    "میخوام",
    "میخواهم",
    "میخواستم",
    "بخوام",
    "دارم",
)

#: Words that carry no signal when a keyword is extracted for a text search.
_STOPWORDS = frozenset(
    normalize(word)
    for word in (
        "قیمت",
        "چند",
        "چقدر",
        "است",
        "هست",
        "برای",
        "با",
        "و",
        "یا",
        "در",
        "از",
        "به",
        "این",
        "آن",
        "چه",
        "چیست",
        "چیه",
        "کدام",
        "کدوم",
        "من",
        "میخواهم",
        "میخوام",
        "پیشنهاد",
        "بده",
        "لطفا",
        "لطفاً",
        "دارم",
        "می",
        "شود",
        "کن",
        "کنم",
        "بدهید",
        "the",
        "a",
        "an",
        "is",
        "are",
        "of",
        "for",
        "what",
        "which",
        "how",
        "much",
        "does",
        "do",
        "and",
        "or",
        "to",
        "with",
        "in",
        "on",
        "compatible",
        "compatibility",
        "price",
        "cost",
        "stock",
        "difference",
        "compare",
        "want",
        "need",
        "recommend",
        "system",
        "pc",
        "build",
        "good",
        "best",
        "about",
    )
)

#: Known technology words worth searching for even without a digit in them.
_TECH_WORDS = frozenset(
    normalize(word)
    for word in (
        "rtx",
        "gtx",
        "rx",
        "ddr3",
        "ddr4",
        "ddr5",
        "ssd",
        "hdd",
        "nvme",
        "am4",
        "am5",
        "lga1700",
        "lga1200",
        "atx",
        "matx",
        "itx",
        "wifi",
        "expo",
        "xmp",
        "dlss",
    )
)


def _cues(table: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Normalise every cue once, so matching is symmetric with the query."""
    return {key: tuple(normalize(cue) for cue in values) for key, values in table.items()}


_TOPICS = _cues(_TOPIC_CUES)
_ASPECTS = _cues(_ASPECT_CUES)
_COMPATIBILITY = tuple(normalize(cue) for cue in _COMPATIBILITY_CUES)
_COMPARE = tuple(normalize(cue) for cue in _COMPARE_CUES)
_BUILD = tuple(normalize(cue) for cue in _BUILD_CUES)
_RECOMMEND = tuple(normalize(cue) for cue in _RECOMMEND_CUES)


@dataclass(frozen=True)
class RequestIntent:
    """What the assistant understood the *request to be*."""

    kind: str = UNCLEAR
    topic: str = ""
    aspects: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    has_budget: bool = False
    has_use_case: bool = False
    has_resolution: bool = False

    @property
    def is_recommendation(self) -> bool:
        """A request for a recommendation with nothing to recommend *from*.

        A use case or a resolution already pins the answer down, so those are not
        "under-specified": only a request that names neither a model nor a use case
        (and has no resolution) is worth a question.
        """
        return (
            self.kind == COMPONENT
            and not self.keywords
            and not self.entities
            and not self.has_use_case
            and not self.has_resolution
        )

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "topic": self.topic,
            "aspects": list(self.aspects),
            "keywords": list(self.keywords),
        }

    def mentions(self, *aspects: str) -> bool:
        return any(aspect in self.aspects for aspect in aspects)


#: Numbers that describe a screen or a budget, not a product identity.
_RESOLUTION_TOKENS = frozenset(
    {"720", "1080", "1440", "2160", "720p", "1080p", "1440p", "2160p", "4k"}
)


def _is_model_token(token: str) -> bool:
    """Whether a token identifies a *thing* (a model or a technology).

    A resolution ("1080p", "1440") and a bare short number (a budget such as "50"
    in "۵۰ میلیون") are not identities: searching the catalog for them finds
    nothing and hides every real product.
    """
    if token in _TECH_WORDS:
        return True
    if token in _RESOLUTION_TOKENS:
        return False
    digits = sum(1 for char in token if char.isdigit())
    if digits == 0:
        return False
    # "50" is a budget, not an identity; a four-character model number ("4070") is.
    return not (digits == len(token) and len(token) < 4)


def _first_match(text: str, table: dict[str, tuple[str, ...]], order: tuple[str, ...]) -> str:
    for key in order:
        if any(cue in text for cue in table.get(key, ())):
            return key
    return ""


def topic_of(text: str) -> str:
    """The component class the request is about ("" when it is about none)."""
    return _first_match(text, _TOPICS, tuple(_TOPICS))


def aspects_of(text: str) -> tuple[str, ...]:
    """Which parts of the request make it answerable on its own."""
    order = (PRICE, STOCK, BENCHMARK, SPEC, CONCEPT)
    return tuple(key for key in order if any(cue in text for cue in _ASPECTS.get(key, ())))


def keywords_of(text: str, limit: int = 4) -> tuple[str, ...]:
    """The model-ish terms worth searching for: "ddr4", "rtx 4070", "7800x3d"."""
    found: list[str] = []
    for token in text.split():
        cleaned = token.strip("?!.,؛:،«»\"'()[]{}")
        if not cleaned or cleaned in _STOPWORDS or not _is_model_token(cleaned):
            continue
        if cleaned not in found:
            found.append(cleaned)
        if len(found) >= limit:
            break
    return tuple(found)


def kind_of(text: str, topic: str, aspects: tuple[str, ...], entities: tuple[str, ...]) -> str:
    """The kind of request, from the words alone."""
    is_build = any(cue in text for cue in _BUILD) and (
        any(cue in text for cue in _RECOMMEND) or topic == "prebuilt"
    )

    # "یک سیستم با قطعات سازگار می‌خواهم" is a build, not a two-part check.
    if is_build and len(entities) < 2:
        return BUILD
    if any(cue in text for cue in _COMPATIBILITY):
        return COMPATIBILITY
    if any(cue in text for cue in _COMPARE) and len(entities) >= 2:
        return COMPARE
    if is_build:
        return BUILD
    if topic or aspects or entities:
        return COMPONENT
    return UNCLEAR


def analyse_request(query: str, *, understanding=None, entities=()) -> RequestIntent:
    """Classify the request.

    `understanding` (a `QueryUnderstanding`) supplies what the user has already
    stated — the budget, the use case, the resolution — so the clarification
    policy never asks for something that is on the table. `entities` are the
    catalog slugs already resolved from the text (kept as a parameter so this
    module stays free of database access and is trivial to test).
    """
    text = normalize(query)
    topic = topic_of(text)
    aspects = aspects_of(text)
    slugs = tuple(slug for slug in entities if slug)

    return RequestIntent(
        kind=kind_of(text, topic, aspects, slugs),
        topic=topic,
        aspects=aspects,
        keywords=keywords_of(text),
        entities=slugs,
        has_budget=bool(getattr(understanding, "budget_max", 0)),
        has_use_case=bool(getattr(understanding, "use_case", "")),
        has_resolution=bool(getattr(understanding, "resolution", "")),
    )


def decide_clarification(intent: RequestIntent, *, ask: bool = True) -> str:
    """The one question worth asking, or "" for none.

    A question about a named part, a price or a stock count is answerable, so it is
    never interrupted. Only a broad build, an under-specified recommendation, an
    incomplete compatibility check and an unintelligible message get a question —
    and each gets a *specific* one, so nothing the user already said is asked again.
    """
    if not ask:
        return ""

    if intent.kind == COMPATIBILITY:
        if len(intent.entities) < 2:
            return "برای بررسی قطعی سازگاری، نام دقیق دو قطعه را بنویس؛ مثلاً پردازنده و مادربرد."
        return ""

    if intent.kind == BUILD:
        # A resolution already pins the recommendation down, so the budget stops
        # being critical. Only what is genuinely missing is asked.
        if intent.has_resolution:
            return ""
        if not intent.has_use_case and not intent.has_budget:
            return "این سیستم را برای چه کاری و با چه بودجه‌ای می‌خواهی؟"
        if not intent.has_budget:
            return "حداکثر بودجه‌ات چقدر است؟"
        if not intent.has_use_case:
            return "این سیستم را برای چه کاری می‌خواهی — بازی، کار اداری یا تولید محتوا؟"
        return ""

    if intent.kind == COMPONENT:
        if intent.mentions(PRICE, STOCK):
            return ""
        if intent.is_recommendation:
            if intent.topic == "ram":
                return (
                    "برای پیشنهاد رم، مدل مادربرد (یا نسل حافظه: DDR4/DDR5) و ظرفیت موردنظر را بگو."
                )
            return "برای پیشنهاد دقیق‌تر، مدل یا محدودهٔ بودجه‌ات را بگو."
        return ""

    if intent.kind == UNCLEAR:
        return (
            "منظورت را روشن‌تر بگو؛ مثلاً نام قطعه (کارت گرافیک، رم) یا کاربرد سیستم "
            "(گیمینگ، اداری) را بنویس."
        )

    return ""
