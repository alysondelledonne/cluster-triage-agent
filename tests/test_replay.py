"""Recording and replaying Kubernetes API responses, and the `triage-seed record` sweep.

Offline: a small in-memory reader stands in for the cluster.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from triage.mcp_server.kube import Kind, KubeError
from triage.mcp_server.kube_server import AGENT_USER
from triage.mcp_server.replay import (
    NotRecorded,
    Recording,
    RecordingReader,
    ReplayReader,
    SecretInRecording,
    check_no_secrets,
)
from triage.scenarios import Kubectl, discover, find, record_scenario, seed_and_record

REPO = Path(__file__).resolve().parents[1]
SCENARIOS = discover(REPO / "scenarios")
NS = "triage-06-rbac-denied"

POD = {
    "metadata": {
        "name": "reporter-5d8f7c9b6-abcde",
        "ownerReferences": [{"kind": "ReplicaSet", "name": "reporter-5d8f7c9b6"}],
    },
    "spec": {"containers": [{"name": "reporter"}]},
    "status": {"containerStatuses": [{"name": "reporter", "restartCount": 0}]},
}


class TinyReader:
    """A cluster with one pod. `previous` logs fail, as they do before a restart."""

    def __init__(self, user: str = AGENT_USER) -> None:
        self.user = user
        self.calls: list[str] = []

    def whoami(self) -> str:
        self.calls.append("whoami")
        return self.user

    def list_pods(self, namespace: str) -> list[dict[str, Any]]:
        self.calls.append("list_pods")
        return [POD]

    def list_events(self, namespace: str) -> list[dict[str, Any]]:
        self.calls.append("list_events")
        return [{"reason": "Started", "involvedObject": {"kind": "Pod", "name": "p"}}]

    def read_log(
        self, namespace: str, pod: str, *, container: str | None, previous: bool, tail: int
    ) -> str:
        self.calls.append(f"read_log previous={previous}")
        if previous:
            raise KubeError(400, f'previous terminated container "{container}" not found')
        return "\n".join(f"line {i}" for i in range(tail))

    def read(self, kind: Kind, namespace: str, name: str) -> dict[str, Any]:
        self.calls.append(f"read {kind}/{name}")
        return {"kind": kind, "metadata": {"name": name, "namespace": namespace}}

    def list_endpoint_slices(self, namespace: str, service: str) -> list[dict[str, Any]]:
        self.calls.append(f"list_endpoint_slices {service}")
        return []

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
        self.calls.append(f"access_review {user} {verb} {resource}")
        return {"allowed": False}


def recording(reader: TinyReader) -> Recording:
    rec = RecordingReader(reader, scenario="06-rbac-denied", namespace=NS, server_version="v1.34.0")
    rec.whoami()
    rec.list_pods(NS)
    rec.list_events(NS)
    rec.read_log(NS, "reporter-5d8f7c9b6-abcde", container="reporter", previous=False, tail=200)
    with pytest.raises(KubeError):
        rec.read_log(NS, "reporter-5d8f7c9b6-abcde", container="reporter", previous=True, tail=200)
    rec.read("serviceaccount", NS, "reporter")
    rec.access_review(
        NS,
        user="system:serviceaccount:x:reporter",
        groups=["g"],
        verb="get",
        resource="configmaps",
        group="",
        subresource="",
    )
    return rec.recording


# ---------- record and replay ----------


def test_replay_returns_what_was_recorded() -> None:
    replay = ReplayReader(recording(TinyReader()))
    assert replay.whoami() == AGENT_USER
    assert replay.list_pods(NS) == [POD]
    assert replay.list_events(NS)[0]["reason"] == "Started"
    assert replay.read("serviceaccount", NS, "reporter")["metadata"]["name"] == "reporter"
    status = replay.access_review(
        NS,
        user="system:serviceaccount:x:reporter",
        groups=["g"],
        verb="get",
        resource="configmaps",
        group="",
        subresource="",
    )
    assert status == {"allowed": False}


def test_replay_raises_recorded_errors() -> None:
    replay = ReplayReader(recording(TinyReader()))
    with pytest.raises(KubeError, match="previous terminated container") as err:
        replay.read_log(
            NS, "reporter-5d8f7c9b6-abcde", container="reporter", previous=True, tail=50
        )
    assert err.value.status == 400


def test_replay_serves_a_shorter_log_tail_from_a_longer_recording() -> None:
    replay = ReplayReader(recording(TinyReader()))
    text = replay.read_log(
        NS, "reporter-5d8f7c9b6-abcde", container="reporter", previous=False, tail=3
    )
    assert text.splitlines() == ["line 197", "line 198", "line 199"]


def test_replay_fails_clearly_for_calls_never_recorded() -> None:
    replay = ReplayReader(recording(TinyReader()))
    with pytest.raises(NotRecorded, match="read") as err:
        replay.read("deployment", NS, "nope")
    assert isinstance(err.value, KubeError)
    with pytest.raises(NotRecorded):
        replay.list_pods("some-other-namespace")


def test_recording_saves_and_loads(tmp_path: Path) -> None:
    rec = recording(TinyReader())
    path = tmp_path / "06" / "recording.json"
    rec.save(path)
    loaded = Recording.load(path)
    assert loaded == rec
    assert loaded.server_version == "v1.34.0"
    assert loaded.agent_user == AGENT_USER


def test_check_no_secrets_rejects_tokens_and_keys() -> None:
    check_no_secrets('{"logs": "loading settings"}')
    token = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjEifQ.eyJzdWIiOiJ4In0.c2lnbmF0dXJl"
    with pytest.raises(SecretInRecording):
        check_no_secrets(f'{{"logs": "Authorization: Bearer {token}"}}')
    with pytest.raises(SecretInRecording):
        check_no_secrets('"-----BEGIN RSA PRIVATE KEY-----\\nMIIE..."')


def test_save_refuses_a_recording_with_a_secret(tmp_path: Path) -> None:
    rec = recording(TinyReader())
    rec.calls[0].result = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJlLXNpZw"
    with pytest.raises(SecretInRecording):
        rec.save(tmp_path / "recording.json")
    assert not (tmp_path / "recording.json").exists()


# ---------- the record sweep ----------


def test_record_scenario_reads_everything_the_tools_can_ask_for() -> None:
    reader = TinyReader()
    rec = record_scenario(find(SCENARIOS, "rbac-denied"), reader, server_version="v1.34.0")

    assert reader.calls[0] == "whoami", "identity is checked before anything else"
    assert {"list_pods", "list_events"} <= set(reader.calls)
    assert "read_log previous=False" in reader.calls
    assert "read_log previous=True" in reader.calls
    assert "read pod/reporter-5d8f7c9b6-abcde" in reader.calls
    assert "read replicaset/reporter-5d8f7c9b6" in reader.calls
    for obj in ["serviceaccount/reporter", "configmap/report-settings", "deployment/reporter"]:
        assert f"read {obj}" in reader.calls
    assert f"access_review system:serviceaccount:{NS}:reporter get configmaps" in reader.calls
    assert f"access_review system:serviceaccount:{NS}:default list pods" in reader.calls

    assert rec.scenario == "06-rbac-denied"
    assert rec.namespace == NS
    failed = [c for c in rec.calls if c.error]
    assert [c.args["previous"] for c in failed] == [True], "the failed call is kept too"


def test_record_scenario_reads_endpoints_for_services() -> None:
    reader = TinyReader()
    record_scenario(find(SCENARIOS, "failing-probe"), reader, server_version="v1.34.0")
    assert "read service/frontend" in reader.calls
    assert "list_endpoint_slices frontend" in reader.calls


def test_record_scenario_refuses_the_wrong_identity() -> None:
    reader = TinyReader(user="kubernetes-admin")
    with pytest.raises(RuntimeError, match="kubernetes-admin"):
        record_scenario(find(SCENARIOS, "crashloop"), reader, server_version="v1.34.0")
    assert reader.calls == ["whoami"]


# ---------- logs without a container name ----------


def two_container_recording() -> Recording:
    rec = recording(TinyReader())
    for container in ("app", "sidecar"):
        rec.calls.append(
            rec.calls[3].model_copy(
                update={"args": {**rec.calls[3].args, "pod": "two", "container": container}}
            )
        )
    return rec


def test_replay_logs_default_to_the_only_container() -> None:
    # The API does the same: with no container named, a one-container pod's log is returned.
    replay = ReplayReader(recording(TinyReader()))
    text = replay.read_log(NS, "reporter-5d8f7c9b6-abcde", container=None, previous=False, tail=2)
    assert text.splitlines() == ["line 198", "line 199"]
    with pytest.raises(KubeError, match="previous terminated container"):
        replay.read_log(NS, "reporter-5d8f7c9b6-abcde", container=None, previous=True, tail=2)


def test_replay_logs_need_a_container_name_when_there_are_several() -> None:
    replay = ReplayReader(two_container_recording())
    with pytest.raises(KubeError, match="container name must be specified") as err:
        replay.read_log(NS, "two", container=None, previous=False, tail=5)
    assert err.value.status == 400
    assert "app" in err.value.message
    assert "sidecar" in err.value.message
    assert replay.read_log(NS, "two", container="sidecar", previous=False, tail=1) == "line 199"


# ---------- seed, settle, re-check, record ----------


class ScriptedKubectl(Kubectl):
    """Answers `get pods` from a script, one payload per call, and logs every command."""

    def __init__(self, pods: list[str], log: list[str]) -> None:
        super().__init__(context="kind-test")
        self.pods = pods
        self.log = log

    def run(self, *args: str, check: bool = True) -> str:
        self.log.append(" ".join(args[:2]))
        return self.pods.pop(0) if args[:2] == ("get", "pods") else ""


def _pods(reason: str) -> str:
    status = {"name": "api", "state": {"waiting": {"reason": reason}}}
    return json.dumps({"items": [{"status": {"containerStatuses": [status]}}]})


def test_record_waits_for_the_signal_again_after_settling() -> None:
    # A failing container moves between states (back-off, retry, back-off), so after
    # the settle pause the recorder waits for the signal again before reading.
    log: list[str] = []
    failing, retrying = _pods("ImagePullBackOff"), _pods("ContainerCreating")
    kubectl = ScriptedKubectl([failing, retrying, retrying, failing], log)

    class LoggingReader(TinyReader):
        def whoami(self) -> str:
            log.append("sweep starts")
            return super().whoami()

    result, rec = seed_and_record(
        find(SCENARIOS, "imagepull"),
        kubectl,
        LoggingReader(),
        server_version="v1.34.0",
        settle_s=15,
        poll_s=1,
        sleep=lambda s: log.append(f"sleep {s:g}"),
    )
    assert log == [
        "apply -f",
        "get pods",
        "sleep 15",
        "get pods",
        "sleep 1",
        "get pods",
        "sleep 1",
        "get pods",
        "sweep starts",
    ]
    assert result.scenario == "02-imagepull"
    assert rec.scenario == "02-imagepull"
