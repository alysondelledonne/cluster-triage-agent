"""Output trimming: what the model sees from a Kubernetes object is small and noise-free.

Offline: works on the hand-written payloads in tests/fixtures/kube/.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from triage.mcp_server import trim

FIXTURES = Path(__file__).parent / "fixtures" / "kube"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def test_strip_noise_removes_bookkeeping_fields() -> None:
    deployment = load("deployment-api.json")
    out = trim.strip_noise(deployment)
    meta = out["metadata"]
    assert "managedFields" not in meta
    assert "resourceVersion" not in meta
    assert "uid" not in meta
    assert "kubectl.kubernetes.io/last-applied-configuration" not in meta["annotations"]
    assert meta["annotations"]["deployment.kubernetes.io/revision"] == "1"
    assert out["status"]["conditions"][0]["reason"] == "MinimumReplicasUnavailable"


def test_strip_noise_leaves_the_input_alone() -> None:
    deployment = load("deployment-api.json")
    before = copy.deepcopy(deployment)
    trim.strip_noise(deployment)
    assert deployment == before


def test_strip_noise_drops_empty_annotations() -> None:
    obj = {"metadata": {"name": "x", "annotations": {trim.LAST_APPLIED: "{}"}}}
    assert trim.strip_noise(obj) == {"metadata": {"name": "x"}}


def test_pod_summary_shows_why_a_container_is_failing() -> None:
    pod = load("pods.json")["items"][0]
    summary = trim.pod_summary(pod)
    assert summary["name"] == "api-7c9d8f6b5-x2k4p"
    assert summary["phase"] == "Running"
    assert summary["ready"] == "0/1"
    assert summary["restarts"] == 4
    assert summary["owner"] == "ReplicaSet/api-7c9d8f6b5"
    container = summary["containers"][0]
    assert container["state"].startswith("waiting: CrashLoopBackOff")
    assert container["last_state"] == (
        "terminated: Error, exit code 1, finished 2026-10-20T20:03:01Z"
    )


def test_pod_summary_handles_a_pod_with_no_status_yet() -> None:
    pod = {"metadata": {"name": "new"}, "status": {"phase": "Pending"}}
    assert trim.pod_summary(pod) == {
        "name": "new",
        "phase": "Pending",
        "ready": "0/0",
        "restarts": 0,
        "containers": [],
    }


def test_events_are_summarised_newest_first() -> None:
    events = trim.events(load("events.json")["items"])
    assert [e["reason"] for e in events] == [
        "BackOff",
        "Unhealthy",
        "Scheduled",
        "ScalingReplicaSet",
    ]
    assert events[0] == {
        "last_seen": "2026-10-20T20:03:10Z",
        "type": "Warning",
        "reason": "BackOff",
        "object": "Pod/api-7c9d8f6b5-x2k4p",
        "count": 6,
        "message": "Back-off restarting failed container api in pod "
        "api-7c9d8f6b5-x2k4p_triage-01-crashloop",
    }
    assert "count" not in events[1], "a null count is left out"


def test_events_filter_by_object_and_cap() -> None:
    items = load("events.json")["items"]
    only_deploy = trim.events(items, kind="Deployment", name="api")
    assert [e["reason"] for e in only_deploy] == ["ScalingReplicaSet"]
    by_name = trim.events(items, name="api-7c9d8f6b5-x2k4p")
    assert {e["object"] for e in by_name} == {"Pod/api-7c9d8f6b5-x2k4p"}

    many = [
        {
            "involvedObject": {"kind": "Pod", "name": "p"},
            "reason": f"R{i}",
            "lastTimestamp": f"2026-10-20T20:{i:02d}:00Z",
        }
        for i in range(45)
    ]
    capped = trim.events(many)
    assert len(capped) == trim.MAX_EVENTS
    assert capped[0]["reason"] == "R44"


def test_event_messages_are_cut() -> None:
    long = {"involvedObject": {"kind": "Pod", "name": "p"}, "message": "x" * 2000}
    (event,) = trim.events([long])
    assert len(event["message"]) <= trim.MAX_LINE_CHARS + len(trim.CUT_MARK)


def test_configmap_shows_keys_not_values() -> None:
    out = trim.trim_object("configmap", load("configmap-app-config.json"))
    assert out["data_keys"] == {"DATABASE_URL": "38 bytes", "LOG_FORMAT": "4 bytes"}
    assert out["binary_data_keys"] == ["logo.png"]
    assert "postgres" not in json.dumps(out)
    assert "data" not in out


def test_serviceaccount_drops_secret_names() -> None:
    out = trim.trim_object("serviceaccount", load("serviceaccount-reporter.json"))
    text = json.dumps(out)
    assert "secrets" not in out
    assert "imagePullSecrets" not in out
    assert "reporter-token" not in text
    assert out["metadata"]["name"] == "reporter"


def test_log_trimming_caps_lines_and_line_length() -> None:
    text = "\n".join(f"line {i}" for i in range(300)) + "\n" + "y" * 2000
    out = trim.log_lines(text, max_lines=50)
    lines = out.splitlines()
    assert len(lines) == 50
    assert lines[0] == "line 251"
    assert lines[-1].endswith(trim.CUT_MARK)
    assert len(lines[-1]) == trim.MAX_LINE_CHARS + len(trim.CUT_MARK)


def test_empty_logs_say_so() -> None:
    assert trim.log_lines("", max_lines=10) == "(no log lines)"


def test_to_text_is_yaml_and_capped() -> None:
    assert trim.to_text({"a": 1, "b": ["x"]}) == "a: 1\nb:\n- x\n"
    big = {"items": ["z" * 100 for _ in range(500)]}
    out = trim.to_text(big)
    assert len(out) <= trim.MAX_OUTPUT_CHARS + len(trim.OUTPUT_CUT_NOTE)
    assert out.endswith(trim.OUTPUT_CUT_NOTE)
