"""One process bus interface and generic consumer; no vendor events or tool names."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from core.result import Err, Ok, Result, bind, err, fmap, require
from harness import work_sessions
from harness.process_messages import (
    Context,
    Origin,
    ProcessStatus,
    Request,
    decode,
    inspect_process,
    list_processes,
    rejection,
    reply,
    valid_context,
)


@dataclass(frozen=True)
class ProcessRecord:
    process_id: str
    context: Context
    execution_id: str
    runtime_status: ProcessStatus = ProcessStatus.RUNNING
    reported_status: ProcessStatus | None = None
    revoked: bool = False
    revision: int = 0
    events: tuple[tuple[str, str], ...] = ()
    completed_executions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Receipt:
    record: ProcessRecord
    duplicate: bool = False
    event_id: str = ""

    def response(self) -> dict[str, Any]:
        return reply(
            self.event_id,
            {
                "process_id": self.record.process_id,
                "revision": self.record.revision,
                "permission_revoked": self.record.revoked,
                "runtime_status": self.record.runtime_status.value,
                "reported_status": self.record.reported_status.value
                if self.record.reported_status is not None
                else None,
                "duplicate": self.duplicate,
            },
        )


@dataclass(frozen=True)
class Listing:
    records: tuple[ProcessRecord, ...]
    event_id: str = ""

    def response(self) -> dict[str, Any]:
        return reply(
            self.event_id, {"processes": [asdict(record) for record in self.records]}
        )


class MessageBus(Protocol):
    def request(
        self, message: dict[str, Any], context: Context
    ) -> Result[Receipt | Listing]: ...

    def exchange(self, message: Any, context: Context) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class LocalMessageBus:
    project: Path

    def request(
        self, message: dict[str, Any], context: Context
    ) -> Result[Receipt | Listing]:
        return fmap(
            bind(
                decode(message, context),
                lambda request: _dispatch(self.project, context, request),
            ),
            lambda receipt: replace(receipt, event_id=message["id"]),
        )

    def exchange(self, message: Any, context: Context) -> dict[str, Any] | None:
        match self.request(message, context):
            case Ok(receipt):
                return receipt.response()
            case Err(failure):
                return rejection(message, failure)


def _dispatch(
    project: Path, context: Context, request: Request
) -> Result[Receipt | Listing]:
    from harness import process_store

    match request.method:
        case "process.get":
            return bind(
                process_store.read(project, context, request.process_id),
                lambda record: (
                    Ok(Receipt(record))
                    if record is not None
                    else err("process_not_found", "process is not registered")
                ),
            )
        case "process.list":
            return fmap(
                process_store.list_owned(project, context),
                lambda records: Listing(records),
            )
        case _:
            return process_store.transact(
                project,
                context,
                request,
                lambda record: _consume(project, context, request, record),
            )


def local_bus(repo: Path) -> MessageBus:
    return LocalMessageBus(repo.resolve())


def get_record(repo: Path, context: Context, process_id: str) -> Result[ProcessRecord]:
    match valid_context(context):
        case False:
            return err("invalid_process_context", "adapter context is missing")
        case True:
            return bind(
                local_bus(repo).request(
                    inspect_process(context, process_id, uuid4().hex), context
                ),
                _single,
            )


def _single(receipt: Receipt | Listing) -> Result[ProcessRecord]:
    match receipt:
        case Receipt(record=record):
            return Ok(record)
        case _:
            return err(
                "invalid_process_reply", "process query returned a different reply type"
            )


def list_records(repo: Path, context: Context) -> Result[tuple[ProcessRecord, ...]]:
    match valid_context(context):
        case False:
            return err("invalid_process_context", "adapter context is missing")
        case True:
            return bind(
                local_bus(repo).request(list_processes(context, uuid4().hex), context),
                _multiple,
            )


def _multiple(receipt: Receipt | Listing) -> Result[tuple[ProcessRecord, ...]]:
    match receipt:
        case Listing(records=records):
            return Ok(records)
        case _:
            return err(
                "invalid_process_reply", "process list returned a different reply type"
            )


def authorize(repo: Path, context: Context, process_id: str) -> Result[ProcessRecord]:
    return bind(
        get_record(repo, context, process_id),
        lambda record: bind(
            work_sessions.require_active(repo, context.work_session_id),
            lambda _: fmap(
                require(
                    not record.revoked
                    and record.runtime_status == ProcessStatus.RUNNING,
                    "process_revoked",
                    "process has no permission to make changes",
                ),
                lambda _: record,
            ),
        ),
    )


def _consume(
    repo: Path, context: Context, request: Request, record: ProcessRecord | None
) -> Result[Receipt]:
    match record:
        case ProcessRecord() if (
            record.context != context or record.process_id != request.process_id
        ):
            return err(
                "process_owner_mismatch",
                "process belongs to another adapter, conversation or work session",
            )
        case ProcessRecord() if any(
            event_id == request.event_id for event_id, _ in record.events
        ):
            return (
                Ok(Receipt(record, True))
                if (request.event_id, request.digest) in record.events
                else err(
                    "process_event_reused",
                    "event identity was reused with a different message",
                )
            )
        case _:
            return bind(
                work_sessions.select(repo, context.work_session_id),
                lambda session: _transition(session, context, request, record),
            )


def _transition(
    session: work_sessions.Session,
    context: Context,
    request: Request,
    record: ProcessRecord | None,
) -> Result[Receipt]:
    match request.method, record:
        case "process.register", None if session.status == work_sessions.Status.ACTIVE:
            return Ok(
                Receipt(
                    ProcessRecord(
                        request.process_id,
                        context,
                        request.execution_id,
                        events=((request.event_id, request.digest),),
                    )
                )
            )
        case "process.register", None:
            return err(
                "process_session_inactive",
                "registration requires an active work session",
            )
        case "process.register", ProcessRecord():
            return err(
                "process_exists",
                "registration cannot replace an existing process or restore its permissions",
            )
        case _, None:
            return err("process_not_found", "process is not registered")
        case _, ProcessRecord() if request.revision != record.revision:
            return err(
                "process_stale_revision",
                "message revision is outdated; inspect current process state",
            )
        case "process.cancel", ProcessRecord():
            return _receipt(record, request, revoked=True)
        case "process.status_update", ProcessRecord() if (
            request.execution_id != record.execution_id
            and request.origin == Origin.AGENT
        ):
            return err(
                "process_execution_mismatch", "report belongs to another execution"
            )
        case "process.status_update", ProcessRecord() if request.origin == Origin.AGENT:
            return _receipt(record, request, reported_status=request.status)
        case "process.status_update", ProcessRecord():
            return _host_status(session, record, request)
        case _:
            return err("invalid_process_message", "unsupported process transition")


def _host_status(
    session: work_sessions.Session, record: ProcessRecord, request: Request
) -> Result[Receipt]:
    match request.status:
        case ProcessStatus.RUNNING if record.revoked:
            return err(
                "process_revoked", "a status update cannot restore revoked permission"
            )
        case ProcessStatus.RUNNING if session.status != work_sessions.Status.ACTIVE:
            return err(
                "process_session_inactive", "execution requires an active work session"
            )
        case ProcessStatus.RUNNING if (
            request.execution_id == record.execution_id
            and record.runtime_status == ProcessStatus.RUNNING
        ):
            return _receipt(record, request)
        case ProcessStatus.RUNNING if (
            record.runtime_status == ProcessStatus.COMPLETED
            and request.execution_id not in record.completed_executions
            and request.execution_id != record.execution_id
        ):
            return _receipt(
                record,
                request,
                execution_id=request.execution_id,
                runtime_status=request.status,
                reported_status=None,
            )
        case ProcessStatus.RUNNING:
            return err(
                "process_execution_replayed",
                "execution cannot be replayed or replaced while it is active",
            )
        case _ if request.execution_id != record.execution_id:
            return err(
                "process_execution_mismatch",
                "status belongs to an older or different execution",
            )
        case _ if (
            record.runtime_status
            in (
                ProcessStatus.COMPLETED,
                ProcessStatus.FAILED,
                ProcessStatus.INTERRUPTED,
            )
            and request.status != record.runtime_status
        ):
            return err(
                "process_execution_closed",
                "a closed execution cannot change its terminal status",
            )
        case ProcessStatus.COMPLETED | ProcessStatus.FAILED | ProcessStatus.INTERRUPTED:
            return _receipt(
                record,
                request,
                runtime_status=request.status,
                revoked=record.revoked
                or request.status in (ProcessStatus.FAILED, ProcessStatus.INTERRUPTED),
                completed_executions=tuple(
                    dict.fromkeys((*record.completed_executions, record.execution_id))
                ),
            )
        case _:
            return _receipt(record, request, runtime_status=request.status)


def _receipt(
    record: ProcessRecord, request: Request, **changes: Any
) -> Result[Receipt]:
    return Ok(
        Receipt(
            replace(
                record,
                revision=record.revision + 1,
                events=(*record.events, (request.event_id, request.digest)),
                **changes,
            )
        )
    )
