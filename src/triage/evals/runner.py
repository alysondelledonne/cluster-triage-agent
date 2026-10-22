"""Eval harness: diagnose every recorded scenario, grade it, report metrics, gate on a baseline.

    uv run triage-eval --provider fake --gate                     # offline; what CI runs
    uv run triage-eval --provider anthropic --repeats 3 --save    # costs a few cents
    uv run triage-eval --provider anthropic --provider grok --repeats 3 --save

Each case is a scenario (scenarios/NN-name/) replayed from its recording
(tests/fixtures/scenarios/NN-name/recording.json), so every model sees the same
cluster output and no cluster is needed (DECISIONS.md 033). A run goes through
the same `diagnose()` as the `triage` command and is graded against the
scenario's expected.yaml (DECISIONS.md 036).

`--provider fake` is a scripted "golden" model: it follows a sensible tool path
and submits the expected answer, quoting the real signal line from the replayed
output. It checks the harness, grading, grounding and gate end to end, for free.
`--save` writes evals/results/<time>-<models>.json and evals/results/latest.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..agent.grounding import submission_attempts
from ..agent.loop import AgentResult
from ..agent.submit import SUBMIT_DIAGNOSIS
from ..cli import ModelAPIError, diagnose
from ..config import load_settings
from ..mcp_server.replay import Recording, ReplayReader
from ..providers import Provider, get_provider
from ..providers.base import Message, ModelTurn, ToolCall
from ..providers.fake import PolicyProvider
from ..scenarios import (
    ContainerTerminated,
    ContainerWaiting,
    EventSeen,
    LogContains,
    Scenario,
    discover,
    find,
)

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "evals"
SCENARIOS_DIR = ROOT / "scenarios"
RECORDINGS_DIR = ROOT / "tests" / "fixtures" / "scenarios"
NOT_RECORDED = "not in this recording"


@dataclass(frozen=True)
class Case:
    scenario: Scenario
    recording: Recording


def load_cases(
    scenarios_dir: Path = SCENARIOS_DIR,
    recordings_dir: Path = RECORDINGS_DIR,
    names: list[str] | None = None,
) -> list[Case]:
    scenarios = discover(scenarios_dir)
    chosen = [find(scenarios, n) for n in names] if names else scenarios
    cases = []
    for s in chosen:
        path = recordings_dir / s.name / "recording.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"no recording for {s.name}; run: uv run triage-seed record {s.name}"
            )
        cases.append(Case(scenario=s, recording=Recording.load(path)))
    return cases


# ---------- the golden model ----------


def _signal_texts(case: Case) -> list[str]:
    """What the failure looks like in tool output, from the scenario's wait condition."""
    cond = case.scenario.expected.seed.wait_for
    if isinstance(cond, ContainerWaiting):
        return list(cond.reasons)
    if isinstance(cond, ContainerTerminated):
        return [cond.reason]
    if isinstance(cond, EventSeen):
        return [f"reason: {cond.reason}"]
    assert isinstance(cond, LogContains)
    return [cond.text]


def _plan(case: Case) -> list[ToolCall]:
    """The golden model's tool calls: pods first, then wherever the signal shows."""
    plan = [ToolCall("g1", "list_pods", {})]
    cond = case.scenario.expected.seed.wait_for
    if isinstance(cond, EventSeen):
        plan.append(ToolCall("g2", "get_events", {}))
    if isinstance(cond, LogContains):
        ns = case.recording.namespace
        pod = ReplayReader(case.recording).list_pods(ns)[0]["metadata"]["name"]
        plan.append(ToolCall("g2", "get_logs", {"pod": pod}))
    return plan


