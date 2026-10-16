"""Files the user must see before a gate marked `shown` is asked about them.

`harness workflow show --artifact <file>...` prints the files and records their digests. A `shown`
gate is then asked only about files shown as they read now. On Claude, tool output is hidden from
the user, so the agent's own reply must also carry every heading the show printed.
"""

from __future__ import annotations

from pathlib import Path

from core.result import Ok, Result, attempt, bind, err, fmap, sequence
from harness import state, work_sessions, workflow
from host_adapters.claude_adapter import assistant_text_after

SHOWN = "shown-artifacts.json"
SHOW_COMMAND = "workflow show"


def show(repo: Path, session: str | None, names: list[str]) -> Result[str]:
    """Print the files a gate will review, and record exactly what was shown."""
    return bind(
        _digests(repo, names),
        lambda digests: bind(
            _record(repo, session, digests),
            lambda _: _render(repo, names),
        ),
    )


def shown(repo: Path, session: str | None, names: list[str]) -> Result[None]:
    """Every file was shown as it reads now."""
    return bind(
        _digests(repo, names),
        lambda digests: bind(
            _read(repo, session),
            lambda recorded: (
                Ok(None)
                if set(digests) <= recorded
                else err(
                    "artifact_not_shown",
                    "show the files first: run `harness workflow show` with these same "
                    "--artifact files and put its output in your reply; a file changed since "
                    "it was shown must be shown again",
                )
            ),
        ),
    )


def shown_in_chat(repo: Path, names: list[str], transcript: Path) -> Result[None]:
    """Claude: the agent's reply after the show carries every heading of these files."""
    return bind(
        _render(repo, names),
        lambda rendered: bind(
            attempt(
                lambda: assistant_text_after(transcript, SHOW_COMMAND),
                "transcript_unavailable",
                "host transcript",
                OSError,
            ),
            lambda text: _all_present(_headings(rendered), text),
        ),
    )


def _digests(repo: Path, names: list[str]) -> Result[tuple[tuple[str, str], ...]]:
    def one(name: str) -> Result[tuple[str, str]]:
        target = (repo / name).resolve()
        if not target.is_relative_to(repo.resolve()) or not target.is_file():
            return err("artifact_invalid", f"{name} is not a file in this project")
        return fmap(workflow.file_digest(target), lambda digest: (name, digest))

    return (
        sequence(one(name) for name in names)
        if names
        else err("artifact_invalid", "name the files to show with --artifact")
    )


def _render(repo: Path, names: list[str]) -> Result[str]:
    def build() -> str:
        parts = [
            "Show everything below this line to the human in your reply, unchanged, before "
            "asking for approval. The approval question is refused until it has been shown.",
        ]
        for name in names:
            parts += [
                "",
                f"## [{name}]({name})",
                "",
                (repo / name).read_text(encoding="utf-8").strip(),
            ]
        return "\n".join(parts) + "\n"

    return attempt(
        build, "artifact_unreadable", "could not read a file to show", OSError
    )


def _headings(rendered: str) -> tuple[str, ...]:
    """Markdown headings, skipping fenced code, where `#` starts a comment."""
    headings: list[str] = []
    fenced = False
    for line in rendered.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
        elif not fenced and stripped.startswith("#"):
            headings.append(stripped)
    return tuple(headings)


def _all_present(expected: tuple[str, ...], text: str) -> Result[None]:
    missing = [line for line in expected if line not in text]
    return (
        Ok(None)
        if not missing
        else err(
            "artifact_not_in_reply",
            "the human has not seen the files: tool output is hidden from them. Put the "
            "`harness workflow show` output in your reply (missing, for example: "
            f"{missing[0]!r}). The host records your reply only once another tool runs, so "
            "text written in the same message as the question is not seen yet: write the files "
            "in your reply, run `harness decision status`, then ask again",
        )
    )


def _record(
    repo: Path, session: str | None, digests: tuple[tuple[str, str], ...]
) -> Result[None]:
    return bind(
        _read(repo, session),
        lambda recorded: bind(
            work_sessions.scope_folder(repo, session),
            lambda folder: attempt(
                lambda: state.write_json(
                    folder / SHOWN,
                    {"artifacts": sorted(map(list, recorded | set(digests)))},
                ),
                "artifact_state_unwritable",
                f"could not save {SHOWN}",
                OSError,
            ),
        ),
    )


def _read(repo: Path, session: str | None) -> Result[set[tuple[str, str]]]:
    return fmap(
        work_sessions.scope_folder(repo, session),
        lambda folder: {
            (str(name), str(digest))
            for name, digest in (state.read_json(folder / SHOWN) or {}).get(
                "artifacts", ()
            )
        },
    )
