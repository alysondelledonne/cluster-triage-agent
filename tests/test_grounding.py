"""Grounding checks: evidence quotes must come from this run's tool output, and the
proposed fix must be safe, parseable YAML for this namespace (DECISIONS.md 006, 026).

Offline: pure functions over tool records.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from triage.agent.grounding import (
    check_diagnosis,
    check_fix_yaml,
    check_quotes,
    submission_attempts,
)
from triage.agent.loop import ToolRecord
from triage.models import Diagnosis, Evidence

NS = "triage-06-rbac-denied"

LOGS = (
    "2026-10-20T21:30:01Z loading settings from configmap report-settings\n"
    '{\n  "message": "configmaps \\"report-settings\\" is forbidden: User '
    '\\"system:serviceaccount:triage-06-rbac-denied:reporter\\" cannot get resource",\n'
    '  "code": 403\n}'
)
PODS = (
    "- name: reporter-75dd647696-4js94\n  phase: Running\n  containers:\n"
    "  - name: reporter\n    state: 'running since 2026-10-20T21:29:50+00:00'\n"
    "    note: 'it''s fine'"
)
NOT_FOUND = (
    "RuntimeError: Error executing tool describe: Kubernetes API error (404): "
    'roles.rbac.authorization.k8s.io "reporter" not found'
)


def record(name: str, result: str, is_error: bool = False) -> ToolRecord:
    return ToolRecord(name, {}, result, is_error, 0.0)


RECORDS = [
    record("list_pods", PODS),
    record("get_logs", LOGS),
    record("describe", NOT_FOUND, is_error=True),
    record("can_i", "allowed: false\n"),
]

ROLE_FIX = f"""apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: reporter-read-settings
  namespace: {NS}
rules:
- apiGroups: [""]
  resources: [configmaps]
  resourceNames: [report-settings]
  verbs: [get]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: reporter-read-settings
