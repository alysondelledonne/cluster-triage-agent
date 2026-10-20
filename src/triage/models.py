"""Shared types for diagnoses and scenarios.

`Category` is the fixed list of failure types the agent can report (see
ARCHITECTURE.md). The `Diagnosis` model joins this file in Milestone 2.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Category(StrEnum):
    CRASH_LOOP = "CrashLoop"
    IMAGE_PULL = "ImagePull"
    OOM_KILLED = "OOMKilled"
    CONFIG_ERROR = "ConfigError"
    PROBE_FAILURE = "ProbeFailure"
    RBAC_DENIED = "RBACDenied"
    NETWORK_POLICY = "NetworkPolicy"
    UNKNOWN = "Unknown"


class ResourceRef(BaseModel):
    """A Kubernetes object by kind and name, e.g. Deployment/api."""

    model_config = ConfigDict(frozen=True)  # hashable, so refs can go in sets

    kind: str
    name: str

    def __str__(self) -> str:
        return f"{self.kind}/{self.name}"
