"""The `triage` command, end to end and offline: a scripted model diagnoses a recorded
scenario through the real MCP tools, grounding checks and report.

No model API and no cluster: the model is a ScriptedProvider and the cluster is
the scenario 6 recording, replayed.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from triage import cli
from triage.agent.prompt import PROMPT_VERSION
from triage.agent.report import render_report, safe
from triage.config import load_settings
from triage.mcp_server.replay import Recording, ReplayReader
from triage.providers.base import ToolCall
from triage.providers.fake import ScriptedProvider, turn

REPO = Path(__file__).resolve().parents[1]
RECORDING = REPO / "tests" / "fixtures" / "scenarios" / "06-rbac-denied" / "recording.json"
NS = "triage-06-rbac-denied"
# The pod's name changes every time the scenario is re-seeded, so read it from the recording.
POD = ReplayReader(Recording.load(RECORDING)).list_pods(NS)[0]["metadata"]["name"]

FIX = f"""apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {{name: reporter-read-settings, namespace: {NS}}}
rules:
- {{apiGroups: [""], resources: [configmaps], resourceNames: [report-settings], verbs: [get]}}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {{name: reporter-read-settings, namespace: {NS}}}
roleRef: {{apiGroup: rbac.authorization.k8s.io, kind: Role, name: reporter-read-settings}}
subjects: [{{kind: ServiceAccount, name: reporter, namespace: {NS}}}]
"""

DIAGNOSIS = {
    "category": "RBACDenied",
    "affected_resource": {"kind": "ServiceAccount", "name": "reporter"},
    "root_cause": "The reporter ServiceAccount has no Role that lets it read the "
    "report-settings ConfigMap, so every API call it makes is forbidden.",
    "evidence": [
        {"tool": "get_logs", "quote": 'configmaps "report-settings" is forbidden'},
        {"tool": "can_i", "quote": "allowed: false"},
    ],
    "proposed_fix": {"explanation": "Let reporter get that one ConfigMap.", "yaml": FIX},
    "confidence": 0.9,
}


def good_run() -> ScriptedProvider:
    return ScriptedProvider(
        [
            turn(calls=[ToolCall("1", "list_pods", {})]),
            turn(calls=[ToolCall("2", "get_logs", {"pod": POD})]),
            turn(
                calls=[
                    ToolCall(
                        "3",
                        "can_i",
                        {"service_account": "reporter", "verb": "get", "resource": "configmaps"},
                    )
                ]
            ),
            turn(calls=[ToolCall("4", "submit_diagnosis", DIAGNOSIS)]),
        ]
    )


def replay() -> ReplayReader:
    return ReplayReader(Recording.load(RECORDING))


@pytest.fixture
def run_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("RUN_LOG", str(path))
    return path


# ---------- diagnose ----------


def test_diagnose_a_recorded_scenario(run_log: Path) -> None:
    provider = good_run()
    result = asyncio.run(
        cli.diagnose(NS, replay(), provider, load_settings(), source=f"replay:{RECORDING.name}")
    )
    assert result.stopped == "submitted"
    assert result.submission.category.value == "RBACDenied"
    assert [t.name for t in result.tool_calls] == [
        "list_pods",
        "get_logs",
        "can_i",
        "submit_diagnosis",
    ]
    # The model saw the triage prompt and was told the namespace.
    first = provider.calls[0][0]
    assert first.role == "user" and f"`{NS}`" in first.content
    assert "submit_diagnosis" in provider.tools_offered[0]

    record = json.loads(run_log.read_text())
    assert record["info"] == {
        "namespace": NS,
        "prompt_version": PROMPT_VERSION,
        "source": f"replay:{RECORDING.name}",
        "alert": None,
    }
    assert record["submission"]["affected_resource"] == {
        "kind": "ServiceAccount",
        "name": "reporter",
    }


def test_the_alert_reaches_the_model(run_log: Path) -> None:
    provider = good_run()
    asyncio.run(cli.diagnose(NS, replay(), provider, load_settings(), alert="reporter is failing"))
    assert "reporter is failing" in provider.calls[0][0].content


def test_settings_cap_the_tool_calls(run_log: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_TOOL_CALLS", "1")
    provider = ScriptedProvider([turn(calls=[ToolCall("1", "list_pods", {})]), turn("can't tell")])
    result = asyncio.run(cli.diagnose(NS, replay(), provider, load_settings()))
    assert result.stopped == "no_submission"
    assert provider.tools_offered[1] == ["submit_diagnosis"]


# ---------- the report ----------


def test_report_reads_well(run_log: Path) -> None:
    result = asyncio.run(cli.diagnose(NS, replay(), good_run(), load_settings()))
    report = render_report(result, NS, max_tool_calls=12)
    assert f"Namespace: {NS}" in report
    assert "RBACDenied: ServiceAccount/reporter (confidence 0.90)" in report
    assert "Root cause: The reporter ServiceAccount" in report
    assert '[get_logs] configmaps "report-settings" is forbidden' in report
    assert "kind: RoleBinding" in report
    assert "3 tool calls" in report
    assert "stopped: submitted" in report
    assert "Hit the" not in report


def test_report_warns_when_the_cap_was_hit(run_log: Path) -> None:
    result = asyncio.run(cli.diagnose(NS, replay(), good_run(), load_settings()))
    result.stopped = "submitted_at_cap"
    assert "Hit the 12-call limit" in render_report(result, NS, max_tool_calls=12)


def test_report_without_a_diagnosis_says_so(run_log: Path) -> None:
    result = asyncio.run(
        cli.diagnose(
            NS, replay(), ScriptedProvider([turn("a"), turn("b"), turn("c")]), load_settings()
        )
    )
    report = render_report(result, NS, max_tool_calls=12)
    assert "No diagnosis" in report
    assert "stopped: no_submission" in report
    assert "Last model text: c" in report


# ---------- main: arguments, exit codes, output ----------


def use_provider(monkeypatch: pytest.MonkeyPatch, provider: ScriptedProvider) -> None:
    monkeypatch.setattr(cli, "get_provider", lambda name, settings: provider)


def test_main_replay_prints_the_report_and_exits_0(
    run_log: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_provider(monkeypatch, good_run())
    assert cli.main(["--replay", str(RECORDING)]) == 0
    out = capsys.readouterr().out
    assert "RBACDenied: ServiceAccount/reporter" in out
    assert json.loads(run_log.read_text())["info"]["source"] == f"replay:{RECORDING}"


def test_main_json_output(
    run_log: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_provider(monkeypatch, good_run())
    assert cli.main(["--replay", str(RECORDING), "--json"]) == 0
    out: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert out["stopped"] == "submitted"
    assert out["namespace"] == NS
    assert out["diagnosis"]["category"] == "RBACDenied"
    assert out["run_id"]


def test_main_exits_1_without_a_diagnosis(
    run_log: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_provider(monkeypatch, ScriptedProvider([turn("a"), turn("b"), turn("c")]))
    assert cli.main(["--replay", str(RECORDING)]) == 1
    assert "No diagnosis" in capsys.readouterr().out


def test_main_refuses_the_wrong_identity(
    run_log: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Admin:
        def whoami(self) -> str:
            return "kubernetes-admin"

    monkeypatch.setattr(cli.KubeClientReader, "from_kubeconfig", lambda path, context: Admin())
    use_provider(monkeypatch, good_run())
    assert cli.main(["--namespace", NS]) == 2
    assert "kubernetes-admin" in capsys.readouterr().err
    assert not run_log.exists(), "nothing ran"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--namespace", NS, "--replay", str(RECORDING)],
        ["--namespace", "Not_A_Namespace"],
    ],
)
def test_main_rejects_bad_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as err:
        cli.main(argv)
    assert err.value.code == 2


def test_main_says_when_a_recording_is_missing(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--replay", "no/such/recording.json"]) == 2
    assert "no/such/recording.json" in capsys.readouterr().err


def test_report_strips_terminal_control_characters() -> None:
    # Quotes come from cluster output; a log line mustn't recolour or clear the terminal.
    assert (
        safe("\x1b[2Jcleared \x1b[31mred\x07 ok\tthen\nnext") == "[2Jcleared [31mred ok\tthen\nnext"
    )


# ---------- model API errors (DECISIONS.md 034) ----------


class RefusingProvider:
    """Fails like a real model API with a bad key."""

    name = "grok"
    model = "grok-test"

    def __init__(self, error: Exception) -> None:
        self.error = error

    def complete(self, system: str, messages: Any, tools: Any) -> Any:
        raise self.error


def _api_errors() -> list[Exception]:
    import anthropic
    import httpx2
    import openai

    request = httpx2.Request("POST", "https://api.example.test/v1/chat/completions")
    return [
        openai.APIError("Incorrect API key provided", request, body=None),
        anthropic.APIError("invalid x-api-key", request, body=None),
    ]


@pytest.mark.parametrize("error", _api_errors(), ids=["openai-compatible", "anthropic"])
def test_a_refused_api_call_is_one_clear_line(
    error: Exception,
    run_log: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "get_provider", lambda name, settings: RefusingProvider(error))
    assert cli.main(["--replay", str(RECORDING)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("triage: the model API refused the request (grok/grok-test): ")
    assert getattr(error, "message", "") in err
    assert err.count("\n") == 1, "one line, no traceback"


def test_diagnose_raises_a_model_api_error(run_log: Path) -> None:
    (error, _) = _api_errors()
    with pytest.raises(cli.ModelAPIError, match="Incorrect API key"):
        asyncio.run(cli.diagnose(NS, replay(), RefusingProvider(error), load_settings()))  # type: ignore[arg-type]
