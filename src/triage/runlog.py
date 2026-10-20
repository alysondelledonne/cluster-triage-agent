"""Append-only JSON-lines log: one line per agent run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_run(path: str | Path, record: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
