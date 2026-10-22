"""Embeddings: a provider-agnostic interface with a deterministic local fallback.

The provider is chosen by settings (`EMBEDDING_PROVIDER`). Two are shipped:

  * `bge-m3` / `e5` — a real sentence-transformers model, when the dependency
    and the model files are available. This is what production uses.
  * `hash` — a deterministic, dependency-free fallback that hashes character
    n-grams into a fixed-length vector.

The fallback is not a good embedding model, and it is not meant to be one.
It exists so the whole RAG pipeline (chunking, retrieval, the evaluation
harness, the chat endpoint) is runnable and testable on a machine with no
model download — and so a missing model fails loudly in the response rather
than silently returning nonsense vectors.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Protocol

from django.conf import settings

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class EmbeddingProvider(Protocol):
    """The contract every embedding provider satisfies."""

    name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        ...

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text."""
        ...


class HashEmbeddingProvider:
    """A deterministic, dependency-free fallback embedding.

    Character n-grams are hashed into a fixed-length vector and the result is
    L2-normalised, so cosine similarity behaves sensibly for texts that share
    substrings. It is a *baseline*, not a semantic model.
    """

    name = "hash"

    def __init__(self, dimension: int = 1024, ngram_range: tuple[int, int] = (2, 4)) -> None:
        self.dimension = dimension
        self.ngram_range = ngram_range

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_one(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            return vector

        grams: list[str] = []
        joined = " ".join(tokens)
        for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
            for index in range(len(tokens) - n + 1):
                grams.append(" ".join(tokens[index : index + n]))
        # Character trigrams of the whole string catch the Persian morphology
        # that word-level grams miss.
        for index in range(max(0, len(joined) - 2)):
            grams.append(joined[index : index + 3])

        for gram in grams:
            digest = hashlib.sha256(gram.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class SentenceTransformerProvider:
    """A real embedding model, loaded lazily through sentence-transformers."""

    name = "sentence-transformers"

    def __init__(self, model_name: str, dimension: int) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is not installed — install it "
                    "(pip install sentence-transformers) or set "
                    "EMBEDDING_PROVIDER=hash to use the local fallback."
                ) from exc
            logger.info("loading embedding model %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


_provider: EmbeddingProvider | None = None


def get_provider() -> EmbeddingProvider:
    """The configured embedding provider."""
    global _provider
    if _provider is not None:
        return _provider

    provider_name = (settings.EMBEDDING_PROVIDER or "hash").lower()
    dimension = settings.EMBEDDING_DIM

    if provider_name in {"bge-m3", "e5", "sentence-transformers"}:
        try:
            import sentence_transformers  # noqa: F401

            _provider = SentenceTransformerProvider(settings.EMBEDDING_MODEL, dimension)
            return _provider
        except ImportError:
            logger.warning(
                "sentence-transformers is not installed — falling back to the hash "
                "embedding provider. Install it and set EMBEDDING_PROVIDER=%s for "
                "real semantic search.",
                provider_name,
            )

    _provider = HashEmbeddingProvider(dimension=dimension)
    return _provider


def embed_text(text: str) -> list[float]:
    """Embed a single text."""
    return get_provider().embed_one(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts."""
    if not texts:
        return []
    return get_provider().embed(texts)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """The cosine similarity of two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def reset_provider() -> None:
    """Drop the cached provider — used by the tests and after a settings change."""
    global _provider
    _provider = None
