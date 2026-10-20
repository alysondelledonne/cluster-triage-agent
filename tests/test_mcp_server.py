import asyncio

import pytest
from mcp.client import Client

from triage.agent.mcp_tools import tools_from_mcp
from triage.mcp_server.server import calculator, server


def test_every_tool_is_annotated_read_only() -> None:
    async def check() -> None:
        async with Client(server) as client:
            listed = await client.list_tools()
            assert listed.tools, "server exposes no tools"
            for t in listed.tools:
                assert t.annotations and t.annotations.read_only_hint, t.name

    asyncio.run(check())


def test_agent_tools_call_through_mcp() -> None:
    async def check() -> str:
        async with Client(server) as client:
            tools = {t.spec.name: t for t in await tools_from_mcp(client)}
            assert {"calculator", "word_count", "utc_now"} <= set(tools)
            return await tools["calculator"].fn({"expression": "17 * 23"})

    assert asyncio.run(check()) == "391"


def test_mcp_tool_errors_raise() -> None:
    async def check() -> None:
        async with Client(server) as client:
            tools = {t.spec.name: t for t in await tools_from_mcp(client)}
            with pytest.raises(RuntimeError):
                await tools["calculator"].fn({"expression": "__import__('os')"})

    asyncio.run(check())


@pytest.mark.parametrize(
    ("expr", "expected"),
    [("2 + 3 * 4", "14"), ("(125 + 75) / 8", "25"), ("2 ** 10", "1024"), ("7 / 2", "3.5")],
)
def test_calculator(expr: str, expected: str) -> None:
    assert calculator(expr) == expected


@pytest.mark.parametrize("expr", ["__import__('os')", "a + 1", "9 ** 999", "[1, 2]"])
def test_calculator_rejects_unsafe_input(expr: str) -> None:
    with pytest.raises(ValueError):
        calculator(expr)
