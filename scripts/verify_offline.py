#!/usr/bin/env python3
"""Prove the test suite needs no network.

Blocks outbound network access, then runs the suite in-process with
``pytest.main`` and exits with pytest's own exit code. This is the
"prove it needs no network" gate for CI.

What is blocked
---------------
* ``socket.create_connection`` -- raises for every destination.
* ``socket.getaddrinfo``       -- raises for every non-loopback hostname,
                                  so no name can be resolved to an address.
* ``socket.socket``            -- instantiating a new AF_INET / AF_INET6
                                  socket raises.

What is deliberately allowed
----------------------------
AF_UNIX sockets and loopback, because asyncio's event loop builds its
self-pipe with ``socket.socketpair()``, which itself constructs a
``socket.socket`` from an existing file descriptor. Blocking that
outright does not test the suite -- it breaks the event loop and every
in-process (ASGI transport) test fails with a socket error unrelated to
the network. Nothing here can reach a remote host: no name resolves, no
IP socket can be created, and no connection can be opened.

Usage (from anywhere):

    python scripts/verify_offline.py

Stdlib only. pytest must be importable in the interpreter that runs this
(the project venv, or CI after installing requirements.lock).
"""

from __future__ import annotations

import os
import socket
import sys

# Work from the repo root (the parent of this script's directory) so the
# "tests" argument resolves no matter where the script is invoked from.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Hostnames/addresses that never leave the machine.
LOOPBACK_HOSTS = {"", "localhost", "localhost.localdomain", "127.0.0.1", "::1"}

_blocked_calls: list[str] = []


class NetworkBlocked(RuntimeError):
    """Raised whenever the suite tries to reach the network."""


def _refuse(what: str, detail: str):
    """Record the attempt and raise; used by every blocked entry point."""

    def _blocked(*_args, **_kwargs):
        _blocked_calls.append(what)
        raise NetworkBlocked(
            f"outbound network access is blocked by scripts/verify_offline.py: "
            f"{detail}. The test suite must not need the network."
        )

    _blocked.__name__ = f"blocked_{what}"
    return _blocked


def _is_loopback(host) -> bool:
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii", "replace")
        except Exception:  # pragma: no cover - defensive
            return False
    if host is None:
        return True
    return str(host).strip().lower() in LOOPBACK_HOSTS


def block_network() -> None:
    """Install the guards on the socket module (in-process, permanent)."""

    real_socket = socket.socket
    real_getaddrinfo = socket.getaddrinfo

    class _GuardedSocket(real_socket):  # type: ignore[misc, valid-type]
        """AF_INET/AF_INET6 construction is refused; AF_UNIX is allowed."""

        def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
            # socketpair() wraps already-open descriptors -- not new network.
            if fileno is not None:
                super().__init__(family, type, proto, fileno)
                return
            if family == getattr(socket, "AF_UNIX", object()):
                super().__init__(family, type, proto)
                return
            _blocked_calls.append("socket.socket")
            raise NetworkBlocked(
                "outbound network access is blocked by scripts/verify_offline.py: "
                "socket.socket() cannot create a new IP socket. The test suite "
                "must not need the network."
            )

    def _guarded_getaddrinfo(host, port, *args, **kwargs):
        # Resolving a loopback name is local; anything else is outbound.
        if _is_loopback(host):
            return real_getaddrinfo(host, port, *args, **kwargs)
        _blocked_calls.append("getaddrinfo")
        raise NetworkBlocked(
            f"outbound network access is blocked by scripts/verify_offline.py: "
            f"getaddrinfo({host!r}) cannot resolve a non-loopback hostname. "
            f"The test suite must not need the network."
        )

    socket.socket = _GuardedSocket  # type: ignore[assignment]
    socket.getaddrinfo = _guarded_getaddrinfo  # type: ignore[assignment]
    socket.create_connection = _refuse(  # type: ignore[assignment]
        "create_connection",
        "socket.create_connection() cannot open a connection",
    )


def main() -> int:
    try:
        import pytest
    except ImportError:
        print(
            "FAIL: pytest is not importable in this interpreter. Run this with "
            "the project venv, e.g. .venv-verify/bin/python scripts/verify_offline.py",
            file=sys.stderr,
        )
        return 2

    os.chdir(REPO_ROOT)
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    block_network()
    print(
        "Network blocked: outbound connections are disabled for this run "
        "(socket.create_connection and non-loopback getaddrinfo raise; new "
        "AF_INET/AF_INET6 sockets are refused; AF_UNIX/loopback stay available "
        "for asyncio's self-pipe)."
    )
    sys.stdout.flush()

    code = int(pytest.main(["-q", "tests"]))
    if _blocked_calls:
        # Unreachable for a green suite: any attempt means a test wanted the net.
        print(
            f"NOTE: {len(_blocked_calls)} blocked network call(s) were attempted: "
            f"{sorted(set(_blocked_calls))}"
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
