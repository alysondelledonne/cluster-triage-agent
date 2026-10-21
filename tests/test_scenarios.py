"""Checks for the seeded failure scenarios and the seeding logic.

Offline: nothing here needs a cluster. Scenario files are checked for shape and
hygiene, and the wait conditions are checked against small hand-written
`kubectl get -o json` style payloads.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from triage.models import Category, ResourceRef
from triage.scenarios import (
    ContainerTerminated,
    ContainerWaiting,
    EventSeen,
    Kubectl,
    LogContains,
    Scenario,
    SeedTimeout,
    delete,
    discover,
    find,
    images_in,
    load_manifest,
    require_kind_context,
    seed,
)

REPO = Path(__file__).resolve().parents[1]
SCENARIOS = discover(REPO / "scenarios")
ALLOWED_IMAGES = {"busybox", "nginx", "curlimages/curl"}


# ---------- the scenario files ----------


def test_six_scenarios_numbered_01_to_06() -> None:
    assert [s.name[:2] for s in SCENARIOS] == ["01", "02", "03", "04", "05", "06"]


def test_each_scenario_covers_a_different_category() -> None:
    assert {s.expected.category for s in SCENARIOS} == {
        Category.CRASH_LOOP,
        Category.IMAGE_PULL,
        Category.OOM_KILLED,
        Category.CONFIG_ERROR,
        Category.PROBE_FAILURE,
        Category.RBAC_DENIED,
    }


def test_namespaces_are_unique() -> None:
    namespaces = [s.expected.namespace for s in SCENARIOS]
    assert len(set(namespaces)) == len(namespaces)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_manifest_stays_inside_its_namespace(scenario: Scenario) -> None:
    docs = load_manifest(scenario.manifest_path)
    first = docs[0]
    assert first["kind"] == "Namespace", "the Namespace must come first so apply creates it"
    assert first["metadata"]["name"] == scenario.expected.namespace
    assert first["metadata"]["labels"]["triage.scenario"] == scenario.name
    for doc in docs[1:]:
        assert doc["kind"] not in {"Namespace", "ClusterRole", "ClusterRoleBinding"}, doc["kind"]
        assert doc["metadata"].get("namespace") == scenario.expected.namespace, doc["kind"]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_expected_resources_exist_in_manifest(scenario: Scenario) -> None:
    docs = load_manifest(scenario.manifest_path)
    present = {ResourceRef(kind=d["kind"], name=d["metadata"]["name"]) for d in docs}
    for ref in [scenario.expected.affected_resource, *scenario.expected.also_accept]:
        assert ref in present, ref


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_manifest_hygiene(scenario: Scenario) -> None:
    docs = load_manifest(scenario.manifest_path)
    assert not [d for d in docs if d["kind"] == "Secret"], "scenarios never create Secrets"
    containers = [c for d in docs for c in _containers(d)]
    assert containers, "every scenario runs at least one container"
    for c in containers:
        assert c.get("resources", {}).get("limits", {}).get("memory"), c["name"]
        assert not c.get("securityContext", {}).get("privileged"), c["name"]
    for image in images_in(docs):
        repo, _, tag = image.rpartition(":")
        assert repo in ALLOWED_IMAGES, image
        assert tag and tag != "latest", f"pin a tag: {image}"


def test_find_accepts_number_name_or_folder() -> None:
    assert find(SCENARIOS, "1").name == "01-crashloop"
    assert find(SCENARIOS, "crashloop").name == "01-crashloop"
    assert find(SCENARIOS, "01-crashloop").name == "01-crashloop"
    with pytest.raises(KeyError):
        find(SCENARIOS, "nope")


# ---------- wait conditions ----------


def _pod(state: dict[str, Any], last: dict[str, Any] | None = None) -> dict[str, Any]:
    status = {"name": "app", "ready": False, "state": state, "lastState": last or {}}
    return {"items": [{"status": {"containerStatuses": [status]}}]}


def test_container_waiting_matches_listed_reasons() -> None:
    cond = ContainerWaiting(reasons=["ErrImagePull", "ImagePullBackOff"])
    assert cond.matches_pods(_pod({"waiting": {"reason": "ImagePullBackOff"}}))
    assert not cond.matches_pods(_pod({"waiting": {"reason": "ContainerCreating"}}))
    assert not cond.matches_pods({"items": []})


def test_container_terminated_checks_current_and_last_state() -> None:
    cond = ContainerTerminated(reason="OOMKilled")
    assert cond.matches_pods(_pod({"terminated": {"reason": "OOMKilled"}}))
    assert cond.matches_pods(
        _pod({"waiting": {"reason": "CrashLoopBackOff"}}, {"terminated": {"reason": "OOMKilled"}})
    )
    assert not cond.matches_pods(_pod({"terminated": {"reason": "Error"}}))


def test_init_containers_count_too() -> None:
    cond = ContainerWaiting(reasons=["CreateContainerConfigError"])
    pods = {
        "items": [
            {
                "status": {
                    "initContainerStatuses": [
                        {"state": {"waiting": {"reason": "CreateContainerConfigError"}}}
                    ]
                }
            }
        ]
    }
    assert cond.matches_pods(pods)


def test_event_seen_matches_reason() -> None:
    cond = EventSeen(reason="Unhealthy")
    assert cond.matches_events({"items": [{"reason": "Scheduled"}, {"reason": "Unhealthy"}]})
    assert not cond.matches_events({"items": [{"reason": "Scheduled"}]})


def test_log_contains_matches_text() -> None:
    cond = LogContains(resource="deployment/reporter", text="403")
    assert cond.matches_logs('{"code": 403, "reason": "Forbidden"}')
    assert not cond.matches_logs("200 OK")


# ---------- kubectl wrapper and seeding ----------


class FakeKubectl(Kubectl):
    """Records commands and answers `get` calls from a queue of payloads."""

    def __init__(self, answers: list[str]) -> None:
        super().__init__(context="kind-test")
        self.calls: list[list[str]] = []
        self.answers = answers

    def run(self, *args: str, check: bool = True) -> str:
        self.calls.append(list(args))
        if args[0] in {"get", "logs"}:
            return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return ""


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_kubectl_always_passes_the_context() -> None:
    assert Kubectl(context="kind-triage").command("get", "pods") == [
        "kubectl",
        "--context",
        "kind-triage",
        "get",
        "pods",
    ]


def test_require_kind_context_refuses_other_clusters() -> None:
    require_kind_context("kind-triage")
    with pytest.raises(ValueError):
        require_kind_context("prod-us-east")
    require_kind_context("prod-us-east", allow_any=True)


def test_seed_applies_then_waits_until_the_failure_shows() -> None:
    scenario = find(SCENARIOS, "imagepull")
    waiting = json.dumps(_pod({"waiting": {"reason": "ContainerCreating"}}))
    failing = json.dumps(_pod({"waiting": {"reason": "ImagePullBackOff"}}))
    kubectl, clock = FakeKubectl([waiting, waiting, failing]), FakeClock()

    result = seed(scenario, kubectl, poll_s=5, clock=clock.time, sleep=clock.sleep)

    assert kubectl.calls[0] == ["apply", "-f", str(scenario.manifest_path)]
    assert result.seconds == 10
    assert result.scenario == "02-imagepull"


def test_seed_times_out_with_a_useful_error() -> None:
    scenario = find(SCENARIOS, "imagepull")
    waiting = json.dumps(_pod({"waiting": {"reason": "ContainerCreating"}}))
    kubectl, clock = FakeKubectl([waiting]), FakeClock()

    with pytest.raises(SeedTimeout, match="02-imagepull"):
        seed(scenario, kubectl, timeout_s=30, poll_s=5, clock=clock.time, sleep=clock.sleep)


def test_delete_removes_only_the_scenario_namespace() -> None:
    scenario = find(SCENARIOS, "imagepull")
    kubectl = FakeKubectl([""])
    delete(scenario, kubectl)
    assert kubectl.calls == [
        ["delete", "namespace", scenario.expected.namespace, "--ignore-not-found", "--wait=true"]
    ]


def _containers(doc: dict[str, Any]) -> list[dict[str, Any]]:
    spec = doc.get("spec", {})
    pod_spec = spec.get("template", {}).get("spec", spec) if doc["kind"] != "Pod" else spec
    return [*pod_spec.get("initContainers", []), *pod_spec.get("containers", [])]


# ---------- the proposed fixes can actually work (DECISIONS.md 031) ----------


def _script(name: str) -> str:
    (doc,) = [
        d for d in load_manifest(find(SCENARIOS, name).manifest_path) if d["kind"] == "Deployment"
    ]
    (container,) = doc["spec"]["template"]["spec"]["containers"]
    return str(container["args"][0])


def test_crashloop_waits_for_the_backoff_event() -> None:
    # The container's waiting state is missed by polling too often (DECISIONS.md 032);
    # the BackOff event stays in the namespace's event list once the kubelet emits it.
    cond = find(SCENARIOS, "crashloop").expected.seed.wait_for
    assert isinstance(cond, EventSeen)
    assert cond.reason == "BackOff"


def test_crashloop_exits_only_without_listen_port() -> None:
    # The scenario breaks because LISTEN_PORT is missing, so setting it must fix it.
    script = _script("crashloop")
    path = {"PATH": os.environ["PATH"]}
    failed = subprocess.run(
        ["sh", "-c", script], capture_output=True, text=True, env=path, timeout=5
    )
    assert failed.returncode == 1
    assert "LISTEN_PORT is missing" in failed.stderr
    with pytest.raises(subprocess.TimeoutExpired):  # still running: the fix works
        subprocess.run(
            ["sh", "-c", script],
            capture_output=True,
            env={**path, "LISTEN_PORT": "8080"},
            timeout=1,
        )


def _mebibytes(quantity: str) -> int:
    assert quantity.endswith("Mi"), quantity
    return int(quantity[:-2])


def test_oomkilled_holds_a_fixed_amount_between_the_limit_and_a_sensible_fix() -> None:
    # Unbounded growth (the old `tail /dev/zero`) can't be fixed by any limit.
    script = _script("oomkilled")
    match = re.search(r"\bdd if=/dev/zero bs=(\d+) count=1\b", script)
    assert match, script
    held_mib = int(match.group(1)) / 2**20
    (doc,) = [
        d
        for d in load_manifest(find(SCENARIOS, "oomkilled").manifest_path)
        if d["kind"] == "Deployment"
    ]
    limit = _mebibytes(
        doc["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["memory"]
    )
    assert held_mib > 2 * limit, "well over the limit, so it is OOMKilled every start"
    assert held_mib + 8 <= 64, "a 64Mi limit (the fix the agent proposed) leaves room for it"
