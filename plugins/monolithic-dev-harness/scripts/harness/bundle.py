"""The six-stage bundle: refined tracker drafts, showing the bundle, and publishing it after approval.

Three rules the harness checks instead of trusting the agent to remember them:

  refined     the bundle carries a `tracker-drafts.json` batch that forms a valid hierarchy for the
              selected tracker: every Story or Bug has acceptance criteria and child Tasks, every
              Epic and Feature has children, and each child kind is one its parent may hold.
  shown       `harness workflow show` printed the exact files (same digests) the final approval will
              bind, and recorded that it did. `implementation-confirm` is refused until then.
  published   after that approval, `harness tracker publish` creates the drafted items in order,
              once each: a receipt per draft means a rerun never creates an item twice.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, err, fmap, sequence
from harness import state, work_sessions, workflow
from integrations.contracts import Manifest, TrackerOps, WorkItemKind

DRAFTS_NAME = "tracker-drafts.json"
SHOWN = "bundle-shown.json"
PUBLISHED = "tracker-published.json"
HISTORY = "decision-history.json"
APPROVED_ANSWERS = frozenset({"approve", "approved", "yes", "approve and continue"})


@dataclass(frozen=True)
class Draft:
    ref: str
    kind: WorkItemKind
    title: str
    parent: str
    description: str
    acceptance_criteria: tuple[str, ...]
    estimate: float | None


# --- drafts -------------------------------------------------------------------------------------


def load_drafts(path: Path) -> Result[tuple[Draft, ...]]:
    return bind(
        attempt(
            lambda: json.loads(path.read_text(encoding="utf-8")),
            "drafts_unreadable",
            f"could not read {path.name} as JSON",
            OSError,
            ValueError,
        ),
        _parse,
    )


def _parse(document: object) -> Result[tuple[Draft, ...]]:
    match document:
        case {"items": list() as items} if items:
            return sequence(_draft(index, item) for index, item in enumerate(items))
        case _:
            return err(
                "drafts_invalid",
                'tracker drafts must be {"items": [...]} with at least one item',
            )


def _draft(index: int, item: object) -> Result[Draft]:
    if not isinstance(item, Mapping):
        return err("drafts_invalid", f"item {index + 1} is not an object")
    kinds = {kind.value for kind in WorkItemKind}
    kind = str(item.get("kind", ""))
    criteria = item.get("acceptance_criteria", [])
    estimate = item.get("estimate")
    if kind not in kinds:
        return err(
            "drafts_invalid",
            f"item {index + 1} has kind {kind!r}; use one of {', '.join(sorted(kinds))}",
        )
    if not str(item.get("ref", "")).strip() or not str(item.get("title", "")).strip():
        return err("drafts_invalid", f"item {index + 1} needs a ref and a title")
    if not isinstance(criteria, list) or not all(isinstance(c, str) for c in criteria):
        return err(
            "drafts_invalid", f"item {index + 1}: acceptance_criteria is a list of text"
        )
    if estimate is not None and not isinstance(estimate, int | float):
        return err("drafts_invalid", f"item {index + 1}: estimate is a number")
    return Ok(
        Draft(
            ref=str(item["ref"]).strip(),
            kind=WorkItemKind(kind),
            title=str(item["title"]).strip(),
            parent=str(item.get("parent") or "").strip(),
            description=str(item.get("description") or ""),
            acceptance_criteria=tuple(c.strip() for c in criteria if c.strip()),
            estimate=float(estimate) if estimate is not None else None,
        )
    )


def check_drafts(
    drafts: tuple[Draft, ...], manifest: Manifest
) -> Result[tuple[Draft, ...]]:
    """Refinement is complete only when the batch is a hierarchy the tracker can hold."""
    problems: list[str] = []
    seen: dict[str, Draft] = {}
    allowed = {artifact.name: artifact for artifact in manifest.artifacts}
    existing = manifest.ids.pattern
    for draft in drafts:
        if draft.ref in seen:
            problems.append(f"{draft.ref}: ref used twice")
        parent = seen.get(draft.parent)
        if (
            draft.parent
            and parent is None
            and not _existing_key(draft.parent, existing)
        ):
            problems.append(
                f"{draft.ref}: parent {draft.parent} is neither an earlier draft nor a tracker key"
            )
        if (
            parent is not None
            and draft.kind.value
            not in allowed.get(parent.kind.value, _NO_CHILDREN).children
        ):
            problems.append(
                f"{draft.ref}: a {parent.kind.value} cannot hold a {draft.kind.value}"
            )
        if draft.kind is WorkItemKind.TASK and not draft.parent:
            problems.append(f"{draft.ref}: a task needs a parent Story or Bug")
        seen[draft.ref] = draft
    children = {ref: tuple(d for d in drafts if d.parent == ref) for ref in seen}
    for draft in drafts:
        below = children[draft.ref]
        match draft.kind:
            case WorkItemKind.EPIC | WorkItemKind.FEATURE if not below:
                problems.append(f"{draft.ref}: a {draft.kind.value} needs child items")
            case WorkItemKind.USER_STORY | WorkItemKind.BUG:
                if not draft.acceptance_criteria:
                    problems.append(f"{draft.ref}: needs acceptance criteria")
                if not any(d.kind is WorkItemKind.TASK for d in below):
                    problems.append(f"{draft.ref}: needs child tasks")
                if (
                    allowed.get(draft.kind.value, _NO_CHILDREN).estimate
                    and draft.estimate is None
                ):
                    problems.append(f"{draft.ref}: needs an estimate")
            case _:
                pass
    if not any(d.kind in (WorkItemKind.USER_STORY, WorkItemKind.BUG) for d in drafts):
        problems.append("the batch has no Story or Bug to build")
    return (
        Ok(drafts)
        if not problems
        else err(
            "drafts_invalid", "tracker drafts are not refined: " + "; ".join(problems)
        )
    )


@dataclass(frozen=True)
class _Leaf:
    children: tuple[str, ...] = ()
    estimate: str = ""


_NO_CHILDREN = _Leaf()


def _existing_key(ref: str, pattern: str) -> bool:
    import re

    return bool(pattern) and re.fullmatch(pattern, ref) is not None


def outline(drafts: tuple[Draft, ...]) -> str:
    """The batch as an indented tree, for showing the human what will be created."""
    refs = {draft.ref for draft in drafts}
    lines: list[str] = []

    def walk(draft: Draft, depth: int) -> None:
        extra = f" · {draft.estimate:g} pts" if draft.estimate is not None else ""
        lines.append(
            f"{'  ' * depth}- **{draft.kind.value}** {draft.ref}: {draft.title}{extra}"
        )
        for criterion in draft.acceptance_criteria:
            lines.append(f"{'  ' * (depth + 1)}- AC: {criterion}")
        for child in drafts:
            if child.parent == draft.ref:
                walk(child, depth + 1)

    for draft in drafts:
        if draft.parent in refs:
            continue
        if draft.parent:
            lines.append(f"- under existing {draft.parent}:")
        walk(draft, 1 if draft.parent else 0)
    return "\n".join(lines)


# --- showing the bundle -------------------------------------------------------------------------


def _digests(repo: Path, names: list[str]) -> Result[tuple[tuple[str, str], ...]]:
    def one(name: str) -> Result[tuple[str, str]]:
        target = (repo / name).resolve()
        if not target.is_relative_to(repo.resolve()) or not target.is_file():
            return err("bundle_invalid", f"{name} is not a file in this project")
        return fmap(workflow.file_digest(target), lambda digest: (name, digest))

    return sequence(one(name) for name in names)


def _drafts_in(
    repo: Path, names: list[str], manifest: Manifest
) -> Result[tuple[str, tuple[Draft, ...]]]:
    found = [name for name in names if Path(name).name == DRAFTS_NAME]
    match found:
        case [name]:
            return fmap(
                bind(load_drafts(repo / name), lambda d: check_drafts(d, manifest)),
                lambda drafts: (name, drafts),
            )
        case []:
            return err(
                "bundle_unrefined",
                f"the bundle has no {DRAFTS_NAME}: refine the work into tracker items first "
                "(generate-work-item or decompose-backlog, then generate-breakdown-work-items, "
                "in draft mode) and pass the drafts file with --artifact",
            )
        case _:
            return err("bundle_invalid", f"pass exactly one {DRAFTS_NAME}")


def show(
    repo: Path, session: str | None, names: list[str], manifest: Manifest
) -> Result[str]:
    """Print the bundle the approval will bind, and record that exactly these files were shown."""
    if not names:
        return err(
            "bundle_invalid", "name the bundle's files with --artifact, plan first"
        )
    return bind(
        _drafts_in(repo, names, manifest),
        lambda found: bind(
            _digests(repo, names),
            lambda digests: bind(
                _record(
                    repo, session, SHOWN, {"artifacts": [list(d) for d in digests]}
                ),
                lambda _: _render(repo, names, found),
            ),
        ),
    )


def _render(
    repo: Path, names: list[str], found: tuple[str, tuple[Draft, ...]]
) -> Result[str]:
    drafts_name, drafts = found

    def build() -> str:
        plan, *companions = names
        parts = [
            "Show everything below this line to the human in your reply, unchanged, before asking "
            "for approval. The approval question is refused until this bundle has been shown.",
            "",
            f"## Implementation plan — [{plan}]({plan})",
            "",
            (repo / plan).read_text(encoding="utf-8").strip(),
            "",
            f"## Work items to create — [{drafts_name}]({drafts_name})",
            "",
            outline(drafts),
        ]
        others = [name for name in companions if name != drafts_name]
        if others:
            parts += ["", "## Companion files", ""]
            parts += [f"- [{name}]({name})" for name in others]
        return "\n".join(parts) + "\n"

    return attempt(build, "bundle_unreadable", "could not read the bundle", OSError)


def ready(
    repo: Path, session: str | None, names: list[str], manifest: Manifest
) -> Result[None]:
    """`implementation-confirm` may be asked only about a refined bundle shown as it is now."""
    return bind(
        _drafts_in(repo, names, manifest),
        lambda _: bind(
            _digests(repo, names),
            lambda digests: bind(
                _read(repo, session, SHOWN),
                lambda shown: (
                    Ok(None)
                    if sorted(map(tuple, shown.get("artifacts", ()))) == sorted(digests)
                    else err(
                        "bundle_not_shown",
                        "show the bundle first: run `harness workflow show` with these same "
                        "--artifact files and put its output in your reply; any file changed "
                        "since it was shown must be shown again",
                    )
                ),
            ),
        ),
    )


# --- publishing ---------------------------------------------------------------------------------


def publish(
    repo: Path,
    session: str | None,
    drafts_name: str,
    manifest: Manifest,
    ops: TrackerOps,
) -> Result[str]:
    """Create the approved drafts in order, once each, recording a receipt per item."""
    return bind(
        _approved(repo, session, drafts_name),
        lambda _: bind(
            bind(load_drafts(repo / drafts_name), lambda d: check_drafts(d, manifest)),
            lambda drafts: _create_all(repo, session, drafts, ops),
        ),
    )


def _last_approval(entries: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The session's last implementation-confirm answer when it approved; a later Revise or Stop
    withdraws an earlier approval."""
    answers = [
        entry
        for entry in entries
        if entry.get("gate") == "implementation-confirm"
        and entry.get("status") == "answered"
    ]
    match answers:
        case [*_, last] if (
            str(last.get("answer", "")).strip().casefold() in APPROVED_ANSWERS
        ):
            return last
        case _:
            return None


