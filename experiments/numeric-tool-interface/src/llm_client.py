"""Minimal model client for Paper 2 tool-call experiments.

This carries over the relevant local Ollama/OpenAI-compatible behavior from the
previous atlas_optimizer harness: reasoning-mode suppression for thinking models,
structured tool-call parsing, JSON-in-text fallback parsing, and percentage-scale
normalization.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]
    source: str = "structured"
    raw_input: dict[str, Any] | None = None
    normalization_applied: bool = False


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class LLMClient:
    """Small provider wrapper for local OpenAI-compatible tool calls."""

    _RATE_LIMITS = {
        "openai": 0.1,
    }

    _THINKING_MODELS = {"qwen3", "deepseek", "gemma4"}

    def __init__(
        self,
        provider: str,
        model_id: str,
        temperature: float = 0.0,
        api_base: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        if provider != "openai":
            raise ValueError("Milestone 2 supports only OpenAI-compatible providers")
        self.provider = provider
        self.model_id = model_id
        self.temperature = temperature
        self.api_base = api_base
        self.timeout = timeout
        self._last_call_time = 0.0
        self._client = self._init_openai()

    def _init_openai(self):
        from openai import OpenAI

        kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self.api_base:
            kwargs["base_url"] = self.api_base
            kwargs["api_key"] = "ollama"
        return OpenAI(**kwargs)

    def _rate_limit(self) -> None:
        min_interval = self._RATE_LIMITS[self.provider]
        elapsed = time.time() - self._last_call_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call_time = time.time()

    def call(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], system: str | None = None) -> LLMResponse:
        self._rate_limit()
        return self._call_openai(messages=messages, tools=tools, system=system)

    def _call_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str | None,
    ) -> LLMResponse:
        oai_messages = self._translate_messages_to_openai(messages, system)
        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": oai_messages,
            "tools": tools if tools else None,
            "temperature": self.temperature,
            "max_tokens": 512,
        }
        if any(prefix in self.model_id.lower() for prefix in self._THINKING_MODELS):
            kwargs["reasoning_effort"] = "none"

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        content = choice.message.content
        if content:
            content = self._strip_thinking_tags(content)
            if not content.strip():
                content = None

        tool_calls: list[ToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                raw_arguments = tc.function.arguments
                parsed_arguments: dict[str, Any]
                if isinstance(raw_arguments, str):
                    parsed_arguments = json.loads(raw_arguments)
                elif isinstance(raw_arguments, dict):
                    parsed_arguments = raw_arguments
                else:
                    parsed_arguments = {}
                tool_calls.append(
                    self._make_tool_call(
                        call_id=tc.id or f"call_{uuid.uuid4().hex[:8]}",
                        name=tc.function.name,
                        arguments=parsed_arguments,
                        source="structured",
                    )
                )

        if not tool_calls and content:
            tool_calls = self._try_parse_tool_calls_from_text(content)
            if tool_calls:
                content = None

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            raw={"id": response.id, "model": response.model},
        )

    def _make_tool_call(
        self,
        call_id: str,
        name: str,
        arguments: dict[str, Any],
        source: str,
    ) -> ToolCall:
        normalized, applied = normalize_numeric_arguments(arguments)
        return ToolCall(
            id=call_id,
            name=name,
            input=normalized,
            source=source,
            raw_input=arguments,
            normalization_applied=applied,
        )

    @staticmethod
    def _translate_messages_to_openai(messages: list[dict[str, Any]], system: str | None) -> list[dict[str, Any]]:
        oai: list[dict[str, Any]] = []
        if system:
            oai.append({"role": "system", "content": system})
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                oai.append({"role": msg["role"], "content": content})
            else:
                oai.append({"role": msg["role"], "content": str(content)})
        return oai

    @staticmethod
    def _strip_thinking_tags(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def _try_parse_tool_calls_from_text(self, content: str) -> list[ToolCall]:
        all_items: list[dict[str, Any]] = []
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            parsed = self._parse_json_candidate(line)
            if isinstance(parsed, list):
                all_items.extend(item for item in parsed if isinstance(item, dict))
            elif isinstance(parsed, dict):
                all_items.append(parsed)

        if not all_items:
            match = re.search(r'\[[\s]*\{[\s]*"name"|\{[\s]*"name"', content)
            if match:
                parsed = self._parse_json_candidate(content[match.start():])
                if isinstance(parsed, list):
                    all_items.extend(item for item in parsed if isinstance(item, dict))
                elif isinstance(parsed, dict):
                    all_items.append(parsed)

        tool_calls: list[ToolCall] = []
        for item in all_items:
            name = item.get("name") or item.get("tool_name")
            arguments = item.get("arguments", item.get("input", {}))
            if name and isinstance(arguments, dict):
                tool_calls.append(
                    self._make_tool_call(
                        call_id=f"call_{uuid.uuid4().hex[:8]}",
                        name=name,
                        arguments=arguments,
                        source="text_json",
                    )
                )
        return tool_calls

    @staticmethod
    def _parse_json_candidate(text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        for end_char in ["]", "}"]:
            idx = text.rfind(end_char)
            if idx > 0:
                try:
                    return json.loads(text[: idx + 1])
                except json.JSONDecodeError:
                    continue
        return None


def normalize_numeric_arguments(tool_input: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Normalize model outputs like 35/50/15 into 0.35/0.50/0.15.

    The previous harness normalized only fields ending in ``_pct``. This testbed
    uses several interchangeable 0-1 numeric parameter names, so the same
    percentage-scale fallback is applied to all numeric tool arguments when any
    emitted numeric value exceeds 1.0.
    """

    numeric_keys = [k for k, value in tool_input.items() if isinstance(value, (int, float)) and not isinstance(value, bool)]
    if not numeric_keys:
        return dict(tool_input), False
    if not any(float(tool_input[k]) > 1.0 for k in numeric_keys):
        return dict(tool_input), False

    normalized = dict(tool_input)
    for key in numeric_keys:
        normalized[key] = round(float(normalized[key]) / 100.0, 4)
    return normalized, True
