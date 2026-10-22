"""The recorded scenarios in tests/fixtures/scenarios/, replayed through the real tools.

Each scenario's recording must show, through the MCP tools the agent will use,
the same failure signal the seeder waits for in that scenario's expected.yaml.
Offline: the recordings are replayed, nothing touches a cluster. Make or refresh
them with `uv run triage-seed record` (README).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.client import Client

from triage.agent.mcp_tools import tools_from_mcp
from triage.mcp_server import trim
from triage.mcp_server.kube_server import build_server
from triage.mcp_server.replay import Recording, ReplayReader, check_no_secrets
from triage.scenarios import (
    ContainerTerminated,
    ContainerWaiting,
    EventSeen,
    LogContains,
    Scenario,
    discover,
    load_manifest,
)

REPO = Path(__file__).resolve().parents[1]
SCENARIOS = discover(REPO / "scenarios")
RECORDINGS = REPO / "tests" / "fixtures" / "scenarios"

ToolFn = Callable[[dict[str, Any]], Awaitable[str]]


def recording_path(scenario: Scenario) -> Path:
    return RECORDINGS / scenario.name / "recording.json"


def run_tools(scenario: Scenario, calls: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """Call tools through a real MCP client over the replayed recording.

    A call that errors (for example previous logs that don't exist) returns its
    error text, the same text the model would see.
    """
    reader = ReplayReader(Recording.load(recording_path(scenario)))

    async def run() -> list[str]:
        async with Client(build_server(scenario.expected.namespace, reader)) as client:
            tools: dict[str, ToolFn] = {t.spec.name: t.fn for t in await tools_from_mcp(client)}
            out = []
            for name, args in calls:
                try:
                    out.append(await tools[name](args))
                except RuntimeError as err:
                    out.append(str(err))
            return out

    return asyncio.run(run())


def pod_names(scenario: Scenario) -> list[str]:
    pods = ReplayReader(Recording.load(recording_path(scenario))).list_pods(
        scenario.expected.namespace
    )
    return [p["metadata"]["name"] for p in pods]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_every_scenario_has_a_recording(scenario: Scenario) -> None:
    assert recording_path(scenario).is_file(), (
        f"no recording for {scenario.name}; run: uv run triage-seed record {scenario.name}"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_recording_matches_its_scenario(scenario: Scenario) -> None:
    rec = Recording.load(recording_path(scenario))
    assert rec.scenario == scenario.name
    assert rec.namespace == scenario.expected.namespace
    assert rec.agent_user == "system:serviceaccount:triage-system:triage-agent"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_tools_show_the_failure_signal(scenario: Scenario) -> None:
    cond = scenario.expected.seed.wait_for
    if isinstance(cond, ContainerWaiting):
        (pods,) = run_tools(scenario, [("list_pods", {})])
        assert any(reason in pods for reason in cond.reasons), pods
    elif isinstance(cond, ContainerTerminated):
        (pods,) = run_tools(scenario, [("list_pods", {})])
        assert cond.reason in pods, pods
    elif isinstance(cond, EventSeen):
        (events,) = run_tools(scenario, [("get_events", {})])
        assert f"reason: {cond.reason}" in events, events
    elif isinstance(cond, LogContains):
        logs = run_tools(scenario, [("get_logs", {"pod": p}) for p in pod_names(scenario)])
        assert any(cond.text in text for text in logs), logs
    else:
        pytest.fail(f"no check for wait condition {cond.type}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_every_tool_result_stays_under_the_cap(scenario: Scenario) -> None:
    kinds = {
        "Deployment": "deployment",
        "Service": "service",
        "ConfigMap": "configmap",
        "ServiceAccount": "serviceaccount",
        "Role": "role",
        "RoleBinding": "rolebinding",
    }
    calls: list[tuple[str, dict[str, Any]]] = [("list_pods", {}), ("get_events", {})]
    for doc in load_manifest(scenario.manifest_path):
        if doc["kind"] in kinds:
            calls.append(
                ("describe", {"kind": kinds[doc["kind"]], "name": doc["metadata"]["name"]})
            )
    for pod in pod_names(scenario):
        calls.append(("describe", {"kind": "pod", "name": pod}))
        calls.append(("get_logs", {"pod": pod, "tail": trim.MAX_LOG_LINES}))
    for out in run_tools(scenario, calls):
        assert len(out) <= trim.MAX_OUTPUT_CHARS + len(trim.OUTPUT_CUT_NOTE) + 200, out[:200]
        assert "managedFields" not in out


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_recording_holds_no_secrets(scenario: Scenario) -> None:
    check_no_secrets(recording_path(scenario).read_text())


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_recording_has_the_namespaces_full_inventory(scenario: Scenario) -> None:
    # Needed for replay to answer unknown objects with "not found" (DECISIONS.md 038);
    # re-record with `uv run triage-seed record` if this fails.
    assert Recording.load(recording_path(scenario)).inventory_complete
