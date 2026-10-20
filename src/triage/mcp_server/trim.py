"""Shrink Kubernetes API output before the model sees it (DECISIONS.md 004).

Real objects carry a lot of bookkeeping the model doesn't need (`managedFields`
alone can be longer than the rest of the object). Everything here is pure: it
takes the camelCase dicts the API returns and gives back smaller dicts or text,
never changing its input.
"""

from __future__ import annotations

import copy
from typing import Any

import yaml

DEFAULT_LOG_LINES = 100
MAX_LOG_LINES = 200
MAX_LINE_CHARS = 500  # per log line and per event message
MAX_EVENTS = 30
MAX_OUTPUT_CHARS = 8000  # hard cap on any one tool result

CUT_MARK = " [...]"
OUTPUT_CUT_NOTE = f"\n[output cut at {MAX_OUTPUT_CHARS} characters]"
LAST_APPLIED = "kubectl.kubernetes.io/last-applied-configuration"

# Metadata fields that only matter to the API server, never to a diagnosis.
NOISY_METADATA = ("managedFields", "resourceVersion", "uid", "selfLink", "generation")

Obj = dict[str, Any]


def cut(text: str, limit: int = MAX_LINE_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + CUT_MARK


def strip_noise(obj: Obj) -> Obj:
    """A copy of `obj` without managed fields, versions, uids or the last-applied annotation."""
    out = copy.deepcopy(obj)
    meta = out.get("metadata", {})
    for key in NOISY_METADATA:
        meta.pop(key, None)
    annotations = meta.get("annotations")
    if annotations is not None:
        annotations.pop(LAST_APPLIED, None)
        if not annotations:
            del meta["annotations"]
    return out


# ---------- pods ----------


def _state(state: Obj) -> str | None:
    """One line for a container state, e.g. 'waiting: CrashLoopBackOff (back-off 1m20s ...)'."""
    if "waiting" in state:
        w = state["waiting"] or {}
        line = f"waiting: {w.get('reason', 'unknown')}"
        return f"{line} ({cut(w['message'])})" if w.get("message") else line
    if "terminated" in state:
        t = state["terminated"] or {}
        parts = [f"terminated: {t.get('reason', 'unknown')}"]
        if t.get("exitCode") is not None:
            parts.append(f"exit code {t['exitCode']}")
        if t.get("finishedAt"):
            parts.append(f"finished {t['finishedAt']}")
        line = ", ".join(parts)
        return f"{line} ({cut(t['message'])})" if t.get("message") else line
    if "running" in state:
        started = (state["running"] or {}).get("startedAt")
        return f"running since {started}" if started else "running"
    return None


def pod_summary(pod: Obj) -> Obj:
    """The parts of a pod that explain why it isn't working."""
    meta = pod.get("metadata", {})
    status = pod.get("status", {})
    statuses = [*status.get("initContainerStatuses", []), *status.get("containerStatuses", [])]
    main = status.get("containerStatuses", [])
    out: Obj = {
        "name": meta.get("name"),
        "phase": status.get("phase"),
        "ready": f"{sum(1 for c in main if c.get('ready'))}/{len(main)}",
        "restarts": sum(c.get("restartCount", 0) for c in statuses),
    }
    owners = meta.get("ownerReferences", [])
    if owners:
        out["owner"] = f"{owners[0]['kind']}/{owners[0]['name']}"
    if status.get("reason"):
        out["reason"] = status["reason"]
    out["containers"] = []
    for c in statuses:
        entry: Obj = {"name": c.get("name"), "restarts": c.get("restartCount", 0)}
        state = _state(c.get("state") or {})
        last = _state(c.get("lastState") or {})
        if state:
            entry["state"] = state
        if last:
            entry["last_state"] = last
        out["containers"].append(entry)
    unready = [
        cond
        for cond in status.get("conditions", [])
        if cond.get("status") == "False" and cond.get("type") != "Ready"
    ]
    if unready:
        out["failing_conditions"] = [
            f"{c['type']}: {c.get('reason', '')} {cut(c.get('message', ''))}".strip()
            for c in unready
        ]
    return out


# ---------- events ----------


def _when(event: Obj) -> str:
    """The latest time an event was seen. Core events fill one of these depending on age."""
    return str(
        event.get("lastTimestamp")
        or event.get("eventTime")
        or event.get("firstTimestamp")
        or (event.get("metadata") or {}).get("creationTimestamp")
        or ""
    )


def events(
    items: list[Obj], *, kind: str | None = None, name: str | None = None, limit: int = MAX_EVENTS
) -> list[Obj]:
    """Events newest first, optionally for one object, each cut to one short record."""
    chosen = []
    for e in items:
        obj = e.get("involvedObject") or {}
        if kind and obj.get("kind", "").lower() != kind.lower():
            continue
        if name and obj.get("name") != name:
            continue
        chosen.append(e)
    chosen.sort(key=_when, reverse=True)
    out = []
    for e in chosen[:limit]:
        obj = e.get("involvedObject") or {}
        record: Obj = {
            "last_seen": _when(e),
            "type": e.get("type"),
            "reason": e.get("reason"),
            "object": f"{obj.get('kind')}/{obj.get('name')}",
        }
        if e.get("count"):
            record["count"] = e["count"]
        record["message"] = cut(e.get("message") or "")
        out.append(record)
    return out


# ---------- describe ----------


def trim_object(kind: str, obj: Obj) -> Obj:
    """What `describe` returns for one object: noise removed, sensitive bits left out."""
    out = strip_noise(obj)
    if kind == "configmap":
        # Values can hold anything; the diagnosis only needs to know which keys exist.
        data = out.pop("data", None) or {}
        binary = out.pop("binaryData", None) or {}
        out["data_keys"] = {k: f"{len(v.encode())} bytes" for k, v in sorted(data.items())}
        if binary:
            out["binary_data_keys"] = sorted(binary)
    if kind == "serviceaccount":
        # Names of token and pull Secrets; the agent never looks at Secrets.
        out.pop("secrets", None)
        out.pop("imagePullSecrets", None)
    if kind == "pod":
        out["status"] = pod_summary(obj)
    return out


def endpoint_counts(slices: list[Obj]) -> Obj:
    """How many endpoints behind a Service are ready, from its EndpointSlices."""
    ready = not_ready = 0
    pods = []
    for s in slices:
        for ep in s.get("endpoints") or []:
            ok = (ep.get("conditions") or {}).get("ready", False)
            ready += 1 if ok else 0
            not_ready += 0 if ok else 1
            target = ep.get("targetRef") or {}
            if target.get("name"):
                pods.append(f"{target['name']} ({'ready' if ok else 'not ready'})")
    return {"ready": ready, "not_ready": not_ready, "pods": pods}


# ---------- logs and final text ----------


def log_lines(text: str, *, max_lines: int) -> str:
    """The last `max_lines` lines, each cut to MAX_LINE_CHARS."""
    lines = text.splitlines()[-max_lines:]
    if not lines:
        return "(no log lines)"
    return "\n".join(cut(line) for line in lines)


def to_text(data: Any) -> str:
    """YAML for the model (fewer tokens than JSON), cut at MAX_OUTPUT_CHARS."""
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + OUTPUT_CUT_NOTE
    return text
