"""The Diagnosis schema and the agent-side submit_diagnosis tool.

Offline: pure validation, no model and no cluster.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, get_args

import pytest
from mcp.client import Client

from triage.agent.submit import (
    SUBMIT_DIAGNOSIS,
    SubmissionError,
    parse_submission,
    submit_diagnosis_spec,
)
from triage.mcp_server.kube_server import build_server
from triage.models import Category, Diagnosis, EvidenceTool, ResourceRef


def valid() -> dict[str, Any]:
    """A diagnosis of scenario 6, as the model would send it."""
    return {
        "category": "RBACDenied",
        "affected_resource": {"kind": "ServiceAccount", "name": "reporter"},
        "root_cause": "The reporter ServiceAccount has no Role allowing it to read the "
        "report-settings ConfigMap, so every API call it makes is denied.",
        "evidence": [
            {"tool": "get_logs", "quote": 'configmaps \\"report-settings\\" is forbidden'},
            {"tool": "can_i", "quote": "allowed: false"},
        ],
        "proposed_fix": {
            "explanation": "Grant the ServiceAccount get on that one ConfigMap.",
            "yaml": "apiVersion: rbac.authorization.k8s.io/v1\nkind: Role\n...",
        },
        "confidence": 0.9,
    }


# ---------- the model ----------


def test_a_valid_diagnosis_parses() -> None:
    d = parse_submission(valid())
    assert d.category is Category.RBAC_DENIED
    assert d.affected_resource == ResourceRef(kind="ServiceAccount", name="reporter")
    assert [e.tool for e in d.evidence] == ["get_logs", "can_i"]
    assert d.proposed_fix is not None
    assert d.confidence == 0.9


@pytest.mark.parametrize(
    ("change", "where"),
    [
        ({"category": "Broken"}, "category"),
        ({"confidence": 1.5}, "confidence"),
        ({"confidence": -0.1}, "confidence"),
        ({"evidence": []}, "evidence"),
        ({"evidence": [{"tool": "kubectl", "quote": "something failed"}]}, "evidence.0.tool"),
        ({"evidence": [{"tool": "get_logs", "quote": ""}]}, "evidence.0.quote"),
        ({"root_cause": ""}, "root_cause"),
        ({"affected_resource": {"kind": "Deployment"}}, "affected_resource.name"),
        ({"proposed_fix": None}, "proposed_fix"),
        ({"severity": "high"}, "severity"),
    ],
)
def test_bad_submissions_are_rejected_with_where_and_why(
    change: dict[str, Any], where: str
) -> None:
    with pytest.raises(SubmissionError) as err:
        parse_submission({**valid(), **change})
    assert f"- {where}:" in str(err.value)
    assert str(err.value).startswith(f"{SUBMIT_DIAGNOSIS} was rejected")


def test_missing_fields_are_named() -> None:
    args = valid()
    del args["evidence"]
    del args["confidence"]
    with pytest.raises(SubmissionError) as err:
        parse_submission(args)
    assert "- evidence: Field required" in str(err.value)
    assert "- confidence: Field required" in str(err.value)


def test_unknown_may_come_without_a_fix() -> None:
    d = parse_submission({**valid(), "category": "Unknown", "proposed_fix": None})
    assert d.category is Category.UNKNOWN
    assert d.proposed_fix is None


def test_evidence_and_fix_have_sensible_limits() -> None:
    too_many = [{"tool": "get_logs", "quote": f"line {i}"} for i in range(9)]
    with pytest.raises(SubmissionError, match="evidence"):
        parse_submission({**valid(), "evidence": too_many})
    with pytest.raises(SubmissionError, match=r"proposed_fix\.yaml"):
        parse_submission({**valid(), "proposed_fix": {"explanation": "x", "yaml": "a: b\n" * 2000}})


def test_diagnosis_round_trips_through_json() -> None:
    d = parse_submission(valid())
    assert Diagnosis.model_validate_json(d.model_dump_json()) == d


# ---------- the tool definition ----------


def test_spec_is_named_and_described() -> None:
    spec = submit_diagnosis_spec()
    assert spec.name == SUBMIT_DIAGNOSIS
    assert "only once" in spec.description


def test_schema_is_self_contained_for_every_provider() -> None:
    schema = submit_diagnosis_spec().input_schema
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text, "inline everything; some APIs reject refs"
    assert schema["type"] == "object"
    assert set(schema["required"]) == {
        "category",
        "affected_resource",
        "root_cause",
        "evidence",
        "proposed_fix",
        "confidence",
    }
    assert schema["additionalProperties"] is False
    category = schema["properties"]["category"]
    assert category["enum"] == [c.value for c in Category]
    tool = schema["properties"]["evidence"]["items"]["properties"]["tool"]
    assert tool["enum"] == list(get_args(EvidenceTool))


def test_every_field_has_a_description_for_the_model() -> None:
    def walk(node: dict[str, Any], path: str) -> None:
        for name, prop in node.get("properties", {}).items():
            assert prop.get("description"), f"{path}{name} has no description"
            if prop.get("type") == "object":
                walk(prop, f"{path}{name}.")
            if prop.get("type") == "array":
                walk(prop["items"], f"{path}{name}[].")

    walk(submit_diagnosis_spec().input_schema, "")


def test_evidence_tools_are_exactly_the_servers_tools() -> None:
    async def names() -> set[str]:
        server = build_server("ns", reader=None)  # type: ignore[arg-type]
        async with Client(server) as client:
            return {t.name for t in (await client.list_tools()).tools}

    assert set(get_args(EvidenceTool)) == asyncio.run(names())


# ---------- what real models send (first real run, DECISIONS.md 029) ----------


def test_an_object_sent_as_a_json_string_is_accepted() -> None:
    # Claude Haiku sent proposed_fix as a JSON-encoded string on its first real run.
    args = valid()
    args["proposed_fix"] = json.dumps(args["proposed_fix"])
    args["affected_resource"] = json.dumps(args["affected_resource"])
    args["evidence"] = json.dumps(args["evidence"])
    d = parse_submission(args)
    assert d.proposed_fix is not None
    assert d.proposed_fix.yaml.startswith("apiVersion")
    assert d.affected_resource.name == "reporter"
    assert len(d.evidence) == 2


def test_a_json_string_with_extra_text_keeps_the_object_and_reports_the_rest() -> None:
    # The first real attempt also folded confidence into the same string.
    args = valid()
    del args["confidence"]
    args["proposed_fix"] = json.dumps(valid()["proposed_fix"]) + ', "confidence": 0.9}'
    with pytest.raises(SubmissionError) as err:
        parse_submission(args)
    assert "- confidence: Field required" in str(err.value)
    assert "proposed_fix" not in str(err.value)


def test_a_plain_string_where_an_object_belongs_gets_a_clear_message() -> None:
    with pytest.raises(SubmissionError) as err:
        parse_submission({**valid(), "proposed_fix": "add a Role"})
    assert "- proposed_fix: send an object with explanation and yaml, not a string" in str(
        err.value
    )


def test_nullable_objects_are_plain_objects_in_the_schema() -> None:
    # anyOf [object, null] is what led the model to send a string; use a type list.
    schema = submit_diagnosis_spec().input_schema
    assert "anyOf" not in json.dumps(schema)
    fix = schema["properties"]["proposed_fix"]
    assert fix["type"] == ["object", "null"]
    assert set(fix["properties"]) == {"explanation", "yaml"}
    assert fix["description"]
