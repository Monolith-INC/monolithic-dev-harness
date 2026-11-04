"""The harness rules, evaluated on every governed tool call. Each deny names its rule.

human-owned         The settings, approvals, manual-check, check and review records, sessions, code baselines,
                    local tracker records, and tracker trust are human-owned.
tracker-invalid     While the selected tracker is missing or broken, tracker and SCM writes are refused, and so is
                    every call to an MCP server that is not the harness's own.
approval-required   Tracker and SCM writes need an approval window opened by the user (a prompt or a click).
protected-items     Protected work items are never written, linked, or parented — approval does not override.
generated-files     Generated files are never edited by hand.
draft-reviewed-prs  Publishing a draft pull request and voting are left to humans. With Git-based delivery,
                    pull requests are created as drafts, only with a `ready` review verdict and passing
                    checks for the code as it is now.
history-preserved   With Git-based delivery, branch history is never rewritten: no rebase, squash merge, or
                    force-push.
feature-branch      With Git-based delivery, a Feature's Story pull request targets the Feature branch.

Tests with code and guarded-path evidence are completion requirements in the workflow catalog
(`harness.workflow_requirements`), checked before a work item is done; no rule reads a commit.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from core.result import Ok

from . import (
    code_content,
    gitstate,
    globs,
    local_tracker,
    sessions,
    shellscan,
    state,
    tracker_policy,
    work_sessions,
    workflow,
)
from .settings import Settings
from .tracker_policy import TrackerPolicy

GATEWAY_WRITES = frozenset(
    {
        "tracker_create_work_item",
        "tracker_update_work_item",
        "tracker_transition_work_item",
        "tracker_publish_artifact",
        "tracker_link_development_artifact",
        "scm_create_pull_request",
        "scm_reply_to_thread",
        "scm_create_review_thread",
        "scm_update_thread_comment",
        "scm_set_thread_status",
        "scm_link_work_item",
        "workflow_skip_tracker",  # pausing enforcement is a human decision
    }
)
_ID_KEYS = frozenset(
    {
        "id",
        "ids",
        "parentId",
        "workItemId",
        "linkToId",
        "ref",
        "work_item_ref",
        "workItemRef",
        "workItems",
        "parentRef",
        "issueId",
    }
)
# Field names and patch paths that set a work item's parent.
_PARENT_FIELDS = frozenset({"System.Parent"})
_NESTED_ID_LISTS = ("batchUpdates", "updates", "items")


@dataclass(frozen=True)
class ToolCall:
    name: str
    kind: str = (
        "other"  # shell, edit, read, mcp, or other; classified by a host adapter
    )
    server: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    cwd: str = ""  # where the host runs the tool; a shell's relative paths start here
    command: str = ""
    file_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    allowed: bool
    rule: str | None = None
    reason: str | None = None

    @classmethod
    def allow(cls) -> Decision:
        return cls(True)

    @classmethod
    def deny(cls, rule: str, reason: str) -> Decision:
        return cls(False, rule, f"[harness {rule}] {reason}")


def make_call(
    name: str,
    tool_input: dict[str, Any] | None,
    server: str = "",
    cwd: str = "",
    *,
    kind: str = "other",
    command: str = "",
    file_paths: tuple[str, ...] = (),
) -> ToolCall:
    return ToolCall(
        name=name,
        kind=kind,
        server=server,
        tool_input=tool_input or {},
        cwd=cwd,
        command=command,
        file_paths=file_paths,
    )


def is_gateway_write(call: ToolCall) -> bool:
    return call.name in GATEWAY_WRITES


def is_remote_write(call: ToolCall, policy: TrackerPolicy) -> bool:
    """A call that changes the tracker or the repository's server: it needs an approval window."""
    match call.kind:
        case "shell":
            return "push" in git_subcommands(call.command)
        case "edit" if not call.server:
            return False
        case _:
            return is_gateway_write(call) or tracker_policy.writes_to_tracker(
                policy, call.server, call.name
            )


def is_write_class(call: ToolCall) -> bool:
    """Calls that must fail closed when the rules themselves cannot run.

    Every edit and shell command counts: if the rules could not read it, nothing says it only
    reads. So does every call to an MCP server, because without the tracker folders nothing says
    which of its tools write.
    """
    return call.kind != "read" or is_gateway_write(call)


# --- helpers ------------------------------------------------------------------------------


def _scalars(value: Any) -> tuple[str, ...]:
    match value:
        case bool() | None:
            return ()
        case str() | int():
            return (str(value),)
        case list() | tuple():
            return tuple(text for item in value for text in _scalars(item))
        case _:
            return ()


