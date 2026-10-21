"""Adapters translate neutral messages to each vendor's format and back.
Uses the SDKs' own response types with a stub client, so no API calls."""

from types import SimpleNamespace
from typing import Any

from anthropic.types import Message as AnthropicMessage
from openai.types.chat import ChatCompletion

from triage.providers import AnthropicProvider, GrokProvider, OpenAICompatProvider
from triage.providers.base import Message, ToolCall, ToolSpec

TOOL = ToolSpec("calculator", "Do math", {"type": "object", "properties": {}})


class Recorder:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


def conversation() -> list[Message]:
    return [
        Message(role="user", content="What is 2+2?"),
        Message(
            role="assistant",
            content="Let me check.",
            tool_calls=[ToolCall("t1", "calculator", {"expression": "2+2"})],
        ),
        Message(role="tool", content="4", tool_call_id="t1"),
    ]


def test_anthropic_round_trip() -> None:
    resp = AnthropicMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-test",
            "content": [
                {"type": "text", "text": "Calling."},
                {
                    "type": "tool_use",
                    "id": "t2",
                    "name": "calculator",
                    "input": {"expression": "3*3"},
                },
            ],
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "usage": {"input_tokens": 12, "output_tokens": 7},
        }
    )
    rec = Recorder(resp)
    p = AnthropicProvider("claude-test", client=SimpleNamespace(messages=rec))
    turn = p.complete("sys", conversation(), [TOOL])

    assert rec.kwargs["system"] == "sys"
    sent = rec.kwargs["messages"]
    assert sent[1]["content"][1] == {
        "type": "tool_use",
        "id": "t1",
        "name": "calculator",
        "input": {"expression": "2+2"},
    }
    assert sent[2]["content"][0]["type"] == "tool_result"
    assert rec.kwargs["tools"][0]["input_schema"] == TOOL.input_schema
    assert turn.text == "Calling."
    assert turn.tool_calls == [ToolCall("t2", "calculator", {"expression": "3*3"})]
    assert (turn.input_tokens, turn.output_tokens) == (12, 7)


def test_anthropic_merges_consecutive_tool_results() -> None:
    msgs = [
        Message(role="user", content="q"),
        Message(
            role="assistant",
            tool_calls=[ToolCall("a", "x", {}), ToolCall("b", "y", {})],
        ),
        Message(role="tool", content="1", tool_call_id="a"),
        Message(role="tool", content="2", tool_call_id="b", is_error=True),
    ]
    out = AnthropicProvider.to_api_messages(msgs)
    assert len(out) == 3
    assert [b["tool_use_id"] for b in out[2]["content"]] == ["a", "b"]
    assert out[2]["content"][1]["is_error"] is True


def _chat_completion(tool_args: str) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-test",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "t9",
                                "type": "function",
                                "function": {"name": "calculator", "arguments": tool_args},
                            }
                        ],
                    },
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 24},
        }
    )


def test_openai_round_trip() -> None:
    rec = Recorder(_chat_completion('{"expression": "5*5"}'))
    client = SimpleNamespace(chat=SimpleNamespace(completions=rec))
    p = OpenAICompatProvider("gpt-test", client=client)
    turn = p.complete("sys", conversation(), [TOOL])

    sent = rec.kwargs["messages"]
    assert sent[0] == {"role": "system", "content": "sys"}
    assert sent[2]["tool_calls"][0]["function"]["arguments"] == '{"expression": "2+2"}'
    assert sent[3] == {"role": "tool", "tool_call_id": "t1", "content": "4"}
    assert rec.kwargs["max_completion_tokens"] == 1024
    assert turn.tool_calls == [ToolCall("t9", "calculator", {"expression": "5*5"})]
    assert (turn.input_tokens, turn.output_tokens) == (20, 4)


def test_openai_bad_tool_json_is_kept_not_crashed() -> None:
    rec = Recorder(_chat_completion("{not json"))
    p = OpenAICompatProvider(
        "gpt-test", client=SimpleNamespace(chat=SimpleNamespace(completions=rec))
    )
    turn = p.complete("sys", [Message(role="user", content="q")], [TOOL])
    assert turn.tool_calls[0].arguments == {"_raw_arguments": "{not json"}


def test_grok_uses_max_tokens() -> None:
    rec = Recorder(_chat_completion("{}"))
    p = GrokProvider("grok-test", client=SimpleNamespace(chat=SimpleNamespace(completions=rec)))
    p.complete("sys", [Message(role="user", content="q")], [])
    assert "max_tokens" in rec.kwargs and "max_completion_tokens" not in rec.kwargs
    assert "tools" not in rec.kwargs


def test_anthropic_note_after_tool_results_joins_their_turn() -> None:
    # The loop's forced last turn adds a note right after tool results. Anthropic wants
    # user and assistant turns to alternate, so the note joins the tool-result turn.
    from triage.providers.anthropic_provider import AnthropicProvider
    from triage.providers.base import Message

    out = AnthropicProvider.to_api_messages(
        [
            Message(role="user", content="diagnose"),
            Message(role="assistant", tool_calls=[ToolCall("t1", "list_pods", {})]),
            Message(role="tool", content="pods...", tool_call_id="t1"),
            Message(role="user", content="Submit now."),
        ]
    )
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert out[-1]["content"][-1] == {"type": "text", "text": "Submit now."}
    assert out[-1]["content"][0]["type"] == "tool_result"
