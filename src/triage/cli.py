"""Ask the agent a question using the example MCP tools.

uv run triage "What is 17 * 23?"
uv run triage --provider grok "How many words are in 'to be or not to be'?"
"""

from __future__ import annotations

import argparse
import asyncio

from mcp.client import Client

from .agent.loop import run_agent
from .agent.mcp_tools import tools_from_mcp
from .config import load_settings
from .mcp_server.server import server
from .providers import get_provider
from .tracing import setup_tracing

SYSTEM_PROMPT = (
    "You are a careful assistant. Use the available tools for any arithmetic or "
    "counting instead of working it out yourself. Answer in one short sentence."
)


async def _main(question: str, provider_name: str | None) -> None:
    settings = load_settings()
    if settings.tracing:
        setup_tracing("ai-project")
    provider = get_provider(provider_name or settings.provider, settings)
    async with Client(server) as client:  # in-memory connection to the MCP server
        tools = await tools_from_mcp(client)
        result = await run_agent(
            provider,
            SYSTEM_PROMPT,
            question,
            tools,
            max_steps=settings.max_steps,
            run_log=settings.run_log,
        )
    print(result.final_text)
    cost = "unknown" if result.cost_usd is None else f"${result.cost_usd:.5f}"
    print(
        f"\n[{result.provider}/{result.model}] steps={result.steps} "
        f"tools={[c.name for c in result.tool_calls]} "
        f"tokens={result.input_tokens}+{result.output_tokens} "
        f"latency={result.total_latency_s:.2f}s cost={cost} stopped={result.stopped}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--provider", choices=["anthropic", "openai", "grok"])
    args = parser.parse_args()
    asyncio.run(_main(args.question, args.provider))


if __name__ == "__main__":
    main()