def referenced_values(tool_input: dict[str, Any]) -> tuple[str, ...]:
    """Values that name a work item: id fields, nested update entries, and the parent field."""
    nested = tuple(
        entry
        for key in _NESTED_ID_LISTS
        for entry in (tool_input.get(key) or ())
        if isinstance(entry, dict)
    )
    fields = tuple(
        entry
        for key in ("fields", "updates", "batchUpdates")
        for entry in (tool_input.get(key) or ())
        if isinstance(entry, dict)
    )
    return (
        *(
            text
            for key, value in tool_input.items()
            if key in _ID_KEYS
            for text in _scalars(value)
        ),
        *(
            text
            for entry in nested
            for key in ("id", "linkToId", "parentId")
            for text in _scalars(entry.get(key))
        ),
        # Setting the parent field is linking, whether as a create field or an update patch.
        *(
            text
            for entry in fields
            if str(entry.get("name") or entry.get("path") or "").rsplit("/", 1)[-1]
            in _PARENT_FIELDS
            for text in _scalars(entry.get("value"))
        ),
    )


def texts(value: Any) -> tuple[str, ...]:
    """Every string anywhere inside a tool input."""
    match value:
        case str():
            return (value,)
        case dict():
            return tuple(text for item in value.values() for text in texts(item))
        case list() | tuple():
            return tuple(text for item in value for text in texts(item))
        case _:
            return ()


def git_invocations(
    command: str, cwd: str | None = ""
) -> list[tuple[str | None, list[str]]]:
    """Every `git` the command runs: (its directory, argv after options). See `shellscan`."""
    return shellscan.git_commands(command, cwd)


def git_subcommands(command: str) -> set[str]:
    return {argv[0] for _, argv in git_invocations(command) if argv}


def _relative(repo: Path, path: str) -> str:
    """`path` relative to the repository, with `.` and `..` collapsed so they cannot hide a target."""
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return candidate.as_posix()
    normalized = posixpath.normpath(globs.normalize(path)) if path else ""
    if normalized == "..":
        normalized = "../."
    if normalized.startswith("../"):
        # It left the repository and may have come back in (`../repo/.harness`): resolve it.
        try:
            return (repo / normalized).resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return normalized
    return "" if normalized == "." else normalized


def _shell_start(call: ToolCall, repo: Path) -> str:
    """Where the shell starts, relative to the repository (`""` for its root)."""
    if not call.cwd:
        return ""
    # Both sides resolved: the repository root comes from git, which resolves symlinks, and a
    # session opened through a symlinked path would otherwise seem to sit outside it.
    relative = posixpath.normpath(
        os.path.relpath(Path(call.cwd).resolve(), repo.resolve())
    )
    return "" if relative == "." else relative


# --- rules --------------------------------------------------------------------------------


# Human-owned paths, as components under the repository root. A write into `.harness/` or
# `.harness/state/` could create one; anything under the last three is a record.
_OWNED_FILES = (
    (".harness",),
    (".harness", "state"),
    (".harness", "settings.json"),
    (".harness", "state", "tracking.json"),
    (".harness", "state", "suspension.json"),
    (".harness", "state", "decision.json"),
    (".harness", "state", "decision-history.json"),
    (".harness", "state", "onboarding.json"),
    (".harness", "state", "setup-proposal.json"),
    (".harness", "state", "setup-cancelled.json"),
)
_OWNED_DIRS = (
    (".harness", "state", "gateway-owners"),
    (".harness", "state", "approvals"),
    (".harness", "state", "manual"),
    (".harness", "state", "asked"),
    (".harness", "state", "control-questions"),
    (".harness", "state", "question-observations"),
    (".harness", "state", "sessions"),
    (".harness", "state", "work_sessions"),
    (".harness", "state", "host_sessions"),
    (".harness", "state", "trackers"),
    (".harness", "state", "adoptions"),
    # Evidence the workflow requirements trust: written by checks.py, review_verdict.py, and
    # the code baseline at link time, never by hand.
    (".harness", "state", "checks"),
    (".harness", "state", "review"),
    (".harness", "state", "code-baselines"),
)


def _components_match(names: tuple[str, ...], patterns: list[str]) -> bool:
    """Whether a (possibly globbed) path's components can name `names`."""
    return len(names) == len(patterns) and all(
        fnmatch(name, pattern) for name, pattern in zip(names, patterns, strict=True)
    )


