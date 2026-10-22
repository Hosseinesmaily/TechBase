"""The LLM interface: provider-agnostic, with a fake for local development.

Three adapters ship:
  * `AnthropicLLM` — the Anthropic API.
  * `OpenAILLM` — any OpenAI-compatible endpoint (vLLM, Ollama, OpenAI).
  * `FakeLLM` — a deterministic local adapter, so the whole stack runs with
    no API key at all. It never invents facts: it answers from the given
    context only, and says so when the context is empty.

The model is chosen by settings (`LLM_PROVIDER`), and the *model* is routed
by task (docs/PLAN.md D10): a cheap model for query understanding, a stronger
one for the final answer.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """One message in a conversation."""

    role: str  # system | user | assistant
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """The result of a completion."""

    text: str
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class LLM(Protocol):
    """The contract every LLM adapter satisfies."""

    name: str

    def complete(self, messages: list[Message], *, max_tokens: int = 1024) -> LLMResponse:
        """Return a complete answer."""
        ...

    def stream(self, messages: list[Message], *, max_tokens: int = 1024) -> Iterator[str]:
        """Yield the answer in pieces, for SSE."""
        ...


class FakeLLM:
    """A deterministic local adapter, so the stack runs without any API key.

    It is deliberately honest: it quotes the context it was given and says so
    when there is none. It is **not** a language model — it exists so the
    plumbing, the guardrails and the evaluation harness can be exercised
    without a network call.
    """

    name = "fake"

    def __init__(self, model: str = "fake") -> None:
        self.model = model

    def complete(self, messages: list[Message], *, max_tokens: int = 1024) -> LLMResponse:
        text = self._respond(messages)
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            input_tokens=sum(len(m.content) for m in messages) // 4,
            output_tokens=len(text) // 4,
        )

    def stream(self, messages: list[Message], *, max_tokens: int = 1024) -> Iterator[str]:
        text = self._respond(messages)
        # Emit in small pieces, so the SSE path is exercised the same way.
        for index in range(0, len(text), 24):
            yield text[index : index + 24]

    def _respond(self, messages: list[Message]) -> str:
        context = ""
        for message in messages:
            if message.role == "system" and "CONTEXT" in message.content:
                context = message.content
                break
        if not context:
            context = messages[-1].content if messages else ""

        if "CONTEXT" in context:
            body = context.split("CONTEXT", 1)[1]
            # Quote the context lines, each with its citation marker, so the
            # guardrail sees a properly cited answer. The fake adapter never
            # invents a fact of its own — it only repeats what it was given.
            quoted: list[str] = []
            for line in body.splitlines():
                line = line.strip()
                if not line or line.startswith("<<<") or line.startswith("==="):
                    continue
                if line.startswith("["):
                    index = line.split("]", 1)[0] + "]"
                    text = line.split("]", 1)[1].strip()
                    if text and len(text) > 20:
                        quoted.append(f"{text} {index}")
            if quoted:
                return "بر اساس مستندات موجود:\n\n" + "\n".join(quoted)
        return "(پاسخ آزمایشی بدون LLM) مدل زبانی در دسترس نیست — از دادهٔ ابزار استفاده کنید."


class AnthropicLLM:
    """The Anthropic API."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _split_system(self, messages: list[Message]) -> tuple[str, list[Message]]:
        """Anthropic takes the system prompt separately from the turns."""
        system_parts = [m.content for m in messages if m.role == "system"]
        turns = [m for m in messages if m.role != "system"]
        return "\n\n".join(system_parts), turns

    def complete(self, messages: list[Message], *, max_tokens: int = 1024) -> LLMResponse:
        system, turns = self._split_system(messages)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or None,
            messages=[m.as_dict() for m in turns],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
            raw={"id": response.id, "stop_reason": response.stop_reason},
        )

    def stream(self, messages: list[Message], *, max_tokens: int = 1024) -> Iterator[str]:
        system, turns = self._split_system(messages)
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system or None,
            messages=[m.as_dict() for m in turns],
        ) as stream:
            yield from stream.text_stream


class OpenAILLM:
    """Any OpenAI-compatible endpoint (OpenAI, vLLM, Ollama, …)."""

    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str = "") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self.api_key or "not-needed"}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def complete(self, messages: list[Message], *, max_tokens: int = 1024) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[m.as_dict() for m in messages],
        )
        text = response.choices[0].message.content or ""
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            input_tokens=getattr(response.usage, "prompt_tokens", 0),
            output_tokens=getattr(response.usage, "completion_tokens", 0),
        )

    def stream(self, messages: list[Message], *, max_tokens: int = 1024) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[m.as_dict() for m in messages],
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


def get_llm(task: str = "chat") -> LLM:
    """The LLM for a task.

    `task` is "chat" (the final answer) or "understand" (query parsing); the
    two are routed to different models, so the cheap one does the cheap work.
    """
    provider = (settings.LLM_PROVIDER or "").lower()

    if not provider:
        provider = _detect_provider()

    model = settings.LLM_UNDERSTAND_MODEL if task == "understand" else settings.LLM_CHAT_MODEL

    if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        return AnthropicLLM(settings.ANTHROPIC_API_KEY, model)
    if provider == "openai" and (settings.OPENAI_API_KEY or settings.OPENAI_BASE_URL):
        return OpenAILLM(settings.OPENAI_API_KEY, model, settings.OPENAI_BASE_URL)
    if provider in {"anthropic", "openai"}:
        logger.warning(
            "LLM provider %r is configured but has no API key — using the fake "
            "adapter. Set %s_API_KEY.",
            provider,
            provider.upper(),
        )

    return FakeLLM(model)


def _detect_provider() -> str:
    """Guess the provider from the configured keys."""
    if settings.ANTHROPIC_API_KEY:
        return "anthropic"
    if settings.OPENAI_API_KEY or settings.OPENAI_BASE_URL:
        return "openai"
    return "fake"


def parse_json_response(text: str) -> dict | None:
    """Parse a JSON object out of a model response.

    Models often wrap JSON in a code fence or add a sentence around it, so
    this looks for the outermost braces rather than parsing the whole string.
    """
    if not text:
        return None

    cleaned = text.strip()
    # Strip a markdown code fence.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None
