"""Turn the tools of a connected MCP server into agent tools."""

from __future__ import annotations

from typing import Any

from mcp.client import Client
from mcp.types import TextContent

from ..providers.base import ToolSpec
from .loop import Tool


async def tools_from_mcp(client: Client, read_only_only: bool = True) -> list[Tool]:
    """List the server's tools and wrap each as a `Tool` the agent loop can call.

    With `read_only_only` (the default), tools not annotated read-only are left
    out, so an agent can't reach a write tool by accident.
    """
    listed = await client.list_tools()
    tools: list[Tool] = []
    for t in listed.tools:
        read_only = bool(t.annotations and t.annotations.read_only_hint)
        if read_only_only and not read_only:
            continue

        async def call(args: dict[str, Any], _name: str = t.name) -> str:
            res = await client.call_tool(_name, args)
            text = "\n".join(c.text for c in res.content if isinstance(c, TextContent))
            if res.is_error:
                raise RuntimeError(text or "tool error")
            return text

        tools.append(
            Tool(
                spec=ToolSpec(
                    name=t.name, description=t.description or "", input_schema=t.input_schema
                ),
                fn=call,
                read_only=read_only,
            )
        )
    return tools
