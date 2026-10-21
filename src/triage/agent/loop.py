"""A small, inspectable tool-calling agent loop.

The model is asked for a turn; any tool calls are run and their results sent
back. Every run returns its full trace plus token, latency and cost totals.

How a run ends depends on whether a finish tool is given:

- Without one (the template's examples), the run ends when the model answers
  without calling a tool, or after `max_steps` turns.
- With one (triage, DECISIONS.md 024), the run only ends on a submission the
  finish tool accepts. The model gets at most `max_tool_calls` investigative
  calls; after that it gets one forced turn where the finish tool is the only
  tool offered (DECISIONS.md 005). A plain-text answer gets a nudge, and a
  rejected submission goes back with the reasons; both are limited, so every
  run ends.
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
from ..providers.base import Message, ModelTurn, Provider, ToolCall, ToolSpec
from ..runlog import append_run
from ..tracing import span

ToolFn = Callable[[dict[str, Any]], Awaitable[str]]

DEFAULT_MAX_TOOL_CALLS = 12  # DECISIONS.md 024
MAX_NUDGES = 2  # plain-text answers tolerated before giving up
MAX_REJECTIONS = 2  # rejected submissions sent back for another try

Stopped = Literal["answered", "max_steps", "submitted", "submitted_at_cap", "no_submission"]


@dataclass
class Tool:
    spec: ToolSpec
    fn: ToolFn
    read_only: bool = True


@dataclass
class Finish:
    """The tool that ends a run. `parse` gets its arguments and every tool call made so
    far in the run (so it can check the answer against them), and returns the run's
    answer or raises ValueError with a message the model can act on."""

    spec: ToolSpec
    parse: Callable[[dict[str, Any], list[ToolRecord]], Any]


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
    stopped: Stopped
    steps: int
    tool_calls: list[ToolRecord] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model_latency_s: float = 0.0
    total_latency_s: float = 0.0
    cost_usd: float | None = 0.0
    submission: Any = None  # the parsed answer from the finish tool, e.g. a Diagnosis
    nudges: int = 0
    rejected_submissions: int = 0
    info: dict[str, Any] = field(default_factory=dict)  # caller's context, e.g. namespace

    def to_record(self) -> dict[str, Any]:
        rec = asdict(self)
        if hasattr(self.submission, "model_dump"):
            rec["submission"] = self.submission.model_dump(mode="json")
        rec["timestamp"] = datetime.now(UTC).isoformat()
        return rec


def nudge_text(finish: str) -> str:
    return f"Don't answer in plain text. Call {finish} with your diagnosis to finish."


def forced_text(finish: str, used: int) -> str:
    return (
        f"You have used all {used} tool calls. Call {finish} now with what you have. "
        "If the evidence isn't conclusive, say so in the root cause and set confidence "
        "below 0.5."
    )


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


def _tool_message(call: ToolCall, rec: ToolRecord) -> Message:
    return Message(role="tool", content=rec.result, tool_call_id=call.id, is_error=rec.is_error)


async def run_agent(
    provider: Provider,
    system: str,
    user_input: str,
    tools: list[Tool],
    max_steps: int = 8,
    run_log: str | None = None,
    *,
    finish: Finish | None = None,
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    info: dict[str, Any] | None = None,
) -> AgentResult:
    result = AgentResult(
        run_id=uuid.uuid4().hex[:12],
        provider=provider.name,
        model=provider.model,
        final_text="",
        stopped="max_steps",
        steps=0,
        info=dict(info or {}),
    )
    messages: list[Message] = [Message(role="user", content=user_input)]
    started = time.perf_counter()
    costs: list[float | None] = []

    async def ask(specs: list[ToolSpec]) -> ModelTurn:
        result.steps += 1
        # Provider SDKs are synchronous; run them off the event loop.
        turn = await asyncio.to_thread(provider.complete, system, messages, specs)
        result.input_tokens += turn.input_tokens
        result.output_tokens += turn.output_tokens
        result.model_latency_s += turn.latency_s
        costs.append(cost_usd(turn.model, turn.input_tokens, turn.output_tokens))
        messages.append(turn.as_message())
        return turn

    with span("agent.run", provider=provider.name, model=provider.model, input=user_input):
        if finish is None:
            await _answer_loop(ask, messages, result, tools, max_steps)
        else:
            await _finish_loop(ask, messages, result, tools, finish, max_tool_calls)

    result.total_latency_s = time.perf_counter() - started
    # Unknown price on any turn makes the run's cost unknown rather than understated.
    result.cost_usd = None if any(c is None for c in costs) else sum(c or 0.0 for c in costs)
    if run_log:
        append_run(run_log, result.to_record())
    return result


Ask = Callable[[list[ToolSpec]], Awaitable[ModelTurn]]


async def _answer_loop(
    ask: Ask, messages: list[Message], result: AgentResult, tools: list[Tool], max_steps: int
) -> None:
    """Without a finish tool: stop at the first plain-text answer or after max_steps turns."""
    by_name = {t.spec.name: t for t in tools}
    specs = [t.spec for t in tools]
    for _ in range(max_steps):
        turn = await ask(specs)
        if not turn.tool_calls:
            result.final_text = turn.text
            result.stopped = "answered"
            return
        for call in turn.tool_calls:
            rec = await _run_tool(by_name, call)
            result.tool_calls.append(rec)
            messages.append(_tool_message(call, rec))


async def _finish_loop(
    ask: Ask,
    messages: list[Message],
    result: AgentResult,
    tools: list[Tool],
    finish: Finish,
    max_tool_calls: int,
) -> None:
    """With a finish tool: stop only on an accepted submission, within the limits.

    Every pass through the loop either uses up a tool call, a nudge or a rejection,
    or ends the run, and each of those is capped, so the loop always terminates.
    """
    by_name = {t.spec.name: t for t in tools}
    all_specs = [t.spec for t in tools] + [finish.spec]
    used = 0  # investigative tool calls run so far
    name = finish.spec.name

    while True:
        forced = used >= max_tool_calls
        turn = await ask([finish.spec] if forced else all_specs)
        result.final_text = turn.text

        if not turn.tool_calls:
            if forced or result.nudges >= MAX_NUDGES:
                result.stopped = "no_submission"
                return
            result.nudges += 1
            messages.append(Message(role="user", content=nudge_text(name)))
            continue

        submitted_or_rejected = False
        for call in turn.tool_calls:
            if call.name == name:
                start = time.perf_counter()
                try:
                    result.submission = finish.parse(call.arguments, list(result.tool_calls))
                except ValueError as err:
                    rec = ToolRecord(name, call.arguments, str(err), True, 0.0)
                    result.tool_calls.append(rec)
                    messages.append(_tool_message(call, rec))
                    result.rejected_submissions += 1
                    submitted_or_rejected = True
                    continue
                elapsed = time.perf_counter() - start
                result.tool_calls.append(
                    ToolRecord(name, call.arguments, "accepted", False, elapsed)
                )
                result.stopped = "submitted_at_cap" if forced else "submitted"
                return  # any calls after an accepted submission are not run

            if used >= max_tool_calls:
                rec = ToolRecord(
                    call.name,
                    call.arguments,
                    f"Not run: the limit of {max_tool_calls} tool calls is reached. "
                    f"Call {name} with what you have.",
                    True,
                    0.0,
                )
            else:
                used += 1
                rec = await _run_tool(by_name, call)
            result.tool_calls.append(rec)
            messages.append(_tool_message(call, rec))

        if result.rejected_submissions > MAX_REJECTIONS:
            result.stopped = "no_submission"
            return
        if forced and not submitted_or_rejected:
            # On the forced turn only the finish tool was offered; anything else is a refusal.
            result.stopped = "no_submission"
            return
        if used >= max_tool_calls and not forced:
            messages.append(Message(role="user", content=forced_text(name, max_tool_calls)))