def is_human_owned(relative: str, tree: bool = False) -> bool:
    """Whether writing `relative` could change the policy, an approval, or a manual-check record.

    `tree` means the write reaches everything under `relative` (`rm -r`, `git clean`), so an
    ancestor of `.harness/` counts too. Globs count when they could match.
    """
    parts = [part for part in relative.split("/") if part not in ("", ".")]
    if parts[:1] == [".."] or relative.startswith(("/", "~")):
        return False
    for owned in _OWNED_FILES:
        if _components_match(owned, parts):
            return True
    for owned in _OWNED_DIRS:
        if len(parts) >= len(owned) and _components_match(owned, parts[: len(owned)]):
            return True
        if len(parts) == len(owned) - 1 and _components_match(owned[:-1], parts):
            return True
    if tree:
        deepest = _OWNED_DIRS[0]
        return len(parts) < len(deepest) and _components_match(
            deepest[: len(parts)], parts
        )
    return False


def _names_harness(word: str) -> bool:
    """Whether a word from code the scanner cannot follow could name `.harness`.

    A wildcard-only word such as `.**` (Markdown bold in a heredoc) is prose, not a target; a glob
    counts once it spells part of the name, as `.h*` does.
    """
    return any(
        fnmatch(".harness", part) and any(char.isalnum() for char in part)
        for part in word.split("/")
        if part
    )


def _inside(relative: str) -> bool:
    """Whether a path from `_relative` may be in the repository; `~/…` may be, so it stays."""
    return not relative.startswith("/") and relative.split("/", 1)[0] != ".."


def _words_naming_harness(repo: Path, words: tuple[str, ...]) -> Iterator[str]:
    """Words of code the scanner cannot follow that could name `.harness` in the repository."""
    relatives = (_relative(repo, word) for word in words)
    return (r for r in relatives if _inside(r) and _names_harness(r))


def shell_human_owned_write(call: ToolCall, repo: Path) -> str | None:
    """The human-owned path a shell command could write, if any."""
    writes = shellscan.scan(call.command, _shell_start(call, repo), repo)
    for path in writes.targets:
        if is_human_owned(_relative(repo, path)):
            return _relative(repo, path)
    for path in writes.trees:
        if is_human_owned(_relative(repo, path), tree=True):
            return _relative(repo, path) or "the repository root"
    named = list(_words_naming_harness(repo, writes.unresolved))
    return next(filter(is_human_owned, named), named[0] if named else None)


def shell_writes_human_owned(command: str, repo: Path | None = None) -> bool:
    return (
        shell_human_owned_write(
            make_call("shell", {"command": command}, kind="shell", command=command),
            repo or Path("."),
        )
        is not None
    )


def shell_writes_matching(
    call: ToolCall, repo: Path, patterns: list[str]
) -> str | None:
    """The first path a shell command could write that matches `patterns`, if any."""
    writes = shellscan.scan(call.command, _shell_start(call, repo), repo)
    for path in (*writes.targets, *writes.unresolved):
        relative = _relative(repo, path)
        if relative and _inside(relative) and globs.matches(relative, patterns):
            return relative
    return None


_HOOK_SCRIPT = re.compile(r"(?:^|[\s/'\"=])(?:hook|hook_runtime)\.py\b")
_HOOK_MODULE = re.compile(
    r"\bhook_runtime\b|\bharness\.hook\b|\bharness\s+import\s+.*\bhook\b"
    r"|\bhost_adapters\.startup_context\b|\bhost_adapters\s+import\s+.*\bstartup_context\b"
)


def runs_harness_hook(command: str) -> bool:
    """Whether a shell command runs the harness's own hook entry points.

    The prompt and answer hooks record the user's answers and approvals from what they read on
    stdin, so an agent that pipes a payload into them could answer for the user. Reading, staging,
    committing or placing the source is not running it.
    """
    plain = shellscan.plain_git_context(command)
    return any(
        _invocation_mentions_hook(invocation, plain=plain)
        for invocation in shellscan.invocations(command)
    )


# Git calls that read, stage or record a file without running it.
_INERT_GIT = frozenset(
    {
        "blame",
        "commit",
        "diff",
        "log",
        "ls-files",
        "mv",
        "restore",
        "rm",
        "show",
        "status",
    }
)
# Commands that put a file somewhere else without running it.
_PLACERS = frozenset({"cp", "install", "ln", "mv"})


def _git_inert(args: tuple[str, ...]) -> bool:
    """Directory and filemode options are fine; an editor, external diff or other configuration is not."""
    match args:
        case ("-C", _, *rest) | ("-c", "core.filemode=false", *rest):
            return _git_inert(tuple(rest))
        case ("add", *rest):
            return _noninteractive_staging(tuple(rest))
        case (subcommand, *rest) if subcommand in _INERT_GIT:
            return "--ext-diff" not in rest
        case _:
            return False


