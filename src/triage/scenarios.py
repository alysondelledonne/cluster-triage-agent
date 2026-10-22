"""Seed, check and clean up the failure scenarios on a local kind cluster.

Each scenario lives in `scenarios/NN-name/`:
- `manifest.yaml` creates a namespace and breaks exactly one thing in it
- `expected.yaml` holds the right answer and how to tell the failure has shown

This is test-harness code, not part of the agent: it creates and deletes
resources, so it runs with your own kube context and refuses anything that
isn't a kind cluster. The agent itself only ever reads (see DECISIONS.md 002).

    uv run triage-seed list
    uv run triage-seed apply crashloop          # seed and wait for the failure
    uv run triage-seed delete crashloop
    uv run triage-seed check                    # seed, wait, delete each in turn
    uv run triage-seed record                   # seed, wait, record every API answer, delete

`record` reads through the agent's own kubeconfig (README, "Run the MCP server"),
never your admin context, and saves raw API responses to
tests/fixtures/scenarios/NN-name/recording.json for offline replay (DECISIONS.md 022).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field

from .mcp_server import trim
from .mcp_server.kube import (
    DEFAULT_AGENT_KUBECONFIG,
    Kind,
    KubeClientReader,
    KubeError,
    KubeReader,
    service_account_subject,
)
from .mcp_server.kube_server import IdentityError, require_agent_identity
from .mcp_server.replay import Recording, RecordingReader, SecretInRecording
from .models import Category, ResourceRef

DEFAULT_CONTEXT = "kind-triage"
DEFAULT_FIXTURES_DIR = Path("tests/fixtures/scenarios")

# ---------- wait conditions: how to tell a scenario's failure has shown ----------


def _container_states(pods: dict[str, Any]) -> list[dict[str, Any]]:
    """Every container's current and last state across all pods in a `get pods -o json`."""
    states: list[dict[str, Any]] = []
    for pod in pods.get("items", []):
        status = pod.get("status", {})
        for c in [*status.get("initContainerStatuses", []), *status.get("containerStatuses", [])]:
            states.extend([c.get("state", {}), c.get("lastState", {})])
    return states


class ContainerWaiting(BaseModel):
    """A container is stuck waiting for one of these reasons (e.g. CrashLoopBackOff)."""

    type: Literal["container_waiting"] = "container_waiting"
    reasons: list[str]

    def matches_pods(self, pods: dict[str, Any]) -> bool:
        return any(
            s.get("waiting", {}).get("reason") in self.reasons for s in _container_states(pods)
        )


class ContainerTerminated(BaseModel):
    """A container has terminated (now or on its last run) for this reason."""

    type: Literal["container_terminated"] = "container_terminated"
    reason: str

    def matches_pods(self, pods: dict[str, Any]) -> bool:
        return any(
            s.get("terminated", {}).get("reason") == self.reason for s in _container_states(pods)
        )


class EventSeen(BaseModel):
    """An event with this reason exists in the namespace (e.g. Unhealthy)."""

    type: Literal["event"] = "event"
    reason: str

    def matches_events(self, events: dict[str, Any]) -> bool:
        return any(e.get("reason") == self.reason for e in events.get("items", []))


class LogContains(BaseModel):
    """The resource's logs contain this text (e.g. a 403 from the API server)."""

    type: Literal["log_contains"] = "log_contains"
    resource: str  # anything `kubectl logs` accepts, e.g. deployment/reporter
    text: str

    def matches_logs(self, logs: str) -> bool:
        return self.text in logs


WaitFor = Annotated[
    ContainerWaiting | ContainerTerminated | EventSeen | LogContains,
    Field(discriminator="type"),
]


class Seed(BaseModel):
    wait_for: WaitFor
    timeout_s: int = 180


class Expected(BaseModel):
    """The contents of a scenario's expected.yaml."""

    namespace: str
    category: Category
    affected_resource: ResourceRef
    # Other answers that are also right, e.g. the ServiceAccount or the Deployment
    # that uses it. Graded as correct in Milestone 3.
    also_accept: list[ResourceRef] = []
    description: str
    seed: Seed


@dataclass(frozen=True)
class Scenario:
    name: str  # folder name, e.g. 01-crashloop
    path: Path
    expected: Expected

    @property
    def manifest_path(self) -> Path:
        return self.path / "manifest.yaml"


