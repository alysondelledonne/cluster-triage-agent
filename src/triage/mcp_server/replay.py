"""Record a cluster's API responses, then replay them offline (DECISIONS.md 022).

`RecordingReader` wraps a real `KubeReader` and keeps every call: method,
arguments, and the raw result or error. `ReplayReader` serves a saved recording
through the same interface, so the MCP tools, trimming included, run unchanged
on real cluster data in unit tests, and later in the offline agent runs and
eval gate (CLAUDE.md: tests never need a live cluster).

Recordings hold raw API responses, not the tools' text output, so they stay
valid when trimming changes and keep the full trail of what the cluster said.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .kube import Kind, KubeError, KubeReader, Obj

T = TypeVar("T")

# Shapes that must never land in a committed file: a JWT (ServiceAccount tokens
# are JWTs) and a PEM private key. Checked on every save and again by a test.
SECRET_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


class SecretInRecording(ValueError):
    pass


class NotRecorded(KubeError):
    """A replayed call that the recording doesn't have. Shown to the model as an API error."""

    def __init__(self, method: str, args: dict[str, Any]) -> None:
        super().__init__(404, f"not in this recording: {method}({_args_text(args)})")


def _args_text(args: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def check_no_secrets(text: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise SecretInRecording(
                f"recording contains something that looks like a secret ({pattern.pattern})"
            )


class CallError(BaseModel):
    status: int
    message: str


class Call(BaseModel):
    method: str
    args: dict[str, Any]
    result: Any = None
    error: CallError | None = None


class Recording(BaseModel):
    """Everything one scenario's cluster said, call by call."""

    scenario: str
    namespace: str
    recorded_at: str
    server_version: str
    agent_user: str = ""
    # True when the recorder read every object `describe` can reach in the namespace
    # (the scenario's objects, its pods and ReplicaSets, and the namespace's built-in
    # ServiceAccount and ConfigMap). Replay can then answer any other name with the
    # API's own "not found" (DECISIONS.md 038). Recordings made before that are False.
    inventory_complete: bool = False
    calls: list[Call] = []

    def save(self, path: Path) -> None:
        text = self.model_dump_json(indent=1) + "\n"
        check_no_secrets(text)  # before anything is written
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    @classmethod
    def load(cls, path: Path) -> Recording:
        return cls.model_validate_json(path.read_text())


def _key(method: str, args: dict[str, Any]) -> str:
    """How a call is looked up on replay. Log reads ignore `tail` (see ReplayReader.read_log)."""
    if method == "read_log":
        args = {k: v for k, v in args.items() if k != "tail"}
    return method + json.dumps(args, sort_keys=True)


class RecordingReader:
    """A `KubeReader` that passes every call through to `inner` and keeps a record of it."""

    def __init__(
        self, inner: KubeReader, *, scenario: str, namespace: str, server_version: str
    ) -> None:
        self.inner = inner
        self.recording = Recording(
            scenario=scenario,
            namespace=namespace,
            recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
            server_version=server_version,
        )

    def _record(self, method: str, args: dict[str, Any], fn: Callable[[], T]) -> T:
        try:
            result = fn()
        except KubeError as err:
            error = CallError(status=err.status, message=err.message)
            self.recording.calls.append(Call(method=method, args=args, error=error))
            raise
        self.recording.calls.append(Call(method=method, args=args, result=result))
        return result

    def whoami(self) -> str:
        user = self._record("whoami", {}, self.inner.whoami)
        self.recording.agent_user = user
        return user

    def list_pods(self, namespace: str) -> list[Obj]:
        return self._record(
            "list_pods", {"namespace": namespace}, lambda: self.inner.list_pods(namespace)
        )

    def list_events(self, namespace: str) -> list[Obj]:
        return self._record(
            "list_events", {"namespace": namespace}, lambda: self.inner.list_events(namespace)
        )

    def read_log(
        self, namespace: str, pod: str, *, container: str | None, previous: bool, tail: int
    ) -> str:
        args = {
            "namespace": namespace,
            "pod": pod,
            "container": container,
            "previous": previous,
            "tail": tail,
        }
        return self._record(
            "read_log",
            args,
            lambda: self.inner.read_log(
                namespace, pod, container=container, previous=previous, tail=tail
            ),
        )

    def read(self, kind: Kind, namespace: str, name: str) -> Obj:
        args = {"kind": kind, "namespace": namespace, "name": name}
        return self._record("read", args, lambda: self.inner.read(kind, namespace, name))

    def list_endpoint_slices(self, namespace: str, service: str) -> list[Obj]:
        args = {"namespace": namespace, "service": service}
        return self._record(
            "list_endpoint_slices",
            args,
            lambda: self.inner.list_endpoint_slices(namespace, service),
        )

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
    ) -> Obj:
        args = {
            "namespace": namespace,
            "user": user,
            "groups": groups,
            "verb": verb,
            "resource": resource,
            "group": group,
            "subresource": subresource,
        }
        return self._record(
            "access_review",
            args,
            lambda: self.inner.access_review(
                namespace,
                user=user,
                groups=groups,
                verb=verb,
                resource=resource,
                group=group,
                subresource=subresource,
            ),
        )


# How the API names each kind in a "not found" message, e.g. deployments.apps "x" not found.
API_RESOURCE = {
    "pod": "pods",
    "deployment": "deployments.apps",
    "replicaset": "replicasets.apps",
    "service": "services",
    "configmap": "configmaps",
    "serviceaccount": "serviceaccounts",
    "role": "roles.rbac.authorization.k8s.io",
    "rolebinding": "rolebindings.rbac.authorization.k8s.io",
}


def not_found(kind: str, name: str) -> KubeError:
    return KubeError(404, f'{API_RESOURCE[kind]} "{name}" not found')


class ReplayReader:
    """A `KubeReader` that answers from a `Recording` instead of a cluster.

    With a complete inventory, questions about objects that don't exist get the
    same answers a cluster gives: "not found" for a read or a pod's logs, no
    endpoints for a Service. Anything else the recording lacks raises NotRecorded.
    """

    def __init__(self, recording: Recording) -> None:
        self.recording = recording
        self.calls = {_key(c.method, c.args): c for c in recording.calls}
        self.known = {
            (c.args["kind"], c.args["name"])
            for c in recording.calls
            if c.method == "read" and c.error is None
        }

    def _missing(self, kind: str, namespace: str, name: str) -> bool:
        """Is this an object the cluster didn't have, rather than one we didn't ask about?"""
        return (
            self.recording.inventory_complete
            and namespace == self.recording.namespace
            and (kind, name) not in self.known
        )

    def _replay(self, method: str, args: dict[str, Any]) -> Any:
        call = self.calls.get(_key(method, args))
        if call is None:
            raise NotRecorded(method, args)
        if call.error:
            raise KubeError(call.error.status, call.error.message)
        return call.result

    def whoami(self) -> str:
        return self.recording.agent_user

    def list_pods(self, namespace: str) -> list[Obj]:
        result: list[Obj] = self._replay("list_pods", {"namespace": namespace})
        return result

    def list_events(self, namespace: str) -> list[Obj]:
        result: list[Obj] = self._replay("list_events", {"namespace": namespace})
        return result

    def read_log(
        self, namespace: str, pod: str, *, container: str | None, previous: bool, tail: int
    ) -> str:
        # Logs are recorded at the maximum tail, so any smaller tail the model asks
        # for is the end of that text rather than a separate recording.
        if self._missing("pod", namespace, pod):
            raise not_found("pod", pod)
        if container is None:
            container = self._only_container(namespace, pod, previous)
        args = {"namespace": namespace, "pod": pod, "container": container, "previous": previous}
        text: str = self._replay("read_log", args)
        return "\n".join(text.splitlines()[-tail:])

    def _only_container(self, namespace: str, pod: str, previous: bool) -> str | None:
        """What the API does when no container is named: use the pod's only container,
        or refuse if it has several. The recorder always names the container."""
        names = sorted(
            {
                c.args["container"]
                for c in self.recording.calls
                if c.method == "read_log"
                and c.args["namespace"] == namespace
                and c.args["pod"] == pod
                and c.args["previous"] == previous
            }
        )
        if len(names) > 1:
            raise KubeError(
                400,
                f"a container name must be specified for pod {pod}, "
                f"choose one of: [{' '.join(names)}]",
            )
        return names[0] if names else None

    def read(self, kind: Kind, namespace: str, name: str) -> Obj:
        if self._missing(kind, namespace, name):
            raise not_found(kind, name)
        result: Obj = self._replay("read", {"kind": kind, "namespace": namespace, "name": name})
        return result

    def list_endpoint_slices(self, namespace: str, service: str) -> list[Obj]:
        if self._missing("service", namespace, service):
            return []  # the API's answer: no EndpointSlices carry that service's label
        args = {"namespace": namespace, "service": service}
        result: list[Obj] = self._replay("list_endpoint_slices", args)
        return result

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
    ) -> Obj:
        args = {
            "namespace": namespace,
            "user": user,
            "groups": groups,
            "verb": verb,
            "resource": resource,
            "group": group,
            "subresource": subresource,
        }
        result: Obj = self._replay("access_review", args)
        return result