def _noninteractive_staging(args: tuple[str, ...]) -> bool:
    match args:
        case () | ("--", *_):
            return True
        case (option, *rest) if not option.startswith("-") or option in {
            "-A",
            "--all",
            "-u",
            "--update",
            "-f",
            "--force",
            "-N",
            "--intent-to-add",
            "--renormalize",
            "-n",
            "--dry-run",
            "-v",
            "--verbose",
            "--ignore-errors",
        }:
            return _noninteractive_staging(tuple(rest))
        case _:
            return False


def _leaves_hook_alone(invocation: shellscan.Invocation, *, plain: bool) -> bool:
    name, args = invocation.name, invocation.args
    return (
        name in shellscan.NON_WRITERS
        or name in _PLACERS
        or (name == "ruff" and args[:1] in (("check",), ("format",)))
        or (name == "git" and plain and _git_inert(args))
        or (
            name in shellscan.IN_PLACE_FLAGS
            and not any(shellscan.IN_PLACE_FLAGS[name].match(arg) for arg in args)
        )
    )


def _invocation_mentions_hook(invocation: shellscan.Invocation, *, plain: bool) -> bool:
    """Whether a command names the hook where it could run it, assignments and wrappers included."""
    words = invocation.raw or (invocation.name, *invocation.args)
    where = (*words, invocation.cwd or "")
    return not _leaves_hook_alone(invocation, plain=plain) and (
        any(_HOOK_MODULE.search(word) for word in words)
        or (
            any(_HOOK_SCRIPT.search(word) for word in where)
            and any("harness" in word for word in where)
        )
    )


def rule_hook_entry(call: ToolCall) -> Decision:
    """Only the host runs the harness hooks; a shell command that runs them is refused."""
    if call.kind == "shell" and runs_harness_hook(call.command):
        return Decision.deny(
            "hook-entry",
            "Only the host runs the harness hooks. Running them yourself could record an answer "
            "or approval the user never gave, so this command is refused.",
        )
    return Decision.allow()


def rule_human_owned(call: ToolCall, repo: Path) -> Decision:
    """The settings, approvals, manual checks, sessions, and tracker trust are written by people or the harness."""
    if call.kind == "edit":
        if call.command and not call.file_paths:
            return Decision.deny(
                "human-owned",
                "The harness could not read which files this patch changes, so it cannot rule out "
                "human-owned files. Write each file header as `*** Update File: <path>`.",
            )
        for path in call.file_paths:
            if is_human_owned(_relative(repo, path)):
                return Decision.deny(
                    "human-owned",
                    f"{_relative(repo, path)} is human-owned. Approvals, manual checks, and tracker trust are "
                    "recorded from the user's own prompt; checkout sessions change through `harness session`, "
                    "and work sessions through `harness work-session`; check results and review verdicts "
                    "are recorded by scripts/harness/checks.py and review_verdict.py; the "
                    "settings are edited by a person (or created once by bootstrap).",
                )
    if call.kind == "shell":
        written = shell_human_owned_write(call, repo)
        if written:
            return Decision.deny(
                "human-owned",
                f"this command could write {written}, which is human-owned harness state or settings.",
            )
    return Decision.allow()


_PROVIDER_ID = re.compile(r"^provider_id:", re.MULTILINE)


def rule_tracked_tickets(call: ToolCall, repo: Path, settings: Settings) -> Decision:
    """With the local tracker, a ticket that is a tracked item changes only through its tools.

    Drafts in `Tickets/` (no `provider_id`) are written by the agile-backlog-toolkit's skills.
    """
    if call.kind != "edit" or settings.tracker.name != "local":
        return Decision.allow()
    root = local_tracker.storage_root(repo).resolve()
    written = " ".join(
        str(call.tool_input.get(name) or "") for name in ("content", "new_string")
    )
    for path in call.file_paths:
        target = (repo / _relative(repo, path)).resolve()
        if not target.is_relative_to(root):
            continue
        if (
            local_tracker.ATTACHMENTS in target.relative_to(root).parts
            or (target.is_file() and local_tracker.is_item(target))
            or _PROVIDER_ID.search(written)
        ):
            return Decision.deny(
                "tracked-tickets",
                f"{_relative(repo, path)} is a work item in the local tracker (or its "
                "attachment). Change it with the tracker tools (`tracker_update_work_item`, "
                "`tracker_transition_work_item`, `tracker_publish_artifact`) after the user "
                "approves the change. A draft without `provider_id` may be written directly.",
            )
    return Decision.allow()


def rule_tracker_valid(call: ToolCall, policy: TrackerPolicy) -> Decision:
    return (
        Decision.deny(
            "tracker-invalid",
            f"`{call.name}` writes to the tracker or the repository's server, and which calls write "
            f"cannot be known: {policy.problem}. Ask a person to fix .harness/settings.json or the "
            "tracker folder it names.",
        )
        if policy.problem and is_remote_write(call, policy)
        else Decision.allow()
    )


