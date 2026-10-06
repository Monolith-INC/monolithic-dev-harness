"""The subagent contract never turns a missing or malformed host answer into success."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.result import Err, Ok, err
from core.schema import errors
from host_adapters import subagents
from host_adapters.subagents import (
    OPERATIONS,
    Activity,
    Brief,
    Claim,
    Declaration,
    Event,
    EventPage,
    Handle,
    Source,
    Status,
    SubagentOps,
    Tier,
)

PLUGIN = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((PLUGIN / "config" / "host.schema.json").read_text())
BRIEF = Brief("tester", "Read README.md", Path("."), Tier.CHEAP, "medium", "key-1")
HANDLE = Handle("claude", "thread-1")
CALLS = {
    "start": lambda ops: ops.start(BRIEF),
    "status": lambda ops: ops.status(HANDLE),
    "follow_up": lambda ops: ops.follow_up(HANDLE, "continue"),
    "cancel": lambda ops: ops.cancel(HANDLE),
    "events": lambda ops: ops.events(""),
}
SOURCED = {
    "level": "empirically-verified",
    "source": "tests/x",
    "retrieved": "2026-10-06",
}


def declared(*supported: str) -> Declaration:
    return Declaration(
        host="claude",
        product="test",
        verified_on="2026-10-06",
        operations={
            name: Claim(name in supported, "empirically-verified", "tests/x", "")
            for name in OPERATIONS
        },
    )


def answering(**answers: object) -> SubagentOps:
    """An adapter whose operations return the given values, unsupported otherwise."""
    base = subagents.unsupported_ops("claude")
    return SubagentOps(
        start=answers.get("start", base.start),
        status=answers.get("status", base.status),
        follow_up=answers.get("follow_up", base.follow_up),
        cancel=answers.get("cancel", base.cancel),
        events=answers.get("events", base.events),
    )


def code(result: object) -> str:
    assert isinstance(result, Err), result
    return result.failure.code


# --- what ships --------------------------------------------------------------------------------


def test_every_adapter_has_a_valid_declaration_and_every_declaration_an_adapter() -> (
    None
):
    shipped = {path.stem for path in (PLUGIN / "hosts").glob("*.json")}
    assert shipped == set(subagents.ADAPTERS)
    for host in shipped:
        document = json.loads((PLUGIN / "hosts" / f"{host}.json").read_text())
        assert errors(SCHEMA, document) == ()
        assert isinstance(subagents.declaration(host), Ok)


@pytest.mark.parametrize("host", sorted(subagents.ADAPTERS))
def test_each_shipped_host_behaves_as_it_declares(host: str) -> None:
    found = subagents.declaration(host).value
    ops = subagents.for_host(host).value
    for operation, call in CALLS.items():
        result = call(ops)
        if not found.supports(operation):
            assert code(result) == "unsupported_capability", (host, operation)


def test_an_unknown_host_is_unsupported_not_an_error() -> None:
    assert code(subagents.for_host("gemini")) == "unsupported_capability"
    assert code(subagents.capabilities("gemini")) == "unsupported_capability"


# --- the declaration ---------------------------------------------------------------------------


def test_a_supported_claim_needs_a_source() -> None:
    document = json.loads((PLUGIN / "hosts" / "claude.json").read_text())
    for provenance in (
        {"level": "unsourced", "caveat": "nobody checked"},
        {"level": "first-party-doc", "source": "https://x", "retrieved": "2026-10-06"},
    ):
        document["subagents"]["start"] = {"supported": True, "provenance": provenance}
        assert errors(SCHEMA, document), provenance
    document["subagents"]["start"] = {"supported": True, "provenance": SOURCED}
    assert errors(SCHEMA, document) == ()


def test_a_declaration_must_match_its_file_name(tmp_path: Path) -> None:
    document = json.loads((PLUGIN / "hosts" / "codex.json").read_text())
    (tmp_path / "claude.json").write_text(json.dumps(document))
    assert code(subagents.declaration("claude", tmp_path)) == "invalid_host_declaration"


# --- the checked operations --------------------------------------------------------------------


def test_the_declaration_wins_over_an_adapter_that_answers_anyway() -> None:
    ops = subagents.checked(declared(), answering(start=lambda _: Ok(HANDLE)))
    assert code(ops.start(BRIEF)) == "unsupported_capability"


def test_a_declared_operation_the_adapter_lacks_stays_unsupported() -> None:
    ops = subagents.checked(declared(*OPERATIONS), answering())
    for call in CALLS.values():
        assert code(call(ops)) == "unsupported_capability"


def test_valid_answers_pass_through() -> None:
    page = EventPage((Event(Source.HOST, "started", "d1", "p1"),), "")
    ops = subagents.checked(
        declared(*OPERATIONS),
        answering(
            start=lambda _: Ok(HANDLE),
            status=lambda handle: Ok(Status(handle, Activity.RUNNING)),
            follow_up=lambda handle, _: Ok(handle),
            cancel=lambda handle: Ok(Status(handle, Activity.CANCELLED)),
            events=lambda _: Ok(page),
        ),
    )
    assert ops.start(BRIEF) == Ok(HANDLE)
    assert ops.status(HANDLE) == Ok(Status(HANDLE, Activity.RUNNING))
    assert ops.follow_up(HANDLE, "go") == Ok(HANDLE)
    assert ops.cancel(HANDLE) == Ok(Status(HANDLE, Activity.CANCELLED))
    assert ops.events("") == Ok(page)


def test_an_adapter_failure_is_passed_on_unchanged() -> None:
    failed = err("host_busy", "try again", retryable=True)
    ops = subagents.checked(declared("start"), answering(start=lambda _: failed))
    assert ops.start(BRIEF) == failed


@pytest.mark.parametrize(
    ("operation", "answer"),
    [
        ("start", lambda _: Ok({})),
        ("start", lambda _: Ok(Handle("claude", ""))),
        ("start", lambda _: Ok(Handle("codex", "thread-1"))),
        ("start", lambda _: {"status": "ok"}),
        ("start", lambda _: 1 / 0),
        ("status", lambda _: Ok(Status(Handle("claude", "other"), Activity.RUNNING))),
        ("status", lambda handle: Ok(Status(handle, "running"))),
        ("follow_up", lambda _handle, _message: Ok(Handle("claude", "other"))),
        ("cancel", lambda _: Ok(None)),
        ("events", lambda _: Ok(EventPage((Event(Source.HOST, "x", ""),), ""))),
        (
            "events",
            lambda _: Ok(
                EventPage(
                    (Event(Source.HOST, "a", "d1"), Event(Source.HOST, "b", "d1")), ""
                )
            ),
        ),
        ("events", lambda _: Ok(EventPage((Event("host", "a", "d1"),), ""))),
        ("events", lambda _: Ok({"events": [], "next_cursor": None})),
    ],
)
def test_a_malformed_answer_is_an_invalid_host_result(
    operation: str, answer: object
) -> None:
    ops = subagents.checked(declared(operation), answering(**{operation: answer}))
    assert code(CALLS[operation](ops)) == "invalid_host_result"