def golden_provider(case: Case) -> Provider:
    """A fake model that does what a good agent would on this scenario: look, then
    submit the expected answer with the signal line quoted from the real output."""
    plan = _plan(case)
    expected = case.scenario.expected
    signals = _signal_texts(case)
    ref = expected.affected_resource
    api_version = {"Deployment": "apps/v1"}.get(ref.kind, "v1")

    def policy(messages: list[Message]) -> ModelTurn:
        results = [m for m in messages if m.role == "tool"]
        if len(results) < len(plan):
            call = plan[len(results)]
            return ModelTurn("", [call], 50, 10, 0.0, "fake", "tool_use")
        output = results[len(plan) - 1].content
        line = next(ln for ln in output.splitlines() if any(s in ln for s in signals))
        submission = {
            "category": expected.category.value,
            "affected_resource": {"kind": ref.kind, "name": ref.name},
            "root_cause": f"Golden answer for {case.scenario.name}: {expected.description}.",
            "evidence": [{"tool": plan[-1].name, "quote": line.strip()[:500]}],
            "proposed_fix": {
                "explanation": "Placeholder fix from the golden model.",
                "yaml": f"apiVersion: {api_version}\nkind: {ref.kind}\n"
                f"metadata:\n  name: {ref.name}\n  namespace: {expected.namespace}\n",
            },
            "confidence": 1.0,
        }
        call = ToolCall("submit", SUBMIT_DIAGNOSIS, submission)
        return ModelTurn("", [call], 80, 40, 0.0, "fake", "tool_use")

    return PolicyProvider(policy)


# ---------- grading ----------


def grade(case: Case, result: AgentResult) -> dict[str, Any]:
    """One run against expected.yaml, plus how it got there."""
    expected = case.scenario.expected
    d = result.submission
    category_ok = d is not None and d.category == expected.category
    resource_ok = d is not None and d.affected_resource in [
        expected.affected_resource,
        *expected.also_accept,
    ]
    attempts = submission_attempts(result.tool_calls, expected.namespace)
    looks = [t for t in result.tool_calls if t.name != SUBMIT_DIAGNOSIS]
    return {
        "scenario": case.scenario.name,
        "model": result.model,
        "run_id": result.run_id,
        "correct": category_ok and resource_ok,
        "category_ok": category_ok,
        "resource_ok": resource_ok,
        "got": f"{d.category.value} {d.affected_resource}" if d is not None else "no diagnosis",
        "confidence": d.confidence if d is not None else None,
        "submitted": result.stopped in ("submitted", "submitted_at_cap"),
        "at_cap": result.stopped == "submitted_at_cap",
        "first_try_grounding": attempts[0].grounded_share if attempts else 0.0,
        "rejected_submissions": result.rejected_submissions,
        "nudges": result.nudges,
        "tool_calls": len(looks),
        "unrecorded_calls": sum(1 for t in looks if NOT_RECORDED in t.result),
        "latency_s": round(result.total_latency_s, 3),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd,
    }


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    costs = [r["cost_usd"] for r in rows]
    lat = [r["latency_s"] for r in rows]
    calls = sum(r["tool_calls"] for r in rows)
    known_cost = not any(c is None for c in costs)
    return {
        "runs": n,
        "accuracy": round(sum(r["correct"] for r in rows) / n, 3),
        "category_accuracy": round(sum(r["category_ok"] for r in rows) / n, 3),
        "submitted_rate": round(sum(r["submitted"] for r in rows) / n, 3),
        "first_try_grounding": round(statistics.mean(r["first_try_grounding"] for r in rows), 3),
        "avg_tool_calls": round(calls / n, 2),
        "cap_rate": round(sum(r["at_cap"] for r in rows) / n, 3),
        "unrecorded_call_rate": round(sum(r["unrecorded_calls"] for r in rows) / max(1, calls), 3),
        "latency_p50_s": round(_pct(lat, 0.5), 2),
        "latency_p95_s": round(_pct(lat, 0.95), 2),
        "cost_per_incident_usd": round(sum(c or 0.0 for c in costs) / n, 5) if known_cost else None,
    }


