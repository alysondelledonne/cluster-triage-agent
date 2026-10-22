"""The eval harness on the six recorded scenarios (DECISIONS.md 033, 036).

Offline: the golden model is scripted and the cluster is the recordings.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from triage.agent.loop import AgentResult, ToolRecord
from triage.evals.runner import (
    Case,
    check_gate,
    golden_provider,
    grade,
    load_cases,
    main,
    markdown_tables,
    run_suite,
    summarize,
)
from triage.models import Category, Diagnosis

NOT_RECORDED = "Kubernetes API error (404): not in this recording: read(kind='pod')"


def case(name: str) -> Case:
    (found,) = [c for c in load_cases() if c.scenario.name.endswith(name)]
    return found


def result(
    submission: dict[str, Any] | None,
    *,
    stopped: str = "submitted",
    tools: list[ToolRecord] | None = None,
    cost: float | None = 0.002,
) -> AgentResult:
    return AgentResult(
        run_id="r1",
        provider="anthropic",
        model="claude-haiku-5-5",
        final_text="",
        stopped=stopped,  # type: ignore[arg-type]
        steps=3,
        tool_calls=tools or [],
        input_tokens=1000,
        output_tokens=100,
        total_latency_s=2.0,
        cost_usd=cost,
        submission=Diagnosis.model_validate(submission) if submission else None,
    )


def diagnosis(category: str, kind: str, name: str) -> dict[str, Any]:
    return {
        "category": category,
        "affected_resource": {"kind": kind, "name": name},
        "root_cause": "Something specific went wrong here.",
        "evidence": [{"tool": "list_pods", "quote": "phase: Running"}],
        "proposed_fix": {
            "explanation": "x",
            "yaml": "apiVersion: v1\nkind: X\nmetadata: {name: y}",
        },
        "confidence": 0.9,
    }


# ---------- the cases ----------


def test_every_scenario_is_a_case_with_its_recording() -> None:
    cases = load_cases()
    assert [c.scenario.name[:2] for c in cases] == ["01", "02", "03", "04", "05", "06"]
    for c in cases:
        assert c.recording.namespace == c.scenario.expected.namespace


def test_a_scenario_without_a_recording_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="triage-seed record"):
        load_cases(recordings_dir=tmp_path)


# ---------- grading ----------


def test_right_category_and_resource_is_correct() -> None:
    row = grade(case("rbac-denied"), result(diagnosis("RBACDenied", "ServiceAccount", "reporter")))
    assert (row["category_ok"], row["resource_ok"], row["correct"]) == (True, True, True)
    assert row["scenario"] == "06-rbac-denied"
    assert row["got"] == "RBACDenied ServiceAccount/reporter"


def test_also_accept_counts_as_correct() -> None:
    row = grade(case("rbac-denied"), result(diagnosis("RBACDenied", "Deployment", "reporter")))
    assert row["correct"]


def test_wrong_category_or_resource_is_wrong() -> None:
    wrong_category = grade(case("crashloop"), result(diagnosis("OOMKilled", "Deployment", "api")))
    assert not wrong_category["category_ok"] and wrong_category["resource_ok"]
    assert not wrong_category["correct"]
    wrong_object = grade(case("crashloop"), result(diagnosis("CrashLoop", "Deployment", "web")))
    assert wrong_object["category_ok"] and not wrong_object["correct"]


def test_no_submission_is_wrong_and_counted() -> None:
    row = grade(case("crashloop"), result(None, stopped="no_submission"))
    assert not row["correct"] and not row["submitted"]
    assert row["got"] == "no diagnosis"
    assert row["first_try_grounding"] == 0.0


def test_cap_tool_calls_and_unrecorded_calls_are_counted() -> None:
    tools = [
        ToolRecord("list_pods", {}, "pods", False, 0.0),
        ToolRecord("describe", {"kind": "pod"}, NOT_RECORDED, True, 0.0),
        ToolRecord(
            "submit_diagnosis", diagnosis("CrashLoop", "Deployment", "api"), "accepted", False, 0.0
        ),
    ]
    row = grade(
        case("crashloop"),
        result(
            diagnosis("CrashLoop", "Deployment", "api"), stopped="submitted_at_cap", tools=tools
        ),
    )
    assert row["submitted"] and row["at_cap"]
    assert row["tool_calls"] == 2
    assert row["unrecorded_calls"] == 1


def test_first_try_grounding_comes_from_the_trace() -> None:
    sub = diagnosis("CrashLoop", "Deployment", "api")
    tools = [
        ToolRecord("list_pods", {}, "phase: Running", False, 0.0),
        ToolRecord("submit_diagnosis", sub, "accepted", False, 0.0),
    ]
    assert grade(case("crashloop"), result(sub, tools=tools))["first_try_grounding"] == 1.0
    invented = {**sub, "evidence": [{"tool": "list_pods", "quote": "OOMKilled"}]}
    tools.insert(1, ToolRecord("submit_diagnosis", invented, "rejected", True, 0.0))
    assert grade(case("crashloop"), result(sub, tools=tools))["first_try_grounding"] == 0.0


# ---------- summaries and the gate ----------


def rows() -> list[dict[str, Any]]:
    good = grade(case("crashloop"), result(diagnosis("CrashLoop", "Deployment", "api")))
    bad = grade(case("crashloop"), result(None, stopped="no_submission", cost=0.004))
    return [good, bad]


def test_summary_metrics() -> None:
    s = summarize(rows())
    assert s["runs"] == 2
    assert s["accuracy"] == 0.5
    assert s["submitted_rate"] == 0.5
    assert s["cost_per_incident_usd"] == pytest.approx(0.003)
    assert s["latency_p50_s"] == 2.0


def test_unknown_cost_makes_the_summary_cost_unknown() -> None:
    r = rows()
    r[0]["cost_usd"] = None
    assert summarize(r)["cost_per_incident_usd"] is None


def test_gate_catches_a_regression() -> None:
    failures = check_gate(summarize(rows()), {"accuracy": 1.0, "submitted_rate": 0.5})
    assert len(failures) == 1 and failures[0].startswith("accuracy")


def test_tables_show_the_summary_and_each_scenario() -> None:
    r = rows()
    summary, per_scenario = markdown_tables({"claude-haiku-5-5": r})
    assert "| claude-haiku-5-5 | 6" not in summary
    assert "| claude-haiku-5-5 | 2 | 0.5 |" in summary
    assert "| 01-crashloop | 1/2 |" in per_scenario


# ---------- the golden model and the offline gate ----------


@pytest.mark.parametrize("c", load_cases(), ids=lambda c: c.scenario.name)
def test_golden_model_gets_every_scenario_right_first_time(
    c: Case, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUN_LOG", str(tmp_path / "runs.jsonl"))
    (row,) = asyncio.run(run_suite("fake", [c], repeats=1))
    assert row["correct"], row
    assert row["first_try_grounding"] == 1.0
    assert row["rejected_submissions"] == 0
    assert row["unrecorded_calls"] == 0


def test_golden_provider_is_offline() -> None:
    provider = golden_provider(case("imagepull"))
    assert provider.name == "fake"


def test_offline_gate_passes_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUN_LOG", str(tmp_path / "runs.jsonl"))
    assert main(["--provider", "fake", "--gate", "--results-dir", str(tmp_path / "results")]) == 0
    assert not (tmp_path / "results").exists()


def test_save_writes_json_and_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_LOG", str(tmp_path / "runs.jsonl"))
    out = tmp_path / "results"
    assert (
        main(["--provider", "fake", "--scenario", "imagepull", "--save", "--results-dir", str(out)])
        == 0
    )
    (saved,) = out.glob("*-fake.json")
    payload = json.loads(saved.read_text())
    assert payload["repeats"] == 1
    assert payload["summaries"]["fake"]["accuracy"] == 1.0
    assert payload["rows"]["fake"][0]["scenario"] == "02-imagepull"
    assert "| 02-imagepull | 1/1 |" in (out / "latest.md").read_text()


def test_category_values_line_up_with_scenarios() -> None:
    assert {c.scenario.expected.category for c in load_cases()} <= set(Category)
