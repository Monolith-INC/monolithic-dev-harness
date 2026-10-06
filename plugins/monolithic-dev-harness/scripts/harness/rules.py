"""The harness rules, evaluated on every governed tool call. Each deny names its rule.

human-owned         The settings, approvals, manual-check records, sessions, and tracker trust are human-owned.
tracker-invalid     While the selected tracker is missing or broken, tracker and SCM writes are refused, and so is
                    every call to an MCP server that is not the harness's own.
approval-required   Tracker and SCM writes need an approval window opened by the user (a prompt or a click).
protected-items     Protected work items are never written, linked, or parented — approval does not override.
tests-with-code     A commit that changes source files must come with test changes (in the commit or the branch).
generated-files     Generated files are never edited by hand.
guarded-paths       A commit touching a guarded path needs that path's evidence for the tree being committed.
draft-reviewed-prs  Pull requests are created as drafts, only with a `ready` review verdict and passing checks
                    for HEAD; publishing a draft and voting are left to humans.
history-preserved   Branch history is never rewritten: no rebase, squash merge, or force-push.
"""

from __future__ import annotations

import os
import posixpath
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from . import gitstate, globs, sessions, shellscan, state, tracker_policy
from .settings import Settings
from .tracker_policy import TrackerPolicy

GATEWAY_WRITES = frozenset(
    {
        "tracker_create_work_item",
        "tracker_transition_work_item",
        "tracker_publish_artifact",
        "tracker_link_development_artifact",
        "scm_create_pull_request",
        "scm_reply_to_thread",
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
)
_OWNED_DIRS = (
    (".harness", "state", "approvals"),
    (".harness", "state", "manual"),
    (".harness", "state", "asked"),
    (".harness", "state", "sessions"),
    (".harness", "state", "work_sessions"),
    (".harness", "state", "host_sessions"),
    (".harness", "state", "trackers"),
    (".harness", "state", "adoptions"),
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
    return any(fnmatch(".harness", part) for part in word.split("/") if part)


def shell_human_owned_write(call: ToolCall, repo: Path) -> str | None:
    """The human-owned path a shell command could write, if any."""
    writes = shellscan.scan(call.command, _shell_start(call, repo), repo)
    for path in writes.targets:
        if is_human_owned(_relative(repo, path)):
            return _relative(repo, path)
    for path in writes.trees:
        if is_human_owned(_relative(repo, path), tree=True):
            return _relative(repo, path) or "the repository root"
    return next((word for word in writes.unresolved if _names_harness(word)), None)


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
        if relative and globs.matches(relative, patterns):
            return relative
    return None


_HOOK_SCRIPT = re.compile(r"(?:^|[\s/'\"=])(?:hook|hook_runtime)\.py\b")
_HOOK_MODULE = re.compile(
    r"\bhook_runtime\b|\bharness\.hook\b|\bharness\s+import\s+.*\bhook\b"
)


def runs_harness_hook(command: str) -> bool:
    """Whether a shell command runs (or copies) the harness's own hook entry points.

    The prompt and answer hooks record the user's answers and approvals from what they read on
    stdin, so an agent that pipes a payload into them could answer for the user.
    """
    return any(
        _invocation_mentions_hook(invocation)
        for invocation in shellscan.invocations(command)
    )


def _invocation_mentions_hook(invocation: shellscan.Invocation) -> bool:
    """Readers may inspect hooks; execution and copying remain protected."""
    return (
        invocation.name not in shellscan.NON_WRITERS
        and (
            invocation.name not in shellscan.IN_PLACE_FLAGS
            or any(
                shellscan.IN_PLACE_FLAGS[invocation.name].match(argument)
                for argument in invocation.args
            )
        )
        and (
            any(_HOOK_MODULE.search(argument) for argument in invocation.args)
            or (
                any(
                    _HOOK_SCRIPT.search(argument)
                    for argument in (
                        invocation.name,
                        *invocation.args,
                        invocation.cwd or "",
                    )
                )
                and any(
                    "harness" in argument
                    for argument in (
                        invocation.name,
                        *invocation.args,
                        invocation.cwd or "",
                    )
                )
            )
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
                    "and work sessions through `harness work-session`; the "
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


def rule_draft_reviewed_prs(call: ToolCall, repo: Path, settings: Settings) -> Decision:
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
    if not _creates_pull_request(call):
        return Decision.allow()
    draft = call.tool_input.get("isDraft", call.tool_input.get("draft"))
    if settings.require_draft and draft is not True:
        return Decision.deny(
            "draft-reviewed-prs",
            "pull requests must be created as drafts (isDraft: true); a human publishes them (gate G4).",
        )
    try:
        head = gitstate.head_sha(repo)
        tree = gitstate.head_tree(repo)
    except gitstate.GitError as exc:
        return Decision.deny(
            "draft-reviewed-prs", f"cannot read HEAD to verify review and checks: {exc}"
        )
    if settings.require_review_verdict and state.review_verdict(repo, head) != "ready":
        return Decision.deny(
            "draft-reviewed-prs",
            f"no `ready` review verdict for HEAD {head[:12]}. Run the review stage; it records the verdict "
            "with scripts/harness/review_verdict.py after the requirements check and thermos pass.",
        )
    required = applicable_checks(repo, settings)
    missing = required - state.passed_checks(repo, tree)
    if missing:
        return Decision.deny(
            "draft-reviewed-prs",
            f"checks {sorted(missing)} have no passing evidence for HEAD tree {tree[:12]}. "
            "Run scripts/harness/checks.py on the committed code.",
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


def applicable_checks(
    repo: Path, settings: Settings, paths: list[str] | None = None
) -> set[str]:
    """The checks whose `when` globs match the branch's changes (or `paths`, when given)."""
    changed = (
        paths
        if paths is not None
        else (_branch_paths(repo, settings.base_branch) if settings.checks else [])
    )
    return {
        check.name
        for check in settings.checks
        if not check.when or globs.select(changed, list(check.when))
    }


def _branch_paths(repo: Path, base: str) -> list[str]:
    try:
        return gitstate.branch_paths(repo, base)
    except gitstate.GitError:
        return []


def rule_approval_required(
    call: ToolCall,
    repo: Path,
    policy: TrackerPolicy,
    work_session_id: str | None = None,
) -> Decision:
    return (
        Decision.deny(
            "approval-required",
            f"`{call.name}` writes to the tracker/SCM and no approval window is open. Tell the user in plain "
            "words what will be written, then ask one question with an `Approve` option and a `Not now` "
            "option; their click opens the window. Where questions cannot be asked (Cursor), give the "
            "batch an id such as HB-7Q2K and ask them to reply `approve HB-7Q2K`. You cannot open the "
            "window yourself.",
        )
        if is_remote_write(call, policy)
        and state.active_approval(repo, work_session_id) is None
        else Decision.allow()
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


def commit_rules(call: ToolCall, repo: Path, settings: Settings) -> Decision:
    if call.kind != "shell":
        return Decision.allow()
    for directory, argv in git_invocations(call.command, _shell_start(call, repo)):
        if not argv or argv[0] != "commit":
            continue
        target = (
            (repo / directory)
            if directory and not Path(directory).is_absolute()
            else Path(directory or repo)
        )
        target_root = gitstate.repo_root(target) or repo
        all_tracked = any(
            a in {"-a", "--all"}
            or (a.startswith("-") and not a.startswith("--") and "a" in a)
            for a in argv[1:]
        )
        try:
            staged = gitstate.staged_paths(
                target_root, include_tracked_modifications=all_tracked
            )
        except gitstate.GitError as exc:
            return Decision.deny(
                "tests-with-code", f"cannot read the staged changes: {exc}"
            )
        for rule in (rule_tests_with_code, rule_guarded_paths):
            decision = rule(target_root, settings, staged)
            if not decision.allowed:
                return decision
    return Decision.allow()


def rule_tests_with_code(repo: Path, settings: Settings, staged: list[str]) -> Decision:
    missing = next(
        (
            (sources, group)
            for group in settings.tests_required
            if (
                sources := globs.select(staged, list(group.source), list(group.exclude))
            )
            and not globs.select(staged, list(group.tests))
            and not globs.select(
                gitstate.branch_paths(repo, settings.base_branch), list(group.tests)
            )
        ),
        None,
    )
    match missing:
        case (sources, group):
            return Decision.deny(
                "tests-with-code",
                f"this commit changes {len(sources)} source file(s) (e.g. {sources[0]}) and neither the commit nor "
                f"the branch changes a test matching {list(group.tests)}. New code ships with tests.",
            )
        case _:
            return Decision.allow()


def rule_guarded_paths(repo: Path, settings: Settings, staged: list[str]) -> Decision:
    guarded = tuple(
        guard for guard in settings.guarded_paths if globs.select(staged, [guard.path])
    )
    if not guarded:
        return Decision.allow()
    try:
        tree = gitstate.index_tree(repo)
    except gitstate.GitError as exc:
        return Decision.deny(
            "guarded-paths", f"cannot compute the tree being committed: {exc}"
        )
    unmet = next(
        (
            guard
            for guard in guarded
            if not _evidence(repo, guard.kind, guard.name, tree)
        ),
        None,
    )
    match unmet:
        case None:
            return Decision.allow()
        case guard if guard.kind == "check":
            return Decision.deny(
                "guarded-paths",
                f"{guard.path} changed; check `{guard.name}` needs passing evidence for this exact tree. "
                "Stage the change, run scripts/harness/checks.py --staged, then commit.",
            )
        case guard:
            return Decision.deny(
                "guarded-paths",
                f"{guard.path} changed and has no automated suite. After the user validates it by hand, they "
                f"reply `harness manual-check {guard.name} ok` with the change staged; that records the evidence.",
            )


def _evidence(repo: Path, kind: str, name: str, tree: str) -> bool:
    return (
        name in state.passed_checks(repo, tree)
        if kind == "check"
        else state.has_manual(repo, name, tree)
    )


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
                lambda: rule_tracker_valid(call, policy),
                lambda: rule_protected_items(call, policy),
                lambda: rule_feature_branch(call, repo),
                lambda: rule_draft_reviewed_prs(call, repo, settings),
                lambda: rule_history_preserved(call),
                lambda: rule_approval_required(call, repo, policy, work_session_id),
                lambda: rule_generated_files(call, repo, settings),
                lambda: commit_rules(call, repo, settings),
            )
            if not (decision := rule()).allowed
        ),
        Decision.allow(),
    )
    approval = (
        state.active_approval(repo, work_session_id)
        if decision.allowed and is_remote_write(call, policy)
        else None
    )
    if approval is not None:
        state.log_write(approval[0], approval[1], call.name)
    return decision
