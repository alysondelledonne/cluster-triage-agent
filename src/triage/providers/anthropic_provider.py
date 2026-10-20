"""Claude via the Anthropic Messages API."""

from __future__ import annotations

import time
from typing import Any

from .base import Message, ModelTurn, ToolCall, ToolSpec


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, max_tokens: int = 1024, client: Any = None) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.client = client
        self.model = model
        self.max_tokens = max_tokens

    @staticmethod
    def to_api_messages(messages: list[Message]) -> list[dict[str, Any]]:
        """Neutral messages -> Anthropic format.

        Tool results go back as `tool_result` blocks inside a user turn, and
        consecutive tool results are merged into one turn.
        """
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "user":
                out.append({"role": "user", "content": m.content})
            elif m.role == "assistant":
                blocks: list[dict[str, Any]] = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    blocks.append(
                        {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                    )
                out.append({"role": "assistant", "content": blocks})
            else:
                block = {
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": m.content,
                    "is_error": m.is_error,
                }
                prev = out[-1] if out else None
                if (
                    prev
                    and prev["role"] == "user"
                    and isinstance(prev["content"], list)
                    and all(b.get("type") == "tool_result" for b in prev["content"])
                ):
                    prev["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
        return out

    @staticmethod
    def to_api_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> ModelTurn:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": self.to_api_messages(messages),
        }
        if tools:
            kwargs["tools"] = self.to_api_tools(tools)
        start = time.perf_counter()
        resp = self.client.messages.create(**kwargs)
        latency = time.perf_counter() - start

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        return ModelTurn(
            text="".join(text_parts),
            tool_calls=calls,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            latency_s=latency,
            model=resp.model,
            stop_reason=resp.stop_reason,
        )
