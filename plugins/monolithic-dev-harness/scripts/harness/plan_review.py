"""Approving one Story's implementation plan: show it as it reads now, then ask about it.

Two rules the harness checks instead of trusting the agent to remember them:

  shown   `harness workflow show --artifact <plan>` printed the plan and recorded its digest. On
          Claude, tool output is hidden from the user, so the agent's own reply must carry it too.
  ready   `implementation-confirm` is asked about exactly one note of type `implementation-plan`,
          marked `status: approved` so the approval pins it, whose `story` is the Story or Bug the
          question names, and that Story or Bug exists in the selected tracker.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap
from harness import local_artifacts, state, work_sessions, workflow
from integrations.contracts import TrackerOps, WorkItemKind

SHOWN = "plan-shown.json"
_BUILDABLE = frozenset({WorkItemKind.USER_STORY, WorkItemKind.BUG})


def show(repo: Path, session: str | None, names: list[str]) -> Result[str]:
    """Print the plan the approval will bind, and record that exactly this content was shown."""
    return bind(
        _one_plan(repo, names),
        lambda plan: bind(
            _digest(repo, plan),
            lambda digest: bind(
                _record(repo, session, {"plan": [plan, digest]}),
                lambda _: _render(repo, plan),
            ),
        ),
    )


def ready(
    repo: Path, session: str | None, names: list[str], story: str, ops: TrackerOps
) -> Result[None]:
    """`implementation-confirm` may be asked only about a shown plan for a tracked Story."""
    return bind(
        _one_plan(repo, names),
        lambda plan: bind(
            _plan_for(repo, plan, story),
            lambda _: bind(
                _tracked(ops, story),
                lambda _: bind(
                    _digest(repo, plan),
                    lambda digest: bind(
                        _read(repo, session),
                        lambda shown: (
                            Ok(None)
                            if shown.get("plan") == [plan, digest]
                            else err(
                                "plan_not_shown",
                                "show the plan first: run `harness workflow show --artifact "
                                f"{plan}` and put its output in your reply; a plan changed since "
                                "it was shown must be shown again",
                            )
                        ),
                    ),
                ),
            ),
        ),
    )


def _one_plan(repo: Path, names: list[str]) -> Result[str]:
    match names:
        case [name]:
            target = (repo / name).resolve()
            return (
                Ok(name)
                if target.is_relative_to(repo.resolve()) and target.is_file()
                else err("plan_invalid", f"{name} is not a file in this project")
            )
        case _:
            return err(
                "plan_invalid",
                "name one implementation plan with --artifact; each Story's plan is approved "
                "on its own",
            )


def _plan_for(repo: Path, name: str, story: str) -> Result[None]:
    frontmatter = local_artifacts.frontmatter(repo / name)
    named = str(frontmatter.get("story", "")).strip().strip("\"'")
    if frontmatter.get("type") != "implementation-plan":
        return err("plan_invalid", f"{name} is not a note of type implementation-plan")
    if str(frontmatter.get("status", "")).strip().lower() != "approved":
        return err(
            "plan_invalid",
            f"set `status: approved` in {name} before asking, so the approval pins it",
        )
    if named != story:
        return err("plan_invalid", f"{name} names {named or 'no Story'}, not {story}")
    return Ok(None)


def _tracked(ops: TrackerOps, story: str) -> Result[None]:
    return bind(
        ops.get_work_item(story),
        lambda item: (
            Ok(None)
            if item.kind in _BUILDABLE
            else err(
                "plan_invalid",
                f"{story} is a {item.kind.value}; a plan is approved for a Story or Bug",
            )
        ),
    )


def _digest(repo: Path, name: str) -> Result[str]:
    return workflow.file_digest((repo / name).resolve())


def _render(repo: Path, plan: str) -> Result[str]:
    def build() -> str:
        story = str(local_artifacts.frontmatter(repo / plan).get("story", "")).strip(
            "\"' "
        )
        return "\n".join(
            [
                "Show everything below this line to the human in your reply, unchanged, before "
                "asking for approval. The approval question is refused until this plan has been "
                "shown.",
                "",
                f"## Implementation plan for {story} — [{plan}]({plan})",
                "",
                (repo / plan).read_text(encoding="utf-8").strip(),
                "",
            ]
        )

    return attempt(build, "plan_unreadable", "could not read the plan", OSError)


def _record(repo: Path, session: str | None, value: dict) -> Result[None]:
    return bind(
        work_sessions.scope_folder(repo, session),
        lambda folder: attempt(
            lambda: state.write_json(folder / SHOWN, value),
            "plan_state_unwritable",
            f"could not save {SHOWN}",
            OSError,
        ),
    )


def _read(repo: Path, session: str | None) -> Result[dict]:
    return fmap(
        work_sessions.scope_folder(repo, session),
        lambda folder: state.read_json(folder / SHOWN) or {},
    )


# --- shown in the conversation ------------------------------------------------------------------


def shown_in_chat(repo: Path, session: str | None, transcript: Path) -> Result[None]:
    """Claude: the agent's own reply, not just a tool result, must carry the shown plan.

    Tool output is collapsed in the host, so the check reads the transcript: every heading of the
    plan `workflow show` printed must appear in assistant text written after that command ran.
    """
    return bind(
        _read(repo, session),
        lambda shown: bind(
            _expected_lines(repo, shown.get("plan")),
            lambda expected: bind(
                _assistant_text_after_show(transcript),
                lambda text: _all_present(expected, text),
            ),
        ),
    )


def _expected_lines(repo: Path, shown: Any) -> Result[tuple[str, ...]]:
    match shown:
        case [str() as plan, str()]:
            return fmap(
                _render(repo, plan),
                lambda rendered: tuple(
                    line.strip()
                    for line in rendered.splitlines()
                    if line.lstrip().startswith("#") and line.strip()
                ),
            )
        case _:
            return err(
                "plan_not_shown", "run `harness workflow show` before the plan approval"
            )


def _assistant_text_after_show(transcript: Path) -> Result[str]:
    def read() -> str:
        texts: list[str] = []
        for line in transcript.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            content = (row.get("message") or {}).get("content")
            if row.get("type") != "assistant" or not isinstance(content, list):
                continue
            for block in content:
                match block:
                    case {
                        "type": "tool_use",
                        "input": {"command": str() as command},
                    } if "workflow show" in command:
                        texts.clear()
                    case {"type": "text", "text": str() as text}:
                        texts.append(text)
                    case _:
                        pass
        return "\n".join(texts)

    return attempt(read, "transcript_unavailable", "host transcript", OSError)


def _all_present(expected: tuple[str, ...], text: str) -> Result[None]:
    missing = [line for line in expected if line not in text]
    return (
        Ok(None)
        if not missing
        else err(
            "plan_not_in_reply",
            "the human has not seen the plan: tool output is hidden from them. Put the "
            "`harness workflow show` output in your reply (missing, for example: "
            f"{missing[0]!r}), then ask again",
        )
    )
