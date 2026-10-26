"""Shared assignment messages carry permission, never native implementation details."""

from dataclasses import asdict

from core.result import Err, Ok
from harness import process_bus, process_messages, work_sessions
from harness.process_assignment import Assignment
from tests.settings_fixture import write_settings


def test_standard_assignment_is_owned_immutable_and_persisted(tmp_path):
    write_settings(tmp_path)
    ctx = process_messages.Context(
        "codex", "main", work_sessions.start(tmp_path, "assignment").value.id
    )
    bus = process_bus.local_bus(tmp_path)
    assert isinstance(
        bus.request(process_messages.register(ctx, "worker", "run", "start"), ctx), Ok
    )
    assignment = Assignment("worker", ("proof.md",), "gpt-5.6-luna", "low")
    message = process_messages.assign(ctx, "worker", assignment, "assignment", 0)
    assert isinstance(bus.request(message, ctx), Ok)
    assert (
        process_bus.get_record(tmp_path, ctx, "worker").value.assignment == assignment
    )
    assert bus.request(message, ctx).value.duplicate
    assert isinstance(
        bus.request(
            process_messages.assign(ctx, "worker", assignment, "other", 1), ctx
        ),
        Err,
    )
    assert isinstance(
        bus.request(
            message, process_messages.Context("codex", "other", ctx.work_session_id)
        ),
        Err,
    )
    assert asdict(process_bus.get_record(tmp_path, ctx, "worker").value)["assignment"][
        "owned_paths"
    ] == ("proof.md",)


def test_revoked_process_cannot_gain_assignment(tmp_path):
    write_settings(tmp_path)
    ctx = process_messages.Context(
        "codex", "main", work_sessions.start(tmp_path, "assignment").value.id
    )
    bus = process_bus.local_bus(tmp_path)
    bus.request(process_messages.register(ctx, "worker", "run", "start"), ctx)
    bus.request(process_messages.cancel(ctx, "worker", "cancel", 0), ctx)
    assert isinstance(
        bus.request(
            process_messages.assign(
                ctx, "worker", Assignment("reviewer", (), "m", "low"), "assign", 1
            ),
            ctx,
        ),
        Err,
    )


def test_completed_ready_subagent_can_receive_assignment_before_followup(tmp_path):
    write_settings(tmp_path)
    ctx = process_messages.Context(
        "codex", "main", work_sessions.start(tmp_path, "ready").value.id
    )
    bus = process_bus.local_bus(tmp_path)
    bus.request(process_messages.register(ctx, "worker", "run", "start"), ctx)
    bus.request(
        process_messages.status_update(
            ctx, "worker", "run", process_messages.ProcessStatus.COMPLETED, "stop", 0
        ),
        ctx,
    )
    assert isinstance(
        bus.request(
            process_messages.assign(
                ctx, "worker", Assignment("reviewer", (), "m", "low"), "assign", 1
            ),
            ctx,
        ),
        Ok,
    )
    assert isinstance(process_bus.authorize(tmp_path, ctx, "worker"), Err)
    assert isinstance(
        bus.request(
            process_messages.status_update(
                ctx,
                "worker",
                "followup",
                process_messages.ProcessStatus.RUNNING,
                "followup",
                2,
            ),
            ctx,
        ),
        Ok,
    )
    assert (
        process_bus.authorize(tmp_path, ctx, "worker").value.assignment.role
        == "reviewer"
    )
