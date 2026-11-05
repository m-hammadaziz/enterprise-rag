"""Thin wrapper over any OpenAI-compatible chat endpoint (Groq by default).

Every call returns token usage so the agent can track latency and cost.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
import time

from app.config import settings


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.calls += other.calls

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens * settings.llm_input_price_per_mtok
            + self.output_tokens * settings.llm_output_price_per_mtok
        ) / 1_000_000


@dataclass
class ChatResult:
    content: str
    tool_calls: list[dict] = field(default_factory=list)  # [{"name":..., "arguments": {...}}]
    usage: Usage = field(default_factory=Usage)


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    return OpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        timeout=settings.llm_timeout_s,
        max_retries=3,
    )


def chat(
    messages: list[dict],
    temperature: float = 0.0,
    tools: list[dict] | None = None,
    json_mode: bool = False,
    max_tokens: int = 800,
) -> ChatResult:
    if not settings.llm_enabled:
        raise RuntimeError("LLM disabled: set GROQ_API_KEY (or run in offline mode)")
    kwargs: dict = dict(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            resp = _client().chat.completions.create(**kwargs)
            break
        except Exception as e:  # tool-call parse failures on some providers -> retry w/o tools
            last_err = e
            if tools and attempt == 0 and "tool" in str(e).lower():
                kwargs.pop("tools", None)
                kwargs.pop("tool_choice", None)
                continue
            raise
    else:  # pragma: no cover
        raise last_err  # type: ignore[misc]

    msg = resp.choices[0].message
    calls = []
    for tc in msg.tool_calls or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append({"name": tc.function.name, "arguments": args})
    u = resp.usage
    usage = Usage(
        input_tokens=getattr(u, "prompt_tokens", 0) or 0,
        output_tokens=getattr(u, "completion_tokens", 0) or 0,
        calls=1,
    )
    return ChatResult(content=msg.content or "", tool_calls=calls, usage=usage)


def chat_json(messages: list[dict], max_tokens: int = 300) -> tuple[dict, Usage]:
    """Chat call that must return a JSON object. Falls back to brace extraction."""
    try:
        res = chat(messages, json_mode=True, max_tokens=max_tokens)
    except Exception:
        res = chat(messages, max_tokens=max_tokens)
    text = res.content.strip()
    try:
        return json.loads(text), res.usage
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(text[s : e + 1]), res.usage
            except json.JSONDecodeError:
                pass
    return {}, res.usage


class Timer:
    def __init__(self):
        self.t0 = time.perf_counter()

    @property
    def ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000