def load_scenario(path: Path) -> Scenario:
    data = yaml.safe_load((path / "expected.yaml").read_text())
    return Scenario(name=path.name, path=path, expected=Expected.model_validate(data))


def discover(root: Path) -> list[Scenario]:
    """All scenario folders under `root`, in number order."""
    return [load_scenario(p) for p in sorted(root.iterdir()) if (p / "expected.yaml").is_file()]


def find(scenarios: list[Scenario], key: str) -> Scenario:
    """Look up a scenario by number ("1"), short name ("crashloop") or folder name."""
    for s in scenarios:
        number, _, short = s.name.partition("-")
        if key in {s.name, short} or (key.isdigit() and int(key) == int(number)):
            return s
    raise KeyError(f"no scenario {key!r}; try: {', '.join(s.name for s in scenarios)}")


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


def images_in(docs: list[dict[str, Any]]) -> list[str]:
    images = []
    for doc in docs:
        spec = doc.get("spec", {})
        pod_spec = spec if doc.get("kind") == "Pod" else spec.get("template", {}).get("spec", {})
        for c in [*pod_spec.get("initContainers", []), *pod_spec.get("containers", [])]:
            images.append(c["image"])
    return images


# ---------- kubectl ----------


def require_kind_context(context: str, *, allow_any: bool = False) -> None:
    """Refuse to seed anything but a kind cluster unless explicitly allowed."""
    if not allow_any and not context.startswith("kind-"):
        raise ValueError(
            f"refusing to seed scenarios into context {context!r}: it isn't a kind cluster. "
            "Pass --allow-any-context if you really mean it."
        )


@dataclass
class Kubectl:
    """Runs kubectl against one explicit context, never the current default."""

    context: str

    def command(self, *args: str) -> list[str]:
        return ["kubectl", "--context", self.context, *args]

    def run(self, *args: str, check: bool = True) -> str:
        done = subprocess.run(self.command(*args), capture_output=True, text=True, check=False)
        if check and done.returncode != 0:
            raise RuntimeError(f"kubectl {' '.join(args)} failed: {done.stderr.strip()}")
        return done.stdout


# ---------- seeding ----------


