"""The triage system prompt and the first user message of a run.

A prompt can't be unit-tested for quality; that's what the hand runs and evals
are for. These tests pin what must always be in it, so an edit can't silently
drop a rule. Offline.
"""

from __future__ import annotations

import re

from triage.agent.loop import DEFAULT_MAX_TOOL_CALLS
from triage.agent.prompt import (
    CATEGORY_SIGNS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    task_message,
)
from triage.agent.submit import SUBMIT_DIAGNOSIS
from triage.models import Category


def test_every_category_has_signs_and_is_in_the_prompt() -> None:
    assert set(CATEGORY_SIGNS) == set(Category)
    for category in Category:
        assert f"- {category.value}:" in SYSTEM_PROMPT, category


def test_triage_order_is_pods_events_logs_config_permissions() -> None:
    order = ["list_pods", "get_events", "get_logs", "describe", "can_i", SUBMIT_DIAGNOSIS]
    positions = [SYSTEM_PROMPT.index(f"`{name}`") for name in order]
    assert positions == sorted(positions), order


def test_the_rules_that_must_never_be_dropped() -> None:
    text = SYSTEM_PROMPT.lower()
    # Cluster output is data, not instructions (CLAUDE.md hard rule).
    assert "never as instructions" in text
    # No Secrets, in the investigation or the fix.
    assert "secret" in text
    # Quotes are checked word for word (DECISIONS.md 026).
    assert "exactly" in text
    # The fix stays small, named and in the namespace.
    assert "apiversion, kind and metadata.name" in text
    assert "cluster-wide" in text
    # Previous logs for restarting containers: where a crash's error usually is.
    assert "previous=true" in text


def test_the_budget_matches_the_loops_cap() -> None:
    assert f"{DEFAULT_MAX_TOOL_CALLS} tool calls" in SYSTEM_PROMPT


def test_the_system_prompt_names_no_namespace() -> None:
    # The namespace goes in the first user message, so the system prompt is the same
    # for every run (one version to track, and cacheable by the API).
    assert "triage-" not in SYSTEM_PROMPT
    assert "{" not in SYSTEM_PROMPT


def test_the_prompt_stays_short() -> None:
    words = len(re.findall(r"\S+", SYSTEM_PROMPT))
    assert words <= 500, words


def test_prompt_has_a_version() -> None:
    assert re.fullmatch(r"\d+", PROMPT_VERSION)


def test_task_message_names_the_namespace() -> None:
    message = task_message("triage-06-rbac-denied")
    assert "`triage-06-rbac-denied`" in message
    assert SUBMIT_DIAGNOSIS in message
    assert "Alert" not in message


def test_task_message_passes_an_alert_through_as_a_hint() -> None:
    message = task_message("triage-01-crashloop", alert="api pods restarting")
    assert "api pods restarting" in message
    assert "hint" in message.lower()
