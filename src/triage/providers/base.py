"""Provider-neutral types. Every model adapter speaks these, so the agent loop never
depends on one vendor's message format."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # set on role="tool" messages
    is_error: bool = False  # set on role="tool" messages when the tool failed


@dataclass
class ModelTurn:
    """One model response, normalized."""

    text: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    latency_s: float
    model: str
    stop_reason: str | None = None

    def as_message(self) -> Message:
        return Message(role="assistant", content=self.text, tool_calls=list(self.tool_calls))


class Provider(Protocol):
    name: str
    model: str

    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> ModelTurn: ...
