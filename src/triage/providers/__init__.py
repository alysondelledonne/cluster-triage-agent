"""Model adapters behind one interface. Switching models is a config change."""

from __future__ import annotations

from ..config import Settings
from .anthropic_provider import AnthropicProvider
from .base import Message, ModelTurn, Provider, ToolCall, ToolSpec
from .openai_compat import GrokProvider, OpenAICompatProvider

__all__ = [
    "AnthropicProvider",
    "GrokProvider",
    "Message",
    "ModelTurn",
    "OpenAICompatProvider",
    "Provider",
    "ToolCall",
    "ToolSpec",
    "get_provider",
]


def get_provider(name: str, settings: Settings) -> Provider:
    model = settings.model_for(name)
    if name != "fake" and not model:
        raise ValueError(f"No model set for provider '{name}'. Set it in .env.")
    if name == "anthropic":
        return AnthropicProvider(model, settings.max_output_tokens)
    if name == "openai":
        return OpenAICompatProvider(model, settings.max_output_tokens)
    if name == "grok":
        return GrokProvider(model, settings.max_output_tokens, base_url=settings.xai_base_url)
    raise ValueError(f"Unknown provider '{name}'. Use anthropic, openai or grok.")
