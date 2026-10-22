"""Shared types for diagnoses and scenarios.

`Category` is the fixed list of failure types the agent can report (see
ARCHITECTURE.md). `Diagnosis` is what the agent hands back at the end of a run,
through the `submit_diagnosis` tool (agent/submit.py, DECISIONS.md 023). Its field
descriptions become the tool's JSON schema, so they are written for the model.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


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

    model_config = ConfigDict(frozen=True, extra="forbid")  # frozen: hashable, can go in sets

    kind: str = Field(description="Kubernetes kind, e.g. Deployment, ServiceAccount, ConfigMap.")
    name: str = Field(description="The object's name in the namespace.")

    def __str__(self) -> str:
        return f"{self.kind}/{self.name}"


# The MCP tools evidence can come from. A test keeps this equal to the server's tools.
EvidenceTool = Literal["list_pods", "get_events", "get_logs", "describe", "can_i"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: EvidenceTool = Field(description="The tool whose output contains the quote.")
    quote: str = Field(
        min_length=3,
        max_length=500,
        description="Text copied exactly from that tool's output, e.g. one log line or "
        "a container state. It is checked against the real output, so don't paraphrase.",
    )


class ProposedFix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(
        min_length=1,
        max_length=1000,
        description="What the fix changes and why it addresses the root cause, in plain English.",
    )
    yaml: str = Field(
        min_length=1,
        max_length=5000,
        description="The smallest YAML a person could `kubectl apply` to fix it. Each "
        "document names apiVersion, kind and metadata.name and holds only the fields that "
        "change, or is a new object (e.g. a Role). Stay in the run's namespace; never a "
        "Secret or a cluster-wide object.",
    )


class Diagnosis(BaseModel):
    """The agent's answer for one namespace. A human reads it and decides on the fix."""

    # Reject unknown fields so a typo in a field name comes back as an error the model
    # can correct, instead of the value being silently dropped.
    model_config = ConfigDict(extra="forbid")

    category: Category = Field(
        description="The kind of failure. Unknown if the evidence doesn't support any other."
    )
    affected_resource: ResourceRef = Field(
        description="The object to fix, e.g. kind Deployment, name api."
    )
    root_cause: str = Field(
        min_length=10,
        max_length=600,
        description="One or two plain-English sentences on why it is failing.",
    )
    evidence: list[Evidence] = Field(
        min_length=1,
        max_length=8,
        description="The lines from tool output that show the root cause, most telling first.",
    )
    proposed_fix: ProposedFix | None = Field(
        description="How to fix it. Null only when category is Unknown."
    )
    confidence: float = Field(
        ge=0, le=1, description="How sure you are, from 0 to 1. Below 0.5 means a guess."
    )

    @field_validator("proposed_fix", mode="before")
    @classmethod
    def empty_fix_means_no_fix(cls, fix: object) -> object:
        # A fix whose YAML is blank is no fix. Treating it as null lets Unknown through
        # and gives a real category the "required" message below, instead of "at least
        # 1 character", which once led a model to invent a placeholder object to pass
        # (DECISIONS.md 041). The schema the model sees is unchanged.
        if isinstance(fix, dict) and isinstance(fix.get("yaml"), str) and not fix["yaml"].strip():
            return None
        return fix

    @field_validator("proposed_fix")
    @classmethod
    def fix_required_unless_unknown(
        cls, fix: ProposedFix | None, info: ValidationInfo
    ) -> ProposedFix | None:
        # `category` is declared earlier, so it is already validated and in info.data.
        if fix is None and info.data.get("category") is not Category.UNKNOWN:
            raise ValueError("required unless category is Unknown")
        return fix