def rule_protected_items(call: ToolCall, policy: TrackerPolicy) -> Decision:
    match call.kind:
        case "shell":
            return _shell_protected_mentions(call, policy)
        case _ if not policy.protected or not is_remote_write(call, policy):
            return Decision.allow()
        case _:
            return _protected_in_input(call, policy)


def _protected_in_input(call: ToolCall, policy: TrackerPolicy) -> Decision:
    named = frozenset(
        found
        for value in referenced_values(call.tool_input)
        for found in tracker_policy.ids_in(policy, value)
    )
    linked = frozenset(
        found
        for text in texts(call.tool_input)
        for found in tracker_policy.mentioned_in(policy, text)
    )
    hit, mentioned = sorted(named & policy.protected), sorted(linked & policy.protected)
    return (
        Decision.deny(
            "protected-items",
            f"work item(s) {hit} are protected in .harness/settings.json and are never written, linked, or "
            "parented, not even with approval (links are two-way and would change them). Name the item in "
            "plain text instead, for example 'Idea 4007', without '#' or a link.",
        )
        if hit
        else Decision.deny(
            "protected-items",
            f"the text mentions protected work item(s) {mentioned} in a form the tracker turns into a link, "
            "which changes the protected item. Name it in plain text instead, for example 'Idea 4007'.",
        )
        if mentioned
        else Decision.allow()
    )


def _shell_protected_mentions(call: ToolCall, policy: TrackerPolicy) -> Decision:
    """A commit message (or tag) links a work item through a mention once it is pushed.

    Checked when the commit is made, not only when it is pushed: the harness's own flow commits
    and pushes in separate calls, and the push itself carries no text.
    """
    linking = bool(
        git_subcommands(call.command) & {"commit", "push", "tag", "notes", "merge"}
    )
    mentioned = (
        sorted(tracker_policy.mentioned_in(policy, call.command) & policy.protected)
        if linking
        else []
    )
    return (
        Decision.deny(
            "protected-items",
            f"this commit or push mentions protected work item(s) {mentioned}, which the repository's server "
            "turns into a link on the protected item. Name it in plain text instead, for example 'Idea 4007'.",
        )
        if mentioned
        else Decision.allow()
    )


def rule_draft_reviewed_prs(
    call: ToolCall, repo: Path, settings: Settings, work_session_id: str | None = None
) -> Decision:
    action = call.tool_input.get("action")
    if call.name == "repo_pull_request_write" and action == "vote":
        return Decision.deny(
            "draft-reviewed-prs",
            "voting on a pull request is a human decision (gate G4).",
        )
    if (
        call.name == "repo_pull_request_write"
        and action == "update"
        and call.tool_input.get("isDraft") is False
    ):
        return Decision.deny(
            "draft-reviewed-prs",
            "publishing a draft pull request is a human decision (gate G4). Do it in Azure Repos.",
        )
    if not _creates_pull_request(call) or not settings.git_delivery:
        return Decision.allow()
    draft = call.tool_input.get("isDraft", call.tool_input.get("draft"))
    if settings.require_draft and draft is not True:
        return Decision.deny(
            "draft-reviewed-prs",
            "pull requests must be created as drafts (isDraft: true); a human publishes them (gate G4).",
        )
    # Evidence describes the files on disk; a pull request carries commits. With Git-based delivery
    # they must be the same code.
    try:
        uncommitted = gitstate.git(
            repo, "status", "--porcelain", "--untracked-files=no"
        )
    except gitstate.GitError as exc:
        return Decision.deny(
            "draft-reviewed-prs", f"cannot read the working tree: {exc}"
        )
    if uncommitted:
        return Decision.deny(
            "draft-reviewed-prs",
            "the working tree has uncommitted changes, so the review and check evidence would "
            "describe code the pull request does not carry. Commit (and re-run the checks and "
            "review) first.",
        )
    current = code_content.files(repo)
    digest = code_content.digest(current)
    if (
        settings.require_review_verdict
        and state.review_verdict(repo, digest) != "ready"
    ):
        return Decision.deny(
            "draft-reviewed-prs",
            f"no `ready` review verdict for the code as it is now ({digest[:12]}). Run the review "
            "stage; it records the verdict with scripts/harness/review_verdict.py after the "
            "requirements check and thermos pass.",
        )
    required = code_content.applicable_checks(
        settings, code_content.changed_since_link(repo, work_session_id, current)
    )
    missing = required - state.passed_checks(repo, digest)
    if missing:
        return Decision.deny(
            "draft-reviewed-prs",
            f"checks {sorted(missing)} have no passing evidence for the code as it is now "
            f"({digest[:12]}). Run scripts/harness/checks.py.",
        )
    return Decision.allow()


