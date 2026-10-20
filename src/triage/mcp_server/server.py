"""Example MCP server (MCP Python SDK v2) with read-only tools.

Replace these example tools with your project's tools. Keep the habits:
typed arguments (they become the JSON schema), a clear docstring (it becomes the
description the model reads), small outputs, and the read-only annotation on
anything that only looks.

Run it on its own over stdio:   uv run triage-mcp
Connect it to Claude Desktop or Claude Code as a stdio MCP server with that command.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from datetime import UTC, datetime

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)

server = MCPServer(
    "example-tools",
    instructions="Example read-only tools. Swap them for your project's tools.",
)

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node: ast.AST) -> float:
    """Evaluate a parsed arithmetic expression without ever calling eval()."""
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    # `type(...) is` rather than isinstance, so booleans (a subclass of int) are rejected.
    if isinstance(node, ast.Constant) and (type(node.value) is int or type(node.value) is float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        if isinstance(node.op, ast.Pow) and abs(_eval(node.right)) > 100:
            raise ValueError("exponent too large")
        return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    raise ValueError("only numbers and + - * / // % ** are allowed")


@server.tool(annotations=READ_ONLY)
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression such as '17 * 23' or '(2 + 3) ** 2'.
    Only numbers and + - * / // % ** and parentheses are allowed."""
    if len(expression) > 200:
        raise ValueError("expression too long")
    value = _eval(ast.parse(expression, mode="eval"))
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


@server.tool(annotations=READ_ONLY)
def word_count(text: str) -> str:
    """Count the words in a piece of text."""
    return str(len(text.split()))


@server.tool(annotations=READ_ONLY)
def utc_now() -> str:
    """Return the current date and time in UTC, ISO 8601."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def main() -> None:
    server.run()  # stdio


if __name__ == "__main__":
    main()
