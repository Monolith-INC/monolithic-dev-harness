"""Protected local transport persistence; locks and writes are isolated here."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, sequence
from harness.process_assignment import decode_assignment
from harness.process_bus import ProcessRecord, Receipt
from harness.process_messages import (
    Context,
    ProcessStatus,
    Request,
    valid_context,
    valid_text,
)

ROOT = Path(".harness/state/host_sessions/processes")
FIELDS = frozenset(
    (
        "version",
        "process_id",
        "context",
        "execution_id",
        "runtime_status",
        "reported_status",
        "revoked",
        "revision",
        "events",
        "completed_executions",
    )
)


def _path(repo: Path, context: Context, process_id: str) -> Path:
    return (
        repo.resolve()
        / ROOT
        / (
            hashlib.sha256(
                json.dumps((context.adapter, process_id)).encode()
            ).hexdigest()
            + ".json"
        )
    )


def _decode(value: Any) -> Result[ProcessRecord]:
    match value:
        case {
            "version": int() as version,
            "process_id": str() as pid,
            "context": {
                "adapter": str() as adapter,
                "owner_id": str() as owner,
                "work_session_id": str() as session,
            },
            "execution_id": str() as execution,
            "runtime_status": str() as status,
            "reported_status": reported,
            "revoked": revoked,
            "revision": revision,
            "events": list() as events,
            "completed_executions": list() as completed,
        } if (
            set(value) in (FIELDS, FIELDS | {"assignment"})
            and (
                value.get("assignment") is None
                or isinstance(decode_assignment(value["assignment"]), Ok)
            )
            and type(version) is int
            and version == 1
            and set(value["context"]) == {"adapter", "owner_id", "work_session_id"}
            and all(
                valid_text(item) for item in (pid, adapter, owner, session, execution)
            )
            and status in tuple(item.value for item in ProcessStatus)
            and (
                reported is None
                or isinstance(reported, str)
                and reported in tuple(item.value for item in ProcessStatus)
            )
            and type(revoked) is bool
            and type(revision) is int
            and revision >= 0
            and all(
                isinstance(event, list)
                and len(event) == 2
                and valid_text(event[0])
                and isinstance(event[1], str)
                and len(event[1]) == 64
                and all(char in "0123456789abcdef" for char in event[1])
                for event in events
            )
            and len({event[0] for event in events}) == len(events) == revision + 1
            and all(valid_text(item) for item in completed)
            and len(set(completed)) == len(completed)
            and (status not in ("failed", "interrupted") or revoked)
            and (
                status not in ("completed", "failed", "interrupted")
                or execution in completed
            )
        ):
            return Ok(
                ProcessRecord(
                    pid,
                    Context(adapter, owner, session),
                    execution,
                    ProcessStatus(status),
                    None if reported is None else ProcessStatus(reported),
                    revoked,
                    revision,
                    tuple(tuple(event) for event in events),
                    tuple(completed),
                    decode_assignment(value["assignment"]).value
                    if value.get("assignment") is not None
                    else None,
                )
            )
        case _:
            return err(
                "process_unreadable",
                "process record does not match the central contract",
            )


def _read_path(path: Path) -> Result[ProcessRecord]:
    return bind(
        attempt(
            lambda: json.loads(path.read_text(encoding="utf-8")),
            "process_unreadable",
            "cannot read process record",
            OSError,
            ValueError,
            UnicodeError,
        ),
        _decode,
    )


def read(repo: Path, context: Context, process_id: str) -> Result[ProcessRecord | None]:
    match valid_context(context) and valid_text(process_id):
        case False:
            return err(
                "invalid_process_context",
                "process identity or adapter context is missing",
            )
        case _:
            return bind(
                attempt(
                    lambda: _path(repo, context, process_id).exists(),
                    "process_unreadable",
                    "cannot inspect process record",
                    OSError,
                ),
                lambda exists: (
                    bind(
                        _read_path(_path(repo, context, process_id)),
                        lambda record: (
                            Ok(record)
                            if record.context == context
                            and record.process_id == process_id
                            else err(
                                "process_owner_mismatch",
                                "process belongs to another conversation or work session",
                            )
                        ),
                    )
                    if exists
                    else Ok(None)
                ),
            )


def list_owned(repo: Path, context: Context) -> Result[tuple[ProcessRecord, ...]]:
    match valid_context(context):
        case False:
            return err("invalid_process_context", "adapter context is missing")
        case _:
            return bind(
                attempt(
                    lambda: tuple((repo.resolve() / ROOT).glob("*.json")),
                    "process_unreadable",
                    "cannot list process records",
                    OSError,
                ),
                lambda paths: fmap(
                    sequence(_read_path(path) for path in paths),
                    lambda records: tuple(
                        record for record in records if record.context == context
                    ),
                ),
            )


def _write(repo: Path, record: ProcessRecord) -> ProcessRecord:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=repo.resolve() / ROOT,
        prefix=".process-",
        delete=False,
    ) as stream:
        try:
            json.dump({"version": 1, **asdict(record)}, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.replace(stream.name, _path(repo, record.context, record.process_id))
        finally:
            Path(stream.name).unlink(missing_ok=True)
    return record


def _lock(handle: Any) -> int:
    match os.name:
        case "nt":
            handle.seek(0)
            handle.write(b"\0")
            handle.flush()
            handle.seek(0)
            importlib.import_module("msvcrt").locking(handle.fileno(), 1, 1)
        case _:
            importlib.import_module("fcntl").flock(handle.fileno(), 2)
    return 0


def _transaction(
    repo: Path,
    context: Context,
    request: Request,
    consume: Callable[[ProcessRecord | None], Result[Receipt]],
) -> Result[Receipt]:
    (repo.resolve() / ROOT).mkdir(parents=True, exist_ok=True)
    with (repo.resolve() / ROOT / ".lock").open("a+b") as lock:
        _lock(lock)
        return bind(
            read(repo, context, request.process_id),
            lambda record: bind(
                consume(record),
                lambda receipt: (
                    Ok(receipt)
                    if receipt.duplicate
                    else fmap(
                        attempt(
                            lambda: _write(repo, receipt.record),
                            "process_write_failed",
                            "cannot write process record",
                            OSError,
                            ValueError,
                        ),
                        lambda _: receipt,
                    )
                ),
            ),
        )


def transact(
    repo: Path,
    context: Context,
    request: Request,
    consume: Callable[[ProcessRecord | None], Result[Receipt]],
) -> Result[Receipt]:
    return bind(
        attempt(
            lambda: _transaction(repo, context, request, consume),
            "process_transport_failed",
            "process bus transaction failed",
            OSError,
            ImportError,
        ),
        lambda result: result,
    )