class SeedTimeout(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedResult:
    scenario: str
    seconds: float


def failure_shown(scenario: Scenario, kubectl: Kubectl) -> bool:
    cond = scenario.expected.seed.wait_for
    ns = scenario.expected.namespace
    if isinstance(cond, ContainerWaiting | ContainerTerminated):
        return cond.matches_pods(json.loads(kubectl.run("get", "pods", "-n", ns, "-o", "json")))
    if isinstance(cond, EventSeen):
        return cond.matches_events(json.loads(kubectl.run("get", "events", "-n", ns, "-o", "json")))
    # Logs aren't there until the container starts, so a failed call just means "not yet".
    return cond.matches_logs(kubectl.run("logs", "-n", ns, cond.resource, "--tail=50", check=False))


def seed(
    scenario: Scenario,
    kubectl: Kubectl,
    *,
    timeout_s: float | None = None,
    poll_s: float = 3,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> SeedResult:
    """Apply the scenario, then poll until its failure shows or the timeout passes."""
    kubectl.run("apply", "-f", str(scenario.manifest_path))
    seconds = wait_for_failure(
        scenario, kubectl, timeout_s=timeout_s, poll_s=poll_s, clock=clock, sleep=sleep
    )
    return SeedResult(scenario=scenario.name, seconds=seconds)


def wait_for_failure(
    scenario: Scenario,
    kubectl: Kubectl,
    *,
    timeout_s: float | None = None,
    poll_s: float = 3,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Poll until the scenario's failure signal shows; return how many seconds that took."""
    limit = timeout_s if timeout_s is not None else scenario.expected.seed.timeout_s
    start = clock()
    while True:
        if failure_shown(scenario, kubectl):
            return round(clock() - start, 1)
        if clock() - start >= limit:
            cond = scenario.expected.seed.wait_for
            raise SeedTimeout(
                f"{scenario.name}: no sign of {cond.model_dump(exclude={'type'})} "
                f"({cond.type}) after {limit:.0f}s in namespace {scenario.expected.namespace}"
            )
        sleep(poll_s)


def delete(scenario: Scenario, kubectl: Kubectl) -> None:
    """Remove the scenario by deleting its namespace (everything it made lives there)."""
    kubectl.run(
        "delete", "namespace", scenario.expected.namespace, "--ignore-not-found", "--wait=true"
    )


# ---------- recording ----------

# Manifest kinds the agent's `describe` tool can read, by the name the tool uses.
DESCRIBABLE: dict[str, Kind] = {
    "Pod": "pod",
    "Deployment": "deployment",
    "ReplicaSet": "replicaset",
    "Service": "service",
    "ConfigMap": "configmap",
    "ServiceAccount": "serviceaccount",
    "Role": "role",
    "RoleBinding": "rolebinding",
}

# Objects every namespace has, which `describe` can reach: the default ServiceAccount
# and the cluster's CA bundle (public, not a Secret). Reading them completes the
# inventory, so replay can answer any other name with "not found" (DECISIONS.md 038).
BUILT_IN: list[tuple[Kind, str]] = [
    ("serviceaccount", "default"),
    ("configmap", "kube-root-ca.crt"),
]

# Permission questions asked for every ServiceAccount, for the agent's `can_i` tool.
ACCESS_CHECKS = [("get", "configmaps"), ("list", "pods")]


def _container_names(pod: dict[str, Any]) -> list[str]:
    status = pod.get("status") or {}
    statuses = [
        *(status.get("initContainerStatuses") or []),
        *(status.get("containerStatuses") or []),
    ]
    if statuses:
        return [c["name"] for c in statuses]
    spec = pod.get("spec") or {}
    containers = [*(spec.get("initContainers") or []), *(spec.get("containers") or [])]
    return [c["name"] for c in containers]


def record_scenario(scenario: Scenario, reader: KubeReader, *, server_version: str) -> Recording:
    """Ask the cluster everything the agent's tools could ask about this scenario.

    Every answer, errors included (e.g. no previous logs before a restart), ends up
    in the returned Recording. Reads only, through `reader`, after checking it is
    the agent's own identity.
    """
    ns = scenario.expected.namespace
    rec = RecordingReader(
        reader, scenario=scenario.name, namespace=ns, server_version=server_version
    )
    require_agent_identity(rec)

    def attempt(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        # A failed read is already in the recording; the agent will see the same error.
        with contextlib.suppress(KubeError):
            fn(*args, **kwargs)

    pods = rec.list_pods(ns)
    rec.list_events(ns)
    accounts = {"default"}
    for pod in pods:
        name = pod["metadata"]["name"]
        attempt(rec.read, "pod", ns, name)
        for owner in pod["metadata"].get("ownerReferences") or []:
            if owner.get("kind") == "ReplicaSet":
                attempt(rec.read, "replicaset", ns, owner["name"])
        for container in _container_names(pod):
            for previous in (False, True):
                attempt(
                    rec.read_log,
                    ns,
                    name,
                    container=container,
                    previous=previous,
                    tail=trim.MAX_LOG_LINES,
                )
        if (pod.get("spec") or {}).get("serviceAccountName"):
            accounts.add(pod["spec"]["serviceAccountName"])

    for doc in load_manifest(scenario.manifest_path):
        kind = DESCRIBABLE.get(doc["kind"])
        if kind is None:
            continue
        name = doc["metadata"]["name"]
        attempt(rec.read, kind, ns, name)
        if kind == "service":
            attempt(rec.list_endpoint_slices, ns, name)
        if kind == "serviceaccount":
            accounts.add(name)

    for kind, name in BUILT_IN:
        attempt(rec.read, kind, ns, name)
    rec.recording.inventory_complete = True

    for account in sorted(accounts):
        user, groups = service_account_subject(ns, account)
        for verb, resource in ACCESS_CHECKS:
            attempt(
                rec.access_review,
                ns,
                user=user,
                groups=groups,
                verb=verb,
                resource=resource,
                group="",
                subresource="",
            )
    return rec.recording


def seed_and_record(
    scenario: Scenario,
    kubectl: Kubectl,
    reader: KubeReader,
    *,
    server_version: str,
    settle_s: float,
    timeout_s: float | None = None,
    poll_s: float = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[SeedResult, Recording]:
    """Seed, let events and restarts pile up, confirm the failure still shows, then record.

    The second wait matters: a failing container cycles through states (CrashLoopBackOff,
    then a restart that crashes again), so the signal seen at seeding time may have moved
    on by the end of the settle pause. Reading straight after it shows again means the
    recording holds the same signal the seeder waited for. The sweep starts within a
    second of that check, well inside the back-off delay of a pod that has already
    restarted a few times.
    """
    result = seed(scenario, kubectl, timeout_s=timeout_s, poll_s=poll_s, sleep=sleep)
    sleep(settle_s)
    wait_for_failure(scenario, kubectl, timeout_s=timeout_s, poll_s=poll_s, sleep=sleep)
    return result, record_scenario(scenario, reader, server_version=server_version)


# ---------- CLI ----------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("action", choices=["list", "apply", "delete", "check", "record"])
    parser.add_argument("names", nargs="*", help="scenario numbers or names; default: all")
    parser.add_argument("--context", default=DEFAULT_CONTEXT)
    parser.add_argument("--allow-any-context", action="store_true")
    parser.add_argument("--scenarios-dir", type=Path, default=Path("scenarios"))
    parser.add_argument("--timeout", type=float, help="seconds; overrides expected.yaml")
    parser.add_argument("--keep", action="store_true", help="check, record: leave scenarios up")
    parser.add_argument(
        "--agent-kubeconfig",
        default=str(DEFAULT_AGENT_KUBECONFIG),
        help="record: kubeconfig with the agent's ServiceAccount token",
    )
    parser.add_argument("--agent-context", help="record: context in that kubeconfig")
    parser.add_argument(
        "--settle", type=float, default=15, help="record: seconds to wait after the failure shows"
    )
    parser.add_argument("--fixtures-dir", type=Path, default=DEFAULT_FIXTURES_DIR)
    args = parser.parse_args(argv)

    try:
        scenarios = discover(args.scenarios_dir)
        chosen = [find(scenarios, n) for n in args.names] if args.names else scenarios
        if args.action != "list":
            require_kind_context(args.context, allow_any=args.allow_any_context)
    except (KeyError, ValueError, FileNotFoundError) as err:
        print(f"error: {err.args[0] if err.args else err}", file=sys.stderr)
        return 2

    if args.action == "list":
        for s in chosen:
            e = s.expected
            print(f"{s.name:20} {e.category:14} {e.affected_resource!s:28} {e.description}")
        return 0

    if args.action == "record":
        return _record(chosen, args)

    kubectl = Kubectl(context=args.context)
    failed = 0
    for s in chosen:
        if args.action == "delete":
            delete(s, kubectl)
            print(f"deleted  {s.name}")
            continue
        try:
            result = seed(s, kubectl, timeout_s=args.timeout)
            print(f"seeded   {s.name:20} failure showed after {result.seconds:5.1f}s")
        except SeedTimeout as err:
            failed += 1
            print(f"TIMEOUT  {err}", file=sys.stderr)
        if args.action == "check" and not args.keep:
            delete(s, kubectl)
    if args.action == "check":
        print(f"\n{len(chosen) - failed}/{len(chosen)} scenarios seeded")
    return 1 if failed else 0


def _record(chosen: list[Scenario], args: argparse.Namespace) -> int:
    """Seed each scenario (your context), record it (the agent's), then clean up."""
    try:
        reader = KubeClientReader.from_kubeconfig(args.agent_kubeconfig, args.agent_context)
        require_agent_identity(reader)  # fail before seeding anything
        version = reader.server_version()
    except (IdentityError, KubeError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    except Exception as err:  # missing kubeconfig, expired token, cluster down
        print(f"error: can't read the cluster as the agent: {err}", file=sys.stderr)
        return 2

    kubectl = Kubectl(context=args.context)
    failed = 0
    for s in chosen:
        try:
            result, recording = seed_and_record(
                s,
                kubectl,
                reader,
                server_version=version,
                settle_s=args.settle,
                timeout_s=args.timeout,
            )
            path = args.fixtures_dir / s.name / "recording.json"
            recording.save(path)
            print(
                f"recorded {s.name:20} failure after {result.seconds:5.1f}s, "
                f"{len(recording.calls)} calls -> {path}"
            )
        except (SeedTimeout, IdentityError, KubeError, SecretInRecording) as err:
            failed += 1
            print(f"FAILED   {s.name}: {err}", file=sys.stderr)
        finally:
            if not args.keep:
                delete(s, kubectl)
    print(f"\n{len(chosen) - failed}/{len(chosen)} scenarios recorded")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
