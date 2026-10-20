import asyncio
import json
from pathlib import Path
from typing import Any

from triage.agent.loop import Tool, run_agent
from triage.providers.base import ToolCall, ToolSpec
from triage.providers.fake import ScriptedProvider, turn


async def _double(args: dict[str, Any]) -> str:
    return str(int(args["n"]) * 2)


async def _boom(args: dict[str, Any]) -> str:
    raise ValueError("bad input")


DOUBLE = Tool(ToolSpec("double", "Double n", {"type": "object"}), _double)
BOOM = Tool(ToolSpec("boom", "Always fails", {"type": "object"}), _boom)


def test_tool_call_then_answer(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [turn(calls=[ToolCall("1", "double", {"n": 21})]), turn("It is 42.")]
    )
    log = tmp_path / "runs.jsonl"
    result = asyncio.run(run_agent(provider, "sys", "double 21", [DOUBLE], run_log=str(log)))

    assert result.final_text == "It is 42."
    assert result.stopped == "answered"
    assert result.steps == 2
    assert result.tool_calls[0].result == "42"
    assert (result.input_tokens, result.output_tokens) == (20, 10)
    # the tool result was sent back to the model on the second turn
    assert provider.calls[1][-1].role == "tool" and provider.calls[1][-1].content == "42"
    # one JSON line per run
    record = json.loads(log.read_text().strip())
    assert record["final_text"] == "It is 42." and record["run_id"] == result.run_id


def test_tool_errors_go_back_to_the_model() -> None:
    provider = ScriptedProvider([turn(calls=[ToolCall("1", "boom", {})]), turn("The tool failed.")])
    result = asyncio.run(run_agent(provider, "sys", "go", [BOOM]))
    rec = result.tool_calls[0]
    assert rec.is_error and "ValueError: bad input" in rec.result
    assert provider.calls[1][-1].is_error is True
    assert result.stopped == "answered"


def test_unknown_tool_is_reported() -> None:
    provider = ScriptedProvider([turn(calls=[ToolCall("1", "nope", {})]), turn("ok")])
    result = asyncio.run(run_agent(provider, "sys", "go", [DOUBLE]))
    assert result.tool_calls[0].is_error
    assert "Unknown tool 'nope'" in result.tool_calls[0].result


def test_step_cap_stops_a_looping_model() -> None:
    looping = [turn(calls=[ToolCall(str(i), "double", {"n": i})]) for i in range(10)]
    result = asyncio.run(run_agent(ScriptedProvider(looping), "sys", "go", [DOUBLE], max_steps=3))
    assert result.stopped == "max_steps"
    assert result.steps == 3 and len(result.tool_calls) == 3


def test_unknown_price_means_unknown_cost() -> None:
    provider = ScriptedProvider([turn("hi")], model="not-in-pricing-file")
    result = asyncio.run(run_agent(provider, "sys", "hi", []))
    assert result.cost_usd is None
