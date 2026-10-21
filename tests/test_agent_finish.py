"""The agent loop with a finish tool: a run only ends on a valid `submit_diagnosis`.

Covers the tool-call cap with its forced last turn, nudges when the model answers
in plain text, and retries when a submission is rejected (DECISIONS.md 005, 024).
Offline: scripted model turns and a stand-in cluster tool.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from triage.agent.loop import Tool, run_agent
from triage.agent.submit import SUBMIT_DIAGNOSIS, diagnosis_finish
from triage.models import Category, Diagnosis
from triage.providers.base import ToolCall, ToolSpec
from triage.providers.fake import ScriptedProvider, turn


async def _list_pods(args: dict[str, Any]) -> str:
    return "- name: api\n  state: 'waiting: CrashLoopBackOff'"


LIST_PODS = Tool(ToolSpec("list_pods", "List pods", {"type": "object"}), _list_pods)


NS = "triage-01-crashloop"
FIX = "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: api}\nspec: {replicas: 1}\n"


def diagnosis(**change: Any) -> dict[str, Any]:
    return {
        "category": "CrashLoop",
        "affected_resource": {"kind": "Deployment", "name": "api"},
        "root_cause": "The api container exits with status 1 on every start.",
        "evidence": [{"tool": "list_pods", "quote": "waiting: CrashLoopBackOff"}],
        "proposed_fix": {"explanation": "Set LISTEN_PORT.", "yaml": FIX},
        "confidence": 0.8,
        **change,
    }


def look(i: int = 0) -> ToolCall:
    return ToolCall(f"look{i}", "list_pods", {})


def submit(i: int = 0, **change: Any) -> ToolCall:
    return ToolCall(f"submit{i}", SUBMIT_DIAGNOSIS, diagnosis(**change))


def run(provider: ScriptedProvider, **kwargs: Any) -> Any:
    return asyncio.run(
        run_agent(provider, "sys", "diagnose", [LIST_PODS], finish=diagnosis_finish(NS), **kwargs)
    )


def last_user_message(provider: ScriptedProvider, call: int) -> str:
    return next(m.content for m in reversed(provider.calls[call]) if m.role == "user")


# ---------- the happy path ----------


def test_investigate_then_submit(tmp_path: Path) -> None:
    provider = ScriptedProvider([turn(calls=[look()]), turn(calls=[submit()])])
    log = tmp_path / "runs.jsonl"
    result = run(provider, run_log=str(log))

    assert result.stopped == "submitted"
    assert isinstance(result.submission, Diagnosis)
    assert result.submission.category is Category.CRASH_LOOP
    assert [t.name for t in result.tool_calls] == ["list_pods", SUBMIT_DIAGNOSIS]
    assert result.tool_calls[-1].result == "accepted"
    assert provider.tools_offered[0] == ["list_pods", SUBMIT_DIAGNOSIS]

    record = json.loads(log.read_text())
    assert record["stopped"] == "submitted"
    assert record["submission"]["category"] == "CrashLoop"


def test_calls_after_an_accepted_submission_are_not_run() -> None:
    provider = ScriptedProvider([turn(calls=[look(1), submit(), look(2)])])
    result = run(provider)
    assert result.stopped == "submitted"
    assert [t.name for t in result.tool_calls] == ["list_pods", SUBMIT_DIAGNOSIS]


# ---------- plain-text answers ----------


def test_a_plain_text_answer_gets_a_nudge() -> None:
    provider = ScriptedProvider(
        [turn(calls=[look()]), turn("It's a crash loop."), turn(calls=[submit()])]
    )
    result = run(provider)
    assert result.stopped == "submitted"
    assert result.nudges == 1
    assert SUBMIT_DIAGNOSIS in last_user_message(provider, 2)


def test_too_many_plain_text_answers_end_without_a_submission() -> None:
    provider = ScriptedProvider([turn("one"), turn("two"), turn("three")])
    result = run(provider)
    assert result.stopped == "no_submission"
    assert result.submission is None
    assert result.nudges == 2
    assert result.steps == 3


# ---------- rejected submissions ----------


def test_a_rejected_submission_goes_back_with_the_reasons() -> None:
    provider = ScriptedProvider(
        [turn(calls=[look()]), turn(calls=[submit(1, confidence=3)]), turn(calls=[submit(2)])]
    )
    result = run(provider)
    assert result.stopped == "submitted"
    assert result.rejected_submissions == 1
    rejected = result.tool_calls[1]
    assert rejected.is_error
    assert "- confidence: Input should be less than or equal to 1" in rejected.result
    sent_back = provider.calls[2][-1]
    assert sent_back.role == "tool" and sent_back.is_error and sent_back.tool_call_id == "submit1"


def test_three_rejections_end_the_run() -> None:
    provider = ScriptedProvider([turn(calls=[submit(i, confidence=3)]) for i in range(3)])
    result = run(provider)
    assert result.stopped == "no_submission"
    assert result.rejected_submissions == 3
    assert result.steps == 3


# ---------- the tool-call cap ----------


def test_at_the_cap_only_submit_is_offered_and_it_counts_as_at_cap() -> None:
    looking = [turn(calls=[look(i)]) for i in range(4)]
    provider = ScriptedProvider([*looking, turn(calls=[submit(confidence=0.3)])])
    result = run(provider, max_tool_calls=4)

    assert result.stopped == "submitted_at_cap"
    assert result.submission.confidence == 0.3
    assert [t.name for t in result.tool_calls].count("list_pods") == 4
    assert provider.tools_offered[3] == ["list_pods", SUBMIT_DIAGNOSIS]
    assert provider.tools_offered[4] == [SUBMIT_DIAGNOSIS]
    forced = last_user_message(provider, 4)
    assert "4 tool calls" in forced and "confidence below 0.5" in forced


def test_calls_past_the_cap_in_one_turn_are_refused() -> None:
    provider = ScriptedProvider([turn(calls=[look(1), look(2), look(3)]), turn(calls=[submit()])])
    result = run(provider, max_tool_calls=2)
    third = result.tool_calls[2]
    assert third.name == "list_pods" and third.is_error
    assert "limit" in third.result
    assert result.stopped == "submitted_at_cap"
    assert sum(1 for t in result.tool_calls if t.name == "list_pods" and not t.is_error) == 2


def test_no_submission_on_the_forced_turn_ends_the_run() -> None:
    provider = ScriptedProvider([turn(calls=[look(1)]), turn(calls=[look(2)]), turn("I give up.")])
    result = run(provider, max_tool_calls=2)
    assert result.stopped == "no_submission"
    assert result.submission is None
    assert result.steps == 3


def test_default_cap_is_twelve_tool_calls() -> None:
    looking = [turn(calls=[look(i)]) for i in range(12)]
    provider = ScriptedProvider([*looking, turn(calls=[submit()])])
    result = run(provider)
    assert result.stopped == "submitted_at_cap"
    assert result.steps == 13


def test_a_rejection_on_the_forced_turn_gets_another_try() -> None:
    provider = ScriptedProvider(
        [turn(calls=[look()]), turn(calls=[submit(1, confidence=3)]), turn(calls=[submit(2)])]
    )
    result = run(provider, max_tool_calls=1)
    assert result.stopped == "submitted_at_cap"
    assert provider.tools_offered[2] == [SUBMIT_DIAGNOSIS]


# ---------- grounding (DECISIONS.md 026) ----------


def test_an_ungrounded_quote_is_sent_back_and_then_corrected() -> None:
    invented = [{"tool": "list_pods", "quote": "OOMKilled"}]
    provider = ScriptedProvider(
        [turn(calls=[look()]), turn(calls=[submit(1, evidence=invented)]), turn(calls=[submit(2)])]
    )
    result = run(provider)
    assert result.stopped == "submitted"
    assert result.rejected_submissions == 1
    rejected = result.tool_calls[1]
    assert rejected.is_error
    assert "- evidence.0.quote: not found in any list_pods output" in rejected.result


def test_quotes_must_come_from_calls_made_before_the_submission() -> None:
    # Submitting before looking: the quote can't be grounded yet.
    provider = ScriptedProvider(
        [turn(calls=[submit(1)]), turn(calls=[look()]), turn(calls=[submit(2)])]
    )
    result = run(provider)
    assert result.rejected_submissions == 1
    assert result.stopped == "submitted"


def test_a_fix_outside_the_namespace_is_sent_back() -> None:
    elsewhere = FIX.replace("{name: api}", "{name: api, namespace: default}")
    fix = {"explanation": "x", "yaml": elsewhere}
    provider = ScriptedProvider(
        [turn(calls=[look()]), turn(calls=[submit(1, proposed_fix=fix)]), turn(calls=[submit(2)])]
    )
    result = run(provider)
    assert result.rejected_submissions == 1
    assert "- proposed_fix.yaml: document 1: namespace default" in result.tool_calls[1].result