roleRef: {{apiGroup: rbac.authorization.k8s.io, kind: Role, name: reporter-read-settings}}
subjects: [{{kind: ServiceAccount, name: reporter}}]
"""


def diagnosis(evidence: list[tuple[str, str]], yaml: str | None = ROLE_FIX) -> Diagnosis:
    data: dict[str, Any] = {
        "category": "RBACDenied" if yaml is not None else "Unknown",
        "affected_resource": {"kind": "ServiceAccount", "name": "reporter"},
        "root_cause": "The reporter ServiceAccount can't read its ConfigMap.",
        "evidence": [{"tool": t, "quote": q} for t, q in evidence],
        "proposed_fix": None if yaml is None else {"explanation": "Grant get.", "yaml": yaml},
        "confidence": 0.9,
    }
    return Diagnosis.model_validate(data)


def grounded(tool: str, quote: str) -> bool:
    (check,) = check_quotes([Evidence(tool=tool, quote=quote)], RECORDS)  # type: ignore[arg-type]
    return check.grounded


# ---------- quotes ----------


@pytest.mark.parametrize(
    ("tool", "quote"),
    [
        ("get_logs", "loading settings from configmap report-settings"),
        ("get_logs", '"code": 403'),
        ("list_pods", "phase: Running"),
        ("can_i", "allowed: false"),
    ],
)
def test_exact_quotes_are_grounded(tool: str, quote: str) -> None:
    assert grounded(tool, quote)


def test_whitespace_and_line_breaks_are_ignored() -> None:
    assert grounded("list_pods", "containers:   - name: reporter")
    assert grounded("get_logs", "  is forbidden:\nUser ")


def test_json_escaped_quotes_match_plain_quotes() -> None:
    # Logs often carry JSON with \" inside; models quote it with plain quotes.
    assert grounded("get_logs", 'configmaps "report-settings" is forbidden')
    assert grounded("get_logs", 'configmaps \\"report-settings\\" is forbidden')


def test_yaml_doubled_single_quotes_match() -> None:
    assert grounded("list_pods", "it's fine")


def test_error_results_count_as_evidence() -> None:
    assert grounded("describe", 'roles.rbac.authorization.k8s.io "reporter" not found')


def test_a_quote_from_another_tool_is_not_grounded() -> None:
    assert not grounded("list_pods", "is forbidden")
    assert not grounded("get_events", "phase: Running")


def test_invented_and_paraphrased_quotes_are_not_grounded() -> None:
    assert not grounded("get_logs", "permission denied reading configmap")
    assert not grounded("get_logs", "Configmaps report-settings is forbidden")


def test_matching_is_case_sensitive() -> None:
    assert not grounded("can_i", "Allowed: False")


# ---------- the fix ----------


def test_a_role_and_binding_in_the_namespace_pass() -> None:
    assert check_fix_yaml(ROLE_FIX, NS) == []


def test_a_patch_with_identity_and_no_namespace_passes() -> None:
    patch = "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: api}\nspec: {replicas: 1}\n"
    assert check_fix_yaml(patch, NS) == []


@pytest.mark.parametrize(
    ("yaml", "problem"),
    [
        ("kind: [unclosed", "doesn't parse as YAML"),
        ("", "no Kubernetes object"),
        ("just a sentence", "not a Kubernetes object"),
        ("kind: Deployment\nmetadata: {name: api}\n", "apiVersion"),
        ("apiVersion: v1\nmetadata: {name: api}\n", "kind"),
        ("apiVersion: v1\nkind: ConfigMap\ndata: {a: b}\n", "metadata.name"),
        ("apiVersion: v1\nkind: Secret\nmetadata: {name: creds}\n", "Secret"),
        (
            "apiVersion: v1\nkind: ConfigMap\nmetadata: {name: x, namespace: default}\n",
            "namespace default",
        ),
        (
            "apiVersion: rbac.authorization.k8s.io/v1\nkind: ClusterRole\nmetadata: {name: x}\n",
            "cluster-wide",
        ),
    ],
)
def test_fix_problems_are_named(yaml: str, problem: str) -> None:
    problems = check_fix_yaml(yaml, NS)
    assert problems and problem in " ".join(problems), problems


def test_problems_say_which_document() -> None:
    two = ROLE_FIX + "---\napiVersion: v1\nkind: Secret\nmetadata: {name: creds}\n"
    (problem,) = check_fix_yaml(two, NS)
    assert problem.startswith("document 3:")


# ---------- the whole diagnosis ----------


def test_a_grounded_diagnosis_is_ok() -> None:
    report = check_diagnosis(
        diagnosis([("get_logs", "is forbidden"), ("can_i", "allowed: false")]), RECORDS, NS
    )
    assert report.ok
    assert report.grounded_share == 1.0
    assert report.problems() == []


def test_problems_are_listed_by_field_for_the_model() -> None:
    bad_fix = "apiVersion: v1\nkind: Secret\nmetadata: {name: creds}\n"
    report = check_diagnosis(
        diagnosis([("get_logs", "is forbidden"), ("get_logs", "access denied")], bad_fix),
        RECORDS,
        NS,
    )
    assert not report.ok
    assert report.grounded_share == 0.5
    problems = report.problems()
    assert problems[0].startswith("- evidence.1.quote: not found in any get_logs output")
    # The rejection repeats prompt version 2's quoting rule (DECISIONS.md 043).
    assert "one line, or a contiguous part of one, exactly as shown" in problems[0]
    assert "don't join lines or add notes" in problems[0]
    assert problems[1].startswith("- proposed_fix.yaml: ")
    assert "Secret" in problems[1]


def test_unknown_without_a_fix_only_checks_quotes() -> None:
    report = check_diagnosis(diagnosis([("can_i", "allowed: false")], yaml=None), RECORDS, NS)
    assert report.ok


# ---------- first-try grounding from a run's trace ----------


def test_submission_attempts_rebuild_each_try_from_the_trace() -> None:
    first = diagnosis([("get_logs", "access denied")]).model_dump(mode="json")
    second = diagnosis([("get_logs", "is forbidden")]).model_dump(mode="json")
    trace = [
        *RECORDS,
        ToolRecord("submit_diagnosis", first, "rejected", True, 0.0),
        ToolRecord("submit_diagnosis", second, "accepted", False, 0.0),
    ]
    attempts = submission_attempts(trace, NS)
    assert [a.grounded_share for a in attempts] == [0.0, 1.0]


def test_attempts_only_see_tool_output_from_before_them() -> None:
    early = diagnosis([("can_i", "allowed: false")]).model_dump(mode="json")
    trace = [
        ToolRecord("submit_diagnosis", early, "rejected", True, 0.0),
        record("can_i", "allowed: false"),
    ]
    (attempt,) = submission_attempts(trace, NS)
    assert attempt.grounded_share == 0.0


def test_attempts_include_a_submission_with_a_field_sent_as_a_json_string() -> None:
    # Run 3, b5a9e8e8cb69 (DECISIONS.md 042): Haiku sent proposed_fix as a JSON string.
    # submit_diagnosis decodes that and accepted it, so the re-check must count it too.
    sub = diagnosis([("get_logs", "is forbidden")]).model_dump(mode="json")
    sub["proposed_fix"] = json.dumps(sub["proposed_fix"])
    trace = [*RECORDS, ToolRecord("submit_diagnosis", sub, "accepted", False, 0.0)]
    (attempt,) = submission_attempts(trace, NS)
    assert attempt.grounded_share == 1.0


def test_attempts_skip_submissions_that_failed_the_schema() -> None:
    trace = [ToolRecord("submit_diagnosis", {"category": "Nope"}, "rejected", True, 0.0)]
    assert submission_attempts(trace, NS) == []


# ---------- escaped line breaks (DECISIONS.md 038) ----------

DESCRIBE_SCRIPT = (
    "spec:\n  containers:\n  - args:\n"
    '    - "echo \\"starting api\\"\\nif [ -z \\"$LISTEN_PORT\\" ]; then\\n  echo \\"fatal: '
    'required setting LISTEN_PORT is missing\\" >&2\\n  exit 1\\nfi\\n"'
)


def test_a_quote_with_real_line_breaks_matches_yaml_escapes() -> None:
    # Run 369e87b3bb3e: the script quoted as it reads, against describe's escaped string.
    records = [record("describe", DESCRIBE_SCRIPT)]
    quote = (
        'if [ -z "$LISTEN_PORT" ]; then\n'
        '  echo "fatal: required setting LISTEN_PORT is missing" >&2\n'
        "  exit 1\nfi"
    )
    (check,) = check_quotes([Evidence(tool="describe", quote=quote)], records)
    assert check.grounded
    tabbed = [record("get_logs", "level=error\\tmsg=boom")]
    (check,) = check_quotes([Evidence(tool="get_logs", quote="level=error\tmsg=boom")], tabbed)
    assert check.grounded


def test_unescaping_doesnt_let_joined_lines_through() -> None:
    # Run f740db3c3d7d: real lines, but not next to each other in the output.
    joined = "ready: 0/1\n  failing_conditions:\n  - 'ContainersReady: ContainersNotReady'"
    output = "ready: 0/1\nrestarts: 0\nfailing_conditions:\n- 'ContainersReady: ContainersNotReady'"
    (check,) = check_quotes(
        [Evidence(tool="list_pods", quote=joined)], [record("list_pods", output)]
    )
    assert not check.grounded
