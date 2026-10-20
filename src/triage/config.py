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
    max_steps: int
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
        max_steps=int(os.getenv("MAX_STEPS", "8")),
        max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", "1024")),
        run_log=os.getenv("RUN_LOG", "runs/runs.jsonl"),
        tracing=os.getenv("TRACING", "0") == "1",
    )
