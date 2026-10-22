"""scripts/agent-kubeconfig.sh, run against a stand-in `kubectl` (DECISIONS.md 045).

The script builds the kubeconfig the agent uses: the cluster from your context, a
short-lived token for the agent's ServiceAccount, and none of your own credentials.
The README, the kind workflow and anyone cloning the repo all run it. Offline: a
stub `kubectl` on PATH logs each call and answers with canned output.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "agent-kubeconfig.sh"
AGENT = "system:serviceaccount:triage-system:triage-agent"

STUB = """#!/usr/bin/env bash
echo "$*" >> "$KUBECTL_LOG"
case "$*" in
  *"config view --minify --raw"*) echo "apiVersion: v1" ;;
  *"jsonpath={.contexts[0].context.user}"*) echo -n "kind-triage" ;;
  *"create token"*) echo -n "the-token" ;;
  *"auth whoami"*) echo -n "$WHOAMI" ;;
esac
"""


Result = tuple[subprocess.CompletedProcess[str], list[str]]


def run(tmp_path: Path, whoami: str = AGENT, *args: str) -> Result:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "kubectl"
    stub.write_text(STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "kubectl.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "KUBECTL_LOG": str(log),
        "WHOAMI": whoami,
    }
    out = tmp_path / "agent.yaml"
    result = subprocess.run(
        ["bash", str(SCRIPT), "--output", str(out), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result, log.read_text().splitlines() if log.exists() else []


def test_builds_a_kubeconfig_with_only_the_agents_token(tmp_path: Path) -> None:
    result, calls = run(tmp_path)
    assert result.returncode == 0, result.stderr
    out = tmp_path / "agent.yaml"
    assert out.exists()
    assert stat.S_IMODE(out.stat().st_mode) == 0o600, "it holds a token: owner-only"
    assert calls[0] == "--context kind-triage config view --minify --raw"
    # Your own user (kind's admin certificate) is removed from the copy.
    assert any(c.endswith("config unset users.kind-triage") for c in calls)
    assert any("-n triage-system create token triage-agent --duration=1h" in c for c in calls)
    assert any("set-credentials triage-agent --token=the-token" in c for c in calls)
    assert AGENT in result.stdout


def test_context_and_duration_can_be_chosen(tmp_path: Path) -> None:
    result, calls = run(tmp_path, AGENT, "--context", "kind-other", "--duration", "10m")
    assert result.returncode == 0, result.stderr
    assert calls[0] == "--context kind-other config view --minify --raw"
    assert any("--duration=10m" in c for c in calls)


def test_fails_if_the_result_isnt_the_agent(tmp_path: Path) -> None:
    result, _ = run(tmp_path, "kubernetes-admin")
    assert result.returncode == 1
    assert "kubernetes-admin" in result.stderr


def test_unknown_options_are_refused(tmp_path: Path) -> None:
    result, calls = run(tmp_path, AGENT, "--namespace", "x")
    assert result.returncode == 2
    assert calls == []


def test_script_is_executable() -> None:
    assert os.access(SCRIPT, os.X_OK)
