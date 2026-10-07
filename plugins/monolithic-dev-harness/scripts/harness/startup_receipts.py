"""Protected completion evidence for a successfully prepared startup invocation."""

import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.result import Result, attempt, fmap
from harness import state, work_sessions


@dataclass(frozen=True)
class Invocation:
    request: str
    selected_id: str | None = None
    new: bool = False


def complete(
    repo: Path, selected: work_sessions.Session, invocation: Invocation, result: dict
) -> Result[dict]:
    return fmap(
        attempt(
            lambda: _save(repo, selected, invocation, result),
            "startup_unwritable",
            "save successful startup selection",
            OSError,
        ),
        lambda receipt: {**result, "startup_receipt": receipt},
    )


def _save(
    repo: Path, selected: work_sessions.Session, invocation: Invocation, result: dict
) -> str:
    receipt = "BS-" + secrets.token_hex(12)
    state.write_json(
        selected.folder / "startups" / f"{receipt}.json",
        {
            "version": 1,
            "id": receipt,
            "created": datetime.now(UTC).isoformat(),
            "invocation": asdict(invocation),
            "session_id": selected.id,
            "result": result,
        },
    )
    work_sessions.remember_current(repo, selected.id)
    return receipt
