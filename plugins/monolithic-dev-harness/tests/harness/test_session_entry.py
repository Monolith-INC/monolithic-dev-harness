"""Saved-work candidates are independent of damaged or hidden mode sessions."""

import fcntl
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from core.result import Err, Ok
from harness import decisions, rules, session_entry, state, work_sessions
from host_adapters import StartEvent, work_session_context


def test_candidates_keep_saved_work_when_another_record_is_damaged(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Continue the report").value
    damaged = work_sessions.root(tmp_path) / "WS-damaged" / "session.json"
    damaged.parent.mkdir(parents=True)
    damaged.write_text("{", encoding="utf-8")

    found = session_entry.candidates(tmp_path)

    assert tuple(session.id for session in found.sessions) == (saved.id,)
    assert found.damaged == (damaged,)


def test_candidates_hide_mode_and_completed_sessions(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Saved work").value
    finished = work_sessions.start(tmp_path, "Finished work").value
    work_sessions.transition(tmp_path, finished.id, "complete")
    work_sessions.create(tmp_path, "Mode work", mode="discovery")

    found = session_entry.candidates(tmp_path)

    assert tuple(session.id for session in found.sessions) == (saved.id,)


def test_unfinished_setup_belongs_to_the_other_conversation(tmp_path: Path) -> None:
    state.write_json(
        tmp_path / decisions.RELATIVE_PATH,
        {"status": "pending", "gate": "setup-confirm", "native_session_id": "old"},
    )

    assert session_entry.candidates(tmp_path, "new").unfinished_setup
    assert not session_entry.candidates(tmp_path, "old").unfinished_setup


def test_single_saved_work_offers_continue_or_new_disposition(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Saved work").value

    options = session_entry.options(session_entry.candidates(tmp_path))

    assert tuple(option.key for option in options) == (
        f"continue:{saved.id}",
        "new:pause",
        "new:stop",
    )


def test_many_saved_sessions_remain_available_across_pages(tmp_path: Path) -> None:
    saved = tuple(work_sessions.start(tmp_path, f"Work {n}").value for n in range(4))

    options = session_entry.options(session_entry.candidates(tmp_path))

    assert tuple(option.key for option in options) == (
        *(f"continue:{session.id}" for session in reversed(saved)),
        "new",
    )
    prepared = session_entry.offer(tmp_path, "codex", "thread-a", "New work").value
    assert tuple(
        option["label"] for option in session_entry.question(prepared, "en")["options"]
    ) == (
        f"Continue 1: {saved[3].request}",
        f"Continue 2: {saved[2].request}",
        "More saved work",
    )


def test_start_orients_without_creating_a_session(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Investigate the report").value
    before = set(work_sessions.root(tmp_path).iterdir())

    text = session_entry.on_start(
        tmp_path, "codex", StartEvent("chat", "resume", False)
    )

    assert text is not None and saved.request in text
    assert set(work_sessions.root(tmp_path).iterdir()) == before


def test_start_describes_bound_work_and_ignores_subagents(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Investigate the report").value
    work_session_context.bind_session(tmp_path, "codex", "chat", saved.id)

    text = session_entry.on_start(
        tmp_path, "codex", StartEvent("chat", "resume", False)
    )

    assert text is not None and saved.request in text and saved.id in text
    assert (
        session_entry.on_start(tmp_path, "codex", StartEvent("chat", "resume", True))
        is None
    )


def test_start_mentions_unfinished_setup_without_saved_work(tmp_path: Path) -> None:
    state.write_json(
        tmp_path / decisions.RELATIVE_PATH,
        {"status": "pending", "gate": "setup-confirm", "native_session_id": "old"},
    )

    text = session_entry.on_start(
        tmp_path, "codex", StartEvent("new", "startup", False)
    )

    assert text is not None and "setup" in text.lower()


def test_session_entry_evidence_is_protected() -> None:
    assert rules.is_human_owned(".harness/state/session-entry/codex/entry.json")


def test_offers_are_isolated_by_conversation_and_repeated_offers_are_stable(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Previous work").value

    first = session_entry.offer(tmp_path, "codex", "chat-a", "New work")
    again = session_entry.offer(tmp_path, "codex", "chat-a", "New work")
    second = session_entry.offer(tmp_path, "codex", "chat-b", "Other work")

    assert isinstance(first, Ok) and first == again
    assert isinstance(second, Ok) and second.value.request == "Other work"
    assert f"continue:{saved.id}" in tuple(option.key for option in first.value.options)


def test_offer_rejects_a_changed_request_while_selection_is_pending(
    tmp_path: Path,
) -> None:
    work_sessions.start(tmp_path, "Previous work")
    assert isinstance(session_entry.offer(tmp_path, "codex", "chat", "First"), Ok)

    changed = session_entry.offer(tmp_path, "codex", "chat", "Different")

    assert isinstance(changed, Err)


def test_corrupt_offer_is_never_overwritten(tmp_path: Path) -> None:
    path = session_entry._offer_path(tmp_path, "codex", "chat").value
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe")

    result = session_entry.offer(tmp_path, "codex", "chat", "New work")

    assert isinstance(result, Err)
    assert path.read_bytes() == b"\xff\xfe"


def test_native_answer_must_match_observed_question_and_conversation(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Previous work").value
    prepared = session_entry.offer(tmp_path, "codex", "chat-a", "New work").value
    question = session_entry.question(prepared, "en")
    shown = {
        "session_id": "chat-a",
        "tool_use_id": "call-1",
        "tool_name": "request_user_input",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(tmp_path, "codex", shown).value
    reply = {
        **shown,
        "tool_response": {
            "answers": {question["question"]: question["options"][0]["label"]}
        },
    }

    foreign = session_entry.answer(tmp_path, "codex", {**reply, "session_id": "chat-b"})
    assert isinstance(foreign, Ok) and foreign.value is None
    assert (
        session_entry.answer(tmp_path, "codex", reply).value == f"continue:{saved.id}"
    )
    assert session_entry.answer(tmp_path, "codex", reply).value is None


def test_question_changed_by_agent_cannot_be_observed(tmp_path: Path) -> None:
    work_sessions.start(tmp_path, "Previous work")
    prepared = session_entry.offer(tmp_path, "codex", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    question["options"][0]["label"] = "An invented option"

    result = session_entry.observe(
        tmp_path,
        "codex",
        {
            "session_id": "chat",
            "tool_use_id": "call",
            "tool_input": {"questions": [question]},
        },
    )

    assert isinstance(result, Ok) and not result.value


def test_only_latest_presentation_can_record_a_reply(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Previous work").value
    prepared = session_entry.offer(tmp_path, "claude", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    first = {
        "session_id": "chat",
        "tool_use_id": "first",
        "tool_input": {"questions": [question]},
    }
    second = {**first, "tool_use_id": "second"}
    assert session_entry.observe(tmp_path, "claude", first).value
    assert session_entry.observe(tmp_path, "claude", second).value
    response = {"answers": {question["question"]: question["options"][0]["label"]}}

    assert (
        session_entry.answer(
            tmp_path, "claude", {**first, "tool_response": response}
        ).value
        is None
    )
    assert (
        session_entry.answer(
            tmp_path, "claude", {**second, "tool_response": response}
        ).value
        == f"continue:{saved.id}"
    )


def test_question_with_prefilled_answer_cannot_be_observed(tmp_path: Path) -> None:
    work_sessions.start(tmp_path, "Previous work")
    prepared = session_entry.offer(tmp_path, "codex", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    question["answers"] = {question["question"]: question["options"][0]["label"]}

    result = session_entry.observe(
        tmp_path,
        "codex",
        {
            "session_id": "chat",
            "tool_use_id": "call",
            "tool_input": {"questions": [question]},
        },
    )

    assert isinstance(result, Ok) and not result.value


def test_question_with_invented_option_description_cannot_be_observed(
    tmp_path: Path,
) -> None:
    work_sessions.start(tmp_path, "Previous work")
    prepared = session_entry.offer(tmp_path, "codex", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    question["options"][0]["description"] = "This deletes all your saved work."

    result = session_entry.observe(
        tmp_path,
        "codex",
        {
            "session_id": "chat",
            "tool_use_id": "call",
            "tool_input": {"questions": [question]},
        },
    )

    assert isinstance(result, Ok) and not result.value


def test_async_reply_is_bound_to_the_observed_question_and_chat(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Previous work").value
    prepared = session_entry.offer(tmp_path, "codex", "chat-a", "New work").value
    question = session_entry.question(prepared, "en")
    payload = {
        "session_id": "chat-a",
        "tool_use_id": "call-1",
        "tool_name": "request_user_input_async",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(tmp_path, "codex", payload).value
    envelope = (
        "<send_user_message_question_reply>\n"
        + json.dumps(
            [
                {
                    "questionItemId": json.dumps(
                        ["request_user_input_async", "call-1", 0]
                    ),
                    "question": question["question"],
                    "answer": question["options"][0]["label"],
                }
            ]
        )
        + "\n</send_user_message_question_reply>"
    )

    assert (
        session_entry.answer_prompt(tmp_path, "codex", "chat-b", envelope).value is None
    )
    assert (
        session_entry.answer_prompt(tmp_path, "codex", "chat-a", envelope).value
        == f"continue:{saved.id}"
    )
    assert (
        session_entry.answer_prompt(tmp_path, "codex", "chat-a", envelope).value is None
    )


def test_concurrent_replies_record_at_most_one_choice(tmp_path: Path) -> None:
    work_sessions.start(tmp_path, "Previous work")
    prepared = session_entry.offer(tmp_path, "claude", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    shown = {
        "session_id": "chat",
        "tool_use_id": "call",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(tmp_path, "claude", shown).value
    responses = tuple(
        {**shown, "tool_response": {"answers": {question["question"]: option["label"]}}}
        for option in question["options"][:2]
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(
                lambda payload: session_entry.answer(tmp_path, "claude", payload),
                responses,
            )
        )

    assert (
        sum(isinstance(result, Ok) and result.value is not None for result in results)
        == 1
    )


def test_unrelated_prompt_does_not_create_session_control_state(tmp_path: Path) -> None:
    assert session_entry.answer_prompt(tmp_path, "codex", "chat", "hello").value is None
    assert not (tmp_path / ".harness" / "state" / "session-entry").exists()


def test_reply_is_durable_when_offer_lock_is_busy_and_recovery_is_idempotent(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Previous work").value
    prepared = session_entry.offer(tmp_path, "claude", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    shown = {
        "session_id": "chat",
        "tool_use_id": "call",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(tmp_path, "claude", shown).value
    response = {
        **shown,
        "tool_response": {
            "answers": {question["question"]: question["options"][0]["label"]}
        },
    }
    path = session_entry._offer_path(tmp_path, "claude", "chat").value
    with path.with_suffix(".lock").open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert isinstance(session_entry.answer(tmp_path, "claude", response), Err)

    assert (
        session_entry.recover_reply(tmp_path, "claude", "chat").value
        == f"continue:{saved.id}"
    )
    assert session_entry.recover_reply(tmp_path, "claude", "chat").value is None


def test_conflicting_replies_do_not_replace_original_evidence(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Previous work").value
    prepared = session_entry.offer(tmp_path, "claude", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    shown = {
        "session_id": "chat",
        "tool_use_id": "call",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(tmp_path, "claude", shown).value

    def make_reply(index: int) -> dict:
        return {
            **shown,
            "tool_response": {
                "answers": {question["question"]: question["options"][index]["label"]}
            },
        }

    path = session_entry._offer_path(tmp_path, "claude", "chat").value
    with path.with_suffix(".lock").open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert isinstance(session_entry.answer(tmp_path, "claude", make_reply(0)), Err)
        conflict = session_entry.answer(tmp_path, "claude", make_reply(1))
        assert (
            isinstance(conflict, Err)
            and conflict.failure.code == "entry_reply_collision"
        )

    assert (
        session_entry.recover_reply(tmp_path, "claude", "chat").value
        == f"continue:{saved.id}"
    )


def test_async_reply_survives_a_busy_offer_lock(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Previous work").value
    prepared = session_entry.offer(tmp_path, "codex", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    shown = {
        "session_id": "chat",
        "tool_use_id": "call",
        "tool_name": "request_user_input_async",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(tmp_path, "codex", shown).value
    envelope = (
        "<send_user_message_question_reply>\n"
        + json.dumps(
            [
                {
                    "questionItemId": json.dumps(
                        ["request_user_input_async", "call", 0]
                    ),
                    "question": question["question"],
                    "answer": question["options"][0]["label"],
                }
            ]
        )
        + "\n</send_user_message_question_reply>"
    )
    path = session_entry._offer_path(tmp_path, "codex", "chat").value
    with path.with_suffix(".lock").open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert isinstance(
            session_entry.answer_prompt(tmp_path, "codex", "chat", envelope), Err
        )

    assert (
        session_entry.recover_reply(tmp_path, "codex", "chat").value
        == f"continue:{saved.id}"
    )


def test_reserved_session_creation_is_idempotent_and_refuses_conflicts(
    tmp_path: Path,
) -> None:
    identifier = "WS-0123456789abcdef01234567"

    first = work_sessions.create_reserved(tmp_path, "New work", identifier)
    second = work_sessions.create_reserved(tmp_path, "New work", identifier)
    different = work_sessions.create_reserved(tmp_path, "Another request", identifier)

    assert isinstance(first, Ok) and second == first
    assert isinstance(different, Err)
    assert tuple(
        session.id for session in work_sessions.list_sessions(tmp_path).value
    ) == (identifier,)


def test_reserved_session_creation_rejects_untrusted_identifier(tmp_path: Path) -> None:
    assert isinstance(
        work_sessions.create_reserved(tmp_path, "New work", "../bad"), Err
    )
    assert not work_sessions.root(tmp_path).exists()


def test_concurrent_reserved_creation_produces_one_session(tmp_path: Path) -> None:
    identifier = "WS-0123456789abcdef01234567"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(
                lambda _: work_sessions.create_reserved(
                    tmp_path, "New work", identifier
                ),
                range(2),
            )
        )

    assert all(isinstance(result, Ok) for result in results)
    assert results[0].value == results[1].value
    assert len(work_sessions.list_sessions(tmp_path).value) == 1


def _answer_entry(repo: Path, index: int) -> str:
    prepared = session_entry.offer(repo, "codex", "chat", "New work").value
    shown = session_entry.question(prepared, "en")
    local_index = index - prepared.page * 2
    if index >= (prepared.page + 1) * 2 and session_entry._visible_options(prepared)[
        -1
    ].key in ("more", "more_saved"):
        payload = {
            "session_id": "chat",
            "tool_use_id": f"call-more-{prepared.page}",
            "tool_input": {"questions": [shown]},
        }
        assert session_entry.observe(repo, "codex", payload).value
        choice = session_entry.answer(
            repo,
            "codex",
            {
                **payload,
                "tool_response": {
                    "answers": {shown["question"]: shown["options"][2]["label"]}
                },
            },
        ).value
        assert choice in ("more", "more_saved")
        result = session_entry.apply_selection(repo, "codex", "chat")
        assert isinstance(result, Err) and result.failure.code == "entry_more_options"
        return _answer_entry(repo, index)
    assert 0 <= local_index < len(shown["options"])
    payload = {
        "session_id": "chat",
        "tool_use_id": "call",
        "tool_input": {"questions": [shown]},
    }
    assert session_entry.observe(repo, "codex", payload).value
    response = {
        **payload,
        "tool_response": {
            "answers": {shown["question"]: shown["options"][local_index]["label"]}
        },
    }
    return session_entry.answer(repo, "codex", response).value


def test_apply_requires_real_answer_and_replays_same_selection(tmp_path: Path) -> None:
    saved = work_sessions.start(tmp_path, "Old work").value
    session_entry.offer(tmp_path, "codex", "chat", "New work")
    assert isinstance(session_entry.apply_selection(tmp_path, "codex", "chat"), Err)
    assert _answer_entry(tmp_path, 0) == f"continue:{saved.id}"

    first = session_entry.apply_selection(tmp_path, "codex", "chat")
    again = session_entry.apply_selection(tmp_path, "codex", "chat")

    assert isinstance(first, Ok) and first.value == saved.id and again == first
    assert (
        work_session_context.resolve_session(tmp_path, "codex", "chat").value
        == saved.id
    )


def test_new_choice_resumes_safely_after_interrupted_bind(
    tmp_path: Path, monkeypatch
) -> None:
    old = work_sessions.start(tmp_path, "Old work").value
    assert _answer_entry(tmp_path, 1) == "new:pause"
    actual = work_session_context.bind_session
    monkeypatch.setattr(
        work_session_context,
        "bind_session",
        lambda *_args, **_kwargs: Err(
            __import__("core.result", fromlist=["Failure"]).Failure(
                "test", "interrupted"
            )
        ),
    )

    interrupted = session_entry.apply_selection(tmp_path, "codex", "chat")
    monkeypatch.setattr(work_session_context, "bind_session", actual)
    recovered = session_entry.apply_selection(tmp_path, "codex", "chat")

    assert isinstance(interrupted, Err) and isinstance(recovered, Ok)
    sessions = work_sessions.list_sessions(tmp_path).value
    assert len(sessions) == 2
    assert (
        work_sessions.select(tmp_path, old.id).value.status
        == work_sessions.Status.PAUSED
    )
    assert (
        next(session for session in sessions if session.id == recovered.value).request
        == "New work"
    )


def test_continue_pending_question_does_not_bind_before_safe_handover(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Old work").value
    state.write_json(
        saved.folder / "decision.json", {"status": "pending", "question": "Approve?"}
    )
    assert _answer_entry(tmp_path, 0) == f"continue:{saved.id}"

    result = session_entry.apply_selection(tmp_path, "codex", "chat")

    assert isinstance(result, Err) and result.failure.code == "entry_handover_required"
    assert work_session_context.resolve_session(tmp_path, "codex", "chat").value is None


def test_continue_hands_over_pending_question_without_marking_it_shown(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Old work").value
    assert isinstance(
        decisions.begin(
            tmp_path,
            "old-question",
            "Approve the plan?",
            ("Approve", "Stop"),
            "blocking",
            work_session_id=saved.id,
            native_session_id="old-chat",
        ),
        Ok,
    )
    before = decisions.record(tmp_path, saved.id)
    assert _answer_entry(tmp_path, 0) == f"continue:{saved.id}"

    result = session_entry.apply_selection(tmp_path, "codex", "chat")

    assert isinstance(result, Ok) and result.value == saved.id
    handed_over = decisions.record(tmp_path, saved.id)
    assert handed_over is not None
    assert handed_over["status"] == "pending"
    assert handed_over["native_session_id"] == "chat"
    assert handed_over["handover_pending"] is True
    assert handed_over["answer"] == before["answer"] == ""
    assert handed_over["question"] == before["question"]
    assert not decisions.presented_here(handed_over, "chat")
    assert not decisions.presented_here(decisions.record(tmp_path, saved.id), "chat")
    assert (
        work_session_context.resolve_session(tmp_path, "codex", "chat").value
        == saved.id
    )


def test_chat_fallback_does_not_count_as_handover_presentation(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Old work").value
    assert isinstance(
        decisions.begin(
            tmp_path,
            "old-question",
            "Approve the plan?",
            ("Approve", "Stop"),
            "blocking",
            work_session_id=saved.id,
            native_session_id="old-chat",
        ),
        Ok,
    )
    assert isinstance(decisions.hand_over(tmp_path, saved.id, "new-chat"), Ok)

    fallback = decisions.fallback(tmp_path, "chat", work_session_id=saved.id)

    assert isinstance(fallback, Ok)
    assert fallback.value["handover_pending"] is True
    assert not decisions.presented_here(fallback.value, "new-chat")

    displayed = decisions.fallback(tmp_path, "chat", work_session_id=saved.id)

    assert isinstance(displayed, Ok)
    assert displayed.value["handover_pending"] is True
    assert not decisions.presented_here(displayed.value, "new-chat")


def test_setup_chat_fallback_does_not_count_as_question_presentation(
    tmp_path: Path,
) -> None:
    assert isinstance(
        decisions.begin(
            tmp_path,
            "setup-question",
            "Set up this project?",
            ("Continue", "Skip"),
            "async",
            native_session_id="old-chat",
        ),
        Ok,
    )
    assert isinstance(decisions.hand_over(tmp_path, None, "new-chat"), Ok)

    shown = decisions.fallback(tmp_path, "chat")

    assert isinstance(shown, Ok)
    assert shown.value["handover_pending"] is True
    assert not decisions.presented_here(shown.value, "new-chat")


def test_stale_reply_and_handover_race_cannot_lose_the_human_answer(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Old work").value
    assert isinstance(
        decisions.begin(
            tmp_path,
            "old-question",
            "Approve the plan?",
            ("Approve", "Stop"),
            "blocking",
            work_session_id=saved.id,
            native_session_id="old-chat",
        ),
        Ok,
    )
    barrier = Barrier(2)

    def hand_over():
        barrier.wait()
        return decisions.hand_over(tmp_path, saved.id, "new-chat")

    def answer_old():
        barrier.wait()
        return decisions.resolve(
            tmp_path,
            "old-question",
            "Approve",
            "blocking",
            work_session_id=saved.id,
            native_session_id="old-chat",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        handover_future = pool.submit(hand_over)
        answer_future = pool.submit(answer_old)
        handover, answer = handover_future.result(), answer_future.result()

    record = decisions.record(tmp_path, saved.id)
    assert record is not None
    assert (
        record["status"] == "answered"
        and record["answer"] == "Approve"
        and isinstance(handover, Err)
        and isinstance(answer, Ok)
    ) or (
        record["status"] == "pending"
        and record.get("handover_pending") is True
        and isinstance(handover, Ok)
        and isinstance(answer, Err)
    )


def test_retry_after_sync_failure_does_not_repeat_session_disposition(
    tmp_path: Path, monkeypatch
) -> None:
    old = work_sessions.start(tmp_path, "Old work").value
    assert _answer_entry(tmp_path, 1) == "new:pause"
    actual = session_entry._sync_effect
    monkeypatch.setattr(
        session_entry,
        "_sync_effect",
        lambda _path: Err(
            __import__("core.result", fromlist=["Failure"]).Failure(
                "sync", "interrupted"
            )
        ),
    )

    interrupted = session_entry.apply_selection(tmp_path, "codex", "chat")
    monkeypatch.setattr(session_entry, "_sync_effect", actual)
    recovered = session_entry.apply_selection(tmp_path, "codex", "chat")

    assert isinstance(interrupted, Err) and isinstance(recovered, Ok)
    assert tuple(
        event["type"] for event in work_sessions.select(tmp_path, old.id).value.events
    ) == ("started", "paused")
    assert len(work_sessions.list_sessions(tmp_path).value) == 2


def test_new_with_multiple_saved_work_requires_a_second_human_disposition(
    tmp_path: Path,
) -> None:
    first = work_sessions.start(tmp_path, "Old work A").value
    second = work_sessions.start(tmp_path, "Old work B").value
    assert _answer_entry(tmp_path, 2) == "new"

    result = session_entry.apply_selection(tmp_path, "codex", "chat")

    assert (
        isinstance(result, Err) and result.failure.code == "entry_disposition_required"
    )
    assert (
        work_sessions.select(tmp_path, first.id).value.status
        == work_sessions.Status.ACTIVE
    )
    assert (
        work_sessions.select(tmp_path, second.id).value.status
        == work_sessions.Status.ACTIVE
    )


def test_new_with_multiple_saved_work_applies_only_the_answered_disposition(
    tmp_path: Path,
) -> None:
    old = tuple(work_sessions.start(tmp_path, f"Old work {n}").value for n in range(2))
    assert _answer_entry(tmp_path, 2) == "new"
    assert isinstance(session_entry.apply_selection(tmp_path, "codex", "chat"), Err)
    prepared = session_entry.offer(tmp_path, "codex", "chat", "New work").value
    question = session_entry.question(prepared, "en")
    payload = {
        "session_id": "chat",
        "tool_use_id": "call-2",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(tmp_path, "codex", payload).value
    assert (
        session_entry.answer(
            tmp_path,
            "codex",
            {
                **payload,
                "tool_response": {
                    "answers": {question["question"]: question["options"][0]["label"]}
                },
            },
        ).value
        == "new:pause-all"
    )

    applied = session_entry.apply_selection(tmp_path, "codex", "chat")

    assert isinstance(applied, Ok)
    assert all(
        work_sessions.select(tmp_path, session.id).value.status
        == work_sessions.Status.PAUSED
        for session in old
    )
    assert len(work_sessions.list_sessions(tmp_path).value) == 3


def test_new_pause_all_disposes_every_saved_session_not_only_offered_three(
    tmp_path: Path,
) -> None:
    old = tuple(work_sessions.start(tmp_path, f"Old work {n}").value for n in range(5))
    assert _answer_entry(tmp_path, 5) == "new"
    assert (
        session_entry.apply_selection(tmp_path, "codex", "chat").failure.code
        == "entry_disposition_required"
    )
    prepared = session_entry.offer(tmp_path, "codex", "chat", "New work").value
    assert tuple(option.key for option in prepared.options) == (
        "new:pause-all",
        "new:stop-all",
    )
    question = session_entry.question(prepared, "en")
    payload = {
        "session_id": "chat",
        "tool_use_id": "call-pause-all",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(tmp_path, "codex", payload).value
    assert (
        session_entry.answer(
            tmp_path,
            "codex",
            {
                **payload,
                "tool_response": {
                    "answers": {question["question"]: "Pause all saved work"}
                },
            },
        ).value
        == "new:pause-all"
    )

    applied = session_entry.apply_selection(tmp_path, "codex", "chat")

    assert isinstance(applied, Ok)
    assert all(
        work_sessions.select(tmp_path, session.id).value.status
        == work_sessions.Status.PAUSED
        for session in old
    )
    assert len(work_sessions.list_sessions(tmp_path).value) == 6
