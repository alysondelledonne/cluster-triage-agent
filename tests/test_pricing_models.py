"""The prices on file for the models this project uses (config/pricing.json)."""

from __future__ import annotations

import pytest

from triage.pricing import cost_usd


def test_the_default_model_has_a_price() -> None:
    # One million tokens each way at the up-to-100K-token rate: $0.10 + $0.50.
    assert cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
