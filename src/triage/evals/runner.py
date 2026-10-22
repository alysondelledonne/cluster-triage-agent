"""Eval harness: run every case, grade it, report metrics, and gate on a baseline.

    uv run triage-eval --provider fake --gate          # offline; what CI runs
    uv run triage-eval --provider anthropic --repeats 3
    uv run triage-eval --provider anthropic --provider grok   # compare models

Each case in evals/cases.jsonl gives an input, the expected answer, and the tool
(and arguments) a good agent would use. Results are written to evals/results/
as JSON plus a Markdown table you can paste into the README.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.client import Client

from ..agent.loop import AgentResult, run_agent
from ..agent.mcp_tools import tools_from_mcp
from ..config import load_settings
from ..mcp_server.server import server
from ..providers import Provider, get_provider
from ..providers.base import Message, ModelTurn, ToolCall
from ..providers.fake import PolicyProvider

# The template's example prompt, for the calculator cases. It goes with them in
# Milestone 3, when the evals move to the scenarios (DECISIONS.md 025).
SYSTEM_PROMPT = (
    "You are a careful assistant. Use the available tools for any arithmetic or "
    "counting instead of working it out yourself. Answer in one short sentence."
)

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "evals"


@dataclass
class Case:
    id: str
    input: str
    expected_answer: str
    expected_tool: str
    expected_args: dict[str, Any]


def load_cases(path: Path = EVAL_DIR / "cases.jsonl") -> list[Case]:
    lines = path.read_text().splitlines()
    return [Case(**json.loads(line)) for line in lines if line.strip()]


def golden_provider(case: Case) -> Provider:
    """A fake model that does exactly what the case expects: call the expected
    tool, then answer with whatever the tool returned. CI uses it to test the
    pipeline end to end for free."""

    def policy(messages: list[Message]) -> ModelTurn:
        last = messages[-1]
        if last.role == "user":
            call = ToolCall(id="call_1", name=case.expected_tool, arguments=case.expected_args)
            return ModelTurn("", [call], 50, 10, 0.0, "fake", "tool_use")
        return ModelTurn(f"The answer is {last.content}.", [], 80, 12, 0.0, "fake", "end_turn")

    return PolicyProvider(policy)


def _numbers(text: str) -> set[str]:
    found = re.findall(r"-?\d[\d,]*(?:\.\d+)?", text)
    out = set()
    for n in found:
        n = n.replace(",", "")
        out.add(n[:-2] if n.endswith(".0") else n)
    return out


def grade(case: Case, result: AgentResult) -> dict[str, Any]:
    expected = case.expected_answer.strip()
    answer_ok = expected in _numbers(result.final_text) or (
        expected.lower() in result.final_text.lower()
    )
    tool_ok = any(c.name == case.expected_tool and not c.is_error for c in result.tool_calls)
    return {
        "case": case.id,
        "answer_ok": answer_ok,
        "tool_ok": tool_ok,
        "answered": result.stopped == "answered",
        "steps": result.steps,
        "latency_s": round(result.total_latency_s, 3),
        "cost_usd": result.cost_usd,
        "final_text": result.final_text,
        "tools": [c.name for c in result.tool_calls],
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
    return {
        "runs": n,
        "answer_accuracy": round(sum(r["answer_ok"] for r in rows) / n, 3),
        "tool_accuracy": round(sum(r["tool_ok"] for r in rows) / n, 3),
        "answered_rate": round(sum(r["answered"] for r in rows) / n, 3),
        "avg_steps": round(statistics.mean(r["steps"] for r in rows), 2),
        "latency_p50_s": round(_pct(lat, 0.5), 3),
        "latency_p95_s": round(_pct(lat, 0.95), 3),
        "cost_per_run_usd": None if any(c is None for c in costs) else round(sum(costs) / n, 6),
    }


async def run_suite(provider_name: str, cases: list[Case], repeats: int) -> list[dict[str, Any]]:
    settings = load_settings()
    rows: list[dict[str, Any]] = []
    async with Client(server) as client:
        tools = await tools_from_mcp(client)
        for case in cases:
            for _ in range(repeats):
                provider = (
                    golden_provider(case)
                    if provider_name == "fake"
                    else get_provider(provider_name, settings)
                )
                result = await run_agent(
                    provider, SYSTEM_PROMPT, case.input, tools, max_steps=settings.max_steps
                )
                rows.append(grade(case, result))
    return rows


def check_gate(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Return a list of failures; empty means the gate passes."""
    return [
        f"{k}: {summary.get(k)} < baseline {v}"
        for k, v in baseline.items()
        if not k.startswith("_") and (summary.get(k) is None or summary[k] < v)
    ]


def markdown_table(summaries: dict[str, dict[str, Any]]) -> str:
    cols = [
        "answer_accuracy",
        "tool_accuracy",
        "answered_rate",
        "avg_steps",
        "latency_p50_s",
        "latency_p95_s",
        "cost_per_run_usd",
    ]
    lines = ["| model | " + " | ".join(cols) + " |", "|" + " --- |" * (len(cols) + 1)]
    for name, s in summaries.items():
        lines.append(f"| {name} | " + " | ".join(str(s.get(c)) for c in cols) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", action="append", choices=["fake", "anthropic", "openai", "grok"]
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--gate", action="store_true", help="exit 1 if below evals/baseline.json")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)

    cases = load_cases()
    providers = args.provider or ["fake"]
    summaries: dict[str, dict[str, Any]] = {}
    all_rows: dict[str, list[dict[str, Any]]] = {}
    for name in providers:
        rows = asyncio.run(run_suite(name, cases, args.repeats))
        all_rows[name] = rows
        summaries[name] = summarize(rows)

    table = markdown_table(summaries)
    print(table)

    # The offline gate checks the pipeline; its fake-model numbers aren't results to keep.
    if not args.no_save and not args.gate:
        out = EVAL_DIR / "results"
        out.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        payload = {"summaries": summaries, "rows": all_rows, "repeats": args.repeats}
        (out / f"{stamp}.json").write_text(json.dumps(payload, indent=2))
        (out / "latest.md").write_text(table + "\n")

    if args.gate:
        baseline = json.loads((EVAL_DIR / "baseline.json").read_text())
        failures = [f"{n}: {f}" for n, s in summaries.items() for f in check_gate(s, baseline)]
        if failures:
            print("\nEVAL GATE FAILED\n" + "\n".join(failures), file=sys.stderr)
            return 1
        print("\nEval gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