def _creates_pull_request(call: ToolCall) -> bool:
    return (
        call.name == "repo_pull_request_write"
        and call.tool_input.get("action") == "create"
    ) or call.name == "scm_create_pull_request"


def _pull_request_target(call: ToolCall) -> str:
    """The target branch of a PR creation, in either provider's shape."""
    return str(
        call.tool_input.get("targetBranch")
        or call.tool_input.get("targetRefName")
        or ""
    ).removeprefix("refs/heads/")


def _branch_name(repo: Path, ref: str) -> str:
    """`feature/x` for `refs/heads/feature/x`, `origin/feature/x`, or `refs/remotes/origin/feature/x`."""
    name = ref.removeprefix("refs/heads/").removeprefix("refs/remotes/")
    remote, _, rest = name.partition("/")
    try:
        remotes = set(gitstate.git(repo, "remote").split())
    except gitstate.GitError:
        remotes = set()
    return rest if rest and remote in remotes else name


def rule_feature_branch(call: ToolCall, repo: Path) -> Decision:
    """A Feature-managed Story PR targets the Feature branch pinned by its session."""
    if not _creates_pull_request(call):
        return Decision.allow()
    match sessions.resolve(repo):
        case sessions.Bound(session) if (
            session.workflow == "feature-implementation" and session.expected_base_ref
        ):
            target = _branch_name(repo, _pull_request_target(call))
            expected = _branch_name(repo, session.expected_base_ref)
            return (
                Decision.allow()
                if target == expected
                else Decision.deny(
                    "feature-branch",
                    f"this Story belongs to Feature branch {session.expected_base_ref!r}; "
                    "create its pull request into that branch.",
                )
            )
        case _:
            return Decision.allow()


# What a remote write is about: ("branch", name), ("pr", ref), ("item", ref) for an existing work
# item, ("content", ref) for rewriting an existing item's text or size, ("tracker", "") for a new
# one, or ("general", "").
Target = tuple[str, str]
_BRANCH_WRITES = frozenset({"scm_create_pull_request"})
_PR_WRITES = frozenset(
    {
        "scm_reply_to_thread",
        "scm_create_review_thread",
        "scm_update_thread_comment",
        "scm_set_thread_status",
        "scm_link_work_item",
    }
)
# Pausing enforcement is a general permission: only a short general window covers it.
_GENERAL_WRITES = frozenset({"workflow_skip_tracker"})
# Fields whose change rewrites what an item says; only an approval of the reviewed text covers it.
_CONTENT_FIELDS = frozenset({"title", "description", "storyPoints"})


def write_targets(call: ToolCall, repo: Path) -> tuple[Target, ...]:
    """Every target a remote write touches, so an approval can be matched to its context."""
    if call.kind == "shell":
        return tuple(
            ("branch", branch)
            for directory, argv in git_invocations(
                call.command, _shell_start(call, repo)
            )
            if argv and argv[0] == "push"
            for branch in _pushed_branches(argv[1:], _git_dir(repo, directory))
        )
    if call.name in _BRANCH_WRITES:
        return (("branch", str(call.tool_input.get("sourceBranch", ""))),)
    if call.name in _PR_WRITES:
        return (("pr", str(call.tool_input.get("pullRequestRef", ""))),)
    if call.name in _GENERAL_WRITES:
        return (("general", ""),)
    if call.name == "tracker_update_work_item" and _CONTENT_FIELDS & set(
        call.tool_input
    ):
        return (("content", str(call.tool_input.get("ref", ""))),)
    return tuple(("item", ref) for ref in referenced_values(call.tool_input)) or (
        ("tracker", ""),
    )


def _git_dir(repo: Path, directory: str | None) -> Path:
    if not directory:
        return repo
    return Path(directory) if Path(directory).is_absolute() else repo / directory


def _pushed_branches(args: list[str], where: Path) -> tuple[str, ...]:
    """Branches a `git push` updates: its refspecs' destinations, else the current branch."""
    positional = [arg for arg in args if not arg.startswith("-")]
    refspecs = positional[1:]
    if refspecs:
        return tuple(
            spec.lstrip("+").rsplit(":", 1)[-1].removeprefix("refs/heads/")
            for spec in refspecs
        )
    try:
        return (
            gitstate.git(where, "symbolic-ref", "--quiet", "--short", "HEAD").strip(),
        )
    except gitstate.GitError:
        return ("",)


