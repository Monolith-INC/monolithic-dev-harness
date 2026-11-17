"""Private POSIX socket served by the host gateway; never launches a provider."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import socket
import socketserver
import stat
import struct
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from core.result import Result
from harness import state
from harness.process_bus import IntegrationReadBus
from harness.process_messages import Context

MAX_MESSAGE = 16 * 1024 * 1024
# AF_UNIX paths are limited to 108 bytes on Linux, including the terminating NUL.
MAX_SOCKET_PATH = 107
HOSTS = frozenset(("claude", "codex", "cursor", "kimi", "default"))


def identity(repo: Path) -> str:
    """The project and configuration a gateway serves; independent of any process environment."""
    return hashlib.sha256(
        (str(repo.resolve()) + "\0" + _settings(repo)).encode()
    ).hexdigest()[:32]


def address(repo: Path) -> Path:
    """Base endpoint. Clients read the owner record instead of recomputing it, so a different
    temporary directory in their environment cannot hide the owner."""
    return (
        Path(tempfile.gettempdir()) / f"mdh-{os.getuid()}" / (identity(repo) + ".sock")
    )


def host_address(repo: Path, host: str) -> Path:
    """A distinct private endpoint for each host connection."""
    return address(repo).with_name(f"{identity(repo)}-{_host(host)}.sock")


def instance_address(repo: Path, host: str, instance: str) -> Path:
    """A distinct endpoint for each process launched by a host product."""
    return address(repo).with_name(
        f"{identity(repo)[:16]}-{_host(host)}-{_instance(instance)[:24]}.sock"
    )


def _host(host: str) -> str:
    match host in HOSTS:
        case True:
            return host
        case False:
            raise ValueError(f"Unsupported workflow-integrations host: {host!r}")


def _instance(instance: str) -> str:
    match len(instance) == 32 and all(char in "0123456789abcdef" for char in instance):
        case True:
            return instance
        case False:
            raise ValueError(
                "Gateway instance id must be 32 lowercase hexadecimal characters"
            )


def _settings(repo: Path) -> str:
    match (repo / ".harness/settings.json").is_file():
        case True:
            return (repo / ".harness/settings.json").read_text()
        case False:
            return ""


def private(path: Path) -> bool:
    return (
        not path.is_symlink()
        and path.stat().st_uid == os.getuid()
        and stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
    )


def owner_record(
    repo: Path, host: str = "default", instance: str | None = None
) -> Path:
    suffix = "" if host == "default" else f"-{_host(host)}"
    suffix += f"-{_instance(instance)}" if instance else ""
    return repo / ".harness/state/gateway-owners" / (identity(repo) + suffix + ".json")


@contextmanager
def serve(
    repo: Path, read: Callable[[str, dict], Result], host: str = "default"
) -> Iterator[Path]:
    """Effect boundary: owns listener/thread/socket cleanup; a duplicate owner fails closed."""
    host = _host(host)
    instance = uuid4().hex if host != "default" else ""
    location = (
        address(repo) if host == "default" else instance_address(repo, host, instance)
    )
    proof = owner_record(repo, host, instance or None)
    if len(os.fsencode(location)) > MAX_SOCKET_PATH:
        raise OSError(
            f"The gateway socket path {location} is longer than a Unix socket allows; start "
            "the gateway with a shorter TMPDIR. No provider was started."
        )
    location.parent.mkdir(mode=0o700, exist_ok=True)
    proof.parent.mkdir(parents=True, exist_ok=True)
    match private(location.parent):
        case False:
            raise PermissionError(
                "Gateway directory must be private and owned by the current user"
            )
        case True:
            pass
    bus = IntegrationReadBus(repo, read)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            # Peer identity comes from the kernel, not request arguments.
            match struct.unpack(
                "3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            ):
                case (_, uid, _) if uid == os.getuid():
                    try:
                        self.request.settimeout(65)
                        self.wfile.write(
                            (
                                json.dumps(
                                    bus.exchange(
                                        json.loads(self.rfile.readline(MAX_MESSAGE)),
                                        Context("local", str(uid), ""),
                                    )
                                )
                                + "\n"
                            ).encode()
                        )
                    except (OSError, ValueError):
                        return
                case _:
                    return

    # Legacy default owners lock beside their stable record. Instance owners lock the endpoint,
    # including the shortened socket name, so even an instance-id collision fails closed.
    lock_path = (
        proof.with_suffix(".lock")
        if host == "default"
        else location.with_suffix(".lock")
    )
    with lock_path.open("a+") as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as failure:
            raise OSError(
                "Another workflow-integrations gateway owns this instance endpoint; reload that host connection. No second provider was started."
            ) from failure
        match location.exists():
            case True if private(location) and stat.S_ISSOCK(location.stat().st_mode):
                location.unlink()  # The owner lock proves this is a stale owned socket.
            case True:
                raise PermissionError(
                    "Refusing to replace an unverified gateway endpoint"
                )
            case False:
                pass
        with socketserver.UnixStreamServer(str(location), Handler) as server:
            os.chmod(location, 0o600)
            state.write_json(
                proof,
                {
                    "pid": os.getpid(),
                    "uid": os.getuid(),
                    "host": host,
                    "instance": instance or None,
                    "endpoint": str(location),
                },
            )
            thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
            )
            thread.start()
            try:
                yield location
            finally:
                server.shutdown()
                thread.join(timeout=2)
                location.unlink(missing_ok=True)
                proof.unlink(missing_ok=True)
