"""The read-only Kubernetes MCP server, end to end through an in-memory MCP client.

Offline: a fake reader serves the payloads in tests/fixtures/kube/ and records
every call, so the tests can also check which namespace each call used.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.client import Client

from triage.agent.mcp_tools import tools_from_mcp
from triage.mcp_server import trim
from triage.mcp_server.kube import Kind, KubeError
from triage.mcp_server.kube_server import (
    AGENT_USER,
    IdentityError,
    build_server,
    main,
    require_agent_identity,
)

FIXTURES = Path(__file__).parent / "fixtures" / "kube"
NAMESPACE = "triage-01-crashloop"
TOOL_NAMES = {"list_pods", "get_events", "get_logs", "describe", "can_i"}


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class FakeReader:
    """Answers from fixtures and records (method, namespace, details) for every call."""

    def __init__(self, user: str = AGENT_USER) -> None:
        self.user = user
        self.calls: list[tuple[str, str | None, dict[str, Any]]] = []
        self.objects: dict[tuple[str, str], dict[str, Any]] = {
            ("deployment", "api"): load("deployment-api.json"),
            ("configmap", "app-config"): load("configmap-app-config.json"),
            ("serviceaccount", "reporter"): load("serviceaccount-reporter.json"),
            ("service", "frontend"): load("service-frontend.json"),
        }
        self.logs = (FIXTURES / "logs-reporter.txt").read_text()
        self.review = load("subjectaccessreview-denied.json")["status"]

    def whoami(self) -> str:
        self.calls.append(("whoami", None, {}))
        return self.user

    def list_pods(self, namespace: str) -> list[dict[str, Any]]:
        self.calls.append(("list_pods", namespace, {}))
        items: list[dict[str, Any]] = load("pods.json")["items"]
        return items

    def list_events(self, namespace: str) -> list[dict[str, Any]]:
        self.calls.append(("list_events", namespace, {}))
        items: list[dict[str, Any]] = load("events.json")["items"]
        return items

    def read_log(
        self, namespace: str, pod: str, *, container: str | None, previous: bool, tail: int
    ) -> str:
        args = {"pod": pod, "container": container, "previous": previous, "tail": tail}
        self.calls.append(("read_log", namespace, args))
        return self.logs

    def read(self, kind: Kind, namespace: str, name: str) -> dict[str, Any]:
        self.calls.append(("read", namespace, {"kind": kind, "name": name}))
        if (kind, name) not in self.objects:
            raise KubeError(404, f'{kind}s "{name}" not found')
        return self.objects[(kind, name)]

    def list_endpoint_slices(self, namespace: str, service: str) -> list[dict[str, Any]]:
        self.calls.append(("list_endpoint_slices", namespace, {"service": service}))
        items: list[dict[str, Any]] = load("endpointslices-frontend.json")["items"]
        return items

    def access_review(
        self,
        namespace: str,
        *,
        user: str,
        groups: list[str],
        verb: str,
        resource: str,
        group: str,
        subresource: str,
    ) -> dict[str, Any]:
        args = {
            "user": user,
            "groups": groups,
            "verb": verb,
            "resource": resource,
            "group": group,
            "subresource": subresource,
        }
        self.calls.append(("access_review", namespace, args))
        return self.review


ToolFn = Callable[[dict[str, Any]], Awaitable[str]]


def call(reader: FakeReader, tool: str, args: dict[str, Any] | None = None) -> str:
    """Call one tool through a real MCP client, as the agent will."""

    async def run() -> str | RuntimeError:
        async with Client(build_server(NAMESPACE, reader)) as client:
            tools: dict[str, ToolFn] = {t.spec.name: t.fn for t in await tools_from_mcp(client)}
            try:
                return await tools[tool](args or {})
            except RuntimeError as err:
                # Raised here it would leave the client's task group wrapped in an
                # ExceptionGroup; hand it out and raise it plainly instead.
                return err

    result = asyncio.run(run())
    if isinstance(result, RuntimeError):
        raise result
    return result


def list_tools(reader: FakeReader) -> list[Any]:
    async def run() -> list[Any]:
        async with Client(build_server(NAMESPACE, reader)) as client:
            return list((await client.list_tools()).tools)

    return asyncio.run(run())


# ---------- the guardrails ----------


def test_exactly_the_five_tools_all_read_only() -> None:
    tools = list_tools(FakeReader())
    assert {t.name for t in tools} == TOOL_NAMES
    for t in tools:
        assert t.annotations and t.annotations.read_only_hint, t.name
        assert t.annotations.destructive_hint is False, t.name


def test_no_tool_lets_the_model_pick_a_namespace() -> None:
    for t in list_tools(FakeReader()):
        assert "namespace" not in t.input_schema.get("properties", {}), t.name


def test_every_cluster_call_uses_the_bound_namespace() -> None:
    reader = FakeReader()
    call(reader, "list_pods")
    call(reader, "get_events")
    call(reader, "get_logs", {"pod": "reporter-abc"})
    call(reader, "describe", {"kind": "deployment", "name": "api"})
    call(reader, "describe", {"kind": "service", "name": "frontend"})
    call(reader, "can_i", {"service_account": "reporter", "verb": "get", "resource": "configmaps"})
    namespaces = {ns for _, ns, _ in reader.calls}
    assert namespaces == {NAMESPACE}


def test_server_instructions_name_the_namespace() -> None:
    server = build_server(NAMESPACE, FakeReader())
    assert NAMESPACE in (server.instructions or "")


@pytest.mark.parametrize("bad", ["", "Has-Caps", "a/b", "../x", "x" * 254, "-leading"])
def test_names_must_be_valid_kubernetes_names(bad: str) -> None:
    reader = FakeReader()
    with pytest.raises(RuntimeError):
        call(reader, "describe", {"kind": "deployment", "name": bad})
    assert not [c for c in reader.calls if c[0] == "read"], "nothing reached the cluster"


def test_describe_rejects_kinds_outside_the_list() -> None:
    reader = FakeReader()
    with pytest.raises(RuntimeError):
        call(reader, "describe", {"kind": "secret", "name": "anything"})
    assert not reader.calls


def test_cluster_errors_come_back_as_tool_errors() -> None:
    with pytest.raises(RuntimeError, match="not found"):
        call(FakeReader(), "describe", {"kind": "deployment", "name": "missing"})


# ---------- each tool ----------


def test_list_pods_shows_the_failure_without_noise() -> None:
    out = call(FakeReader(), "list_pods")
    assert "CrashLoopBackOff" in out
    assert "exit code 1" in out
    assert "ReplicaSet/api-7c9d8f6b5" in out
    assert "managedFields" not in out
    assert "resourceVersion" not in out


def test_get_events_newest_first_and_filtered() -> None:
    out = call(FakeReader(), "get_events")
    assert out.index("BackOff") < out.index("Scheduled")
    only = call(FakeReader(), "get_events", {"kind": "Deployment", "name": "api"})
    assert "ScalingReplicaSet" in only
    assert "BackOff" not in only


def test_get_events_says_when_there_are_none() -> None:
    out = call(FakeReader(), "get_events", {"kind": "Pod", "name": "nothing-here"})
    assert out == "No events found."


def test_get_logs_passes_options_and_caps_tail() -> None:
    reader = FakeReader()
    out = call(reader, "get_logs", {"pod": "reporter-abc", "previous": True, "tail": 5000})
    assert "is forbidden" in out
    (_, _, args) = next(c for c in reader.calls if c[0] == "read_log")
    assert args == {
        "pod": "reporter-abc",
        "container": None,
        "previous": True,
        "tail": trim.MAX_LOG_LINES,
    }


def test_get_logs_default_tail() -> None:
    reader = FakeReader()
    call(reader, "get_logs", {"pod": "reporter-abc", "container": "reporter"})
    (_, _, args) = next(c for c in reader.calls if c[0] == "read_log")
    assert args["tail"] == trim.DEFAULT_LOG_LINES
    assert args["container"] == "reporter"


def test_describe_trims_the_object() -> None:
    out = call(FakeReader(), "describe", {"kind": "deployment", "name": "api"})
    assert "MinimumReplicasUnavailable" in out
    assert "managedFields" not in out
    assert "last-applied-configuration" not in out


def test_describe_configmap_hides_values() -> None:
    out = call(FakeReader(), "describe", {"kind": "configmap", "name": "app-config"})
    assert "LOG_FORMAT" in out
    assert "postgres" not in out


def test_describe_service_counts_ready_endpoints() -> None:
    reader = FakeReader()
    out = call(reader, "describe", {"kind": "service", "name": "frontend"})
    assert "ready: 0" in out
    assert "not_ready: 1" in out
    assert ("list_endpoint_slices", NAMESPACE, {"service": "frontend"}) in reader.calls


def test_can_i_asks_about_a_service_account_in_the_bound_namespace() -> None:
    reader = FakeReader()
    out = call(
        reader,
        "can_i",
        {"service_account": "reporter", "verb": "get", "resource": "configmaps"},
    )
    assert "allowed: false" in out
    (_, ns, args) = next(c for c in reader.calls if c[0] == "access_review")
    assert ns == NAMESPACE
    assert args["user"] == f"system:serviceaccount:{NAMESPACE}:reporter"
    assert args["groups"] == [
        "system:serviceaccounts",
        f"system:serviceaccounts:{NAMESPACE}",
        "system:authenticated",
    ]
    assert (args["verb"], args["resource"], args["group"], args["subresource"]) == (
        "get",
        "configmaps",
        "",
        "",
    )


def test_can_i_rejects_a_made_up_verb() -> None:
    reader = FakeReader()
    with pytest.raises(RuntimeError):
        call(reader, "can_i", {"service_account": "reporter", "verb": "rm -rf", "resource": "pods"})
    assert not [c for c in reader.calls if c[0] == "access_review"]


# ---------- startup identity check ----------


def test_identity_check_accepts_the_agent_service_account() -> None:
    require_agent_identity(FakeReader())


def test_identity_check_refuses_anyone_else() -> None:
    with pytest.raises(IdentityError, match="kubernetes-admin"):
        require_agent_identity(FakeReader(user="kubernetes-admin"))


def test_main_refuses_to_start_under_the_wrong_identity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "triage.mcp_server.kube_server.KubeClientReader.from_kubeconfig",
        lambda path, context: FakeReader(user="kubernetes-admin"),
    )
    assert main(["--namespace", NAMESPACE]) == 2
    assert "kubernetes-admin" in capsys.readouterr().err


def test_main_requires_a_namespace() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_an_unauthorized_token_gets_a_hint_to_renew_it() -> None:
    from kubernetes.client import ApiException

    from triage.mcp_server.kube import _message

    message = _message(ApiException(status=401, reason="Unauthorized"))
    assert message.startswith("Unauthorized")
    assert "renew" in message and "README" in message


def test_building_the_server_leaves_logging_quiet() -> None:
    # The MCP SDK configures root logging at its log level; at INFO every HTTP request
    # the model SDK makes was printed in the middle of the report.
    server = build_server(NAMESPACE, FakeReader())
    assert server.settings.log_level == "WARNING"