def _context_unchanged(
    repo: Path, binds: dict[str, Any], approval_id: str = ""
) -> bool:
    """Every reviewed file reads as it did. A reviewed draft in `Tickets/` that became its item
    still counts as reviewed: the toolkit renames the draft, or writes the new item's id into the
    same file. It is then gone, or an item this approval created (the gateway's receipt says so)
    whose body is still the approved one. One approval can publish a whole batch."""
    tickets = local_tracker.storage_root(repo).resolve()
    bodies = set(binds.get("bodies", ()))
    for name, digest in binds.get("artifacts", ()):
        path = repo / str(name)
        if path.resolve().is_relative_to(tickets) and (
            not path.exists() or _published_as_approved(repo, path, bodies, approval_id)
        ):
            continue
        if workflow.file_digest(path) != Ok(digest):
            return False
    return True


def _published_as_approved(
    repo: Path, path: Path, bodies: set[str], approval_id: str
) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    key = str(local_tracker.parse_frontmatter(text)[0].get("provider_id") or "")
    return (
        bool(key and approval_id)
        and local_tracker.body_digest(text) in bodies
        and any(
            receipt.get("approval_id") == approval_id and receipt.get("item") == key
            for receipt_path in work_sessions.root(repo).glob("*/publications/*.json")
            for receipt in (state.read_json(receipt_path) or {},)
            if receipt.get("verified") is True
        )
    )


def _covers(record: dict[str, Any], target: Target) -> bool:
    """Whether one open approval's context covers one write target (content not yet checked)."""
    binds = record.get("binds")
    if not isinstance(binds, dict) or not binds:
        return True  # a general window covers any write while it lasts
    kind, value = target
    match binds.get("target"):
        case [bound_kind, bound_value]:
            return (bound_kind, bound_value) == (kind, value) and bool(value)
        case _:
            # Reviewed content with no target (drafts, an approved spec) covers tracker writes,
            # including rewriting an item's text; an approval tied to one item (move-item) does
            # not cover that.
            return kind in ("tracker", "item", "content")


def covering_approval(
    call: ToolCall, repo: Path, work_session_id: str | None
) -> tuple[tuple[Path, dict[str, Any]] | None, bool]:
    """The open approval whose context covers every target of this write, and whether an
    approval for the same target exists but its reviewed content has since changed."""
    targets = write_targets(call, repo) or (("tracker", ""),)
    if work_sessions.ended(repo, work_session_id):
        return None, False
    stale = False
    for path, record in state.open_approvals(repo, work_session_id):
        if not all(_covers(record, target) for target in targets):
            continue
        if _context_unchanged(
            repo, record.get("binds") or {}, str(record.get("id", ""))
        ):
            return (path, record), False
        stale = True
    return None, stale


_TEXT_WRITES = ("tracker_create_work_item", "tracker_update_work_item")


def _written_body(call: ToolCall) -> str | None:
    """The description a create or update writes, when it writes one."""
    if call.name not in _TEXT_WRITES or "description" not in call.tool_input:
        return None
    return str(call.tool_input.get("description") or "")


def _approved_body(repo: Path, work_session_id: str | None, body: str) -> bool:
    """Whether an open approval, its reviewed files unchanged, holds a draft with this body."""
    digest = hashlib.sha256(body.strip().encode("utf-8")).hexdigest()
    return not work_sessions.ended(repo, work_session_id) and any(
        digest in (record.get("binds") or {}).get("bodies", ())
        and _context_unchanged(
            repo, record.get("binds") or {}, str(record.get("id", ""))
        )
        for _, record in state.open_approvals(repo, work_session_id)
    )


def rule_approval_required(
    call: ToolCall,
    repo: Path,
    policy: TrackerPolicy,
    work_session_id: str | None = None,
) -> Decision:
    if not is_remote_write(call, policy):
        return Decision.allow()
    match _written_body(call):
        case str() as body if not _approved_body(repo, work_session_id, body):
            return Decision.deny(
                "approval-required",
                f"`{call.name}` writes a work item's text that no approved draft holds. Write "
                "the item as its draft (the agile-backlog-toolkit's skills write drafts to "
                "`Tickets/Ready/`), show it with `harness workflow show --artifact <draft>`, and "
                "ask `harness decision present --gate publish-items --artifact <draft>`. The "
                "description must be the draft's body, word for word. You cannot approve it "
                "yourself.",
            )
    match covering_approval(call, repo, work_session_id):
        case (_, _), _:
            return Decision.allow()
        case None, True:
            return Decision.deny(
                "approval-required",
                f"`{call.name}` is covered by an earlier approval, but what the user reviewed has "
                "changed since. Tell the user in plain words what changed, then ask for approval "
                "again for the current content. You cannot approve it yourself.",
            )
        case _:
            return Decision.deny(
                "approval-required",
                f"`{call.name}` writes to the tracker/SCM and no approval covers it. Tell the user in "
                "plain words what will be written, then ask the matching approval gate "
                "(`harness decision present --gate ...`), which ties the approval to that content "
                "or target. Where questions cannot be asked (Cursor), give the batch an id such as "
                "HB-7Q2K and ask them to reply `approve HB-7Q2K`. You cannot approve it yourself.",
            )


