"""Settings read from environment variables (and a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    provider: str
    anthropic_model: str
    openai_model: str
    xai_model: str
    xai_base_url: str
    max_tool_calls: int  # investigative tool calls per triage run (DECISIONS.md 024)
    max_output_tokens: int
    run_log: str
    tracing: bool

    def model_for(self, provider: str) -> str:
        return {
            "anthropic": self.anthropic_model,
            "openai": self.openai_model,
            "grok": self.xai_model,
            "fake": "fake",
        }.get(provider, "")


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        provider=os.getenv("PROVIDER", "anthropic"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        openai_model=os.getenv("OPENAI_MODEL", ""),
        xai_model=os.getenv("XAI_MODEL", ""),
        xai_base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
        max_tool_calls=int(os.getenv("MAX_TOOL_CALLS", "12")),
        # A diagnosis with a Role and RoleBinding fix is several hundred tokens; a reply cut
        # off at the limit loses its tool call, so leave room (DECISIONS.md 028).
        max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", "2048")),
        run_log=os.getenv("RUN_LOG", "runs/runs.jsonl"),
        tracing=os.getenv("TRACING", "0") == "1",
    )
