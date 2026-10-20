"""Read access to one Kubernetes cluster, behind a small interface.

The MCP tools talk to a `KubeReader`, never to the Kubernetes client directly,
so unit tests can swap in a fake that serves recorded payloads. `KubeClientReader`
is the real one, built on the official `kubernetes` client (DECISIONS.md 019).

Every method here reads, except `access_review`, which creates a
SubjectAccessReview: a question to the API server ("may X do Y?") that stores
nothing. That matches the ClusterRole in deploy/rbac/, which is what actually
enforces read-only; this file just never asks for more.

Results are plain dicts in the API's camelCase shape (what `kubectl get -o json`
prints), so the trimming code and the test fixtures share one format.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Protocol, cast

from kubernetes import client, config

# The kinds `describe` can read. Secrets are deliberately not here (CLAUDE.md).
Kind = Literal[
    "pod",
    "deployment",
    "replicaset",
    "service",
    "configmap",
    "serviceaccount",
    "role",
    "rolebinding",
]

Obj = dict[str, Any]


def service_account_subject(namespace: str, name: str) -> tuple[str, list[str]]:
    """The user and groups the API server sees for a ServiceAccount, for access reviews.

    Groups matter: a RoleBinding can grant access to all ServiceAccounts in a
    namespace through `system:serviceaccounts:<namespace>`.
    """
    return (
        f"system:serviceaccount:{namespace}:{name}",
        ["system:serviceaccounts", f"system:serviceaccounts:{namespace}", "system:authenticated"],
    )


class KubeError(Exception):
    """An error from the API server, with its HTTP status and readable message."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class KubeReader(Protocol):
    def whoami(self) -> str: ...

    def list_pods(self, namespace: str) -> list[Obj]: ...

    def list_events(self, namespace: str) -> list[Obj]: ...

    def read_log(
        self, namespace: str, pod: str, *, container: str | None, previous: bool, tail: int
    ) -> str: ...

    def read(self, kind: Kind, namespace: str, name: str) -> Obj: ...

    def list_endpoint_slices(self, namespace: str, service: str) -> list[Obj]: ...

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
    ) -> Obj: ...


def _message(err: client.ApiException) -> str:
    """The API server's own message from an error body, e.g. 'pods "x" not found'."""
    try:
        return str(json.loads(err.body or "")["message"])
    except (ValueError, KeyError, TypeError):
        return f"{err.status} {err.reason}"


class KubeClientReader:
    """`KubeReader` backed by the official Kubernetes Python client."""

    def __init__(self, api: client.ApiClient) -> None:
        self.api = api
        self.core = client.CoreV1Api(api)
        self.apps = client.AppsV1Api(api)
        self.rbac = client.RbacAuthorizationV1Api(api)
        self.discovery = client.DiscoveryV1Api(api)
        self.authn = client.AuthenticationV1Api(api)
        self.authz = client.AuthorizationV1Api(api)

    @classmethod
    def from_kubeconfig(cls, path: str | None, context: str | None) -> KubeClientReader:
        """Connect with a kubeconfig file (default: the usual ~/.kube/config lookup)."""
        return cls(config.new_client_from_config(config_file=path, context=context))

    def _plain(self, obj: Any) -> Any:
        """Client model objects to plain camelCase dicts, as the API sent them."""
        return self.api.sanitize_for_serialization(obj)

    def _call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except client.ApiException as err:
            raise KubeError(err.status or 0, _message(err)) from err

    def whoami(self) -> str:
        """Ask the API server who these credentials are (a SelfSubjectReview)."""
        review = self._call(self.authn.create_self_subject_review, client.V1SelfSubjectReview())
        return str(review.status.user_info.username)

    def server_version(self) -> str:
        """The cluster's Kubernetes version, e.g. v1.34.0 (recorded with each scenario)."""
        info = self._call(client.VersionApi(self.api).get_code)
        return str(info.git_version)

    def list_pods(self, namespace: str) -> list[Obj]:
        pods = self._call(self.core.list_namespaced_pod, namespace)
        return cast(list[Obj], self._plain(pods.items))

    def list_events(self, namespace: str) -> list[Obj]:
        events = self._call(self.core.list_namespaced_event, namespace)
        return cast(list[Obj], self._plain(events.items))

    def read_log(
        self, namespace: str, pod: str, *, container: str | None, previous: bool, tail: int
    ) -> str:
        text = self._call(
            self.core.read_namespaced_pod_log,
            pod,
            namespace,
            container=container,
            previous=previous,
            tail_lines=tail,
        )
        return str(text or "")

    def read(self, kind: Kind, namespace: str, name: str) -> Obj:
        readers = {
            "pod": self.core.read_namespaced_pod,
            "deployment": self.apps.read_namespaced_deployment,
            "replicaset": self.apps.read_namespaced_replica_set,
            "service": self.core.read_namespaced_service,
            "configmap": self.core.read_namespaced_config_map,
            "serviceaccount": self.core.read_namespaced_service_account,
            "role": self.rbac.read_namespaced_role,
            "rolebinding": self.rbac.read_namespaced_role_binding,
        }
        return cast(Obj, self._plain(self._call(readers[kind], name, namespace)))

    def list_endpoint_slices(self, namespace: str, service: str) -> list[Obj]:
        slices = self._call(
            self.discovery.list_namespaced_endpoint_slice,
            namespace,
            label_selector=f"kubernetes.io/service-name={service}",
        )
        return cast(list[Obj], self._plain(slices.items))

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
        body = client.V1SubjectAccessReview(
            spec=client.V1SubjectAccessReviewSpec(
                user=user,
                groups=groups,
                resource_attributes=client.V1ResourceAttributes(
                    namespace=namespace,
                    verb=verb,
                    resource=resource,
                    group=group,
                    subresource=subresource or None,
                ),
            )
        )
        review = self._call(self.authz.create_subject_access_review, body)
        return cast(Obj, self._plain(review.status))
