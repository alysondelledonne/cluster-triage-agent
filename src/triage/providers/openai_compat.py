"""OpenAI Chat Completions, plus any OpenAI-compatible API (xAI's Grok)."""

from __future__ import annotations

import json
import time
from typing import Any

from .base import Message, ModelTurn, ToolCall, ToolSpec


class OpenAICompatProvider:
    name = "openai"
    # OpenAI's current parameter for the output limit. Some compatible APIs use
    # "max_tokens" instead; subclasses override this.
    token_param = "max_completion_tokens"

    def __init__(
        self,
        model: str,
        max_tokens: int = 1024,
        client: Any = None,
        base_url: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        if client is None:
            import os

            import openai

            client = openai.OpenAI(api_key=os.getenv(api_key_env), base_url=base_url)
        self.client = client
        self.model = model
        self.max_tokens = max_tokens

    @staticmethod
    def to_api_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m.role == "user":
                out.append({"role": "user", "content": m.content})
            elif m.role == "assistant":
                msg: dict[str, Any] = {"role": "assistant", "content": m.content or None}
                if m.tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in m.tool_calls
                    ]
                out.append(msg)
            else:
                content = f"ERROR: {m.content}" if m.is_error else m.content
                out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": content})
        return out

    @staticmethod
    def to_api_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> ModelTurn:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self.to_api_messages(system, messages),
            self.token_param: self.max_tokens,
        }
        if tools:
            kwargs["tools"] = self.to_api_tools(tools)
        start = time.perf_counter()
        resp = self.client.chat.completions.create(**kwargs)
        latency = time.perf_counter() - start

        choice = resp.choices[0]
        calls: list[ToolCall] = []
        for tc in choice.message.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                # Keep the raw text so the tool reports a clear error instead of crashing.
                args = {"_raw_arguments": tc.function.arguments}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        usage = resp.usage
        return ModelTurn(
            text=choice.message.content or "",
            tool_calls=calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_s=latency,
            model=resp.model,
            stop_reason=choice.finish_reason,
        )


class GrokProvider(OpenAICompatProvider):
    """xAI Grok through its OpenAI-compatible endpoint."""

    name = "grok"
    token_param = "max_tokens"

    def __init__(
        self,
        model: str,
        max_tokens: int = 1024,
        client: Any = None,
        base_url: str = "https://api.x.ai/v1",
    ) -> None:
        super().__init__(
            model, max_tokens, client=client, base_url=base_url, api_key_env="XAI_API_KEY"
        )
