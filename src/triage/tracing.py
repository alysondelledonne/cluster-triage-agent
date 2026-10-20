"""Optional tracing with Arize Phoenix (self-hosted, OpenTelemetry).

Off by default. Turn on with TRACING=1 after `uv sync --extra tracing` and
starting Phoenix (`docker run -p 6006:6006 arizephoenix/phoenix`). If the
packages aren't installed, every function here is a no-op, so the rest of the
code never has to check.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from typing import Any

log = logging.getLogger(__name__)
_tracer: Any = None


def setup_tracing(project_name: str = "ai-project") -> bool:
    """Register Phoenix and auto-instrument the Anthropic and OpenAI SDKs."""
    global _tracer
    try:
        from phoenix.otel import register
    except ImportError:
        log.warning("Tracing requested but extras not installed: uv sync --extra tracing")
        return False
    tracer_provider = register(project_name=project_name)
    for module, cls in (
        ("openinference.instrumentation.anthropic", "AnthropicInstrumentor"),
        ("openinference.instrumentation.openai", "OpenAIInstrumentor"),
    ):
        with contextlib.suppress(ImportError):
            mod = __import__(module, fromlist=[cls])
            getattr(mod, cls)().instrument(tracer_provider=tracer_provider)
    _tracer = tracer_provider.get_tracer(project_name)
    return True


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """A trace span when tracing is on; does nothing otherwise."""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as s:
        for k, v in attributes.items():
            s.set_attribute(k, v if isinstance(v, str | int | float | bool) else str(v))
        yield s
