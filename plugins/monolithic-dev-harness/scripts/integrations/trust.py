"""Which onboarded tracker folders the user trusts, pinned to the folder's exact content.

Only the hooks record trust, from the user's own action: clicking Trust on a question about the
tracker (the question hook pins the folder's digest when the question is shown), or, in Cursor,
replying `approve <short id>`. The agent can never trust a tracker itself. Changing any file in the
folder changes its digest, and the tracker stops counting until the user trusts it again.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from core.result import Result, attempt, bind, require
from harness import state

TRUST_RELATIVE_PATH = Path(".harness") / "state" / "trackers"
DIGEST_PREFIX_LENGTH = 12


def digest(folder: Path) -> str:
    """One hash over every file's path and bytes; links are hashed as links, never followed."""
    files = sorted(
        path for path in folder.rglob("*") if path.is_symlink() or path.is_file()
    )
    return hashlib.sha256(
        b"".join(
            path.relative_to(folder).as_posix().encode()
            + b"\0"
            + _content(path)
            + b"\0"
            for path in files
        )
    ).hexdigest()


def _content(path: Path) -> bytes:
    return (
        b"symlink:" + str(path.readlink()).encode()
        if path.is_symlink()
        else path.read_bytes()
    )


def short_id(name: str, folder_digest: str) -> str:
    """A short reply id for one version of one tracker, for hosts without question buttons."""
    return (
        "HT-"
        + hashlib.sha256(f"{name}:{folder_digest}".encode()).hexdigest()[:6].upper()
    )


def trusted_names(repo: Path) -> tuple[str, ...]:
    """Every tracker with a trust record, whether or not its folder still exists."""
    folder = repo / TRUST_RELATIVE_PATH
    return (
        tuple(sorted(path.stem for path in folder.glob("*.json")))
        if folder.is_dir()
        else ()
    )


def _record_path(repo: Path, name: str) -> Path:
    return repo / TRUST_RELATIVE_PATH / f"{name}.json"


def trusted_digest(repo: Path, name: str) -> str:
    return str((state.read_json(_record_path(repo, name)) or {}).get("digest", ""))


def is_trusted(repo: Path, name: str, folder: Path) -> bool:
    stored = trusted_digest(repo, name)
    return bool(stored) and folder.is_dir() and stored == digest(folder)


def trust(repo: Path, name: str, folder: Path, prefix: str) -> Result[str]:
    """Trust the folder as it reads now, if the user named the digest it has now."""
    current = digest(folder) if folder.is_dir() else ""
    return bind(
        require(
            bool(current),
            "unknown_tracker",
            f"there is no onboarded tracker folder named {name!r}",
        ),
        lambda _: bind(
            require(
                len(prefix) >= DIGEST_PREFIX_LENGTH
                and current.startswith(prefix.lower()),
                "digest_mismatch",
                f"{name!r} reads differently from what you were shown (digest {current[:DIGEST_PREFIX_LENGTH]}); "
                "ask the user again",
            ),
            lambda _: _write(repo, name, current),
        ),
    )


def _write(repo: Path, name: str, value: str) -> Result[str]:
    path = _record_path(repo, name)
    record = {
        "name": name,
        "digest": value,
        "trusted": datetime.now(UTC).isoformat(),
    }
    return attempt(
        lambda: state.write_json(path, record) or value,
        "state_unwritable",
        str(path),
        OSError,
    )


def untrust(repo: Path, name: str) -> Result[bool]:
    path = _record_path(repo, name)
    return attempt(
        lambda: path.unlink() is None if path.exists() else False,
        "state_unwritable",
        str(path),
        OSError,
    )
