"""A small, inspectable tool-calling agent loop.

The model is asked for a turn; any tool calls are run and their results sent
back; this repeats until the model answers without calling a tool or the step
cap is hit. Every run returns its full trace plus token, latency and cost totals.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from ..pricing import cost_usd
from ..providers.base import Message, Provider, ToolCall, ToolSpec
from ..runlog import append_run
from ..tracing import span

ToolFn = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass
class Tool:
    spec: ToolSpec
    fn: ToolFn
    read_only: bool = True


@dataclass
class ToolRecord:
    name: str
    arguments: dict[str, Any]
    result: str
    is_error: bool
    latency_s: float


@dataclass
class AgentResult:
    run_id: str
    provider: str
    model: str
    final_text: str
    stopped: Literal["answered", "max_steps"]
    steps: int
    tool_calls: list[ToolRecord] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model_latency_s: float = 0.0
    total_latency_s: float = 0.0
    cost_usd: float | None = 0.0

    def to_record(self) -> dict[str, Any]:
        rec = asdict(self)
        rec["timestamp"] = datetime.now(UTC).isoformat()
        return rec


async def _run_tool(tools: dict[str, Tool], call: ToolCall) -> ToolRecord:
    start = time.perf_counter()
    tool = tools.get(call.name)
    if tool is None:
        result, is_error = f"Unknown tool '{call.name}'. Available: {sorted(tools)}", True
    else:
        try:
            with span(f"tool.{call.name}", arguments=call.arguments):
                result, is_error = await tool.fn(call.arguments), False
        except Exception as exc:  # report tool failures to the model instead of crashing
            result, is_error = f"{type(exc).__name__}: {exc}", True
    return ToolRecord(call.name, call.arguments, result, is_error, time.perf_counter() - start)


async def run_agent(
    provider: Provider,
    system: str,
    user_input: str,
    tools: list[Tool],
    max_steps: int = 8,
    run_log: str | None = None,
) -> AgentResult:
    by_name = {t.spec.name: t for t in tools}
    specs = [t.spec for t in tools]
    messages: list[Message] = [Message(role="user", content=user_input)]
    result = AgentResult(
        run_id=uuid.uuid4().hex[:12],
        provider=provider.name,
        model=provider.model,
        final_text="",
        stopped="max_steps",
        steps=0,
    )
    started = time.perf_counter()
    costs: list[float | None] = []

    with span("agent.run", provider=provider.name, model=provider.model, input=user_input):
        for _ in range(max_steps):
            result.steps += 1
            # Provider SDKs are synchronous; run them off the event loop.
            turn = await asyncio.to_thread(provider.complete, system, messages, specs)
            result.input_tokens += turn.input_tokens
            result.output_tokens += turn.output_tokens
            result.model_latency_s += turn.latency_s
            costs.append(cost_usd(turn.model, turn.input_tokens, turn.output_tokens))
            messages.append(turn.as_message())

            if not turn.tool_calls:
                result.final_text = turn.text
                result.stopped = "answered"
                break

            for call in turn.tool_calls:
                rec = await _run_tool(by_name, call)
                result.tool_calls.append(rec)
                messages.append(
                    Message(
                        role="tool",
                        content=rec.result,
                        tool_call_id=call.id,
                        is_error=rec.is_error,
                    )
                )

    result.total_latency_s = time.perf_counter() - started
    # Unknown price on any turn makes the run's cost unknown rather than understated.
    result.cost_usd = None if any(c is None for c in costs) else sum(c or 0.0 for c in costs)
    if run_log:
        append_run(run_log, result.to_record())
    return result
