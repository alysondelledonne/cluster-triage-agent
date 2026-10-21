"""The `submit_diagnosis` tool: how the agent ends a run (DECISIONS.md 023).

It lives on the agent side, not on the MCP server: it doesn't look at the cluster,
it validates the model's answer against the `Diagnosis` schema. The agent loop
offers it next to the MCP tools and stops when a submission parses
(`diagnosis_finish`, DECISIONS.md 024). When one doesn't, `SubmissionError` carries
a message listing each problem by field, which goes back to the model so it can
correct the call.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..models import Diagnosis
from ..providers.base import ToolSpec
from .grounding import check_diagnosis
from .loop import Finish, ToolRecord

SUBMIT_DIAGNOSIS = "submit_diagnosis"

DESCRIPTION = (
    "Submit your diagnosis of the namespace. Call this only once, when you have the "
    "evidence, and it ends the investigation. Every evidence quote must be copied exactly "
    "from an earlier tool result."
)


class SubmissionError(ValueError):
    """A submission that doesn't fit the schema, explained for the model."""


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic puts nested models under $defs and points at them with $ref. Some model
    APIs reject or mishandle refs in tool schemas, so replace each ref with its definition."""
    defs = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                target = resolve(defs[node["$ref"].split("/")[-1]])
                extra = {k: resolve(v) for k, v in node.items() if k != "$ref"}
                return {**target, **extra}
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    resolved: dict[str, Any] = resolve(schema)
    return resolved


def submit_diagnosis_spec() -> ToolSpec:
    return ToolSpec(
        name=SUBMIT_DIAGNOSIS,
        description=DESCRIPTION,
        input_schema=_inline_refs(Diagnosis.model_json_schema()),
    )


def _where(loc: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in loc) or "(whole submission)"


def parse_submission(arguments: dict[str, Any]) -> Diagnosis:
    """The model's tool arguments as a Diagnosis, or a SubmissionError saying what to fix."""
    try:
        return Diagnosis.model_validate(arguments)
    except ValidationError as err:
        problems = []
        for e in err.errors():
            # Pydantic prefixes a custom validator's message with "Value error, ".
            message = str(e["msg"]).removeprefix("Value error, ")
            problems.append(f"- {_where(e['loc'])}: {message}")
        raise _rejected(problems) from err


def _rejected(problems: list[str]) -> SubmissionError:
    return SubmissionError(
        f"{SUBMIT_DIAGNOSIS} was rejected; fix these and call it again:\n" + "\n".join(problems)
    )


def diagnosis_finish(namespace: str) -> Finish:
    """`submit_diagnosis` as the agent loop's finish tool for a run in `namespace`.

    A submission must fit the schema, quote only text from this run's tool output, and
    propose a fix that stays in the namespace (agent/grounding.py, DECISIONS.md 026).
    """

    def parse(arguments: dict[str, Any], records: list[ToolRecord]) -> Diagnosis:
        diagnosis = parse_submission(arguments)
        report = check_diagnosis(diagnosis, records, namespace)
        if not report.ok:
            raise _rejected(report.problems())
        return diagnosis

    return Finish(spec=submit_diagnosis_spec(), parse=parse)