def covers(repo: Path, session: str, work_item: str) -> bool:
    """The session's last implementation-confirm answer approved its bundle, every reviewed file
    is unchanged since, and that bundle published `work_item`."""
    match _history(repo, session), _read(repo, session, PUBLISHED):
        case Ok(entries), Ok(published):
            pass
        case _:
            return False
    approval = _last_approval(entries)
    reviewed = approval.get("artifacts") if approval is not None else None
    return (
        approval is not None
        and approval.get("approval") is True
        and isinstance(reviewed, list)
        and bool(reviewed)
        and _unchanged(repo, reviewed)
        and work_item in dict(published.get("keys", {})).values()
    )


def _unchanged(repo: Path, reviewed: list[Any]) -> bool:
    pairs = [entry for entry in reviewed if isinstance(entry, list) and len(entry) == 2]
    return len(pairs) == len(reviewed) and _digests(
        repo, [str(name) for name, _ in pairs]
    ) == Ok(tuple((str(name), digest) for name, digest in pairs))


def _approved(repo: Path, session: str | None, drafts_name: str) -> Result[None]:
    def approved(entries: list[Mapping[str, Any]], digest: str) -> bool:
        approval = _last_approval(entries)
        return approval is not None and [drafts_name, digest] in approval.get(
            "artifacts", []
        )

    return bind(
        _digests(repo, [drafts_name]),
        lambda digests: bind(
            _history(repo, session),
            lambda entries: (
                Ok(None)
                if approved(entries, digests[0][1])
                else err(
                    "publish_unapproved",
                    f"{drafts_name} is not part of an approved implementation bundle as it is "
                    "now; publish only after implementation-confirm approved these drafts",
                )
            ),
        ),
    )


