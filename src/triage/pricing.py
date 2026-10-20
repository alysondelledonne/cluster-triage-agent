"""Cost per call from token counts, using prices you keep in config/pricing.json."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

DEFAULT_PRICING_FILE = Path(__file__).resolve().parents[2] / "config" / "pricing.json"


@cache
def _load(path: str) -> dict[str, dict[str, float]]:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing_file: str | Path = DEFAULT_PRICING_FILE,
) -> float | None:
    """Return the cost in USD, or None when the model has no price on file.

    None is deliberate: a missing price should show up as "unknown" in reports,
    not silently as $0.
    """
    prices = _load(str(pricing_file)).get(model)
    if prices is None:
        return None
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
