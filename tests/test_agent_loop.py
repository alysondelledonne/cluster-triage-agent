"""The agent loop's basics: tool calls, errors and the run log.

Every run needs a finish tool now (DECISIONS.md 035); these tests use a tiny one
so they don't depend on the Diagnosis schema. The submission rules, cap and
retries are covered in test_agent_finish.py.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from triage.agent.loop import Finish, Tool, ToolRecord, run_agent
from triage.providers.base import ToolCall, ToolSpec
from triage.providers.fake import ScriptedProvider, turn


async def _double(args: dict[str, Any]) -> str:
    return str(int(args["n"]) * 2)


async def _boom(args: dict[str, Any]) -> str:
    raise ValueError("bad input")


def _answer(args: dict[str, Any], records: list[ToolRecord]) -> str:
    if "answer" not in args:
        raise ValueError("- answer: Field required")
    return str(args["answer"])


DOUBLE = Tool(ToolSpec("double", "Double n", {"type": "object"}), _double)
BOOM = Tool(ToolSpec("boom", "Always fails", {"type": "object"}), _boom)
DONE = Finish(ToolSpec("done", "Give the answer", {"type": "object"}), _answer)


def done(answer: str) -> ToolCall:
    return ToolCall("d", "done", {"answer": answer})


def run(provider: ScriptedProvider, tools: list[Tool], **kwargs: Any) -> Any:
    return asyncio.run(run_agent(provider, "sys", "go", tools, finish=DONE, **kwargs))


def test_tool_call_then_finish(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [turn(calls=[ToolCall("1", "double", {"n": 21})]), turn(calls=[done("42")])]
    )
    log = tmp_path / "runs.jsonl"
    result = run(provider, [DOUBLE], run_log=str(log), info={"namespace": "ns"})

    assert result.submission == "42"
    assert result.stopped == "submitted"
    assert result.steps == 2
    assert result.tool_calls[0].result == "42"
    assert (result.input_tokens, result.output_tokens) == (20, 10)
    # the tool result was sent back to the model on the second turn
    assert provider.calls[1][-1].role == "tool" and provider.calls[1][-1].content == "42"
    # one JSON line per run
    record = json.loads(log.read_text().strip())
    assert record["run_id"] == result.run_id
    assert record["submission"] == "42"
    assert record["info"] == {"namespace": "ns"}


def test_tool_errors_go_back_to_the_model() -> None:
    provider = ScriptedProvider([turn(calls=[ToolCall("1", "boom", {})]), turn(calls=[done("x")])])
    result = run(provider, [BOOM])
    rec = result.tool_calls[0]
    assert rec.is_error and "ValueError: bad input" in rec.result
    assert provider.calls[1][-1].is_error is True
    assert result.stopped == "submitted"


def test_unknown_tool_is_reported() -> None:
    provider = ScriptedProvider([turn(calls=[ToolCall("1", "nope", {})]), turn(calls=[done("ok")])])
    result = run(provider, [DOUBLE])
    assert result.tool_calls[0].is_error
    assert "Unknown tool 'nope'" in result.tool_calls[0].result


def test_a_run_that_never_finishes_says_so() -> None:
    provider = ScriptedProvider([turn("a"), turn("b"), turn("c")])
    result = run(provider, [DOUBLE])
    assert result.stopped == "no_submission"
    assert result.submission is None


def test_unknown_price_means_unknown_cost() -> None:
    provider = ScriptedProvider([turn(calls=[done("hi")])], model="not-in-pricing-file")
    result = run(provider, [])
    assert result.cost_usd is None
