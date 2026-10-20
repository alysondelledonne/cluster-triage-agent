import json
from pathlib import Path

from triage.pricing import cost_usd


def test_cost_from_pricing_file(tmp_path: Path) -> None:
    f = tmp_path / "pricing.json"
    f.write_text(json.dumps({"m": {"input": 1.0, "output": 5.0}}))
    assert cost_usd("m", 1_000_000, 200_000, pricing_file=f) == 2.0


def test_unknown_model_has_no_cost(tmp_path: Path) -> None:
    f = tmp_path / "pricing.json"
    f.write_text("{}")
    assert cost_usd("missing", 10, 10, pricing_file=f) is None
