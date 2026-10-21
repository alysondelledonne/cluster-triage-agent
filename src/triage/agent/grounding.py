"""Check a diagnosis against what actually happened in the run (DECISIONS.md 006, 026).

- Every evidence quote must appear in the output of an earlier call to the tool
  it names. A quote that can't be found was paraphrased or made up.
- The proposed fix must be YAML a person could apply in this namespace: each
  object names its apiVersion, kind and metadata.name, and nothing is a Secret,
  cluster-wide, or in another namespace.

`submit_diagnosis` rejects a submission that fails either check and sends the
problems back to the model (agent/submit.py), so a report only ever shows
checked quotes. `submission_attempts` rebuilds every attempt from a run's trace,
so the evals can still measure how often the first try was ungrounded.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import yaml
from pydantic import ValidationError

from ..models import Diagnosis, Evidence
from .loop import ToolRecord

# Objects a fix must never touch: they reach beyond the run's namespace.
CLUSTER_SCOPED = {
    "ClusterRole",
    "ClusterRoleBinding",
    "Namespace",
    "Node",
    "PersistentVolume",
    "StorageClass",
    "PriorityClass",
    "CustomResourceDefinition",
    "MutatingWebhookConfiguration",
    "ValidatingWebhookConfiguration",
}


def _normalize(text: str) -> str:
    """Make a quote and tool output comparable without loosening what counts as a match.

    - Whitespace and line breaks collapse to single spaces: quotes often span a
      wrapped line, and YAML indentation shouldn't matter.
    - `\\"` becomes `"`: logs often carry JSON with escaped quotes, and models
      quote them with plain ones.
    - `''` becomes `'`: YAML doubles single quotes inside single-quoted strings.
    Case and every other character must match exactly.
    """
    text = text.replace('\\"', '"').replace("''", "'")
    return " ".join(text.split())


@dataclass(frozen=True)
class QuoteCheck:
    tool: str
    quote: str
    grounded: bool


def check_quotes(evidence: Sequence[Evidence], records: Sequence[ToolRecord]) -> list[QuoteCheck]:
    """Is each quote in the output of a call to its named tool? Error results count too."""
    outputs: dict[str, list[str]] = {}
    for rec in records:
        outputs.setdefault(rec.name, []).append(_normalize(rec.result))
    checks = []
    for e in evidence:
        quote = _normalize(e.quote)
        found = bool(quote) and any(quote in out for out in outputs.get(e.tool, []))
        checks.append(QuoteCheck(tool=e.tool, quote=e.quote, grounded=found))
    return checks


def check_fix_yaml(text: str, namespace: str) -> list[str]:
    """Problems with a proposed fix, one per issue, naming the YAML document."""
    try:
        docs: list[Any] = [d for d in yaml.safe_load_all(text) if d is not None]
    except yaml.YAMLError as err:
        return [f"doesn't parse as YAML: {str(err).splitlines()[0]}"]
    if not docs:
        return ["contains no Kubernetes object"]

    problems = []
    for i, doc in enumerate(docs, start=1):
        where = f"document {i}"
        if not isinstance(doc, dict):
            problems.append(f"{where}: is not a Kubernetes object (apiVersion, kind, metadata)")
            continue
        raw_meta = doc.get("metadata")
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        missing = [
            field
            for field, value in (
                ("apiVersion", doc.get("apiVersion")),
                ("kind", doc.get("kind")),
                ("metadata.name", meta.get("name")),
            )
            if not value
        ]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
        kind = str(doc.get("kind") or "")
        if kind.lower() == "secret":
            problems.append(f"{where}: is a Secret; a fix must never create or change Secrets")
        elif kind in CLUSTER_SCOPED:
            problems.append(
                f"{where}: {kind} is cluster-wide; keep the fix inside namespace {namespace} "
                "(e.g. a Role instead of a ClusterRole)"
            )
        ns = meta.get("namespace")
        if ns and ns != namespace:
            problems.append(f"{where}: namespace {ns} is not this run's namespace {namespace}")
    return problems


@dataclass(frozen=True)
class GroundingReport:
    quotes: list[QuoteCheck]
    fix_problems: list[str]

    @property
    def ok(self) -> bool:
        return all(q.grounded for q in self.quotes) and not self.fix_problems

    @property
    def grounded_share(self) -> float:
        if not self.quotes:
            return 0.0
        return sum(q.grounded for q in self.quotes) / len(self.quotes)

    def problems(self) -> list[str]:
        """One line per problem, by field, in the same form as schema errors."""
        out = [
            f"- evidence.{i}.quote: not found in any {q.tool} output in this run; "
            "copy it exactly from a tool result"
            for i, q in enumerate(self.quotes)
            if not q.grounded
        ]
        out += [f"- proposed_fix.yaml: {p}" for p in self.fix_problems]
        return out


def check_diagnosis(
    diagnosis: Diagnosis, records: Sequence[ToolRecord], namespace: str
) -> GroundingReport:
    fix = diagnosis.proposed_fix
    return GroundingReport(
        quotes=check_quotes(diagnosis.evidence, records),
        fix_problems=check_fix_yaml(fix.yaml, namespace) if fix else [],
    )


def submission_attempts(
    trace: Sequence[ToolRecord], namespace: str, tool_name: str = "submit_diagnosis"
) -> list[GroundingReport]:
    """Re-check every schema-valid submission in a run against the calls made before it."""
    reports = []
    for i, rec in enumerate(trace):
        if rec.name != tool_name:
            continue
        try:
            diagnosis = Diagnosis.model_validate(rec.arguments)
        except ValidationError:
            continue  # rejected by the schema before grounding was checked
        reports.append(check_diagnosis(diagnosis, trace[:i], namespace))
    return reports