def _create_all(
    repo: Path, session: str | None, drafts: tuple[Draft, ...], ops: TrackerOps
) -> Result[str]:
    match _read(repo, session, PUBLISHED):
        case Err() as failure:
            return failure
        case Ok(previous):
            keys: dict[str, str] = dict(previous.get("keys", {}))
    created: list[str] = []
    for draft in drafts:
        if draft.ref in keys:
            continue
        parent = keys.get(draft.parent, draft.parent)
        match ops.create_work_item(
            draft.kind, draft.title, _description(draft), parent
        ):
            case Err() as failure:
                return failure
            case Ok(item):
                keys[draft.ref] = item.key
                created.append(f"{draft.ref} → {item.key} {draft.title}")
                match _record(repo, session, PUBLISHED, {"keys": keys}):
                    case Err() as failure:
                        return failure
                    case Ok():
                        pass
    return Ok(
        "\n".join(created)
        if created
        else "every draft was already created; nothing to do"
    )


def _description(draft: Draft) -> str:
    parts = [draft.description.strip()] if draft.description.strip() else []
    if draft.acceptance_criteria:
        parts.append(
            "Acceptance criteria:\n"
            + "\n".join(f"- {criterion}" for criterion in draft.acceptance_criteria)
        )
    if draft.estimate is not None:
        parts.append(f"Estimate: {draft.estimate:g} points")
    return "\n\n".join(parts)


