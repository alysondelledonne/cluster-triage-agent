"""Offline providers for tests and CI. They never call an API and cost nothing."""

from __future__ import annotations

from collections.abc import Callable

from .base import Message, ModelTurn, ToolCall, ToolSpec


class ScriptedProvider:
    """Returns a fixed list of turns in order. Good for unit tests of the loop."""

    name = "fake"

    def __init__(self, turns: list[ModelTurn], model: str = "fake") -> None:
        self.turns = list(turns)
        self.model = model
        self.calls: list[list[Message]] = []
        self.tools_offered: list[list[str]] = []  # tool names offered on each call

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> ModelTurn:
        self.calls.append(list(messages))
        self.tools_offered.append([t.name for t in tools])
        if not self.turns:
            raise RuntimeError("ScriptedProvider ran out of turns")
        return self.turns.pop(0)


class PolicyProvider:
    """Decides each turn with a function of the conversation so far.

    The eval harness uses this to build a "golden" model from each case's expected
    tool call, so CI can check the whole pipeline (loop, tools, grading, gate)
    without spending money.
    """

    name = "fake"

    def __init__(self, policy: Callable[[list[Message]], ModelTurn], model: str = "fake") -> None:
        self.policy = policy
        self.model = model

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> ModelTurn:
        return self.policy(messages)


def turn(text: str = "", calls: list[ToolCall] | None = None) -> ModelTurn:
    """Small helper for building fake turns."""
    return ModelTurn(
        text=text,
        tool_calls=calls or [],
        input_tokens=10,
        output_tokens=5,
        latency_s=0.0,
        model="fake",
        stop_reason="tool_use" if calls else "end_turn",
    )
