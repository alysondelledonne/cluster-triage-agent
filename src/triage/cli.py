"""Diagnose a broken namespace: the `triage` command.

    uv run triage --namespace triage-01-crashloop
    uv run triage --namespace triage-06-rbac-denied --alert "reporter can't load settings"
    uv run triage --replay tests/fixtures/scenarios/06-rbac-denied/recording.json
    uv run triage --namespace triage-01-crashloop --json

With --namespace it reads the live cluster through the agent's own kubeconfig
(README, "Run the MCP server") and refuses to run as anyone but the agent's
ServiceAccount. With --replay it reads a recording instead, so no cluster is
needed; the model is still real, so it still costs a little.

Exit codes: 0 a diagnosis was submitted, 1 the agent didn't submit one,
2 setup problem (arguments, kubeconfig, identity, missing recording).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp.client import Client

from .agent.loop import AgentResult, run_agent
from .agent.mcp_tools import tools_from_mcp
from .agent.prompt import PROMPT_VERSION, SYSTEM_PROMPT, task_message
from .agent.report import render_report
from .agent.submit import diagnosis_finish
from .config import Settings, load_settings
from .mcp_server.kube import DEFAULT_AGENT_KUBECONFIG, KubeClientReader, KubeError, KubeReader
from .mcp_server.kube_server import NAME, IdentityError, build_server, require_agent_identity
from .mcp_server.replay import Recording, ReplayReader
from .providers import Provider, get_provider
from .tracing import setup_tracing


async def diagnose(
    namespace: str,
    reader: KubeReader,
    provider: Provider,
    settings: Settings,
    *,
    alert: str | None = None,
    source: str = "cluster",
) -> AgentResult:
    """One triage run: the read-only tools over `reader`, the triage prompt, and
    `submit_diagnosis` as the only way to finish."""
    server = build_server(namespace, reader)
    async with Client(server) as client:  # in-memory MCP connection, same tools as triage-mcp
        tools = await tools_from_mcp(client)
        return await run_agent(
            provider,
            SYSTEM_PROMPT,
            task_message(namespace, alert),
            tools,
            run_log=settings.run_log,
            finish=diagnosis_finish(namespace),
            max_tool_calls=settings.max_tool_calls,
            info={
                "namespace": namespace,
                "prompt_version": PROMPT_VERSION,
                "source": source,
                "alert": alert,
            },
        )


def _as_json(result: AgentResult, namespace: str) -> dict[str, Any]:
    d = result.submission
    return {
        "run_id": result.run_id,
        "namespace": namespace,
        "stopped": result.stopped,
        "diagnosis": d.model_dump(mode="json") if d is not None else None,
        "tool_calls": sum(1 for t in result.tool_calls if t.name != "submit_diagnosis"),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_s": round(result.total_latency_s, 2),
        "cost_usd": result.cost_usd,
        "provider": result.provider,
        "model": result.model,
    }


def _fail(message: str) -> int:
    print(f"triage: {message}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--namespace", help="the namespace to diagnose (live cluster)")
    where.add_argument("--replay", type=Path, help="a recording.json to diagnose instead")
    parser.add_argument("--alert", help="what the caller already knows; passed as a hint")
    parser.add_argument("--provider", choices=["anthropic", "openai", "grok"])
    parser.add_argument("--kubeconfig", default=str(DEFAULT_AGENT_KUBECONFIG))
    parser.add_argument("--context", help="context in that kubeconfig (default: its current)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a report")
    args = parser.parse_args(argv)
    if args.namespace and (len(args.namespace) > 63 or not NAME.match(args.namespace)):
        parser.error(f"--namespace {args.namespace!r} isn't a valid namespace name")

    settings = load_settings()
    reader: KubeReader
    if args.replay:
        try:
            recording = Recording.load(args.replay)
        except (OSError, ValueError) as err:
            return _fail(f"can't read recording {args.replay}: {err}")
        namespace, reader, source = (
            recording.namespace,
            ReplayReader(recording),
            f"replay:{args.replay}",
        )
    else:
        try:
            reader = KubeClientReader.from_kubeconfig(args.kubeconfig, args.context)
            require_agent_identity(reader)
        except (IdentityError, KubeError) as err:
            return _fail(f"refusing to run: {err}")
        except Exception as err:  # missing kubeconfig, expired token, cluster down
            return _fail(f"can't read the cluster as the agent: {err}")
        namespace, source = args.namespace, "cluster"

    if settings.tracing:
        setup_tracing("cluster-triage-agent")
    try:
        provider = get_provider(args.provider or settings.provider, settings)
    except ValueError as err:
        return _fail(str(err))

    result = asyncio.run(
        diagnose(namespace, reader, provider, settings, alert=args.alert, source=source)
    )
    if args.json:
        print(json.dumps(_as_json(result, namespace), indent=2))
    else:
        print(render_report(result, namespace, max_tool_calls=settings.max_tool_calls))
    return 0 if result.submission is not None else 1


if __name__ == "__main__":
    sys.exit(main())
