"""Tests never reach the network (CLAUDE.md: no model API, no live cluster in tests or CI).

`tests/conftest.py` blocks every outbound connection that isn't to this machine, so
a test that accidentally builds a real API client or kubeconfig fails here, loudly,
instead of passing on a laptop with keys and failing (or spending money) in CI.
"""

from __future__ import annotations

import socket
import threading

import pytest
from conftest import NetworkBlocked


@pytest.mark.parametrize("host", ["api.anthropic.com", "api.x.ai", "203.0.113.7"])
def test_outbound_connections_are_refused(host: str) -> None:
    with pytest.raises(NetworkBlocked, match="tests must not use the network"):
        socket.create_connection((host, 443), timeout=1)


def test_name_lookups_for_other_hosts_are_refused() -> None:
    with pytest.raises(NetworkBlocked):
        socket.getaddrinfo("api.anthropic.com", 443)


def test_connections_to_this_machine_still_work() -> None:
    # Local sockets are how some libraries talk to themselves; they stay allowed.
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    accepted = threading.Thread(target=lambda: server.accept()[0].close())
    accepted.start()
    with socket.create_connection(("localhost", port), timeout=1):
        pass
    accepted.join()
    server.close()


def test_a_real_model_client_cannot_reach_its_api() -> None:
    import anthropic

    client = anthropic.Anthropic(api_key="sk-test", max_retries=0)
    with pytest.raises(anthropic.APIConnectionError):
        client.messages.create(
            model="claude-haiku-5-5", max_tokens=1, messages=[{"role": "user", "content": "hi"}]
        )
