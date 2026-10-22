"""Heading-based chunking.

A wiki page is cut along its heading structure, not at fixed token windows
(docs/PLAN.md D9): a chunk is a section, so a citation can point at a
specific part of a page and the retrieved text keeps its context.

A section that is too long is split further, on paragraph boundaries, with a
small overlap so a sentence that straddles a split is still findable.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

#: Target chunk size in tokens (roughly words for Persian/Latin mixed text).
TARGET_TOKENS = 500
#: The maximum size a chunk may reach before it is split.
MAX_TOKENS = 800
#: How many tokens of the previous chunk are repeated at the start of a split.
OVERLAP_TOKENS = 50

#: A rough token estimate: split on whitespace and punctuation.
_TOKEN_RE = re.compile(r"\S+")


def estimate_tokens(text: str) -> int:
    """A rough token count.

    A real tokenizer would be better, but the count only has to be good
    enough to decide where to split — and it must not depend on a model being
    downloaded.
    """
    return len(_TOKEN_RE.findall(text))


def content_hash(text: str) -> str:
    """A stable hash of a chunk's text, used to skip unchanged chunks."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


@dataclass
class Chunk:
    """One chunk of a page."""

    text: str
    heading: str = ""
    section_path: str = ""
    heading_level: int = 0
    token_count: int = 0
    content_hash: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.token_count:
            self.token_count = estimate_tokens(self.text)
        if not self.content_hash:
            self.content_hash = content_hash(self.text)


@dataclass
class _Section:
    """A heading and the blocks under it."""

    heading: str
    level: int
    path: str
    parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(part for part in self.parts if part.strip())


def _block_text(block_type: str, value: dict) -> str:
    """The plain text of a StreamField block."""
    if block_type == "paragraph":
        return str(value)
    if block_type == "rich_text":
        return str(value)
    if block_type == "list":
        return "\n".join(f"- {item}" for item in value.get("items", []))
    if block_type == "quote":
        text = value.get("text", "")
        source = value.get("source", "")
        return f"{text}\n— {source}" if source else str(text)
    if block_type == "callout":
        title = value.get("title", "")
        text = value.get("text", "")
        return f"{title}\n{text}" if title else str(text)
    if block_type == "spec_table":
        return "\n".join(
            f"{row.get('label', '')}: {row.get('value', '')}" for row in value.get("rows", [])
        )
    if block_type == "image":
        return value.get("caption", "")
    if block_type == "related_entity":
        return value.get("note", "")
    return ""


def split_long_text(
    text: str,
    *,
    target: int = TARGET_TOKENS,
    maximum: int = MAX_TOKENS,
    overlap: int = OVERLAP_TOKENS,
) -> list[str]:
    """Split a long text on paragraph boundaries, with a token overlap.

    The overlap repeats the last few tokens of the previous chunk so a
    sentence that straddles the boundary is still fully present in one of
    them.
    """
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        paragraph_tokens = estimate_tokens(paragraph)
        if current and current_tokens + paragraph_tokens > target:
            chunks.append("\n\n".join(current))
            # Start the next chunk with the tail of the previous one.
            if overlap > 0:
                tail = _tail_tokens("\n\n".join(current), overlap)
                if tail:
                    current = [tail]
                    current_tokens = estimate_tokens(tail)
                else:
                    current = []
                    current_tokens = 0
            else:
                current = []
                current_tokens = 0

        current.append(paragraph)
        current_tokens += paragraph_tokens

    if current:
        chunk = "\n\n".join(current)
        # A single paragraph may still be too long: cut it on sentences.
        if estimate_tokens(chunk) > maximum:
            chunks.extend(_split_long_paragraph(chunk, maximum, overlap))
        else:
            chunks.append(chunk)

    return chunks


def _tail_tokens(text: str, count: int) -> str:
    """The last `count` tokens of a text."""
    tokens = text.split()
    if len(tokens) <= count:
        return text
    return " ".join(tokens[-count:])


def _split_long_paragraph(text: str, maximum: int, overlap: int) -> list[str]:
    """Cut a very long paragraph on sentence boundaries."""
    sentences = re.split(r"(?<=[.!?؟۔])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        tokens = estimate_tokens(sentence)
        if current and current_tokens + tokens > maximum:
            chunks.append(" ".join(current))
            tail = _tail_tokens(" ".join(current), overlap)
            current = [tail] if tail else []
            current_tokens = estimate_tokens(tail) if tail else 0
        current.append(sentence)
        current_tokens += tokens

    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_page(page) -> list[Chunk]:
    """Cut a wiki page into chunks along its heading structure.

    A page with no headings produces a single chunk, so nothing is lost.
    """
    specific = page.specific if hasattr(page, "specific") else page
    body = getattr(specific, "body", None)
    if not body:
        return []

    sections: list[_Section] = []
    heading_stack: list[tuple[int, str]] = []
    preamble: list[str] = []

    for block in body:
        block_type = block.block_type
        value = block.value

        if block_type == "heading":
            level = int(str(value.get("level", "h2")).lstrip("h") or 2)
            heading = value.get("text", "")
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading))
            path = " > ".join(h for _, h in heading_stack)
            sections.append(_Section(heading=heading, level=level, path=path))
            continue

        text = _block_text(block_type, value)
        if not text.strip():
            continue
        if sections:
            sections[-1].parts.append(text)
        else:
            preamble.append(text)

    chunks: list[Chunk] = []

    if preamble:
        chunks.extend(_chunks_for_text("\n\n".join(preamble), heading="", path="", level=0))

    for section in sections:
        chunks.extend(
            _chunks_for_text(
                section.text, heading=section.heading, path=section.path, level=section.level
            )
        )

    return chunks


def _chunks_for_text(text: str, *, heading: str, path: str, level: int) -> list[Chunk]:
    """Turn one section into chunks."""
    if not text.strip():
        return []
    pieces = split_long_text(text)
    if not pieces:
        return []
    if len(pieces) == 1:
        return [Chunk(text=pieces[0], heading=heading, section_path=path, heading_level=level)]
    return [
        Chunk(
            text=piece,
            heading=heading if index == 0 else f"{heading} (ادامه)",
            section_path=path,
            heading_level=level,
        )
        for index, piece in enumerate(pieces)
    ]
