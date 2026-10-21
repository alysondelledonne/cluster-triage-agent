"""A run's diagnosis as plain text for a person at a terminal.

The evidence quotes and the fix come from the model, and the quotes come from
cluster output, so control characters are stripped before printing: a log line
can't change the terminal (colours, cursor moves, a cleared screen).
"""

from __future__ import annotations

import re

from ..models import Diagnosis
from .loop import AgentResult

# Everything below a space except tab and newline, plus DEL and the C1 range.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def safe(text: str) -> str:
    return _CONTROL.sub("", text)


def _indent(text: str, by: str = "    ") -> str:
    return "\n".join(by + line for line in text.rstrip().splitlines())


def _run_line(result: AgentResult, finish_name: str) -> str:
    looked = sum(1 for t in result.tool_calls if t.name != finish_name)
    cost = "unknown" if result.cost_usd is None else f"${result.cost_usd:.4f}"
    return (
        f"Run {result.run_id}: {looked} tool calls, {result.steps} model turns, "
        f"stopped: {result.stopped}, tokens {result.input_tokens} in / "
        f"{result.output_tokens} out, {result.total_latency_s:.1f}s, cost {cost} "
        f"({result.provider}/{result.model})"
    )


def render_report(
    result: AgentResult,
    namespace: str,
    *,
    max_tool_calls: int,
    finish_name: str = "submit_diagnosis",
) -> str:
    lines = [f"Namespace: {namespace}"]
    if result.info.get("source", "cluster") != "cluster":
        lines.append(f"Source: {result.info['source']}")
    lines.append("")

    d = result.submission
    if not isinstance(d, Diagnosis):
        lines.append("No diagnosis: the agent did not submit one.")
        if result.final_text:
            lines.append(f"Last model text: {safe(result.final_text)}")
        lines += ["", _run_line(result, finish_name)]
        return "\n".join(lines)

    lines.append(f"{d.category.value}: {d.affected_resource} (confidence {d.confidence:.2f})")
    if result.stopped == "submitted_at_cap":
        lines.append(
            f"Hit the {max_tool_calls}-call limit before submitting; "
            "check the evidence before trusting this."
        )
    lines += ["", f"Root cause: {safe(d.root_cause)}", "", "Evidence:"]
    lines += [f"  [{e.tool}] {safe(e.quote)}" for e in d.evidence]
    lines.append("")
    if d.proposed_fix is None:
        lines.append("Proposed fix: none")
    else:
        lines.append(f"Proposed fix: {safe(d.proposed_fix.explanation)}")
        lines.append(_indent(safe(d.proposed_fix.yaml)))
    lines += ["", _run_line(result, finish_name)]
    return "\n".join(lines)