def check_gate(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Return a list of failures; empty means the gate passes. Baseline values are minimums."""
    return [
        f"{k}: {summary.get(k)} < baseline {v}"
        for k, v in baseline.items()
        if not k.startswith("_") and (summary.get(k) is None or summary[k] < v)
    ]


SUMMARY_COLUMNS = [
    "runs",
    "accuracy",
    "category_accuracy",
    "submitted_rate",
    "first_try_grounding",
    "avg_tool_calls",
    "cap_rate",
    "unrecorded_call_rate",
    "latency_p50_s",
    "latency_p95_s",
    "cost_per_incident_usd",
]


def markdown_tables(all_rows: dict[str, list[dict[str, Any]]]) -> tuple[str, str]:
    """A summary row per model, and a scenario x model grid of correct runs."""
    summary = ["| model | " + " | ".join(SUMMARY_COLUMNS) + " |"]
    summary.append("|" + " --- |" * (len(SUMMARY_COLUMNS) + 1))
    for name, rows in all_rows.items():
        s = summarize(rows)
        summary.append(f"| {name} | " + " | ".join(str(s[c]) for c in SUMMARY_COLUMNS) + " |")

    models = list(all_rows)
    grid = ["| scenario | " + " | ".join(models) + " |", "|" + " --- |" * (len(models) + 1)]
    scenarios = sorted({r["scenario"] for rows in all_rows.values() for r in rows})
    for scenario in scenarios:
        cells = []
        for name in models:
            mine = [r for r in all_rows[name] if r["scenario"] == scenario]
            cells.append(f"{sum(r['correct'] for r in mine)}/{len(mine)}")
        grid.append(f"| {scenario} | " + " | ".join(cells) + " |")
    return "\n".join(summary), "\n".join(grid)


# ---------- running ----------


async def run_suite(provider_name: str, cases: list[Case], repeats: int) -> list[dict[str, Any]]:
    settings = load_settings()
    rows = []
    for case in cases:
        for _ in range(repeats):
            provider = (
                golden_provider(case)
                if provider_name == "fake"
                else get_provider(provider_name, settings)
            )
            result = await diagnose(
                case.recording.namespace,
                ReplayReader(case.recording),
                provider,
                settings,
                source=f"eval:{case.scenario.name}",
            )
            rows.append(grade(case, result))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--provider", action="append", choices=["fake", "anthropic", "openai", "grok"]
    )
    parser.add_argument("--repeats", type=int, default=1, help="runs per scenario per model")
    parser.add_argument("--scenario", action="append", help="number or name; default: all")
    parser.add_argument("--gate", action="store_true", help="exit 1 if below evals/baseline.json")
    parser.add_argument("--save", action="store_true", help="write results to --results-dir")
    parser.add_argument("--results-dir", type=Path, default=EVAL_DIR / "results")
    args = parser.parse_args(argv)

    try:
        cases = load_cases(names=args.scenario)
    except (FileNotFoundError, KeyError) as err:
        print(f"triage-eval: {err.args[0] if err.args else err}", file=sys.stderr)
        return 2

    settings = load_settings()
    all_rows: dict[str, list[dict[str, Any]]] = {}
    for name in args.provider or ["fake"]:
        label = settings.model_for(name) or name
        try:
            all_rows[label] = asyncio.run(run_suite(name, cases, args.repeats))
        except ModelAPIError as err:
            print(f"triage-eval: the model API refused the request {err}", file=sys.stderr)
            return 2
        except ValueError as err:  # no model configured for that provider
            print(f"triage-eval: {err}", file=sys.stderr)
            return 2

    summary, per_scenario = markdown_tables(all_rows)
    print(summary + "\n\n" + per_scenario)

    if args.save:
        out = args.results_dir
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        payload = {
            "repeats": args.repeats,
            "summaries": {name: summarize(rows) for name, rows in all_rows.items()},
            "rows": all_rows,
        }
        (out / f"{stamp}-{'+'.join(all_rows)}.json").write_text(json.dumps(payload, indent=2))
        (out / "latest.md").write_text(summary + "\n\n" + per_scenario + "\n")

    if args.gate:
        baseline = json.loads((EVAL_DIR / "baseline.json").read_text())
        failures = [
            f"{name}: {f}"
            for name, rows in all_rows.items()
            for f in check_gate(summarize(rows), baseline)
        ]
        if failures:
            print("\nEVAL GATE FAILED\n" + "\n".join(failures), file=sys.stderr)
            return 1
        print("\nEval gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