def rule_generated_files(call: ToolCall, repo: Path, settings: Settings) -> Decision:
    patterns = list(settings.generated)
    if not patterns:
        return Decision.allow()
    if call.kind == "edit":
        for path in call.file_paths:
            rel = _relative(repo, path)
            if globs.matches(rel, patterns):
                return Decision.deny(
                    "generated-files",
                    f"{rel} is generated. Change its source and re-run the generator instead of editing it.",
                )
    if call.kind == "shell":
        written = shell_writes_matching(call, repo, patterns)
        if written:
            return Decision.deny(
                "generated-files",
                f"{written} is generated; this command would edit it by hand.",
            )
    return Decision.allow()


_FORCE_PUSH_FLAGS = frozenset(
    {"--force", "--force-with-lease", "--force-if-includes", "--mirror"}
)
_REBASE_EXITS = frozenset({"--abort", "--quit"})


def _history_rewrite(argv: list[str]) -> str | None:
    """What a git invocation would rewrite, if anything."""
    if not argv:
        return None
    subcommand, options = argv[0], argv[1:]
    if subcommand == "rebase" and not _REBASE_EXITS & set(options):
        return "`git rebase` rewrites the branch's commits"
    if subcommand == "pull" and any(
        option in {"--rebase", "-r"}
        or (option.startswith("--rebase=") and option != "--rebase=false")
        for option in options
    ):
        return "`git pull --rebase` rewrites the branch's commits"
    if subcommand == "merge" and "--squash" in options:
        return "`git merge --squash` collapses the merged branch into one commit"
    if subcommand == "push" and any(
        option in _FORCE_PUSH_FLAGS
        or option.startswith("--force-with-lease=")
        or (re.match(r"^-[A-Za-z]*f", option) and not option.startswith("--"))
        or (option.startswith("+") and len(option) > 1)
        for option in options
    ):
        return "a force-push replaces the branch on the server"
    if subcommand in {"filter-branch", "filter-repo"}:
        return f"`git {subcommand}` rewrites history"
    return None


def rule_history_preserved(call: ToolCall) -> Decision:
    """Story and Feature branches keep their history: stacked branches are merged, never rebased,
    squashed, or force-pushed, so every later Story still builds on the commits it branched from.
    Always on in a governed repository, however the command is written."""
    if call.kind == "shell":
        for _directory, argv in git_invocations(call.command):
            rewrite = _history_rewrite(argv)
            if rewrite:
                return Decision.deny(
                    "history-preserved",
                    f"{rewrite}. Branch history is never rewritten here: bring changes in with "
                    "`git merge` (see `reconcile-feature-stack`), and land Stories with merge commits.",
                )
    strategy = call.tool_input.get("mergeStrategy")
    if call.name == "repo_pull_request_write" and strategy not in (
        None,
        "NoFastForward",
    ):
        return Decision.deny(
            "history-preserved",
            f"completing a pull request with `{strategy}` rewrites its commits; use a merge commit "
            "(`NoFastForward`).",
        )
    return Decision.allow()


def _delivery(settings: Settings, rule: Callable[[], Decision]) -> Decision:
    """A rule about Git commands applies only when the user chose Git-based delivery."""
    return rule() if settings.git_delivery else Decision.allow()


def evaluate(
    call: ToolCall,
    repo: Path,
    settings: Settings,
    policy: TrackerPolicy,
    work_session_id: str | None = None,
) -> Decision:
    """The first rule that denies the call, or allow. A write that passes is logged to its approval."""
    decision = next(
        (
            decision
            for rule in (
                lambda: rule_human_owned(call, repo),
                lambda: rule_tracked_tickets(call, repo, settings),
                lambda: rule_tracker_valid(call, policy),
                lambda: rule_protected_items(call, policy),
                lambda: _delivery(settings, lambda: rule_feature_branch(call, repo)),
                lambda: rule_draft_reviewed_prs(call, repo, settings, work_session_id),
                lambda: _delivery(settings, lambda: rule_history_preserved(call)),
                lambda: rule_approval_required(call, repo, policy, work_session_id),
                lambda: rule_generated_files(call, repo, settings),
            )
            if not (decision := rule()).allowed
        ),
        Decision.allow(),
    )
    approval = (
        covering_approval(call, repo, work_session_id)[0]
        if decision.allowed and is_remote_write(call, policy)
        else None
    )
    if approval is not None:
        state.log_write(approval[0], approval[1], call.name)
    return decision
