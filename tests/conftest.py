"""Shared test setup: no test may reach the network (DECISIONS.md 045).

CLAUDE.md's rule is that unit tests and CI never call a model API or need a live
cluster. This makes the rule enforced rather than hoped for: for the whole test
session, Python's socket layer refuses any connection, or name lookup, for a host
that isn't this machine. Model SDKs, the Kubernetes client and plain sockets all
go through it, so an accidental real call fails at once with a clear message.

Local addresses stay allowed (some libraries talk to themselves over loopback),
and so do Unix sockets. The MCP client and server in tests talk in memory, not
over a socket, so they are unaffected.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator
from typing import Any

import pytest

LOCAL_NAMES = {"localhost", "localhost.localdomain", ""}


class NetworkBlocked(RuntimeError):
    pass


def _is_local(host: object) -> bool:
    if not isinstance(host, str):
        return False
    if host.lower() in LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _refuse(host: object) -> NetworkBlocked:
    return NetworkBlocked(
        f"tests must not use the network (tried to reach {host!r}); "
        "use the fake providers and the recordings in tests/fixtures/"
    )


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo


def _guarded_connect(self: socket.socket, address: Any) -> None:
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(address[0]):
        raise _refuse(address[0])
    _real_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: Any) -> int:
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(address[0]):
        raise _refuse(address[0])
    return _real_connect_ex(self, address)


def _guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    if host is not None and not _is_local(host if isinstance(host, str) else str(host)):
        raise _refuse(host)
    return _real_getaddrinfo(host, *args, **kwargs)


@pytest.fixture(autouse=True, scope="session")
def _no_network() -> Iterator[None]:
    patch = pytest.MonkeyPatch()
    patch.setattr(socket.socket, "connect", _guarded_connect)
    patch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    patch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)
    yield
    patch.undo()
