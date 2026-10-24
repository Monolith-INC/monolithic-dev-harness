"""The same process protocol and consumer apply to every adapter."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from core.result import Err, Ok
from harness import process_bus as bus
from harness import process_messages as msg
from harness import process_store, work_sessions
from tests.settings_fixture import write_settings


@pytest.fixture
def ctx(tmp_path: Path) -> msg.Context:
    write_settings(tmp_path)
    return msg.Context(
        "test-adapter",
        "main-agent",
        work_sessions.start(tmp_path, "message bus proof").value.id,
    )


def opened(repo: Path, ctx: msg.Context):
    return bus.local_bus(repo).request(
        msg.register(ctx, "worker", "run-1", "start"), ctx
    )


def test_catalog_wire_and_actual_consumer(tmp_path: Path, ctx: msg.Context) -> None:
    assert msg.register(ctx, "worker", "run-1", "start")["id"] == "start"
    assert isinstance(opened(tmp_path, ctx), Ok)
    assert (
        bus.authorize(tmp_path, ctx, "worker").value.runtime_status
        == msg.ProcessStatus.RUNNING
    )
    assert len(bus.list_records(tmp_path, ctx).value) == 1
    assert opened(tmp_path, ctx).value.response() == {
        "jsonrpc": "2.0",
        "id": "start",
        "result": {
            "process_id": "worker",
            "revision": 0,
            "permission_revoked": False,
            "runtime_status": "running",
            "reported_status": None,
            "duplicate": True,
        },
    }


def test_queries_use_the_same_bus_catalog_and_correlation(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    saved = process_store._path(tmp_path, ctx, "worker").read_bytes()
    one = bus.local_bus(tmp_path).request(
        msg.inspect_process(ctx, "worker", "inspect"), ctx
    )
    many = bus.local_bus(tmp_path).request(msg.list_processes(ctx, "listing"), ctx)
    assert one.value.response()["id"] == "inspect"
    assert one.value.response()["result"]["process_id"] == "worker"
    assert many.value.response()["id"] == "listing"
    assert len(many.value.response()["result"]["processes"]) == 1
    assert process_store._path(tmp_path, ctx, "worker").read_bytes() == saved


def test_list_contract_rejects_private_scope_extensions(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    message = msg.list_processes(ctx, "query")
    assert isinstance(
        bus.local_bus(tmp_path).request(
            {**message, "params": {**message["params"], "all_owners": True}}, ctx
        ),
        Err,
    )


@pytest.mark.parametrize("adapter", ("claude", "codex", "cursor", "unlisted-adapter"))
def test_consumer_does_not_branch_on_vendor(
    tmp_path: Path, ctx: msg.Context, adapter: str
) -> None:
    context = replace(ctx, adapter=adapter)
    assert isinstance(opened(tmp_path, context), Ok)
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.cancel(context, "worker", "cancel", 0), context
        ),
        Ok,
    )
    assert isinstance(bus.authorize(tmp_path, context, "worker"), Err)


def test_cancel_is_permission_withdrawal_not_runtime_confirmation(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    result = (
        bus.local_bus(tmp_path)
        .request(msg.cancel(ctx, "worker", "cancel", 0), ctx)
        .value
    )
    assert result.record.revoked
    assert result.record.runtime_status == msg.ProcessStatus.RUNNING
    assert isinstance(bus.authorize(tmp_path, ctx, "worker"), Err)
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.status_update(
                ctx, "worker", "run-1", msg.ProcessStatus.RUNNING, "revive", 1
            ),
            ctx,
        ),
        Err,
    )
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.register(ctx, "worker", "run-2", "register-again"), ctx
        ),
        Err,
    )


def test_agent_report_does_not_confirm_host_status_or_grant_permission(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    assert isinstance(
        bus.local_bus(tmp_path).request(msg.cancel(ctx, "worker", "cancel", 0), ctx), Ok
    )
    report = (
        bus.local_bus(tmp_path)
        .request(
            msg.status_update(
                ctx,
                "worker",
                "run-1",
                msg.ProcessStatus.INTERRUPTED,
                "report",
                1,
                msg.Origin.AGENT,
            ),
            ctx,
        )
        .value.record
    )
    assert report.reported_status == msg.ProcessStatus.INTERRUPTED
    assert report.runtime_status == msg.ProcessStatus.RUNNING and report.revoked
    observed = (
        bus.local_bus(tmp_path)
        .request(
            msg.status_update(
                ctx, "worker", "run-1", msg.ProcessStatus.INTERRUPTED, "observed", 2
            ),
            ctx,
        )
        .value.record
    )
    assert observed.runtime_status == msg.ProcessStatus.INTERRUPTED and observed.revoked


def test_duplicate_and_stale_messages_preserve_bytes(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    request = msg.cancel(ctx, "worker", "cancel", 0)
    assert isinstance(bus.local_bus(tmp_path).request(request, ctx), Ok)
    saved = process_store._path(tmp_path, ctx, "worker").read_bytes()
    assert bus.local_bus(tmp_path).request(request, ctx).value.duplicate
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.status_update(
                ctx, "worker", "run-1", msg.ProcessStatus.RUNNING, "stale", 0
            ),
            ctx,
        ),
        Err,
    )
    assert isinstance(
        bus.local_bus(tmp_path).request(msg.cancel(ctx, "worker", "cancel", 1), ctx),
        Err,
    )
    assert process_store._path(tmp_path, ctx, "worker").read_bytes() == saved


@pytest.mark.parametrize(
    "field,value", (("owner_id", "other-main"), ("work_session_id", "other-session"))
)
def test_other_scope_cannot_read_list_cancel_or_authorize(
    tmp_path: Path, ctx: msg.Context, field: str, value: str
) -> None:
    opened(tmp_path, ctx)
    other = replace(ctx, **{field: value})
    assert isinstance(bus.get_record(tmp_path, other, "worker"), Err)
    assert bus.list_records(tmp_path, other) == Ok(())
    assert isinstance(
        bus.local_bus(tmp_path).request(msg.cancel(other, "worker", "bad", 0), other),
        Err,
    )
    assert isinstance(bus.authorize(tmp_path, other, "worker"), Err)
    assert not bus.get_record(tmp_path, ctx, "worker").value.revoked


def test_context_payload_is_not_caller_identity(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.cancel(ctx, "worker", "bad", 0), replace(ctx, owner_id="someone-else")
        ),
        Err,
    )


def test_completed_execution_and_old_notifications_cannot_replay(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.status_update(
                ctx, "worker", "run-1", msg.ProcessStatus.COMPLETED, "stop-1", 0
            ),
            ctx,
        ),
        Ok,
    )
    assert isinstance(bus.authorize(tmp_path, ctx, "worker"), Err)
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.status_update(
                ctx, "worker", "run-1", msg.ProcessStatus.RUNNING, "replay", 1
            ),
            ctx,
        ),
        Err,
    )
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.status_update(
                ctx, "worker", "run-2", msg.ProcessStatus.RUNNING, "start-2", 1
            ),
            ctx,
        ),
        Ok,
    )
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.status_update(
                ctx, "worker", "run-1", msg.ProcessStatus.COMPLETED, "old-stop", 2
            ),
            ctx,
        ),
        Err,
    )
    assert bus.authorize(tmp_path, ctx, "worker").value.execution_id == "run-2"


def test_new_execution_drops_previous_main_agent_report(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.status_update(
                ctx,
                "worker",
                "run-1",
                msg.ProcessStatus.COMPLETED,
                "report-1",
                0,
                msg.Origin.AGENT,
            ),
            ctx,
        ),
        Ok,
    )
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.status_update(
                ctx, "worker", "run-1", msg.ProcessStatus.COMPLETED, "stop-1", 1
            ),
            ctx,
        ),
        Ok,
    )
    result = bus.local_bus(tmp_path).request(
        msg.status_update(
            ctx, "worker", "run-2", msg.ProcessStatus.RUNNING, "start-2", 2
        ),
        ctx,
    )
    assert isinstance(result, Ok)
    assert result.value.record.reported_status is None


@pytest.mark.parametrize(
    "status", (msg.ProcessStatus.INTERRUPTED, msg.ProcessStatus.FAILED)
)
def test_observed_terminal_failure_revokes(
    tmp_path: Path, ctx: msg.Context, status: msg.ProcessStatus
) -> None:
    opened(tmp_path, ctx)
    assert (
        bus.local_bus(tmp_path)
        .request(msg.status_update(ctx, "worker", "run-1", status, "terminal", 0), ctx)
        .value.record.revoked
    )


def test_inactive_session_cannot_register_but_can_withdraw(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    work_sessions.transition(tmp_path, ctx.work_session_id, "pause")
    assert isinstance(
        bus.local_bus(tmp_path).request(
            msg.register(ctx, "new-worker", "run", "new"), ctx
        ),
        Err,
    )
    assert isinstance(
        bus.local_bus(tmp_path).request(msg.cancel(ctx, "worker", "cancel", 0), ctx), Ok
    )


@pytest.mark.parametrize(
    "changes",
    (
        {"jsonrpc": "1.0"},
        {"id": None},
        {"method": "vendor.private"},
        {"extra": "noise"},
    ),
)
def test_invalid_envelope_is_rejected_without_state(
    tmp_path: Path, ctx: msg.Context, changes: dict
) -> None:
    assert isinstance(
        bus.local_bus(tmp_path).request(
            {**msg.register(ctx, "worker", "run", "start"), **changes}, ctx
        ),
        Err,
    )
    assert bus.list_records(tmp_path, ctx) == Ok(())


@pytest.mark.parametrize(
    "field,value",
    (
        ("version", True),
        ("version", 2),
        ("event_id", ""),
        ("process_id", None),
        ("execution_id", []),
        ("noise", "extra"),
    ),
)
def test_invalid_params_are_rejected(
    tmp_path: Path, ctx: msg.Context, field: str, value: object
) -> None:
    message = msg.register(ctx, "worker", "run", "start")
    assert isinstance(
        bus.local_bus(tmp_path).request(
            {**message, "params": {**message["params"], field: value}}, ctx
        ),
        Err,
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("status", "invented"),
        ("status", []),
        ("origin", "invented"),
        ("revision", True),
        ("revision", -1),
    ),
)
def test_invalid_status_message_returns_error(
    tmp_path: Path, ctx: msg.Context, field: str, value: object
) -> None:
    opened(tmp_path, ctx)
    message = msg.status_update(
        ctx, "worker", "run-1", msg.ProcessStatus.COMPLETED, "status", 0
    )
    assert isinstance(
        bus.local_bus(tmp_path).request(
            {**message, "params": {**message["params"], field: value}}, ctx
        ),
        Err,
    )


@pytest.mark.parametrize(
    "payload", (None, [], {}, {"version": True}, {"events": [None]})
)
def test_corrupt_record_fails_closed(
    tmp_path: Path, ctx: msg.Context, payload: object
) -> None:
    opened(tmp_path, ctx)
    process_store._path(tmp_path, ctx, "worker").write_text(json.dumps(payload))
    assert isinstance(bus.get_record(tmp_path, ctx, "worker"), Err)
    assert isinstance(bus.list_records(tmp_path, ctx), Err)
    assert isinstance(
        bus.local_bus(tmp_path).request(msg.cancel(ctx, "worker", "cancel", 0), ctx),
        Err,
    )


def test_protocol_factory_does_not_expose_context_mutation(ctx: msg.Context) -> None:
    message = msg.register(ctx, "worker", "run", "start")
    message["params"]["context"]["owner_id"] = "someone-else"
    assert ctx.owner_id == "main-agent"


def test_concurrent_same_revision_has_one_winner(
    tmp_path: Path, ctx: msg.Context
) -> None:
    opened(tmp_path, ctx)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda event: bus.local_bus(tmp_path).request(
                    msg.cancel(ctx, "worker", event, 0), ctx
                ),
                ("first", "second"),
            )
        )
    assert sum(isinstance(result, Ok) for result in results) == 1
    assert bus.get_record(tmp_path, ctx, "worker").value.revoked


def test_wire_binding_returns_standard_errors_without_state(
    tmp_path: Path, ctx: msg.Context
) -> None:
    wire = bus.local_bus(tmp_path)
    assert (
        wire.exchange(
            {"jsonrpc": "2.0", "id": "bad", "method": "vendor.private", "params": {}},
            ctx,
        )["error"]["code"]
        == -32601
    )
    assert (
        wire.exchange(
            {"jsonrpc": "2.0", "id": "bad", "method": "process.register", "params": {}},
            ctx,
        )["error"]["code"]
        == -32602
    )
    assert wire.exchange([], ctx)["error"]["code"] == -32600
    assert (
        wire.exchange({"jsonrpc": "2.0", "method": "process.cancel", "params": {}}, ctx)
        is None
    )
    assert bus.list_records(tmp_path, ctx) == Ok(())


def test_wire_binding_has_standard_correlated_success(
    tmp_path: Path, ctx: msg.Context
) -> None:
    response = bus.local_bus(tmp_path).exchange(
        msg.register(ctx, "worker", "run", "registered"), ctx
    )
    assert response["jsonrpc"] == "2.0" and response["id"] == "registered"
    assert response["result"]["process_id"] == "worker"
    assert "error" not in response


def test_invalid_query_context_returns_error(tmp_path: Path) -> None:
    assert isinstance(bus.get_record(tmp_path, None, "worker"), Err)
    assert isinstance(bus.list_records(tmp_path, None), Err)
