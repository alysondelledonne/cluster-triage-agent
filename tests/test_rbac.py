"""Guards the agent's RBAC in deploy/rbac/: read-only, no Secrets, nothing unreviewed.

CLAUDE.md hard rule: don't weaken or skip this test. If the MCP server needs a new
permission, add it to ALLOWED_READS below in the same change, and say why in the PR.

The check is an allowlist of (apiGroup, resource) pairs, not just a ban on write
verbs: some read verbs are dangerous on subresources (`get pods/exec` can open a
shell over WebSockets, `get nodes/proxy` reaches the kubelet API), so anything
not listed here fails until someone reviews it. See DECISIONS.md 017.

Offline: the manifests are parsed as YAML, nothing touches a cluster.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
RBAC_DIR = REPO / "deploy" / "rbac"

SA_NAMESPACE = "triage-system"
SA_NAME = "triage-agent"
ROLE_NAME = "triage-agent-read"

READ_VERBS = {"get", "list", "watch"}

# Every (apiGroup, resource) the agent may read. "" is the core API group.
ALLOWED_READS = {
    ("", "pods"),
    ("", "pods/log"),
    ("", "events"),
    ("", "services"),
    ("", "configmaps"),
    ("", "serviceaccounts"),
    ("events.k8s.io", "events"),
    ("apps", "deployments"),
    ("apps", "replicasets"),
    ("discovery.k8s.io", "endpointslices"),
    ("rbac.authorization.k8s.io", "roles"),
    ("rbac.authorization.k8s.io", "rolebindings"),
}

# The one non-read permission: asking the API server "may X do Y?" for the can_i
# tool. A SubjectAccessReview is a question; nothing is stored or changed.
ALLOWED_CREATES = {("authorization.k8s.io", "subjectaccessreviews")}

# Verbs that let a holder gain permissions they don't have, whatever the resource.
ESCALATION_VERBS = {"escalate", "bind", "impersonate"}

# The only objects deploy/rbac/ may contain.
EXPECTED_OBJECTS = {
    ("Namespace", SA_NAMESPACE),
    ("ServiceAccount", SA_NAME),
    ("ClusterRole", ROLE_NAME),
    ("ClusterRoleBinding", ROLE_NAME),
}

Doc = dict[str, Any]


def load_docs() -> list[Doc]:
    docs: list[Doc] = []
    for path in sorted(RBAC_DIR.glob("*.yaml")):
        docs.extend(d for d in yaml.safe_load_all(path.read_text()) if d)
    return docs


def rule_problems(rule: Doc) -> list[str]:
    """Everything wrong with one RBAC rule, as readable messages."""
    groups = rule.get("apiGroups", [])
    resources = rule.get("resources", [])
    verbs = rule.get("verbs", [])
    problems = []
    if rule.get("nonResourceURLs"):
        problems.append(f"nonResourceURLs not allowed: {rule['nonResourceURLs']}")
    for field, values in (("apiGroups", groups), ("resources", resources), ("verbs", verbs)):
        if any("*" in v for v in values):
            problems.append(f"wildcard in {field}: {values}")
    for group in groups:
        for resource in resources:
            if resource == "secrets" or resource.startswith("secrets/"):
                problems.append(f"Secrets access: {resource}")
                continue
            for verb in verbs:
                if verb in ESCALATION_VERBS:
                    problems.append(f"escalation verb {verb!r} on {resource}")
                elif not allowed(group, resource, verb):
                    problems.append(f"not allowed: {verb} {group or 'core'}/{resource}")
    return problems


def allowed(group: str, resource: str, verb: str) -> bool:
    pair = (group, resource)
    if verb in READ_VERBS:
        return pair in ALLOWED_READS
    return verb == "create" and pair in ALLOWED_CREATES


def problems_in(docs: list[Doc]) -> list[str]:
    """Everything wrong with the RBAC manifests. Empty means they pass."""
    problems = []
    found = {(d["kind"], d["metadata"]["name"]) for d in docs}
    for kind, name in sorted(found - EXPECTED_OBJECTS):
        problems.append(f"unexpected object: {kind}/{name}")
    for kind, name in sorted(EXPECTED_OBJECTS - found):
        problems.append(f"missing object: {kind}/{name}")

    for doc in docs:
        kind = doc["kind"]
        if kind in {"ClusterRole", "Role"}:
            if "aggregationRule" in doc:
                problems.append(f"{kind} uses aggregationRule (pulls in other roles' rules)")
            for rule in doc.get("rules", []):
                problems.extend(rule_problems(rule))
        if kind == "ServiceAccount" and doc["metadata"].get("namespace") != SA_NAMESPACE:
            problems.append(f"ServiceAccount must be in namespace {SA_NAMESPACE}")
        if kind == "ClusterRoleBinding":
            role_ref = doc.get("roleRef", {})
            if (role_ref.get("kind"), role_ref.get("name")) != ("ClusterRole", ROLE_NAME):
                problems.append(f"binding points at the wrong role: {role_ref}")
            subject = {"kind": "ServiceAccount", "name": SA_NAME, "namespace": SA_NAMESPACE}
            if doc.get("subjects") != [subject]:
                problems.append(f"binding must name only {SA_NAMESPACE}/{SA_NAME}")
    return problems


def granted(docs: list[Doc]) -> set[tuple[str, str, str]]:
    """Every (apiGroup, resource, verb) the ClusterRole grants."""
    role = next(d for d in docs if d["kind"] == "ClusterRole")
    return {
        (g, r, v)
        for rule in role["rules"]
        for g in rule["apiGroups"]
        for r in rule["resources"]
        for v in rule["verbs"]
    }


# ---------- the real manifests ----------


def test_rbac_manifests_pass_every_check() -> None:
    assert problems_in(load_docs()) == []


def test_role_grants_exactly_what_the_tools_need() -> None:
    # Catches the other direction too: a read the tools need but the role dropped.
    expected = {(g, r, v) for g, r in ALLOWED_READS for v in READ_VERBS}
    expected |= {(g, r, "create") for g, r in ALLOWED_CREATES}
    assert granted(load_docs()) == expected


# ---------- prove each check fails when it should ----------


def _role(docs: list[Doc]) -> Doc:
    return next(d for d in docs if d["kind"] == "ClusterRole")


def _binding(docs: list[Doc]) -> Doc:
    return next(d for d in docs if d["kind"] == "ClusterRoleBinding")


def _add_rule(
    groups: list[str], resources: list[str], verbs: list[str]
) -> Callable[[list[Doc]], None]:
    def mutate(docs: list[Doc]) -> None:
        _role(docs)["rules"].append({"apiGroups": groups, "resources": resources, "verbs": verbs})

    return mutate


def _set(path: str, value: Any) -> Callable[[list[Doc]], None]:
    """Set a field on the binding, e.g. 'roleRef.name'."""

    def mutate(docs: list[Doc]) -> None:
        target = _binding(docs)
        *parents, last = path.split(".")
        for key in parents:
            target = target[key]
        target[last] = value

    return mutate


def _extra_doc(doc: Doc) -> Callable[[list[Doc]], None]:
    return lambda docs: docs.append(doc)


BAD_CHANGES: dict[str, Callable[[list[Doc]], None]] = {
    "write verb": _add_rule([""], ["pods"], ["delete"]),
    "patch a deployment": _add_rule(["apps"], ["deployments"], ["patch"]),
    "read secrets": _add_rule([""], ["secrets"], ["get"]),
    "wildcard resource": _add_rule([""], ["*"], ["get"]),
    "wildcard verb": _add_rule([""], ["pods"], ["*"]),
    "exec into pods": _add_rule([""], ["pods/exec"], ["get"]),
    "kubelet proxy": _add_rule([""], ["nodes/proxy"], ["get"]),
    "unreviewed read": _add_rule([""], ["nodes"], ["list"]),
    "create a token": _add_rule([""], ["serviceaccounts/token"], ["create"]),
    "impersonate": _add_rule([""], ["users"], ["impersonate"]),
    "escalate roles": _add_rule(["rbac.authorization.k8s.io"], ["roles"], ["escalate"]),
    "non-resource URL": lambda docs: _role(docs)["rules"].append(
        {"nonResourceURLs": ["/metrics"], "verbs": ["get"]}
    ),
    "aggregation rule": lambda docs: _role(docs).__setitem__(
        "aggregationRule", {"clusterRoleSelectors": [{"matchLabels": {"x": "y"}}]}
    ),
    "binding to another role": _set("roleRef.name", "cluster-admin"),
    "binding to another subject": _set(
        "subjects", [{"kind": "Group", "name": "system:authenticated"}]
    ),
    "extra RoleBinding": _extra_doc(
        {"kind": "RoleBinding", "metadata": {"name": "sneaky", "namespace": "default"}}
    ),
}


@pytest.mark.parametrize("change", BAD_CHANGES.values(), ids=BAD_CHANGES.keys())
def test_checks_catch_a_bad_change(change: Callable[[list[Doc]], None]) -> None:
    docs = copy.deepcopy(load_docs())
    change(docs)
    assert problems_in(docs), "this change should have been flagged"