# --- session records ----------------------------------------------------------------------------


def _record(repo: Path, session: str | None, name: str, value: dict) -> Result[None]:
    return bind(
        work_sessions.scope_folder(repo, session),
        lambda folder: attempt(
            lambda: state.write_json(folder / name, value),
            "bundle_state_unwritable",
            f"could not save {name}",
            OSError,
        ),
    )


def _read(repo: Path, session: str | None, name: str) -> Result[dict]:
    return fmap(
        work_sessions.scope_folder(repo, session),
        lambda folder: state.read_json(folder / name) or {},
    )


def _history(repo: Path, session: str | None) -> Result[list[Mapping[str, Any]]]:
    return fmap(
        work_sessions.scope_folder(repo, session),
        lambda folder: [
            *((state.read_json(folder / HISTORY) or {}).get("answers", [])),
            state.read_json(folder / "decision.json") or {},
        ],
    )


# --- shown in the conversation ------------------------------------------------------------------


def shown_in_chat(
    repo: Path, session: str | None, transcript: Path, manifest: Manifest
) -> Result[None]:
    """Claude: the agent's own reply, not just a tool result, must carry the shown bundle.

    Tool output is collapsed in the host, so the check reads the transcript: every heading and
    file link of the bundle `workflow show` printed must appear in assistant text written after
    that command ran.
    """
    return bind(
        _read(repo, session, SHOWN),
        lambda shown: bind(
            _expected_lines(
                repo, [str(name) for name, _ in shown.get("artifacts", ())], manifest
            ),
            lambda expected: bind(
                _assistant_text_after_show(transcript),
                lambda text: _all_present(expected, text),
            ),
        ),
    )


def _expected_lines(
    repo: Path, names: list[str], manifest: Manifest
) -> Result[tuple[str, ...]]:
    if not names:
        return err(
            "bundle_not_shown", "run `harness workflow show` before the final approval"
        )
    return fmap(
        bind(
            _drafts_in(repo, names, manifest), lambda found: _render(repo, names, found)
        ),
        lambda rendered: tuple(
            line.strip()
            for line in rendered.splitlines()
            if line.lstrip().startswith(("#", "- [")) and line.strip()
        ),
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
            "bundle_not_in_reply",
            "the human has not seen the bundle: tool output is hidden from them. Put the "
            "`harness workflow show` output in your reply (missing, for example: "
            f"{missing[0]!r}), then ask again",
        )
    )
