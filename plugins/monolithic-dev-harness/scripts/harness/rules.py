"""The harness rules, evaluated on every governed tool call. Each deny names its rule.

human-owned         Approvals, manual-check records, and the policy file are human-owned; the agent cannot write them.
approval-required   Azure / tracker / SCM writes need an approval window opened by the user's own prompt.
protected-items     Protected work items are never written, linked, or parented — approval does not override.
tests-with-code     A commit that changes source files must come with test changes (in the commit or the branch).
generated-files     Generated files are never edited by hand.
guarded-paths       A commit touching a guarded path needs that path's evidence for the tree being committed.
draft-reviewed-prs  Pull requests are created as drafts, only with a `ready` review verdict and passing checks
                    for HEAD; publishing a draft and voting are left to humans.
"""

from __future__ import annotations

import os
import posixpath
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from . import gitstate, globs, shellscan, state
from .config import protected_ids

EDIT_TOOLS = frozenset(
    {
        # Claude Code
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        # Cursor
        "StrReplace",
        "Delete",
        "edit_file",
        "write",
        "delete_file",
        "search_replace",
        # other hosts reaching this runtime through the shared adapters
        "apply_patch",
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
    }
)
SHELL_TOOLS = frozenset({"Bash", "Shell", "run_terminal_cmd", "shell", "run_command"})
AZURE_EXTRA_WRITES = frozenset(
    {"repo_create_branch", "pipelines_run", "wiki_upsert_page"}
)
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
        "workItems",
        "parentRef",
    }
)
# Field names and patch paths that set a work item's parent.
_PARENT_FIELDS = frozenset({"System.Parent"})
_NESTED_ID_LISTS = ("batchUpdates", "updates", "items")
# Text that links a work item when Azure DevOps saves it: a `#123` / `AB#123` mention (not an HTML
# entity such as `&#127919;`, and not a `#004007` colour, which no work-item id looks like) or a
# work item URL in any of its forms.
_TEXT_REFERENCE = re.compile(
    r"(?<![&\w])(?:AB|US)?#([1-9]\d*)\b"
    r"|_workitems/edit/(\d+)"
    r"|_workitems[^\s]*[?&]id=(\d+)"
    r"|/_apis/wit/workItems/(\d+)"
    r"|vstfs:///WorkItemTracking/WorkItem/(\d+)",
    re.IGNORECASE,
)
# In a commit message or branch name, only the `AB#123` form creates a link.
_COMMIT_REFERENCE = re.compile(r"(?<![&\w])(?:AB|US)#([1-9]\d*)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ToolCall:
    raw_name: str
    name: str
    server: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    cwd: str = ""  # where the host runs the tool; a shell's relative paths start here

    @property
    def command(self) -> str:
        value = (
            self.tool_input.get("command") or self.tool_input.get("CommandLine") or ""
        )
        return value if isinstance(value, str) else ""

    @property
    def file_paths(self) -> list[str]:
        paths = []
        for key in (
            "file_path",
            "path",
            "notebook_path",
            "target_file",
            "TargetFile",
            "AbsolutePath",
            "file",
        ):
            value = self.tool_input.get(key)
            if isinstance(value, str) and value:
                paths.append(value)
        return paths


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


def split_tool_name(raw: str) -> tuple[str, str]:
    """`mcp__plugin_x_azure-devops__wit_work_item` → ("plugin_x_azure-devops", "wit_work_item")."""
    if raw.startswith("mcp__"):
        parts = raw.split("__")
        if len(parts) >= 3:
            return parts[1], "__".join(parts[2:])
    return "", raw


def make_call(
    raw_name: str, tool_input: dict[str, Any] | None, server: str = "", cwd: str = ""
) -> ToolCall:
    parsed_server, name = split_tool_name(raw_name)
    return ToolCall(
        raw_name=raw_name,
        name=name,
        server=server or parsed_server,
        tool_input=tool_input or {},
        cwd=cwd,
    )


def is_azure_write(call: ToolCall) -> bool:
    azureish = "azure-devops" in call.server or call.server == ""
    return azureish and (
        call.name.endswith("_write") or call.name in AZURE_EXTRA_WRITES
    )


def is_gateway_write(call: ToolCall) -> bool:
    return call.name in GATEWAY_WRITES


def is_remote_write(call: ToolCall) -> bool:
    if call.name in SHELL_TOOLS:
        return "push" in git_subcommands(call.command)
    return (call.server != "" or call.name not in EDIT_TOOLS) and (
        is_azure_write(call) or is_gateway_write(call)
    )


def is_write_class(call: ToolCall) -> bool:
    """Calls that must fail closed if the rules themselves cannot run."""
    if is_remote_write(call) or call.name in EDIT_TOOLS:
        return True
    return call.name in SHELL_TOOLS and bool(
        git_subcommands(call.command) & {"commit", "push", "merge"}
    )


# --- helpers ------------------------------------------------------------------------------


def _ints(value: Any) -> set[int]:
    if isinstance(value, bool):
        return set()
    if isinstance(value, int):
        return {value}
    if isinstance(value, str):
        return {int(token) for token in re.findall(r"\d+", value)}
    if isinstance(value, list):
        found: set[int] = set()
        for item in value:
            found |= _ints(item)
        return found
    return set()


def referenced_ids(tool_input: dict[str, Any]) -> set[int]:
    found: set[int] = set()
    for key, value in tool_input.items():
        if key in _ID_KEYS:
            found |= _ints(value)
    for key in _NESTED_ID_LISTS:
        for entry in tool_input.get(key) or []:
            if isinstance(entry, dict):
                for nested_key in ("id", "linkToId", "parentId"):
                    found |= _ints(entry.get(nested_key))
    # Setting the parent field is linking, whether as a create field or an update patch.
    for entry in [
        *(tool_input.get("fields") or []),
        *(tool_input.get("updates") or []),
        *(tool_input.get("batchUpdates") or []),
    ]:
        if not isinstance(entry, dict):
            continue
        field_name = str(entry.get("name") or entry.get("path") or "").rsplit("/", 1)[
            -1
        ]
        if field_name in _PARENT_FIELDS:
            found |= _ints(entry.get("value"))
    return found


def git_invocations(
    command: str, cwd: str | None = ""
) -> list[tuple[str | None, list[str]]]:
    """Every `git` the command runs: (its directory relative to `cwd`'s base, argv after options).

    Walks the same invocations as the write rules, so `sudo git push`, `(git push)`, and
    `if …; then git push; fi` are all seen.
    """
    found: list[tuple[str | None, list[str]]] = []
    for invocation in shellscan.invocations(command, cwd):
        if invocation.name != "git":
            continue
        directory = invocation.cwd or None
        rest = list(invocation.args)
        while rest and rest[0].startswith("-"):
            flag = rest.pop(0)
            if flag in {"-C", "-c", "--git-dir", "--work-tree"} and rest:
                value = rest.pop(0)
                if flag == "-C":
                    directory = shellscan.resolve(value, directory or "")
        found.append((directory, rest))
    return found


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
    return "" if normalized == "." else normalized


def _shell_start(call: ToolCall, repo: Path) -> str:
    """Where the shell starts, relative to the repository (`""` for its root)."""
    if not call.cwd:
        return ""
    relative = posixpath.normpath(os.path.relpath(call.cwd, repo))
    return "" if relative == "." else relative


# --- rules --------------------------------------------------------------------------------


# Human-owned paths, as components under the repository root. A write into `.harness/` or
# `.harness/state/` could create one; anything under the last two is a record.
_OWNED_FILES = ((".harness",), (".harness", "state"), (".harness", "policy.json"))
_OWNED_DIRS = ((".harness", "state", "approvals"), (".harness", "state", "manual"))


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
            make_call("Bash", {"command": command}), repo or Path(".")
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


def rule_human_owned(call: ToolCall, repo: Path) -> Decision:
    """Approvals, manual-check records, and the policy itself are written by humans (via prompts/bootstrap)."""
    if call.name in EDIT_TOOLS:
        for path in call.file_paths:
            if is_human_owned(_relative(repo, path)):
                return Decision.deny(
                    "human-owned",
                    f"{_relative(repo, path)} is human-owned. Approvals and manual checks are recorded from the "
                    "user's own prompt; the policy is edited by a person (or created once by bootstrap).",
                )
    if call.name in SHELL_TOOLS:
        written = shell_human_owned_write(call, repo)
        if written:
            return Decision.deny(
                "human-owned",
                f"this command could write {written}, which is human-owned harness state or policy.",
            )
    return Decision.allow()


def mentioned_ids(value: Any, pattern: re.Pattern[str] = _TEXT_REFERENCE) -> set[int]:
    """Work item ids that text in a payload would link: `#123` mentions and work item URLs."""
    if isinstance(value, str):
        return {
            int(next(group for group in match.groups() if group))
            for match in pattern.finditer(value)
        }
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        found: set[int] = set()
        for item in value:
            found |= mentioned_ids(item, pattern)
        return found
    return set()


def rule_protected_items(call: ToolCall, policy: dict[str, Any]) -> Decision:
    protected = protected_ids(policy)
    if call.name in SHELL_TOOLS:
        return _shell_protected_mentions(call, protected)
    if not is_remote_write(call):
        return Decision.allow()
    hit = referenced_ids(call.tool_input) & protected
    if hit:
        return Decision.deny(
            "protected-items",
            f"work item(s) {sorted(hit)} are protected in .harness/policy.json and are never written, "
            "linked, or parented — not even with approval (links are two-way and would change them). "
            "Name the item in plain text instead, for example 'Idea 4007', without '#' or a link.",
        )
    mentioned = mentioned_ids(call.tool_input) & protected
    if mentioned:
        return Decision.deny(
            "protected-items",
            f"the text mentions protected work item(s) {sorted(mentioned)} as '#<id>' or by URL. "
            "Azure DevOps turns a mention into a link, which changes the protected item. Name it in "
            "plain text instead, for example 'Idea 4007', without '#' or a link.",
        )
    return Decision.allow()


def _shell_protected_mentions(call: ToolCall, protected: set[int]) -> Decision:
    """A commit message (or tag) links a work item through `AB#123` once it is pushed.

    Checked when the commit is made, not only when it is pushed: the harness's own flow commits
    and pushes in separate calls, and the push itself carries no text.
    """
    if not git_subcommands(call.command) & {"commit", "push", "tag", "notes", "merge"}:
        return Decision.allow()
    mentioned = mentioned_ids(call.command, _COMMIT_REFERENCE) & protected
    if mentioned:
        return Decision.deny(
            "protected-items",
            f"this commit or push mentions protected work item(s) {sorted(mentioned)} as `AB#<id>`, "
            "which Azure Repos turns into a link on the protected item. Name it in plain text "
            "instead, for example 'Idea 4007'.",
        )
    return Decision.allow()


def rule_draft_reviewed_prs(
    call: ToolCall, repo: Path, policy: dict[str, Any]
) -> Decision:
    rules = policy.get("pull_requests", {})
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
    creating = (
        call.name == "repo_pull_request_write" and action == "create"
    ) or call.name == "scm_create_pull_request"
    if not creating:
        return Decision.allow()
    draft = call.tool_input.get("isDraft", call.tool_input.get("draft"))
    if rules.get("require_draft", True) and draft is not True:
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
    if (
        rules.get("require_review_verdict", True)
        and state.review_verdict(repo, head) != "ready"
    ):
        return Decision.deny(
            "draft-reviewed-prs",
            f"no `ready` review verdict for HEAD {head[:12]}. Run the review stage; it records the verdict "
            "with scripts/harness/review_verdict.py after the requirements check and thermos pass.",
        )
    required = _applicable_checks(repo, policy)
    missing = required - state.passed_checks(repo, tree)
    if missing:
        return Decision.deny(
            "draft-reviewed-prs",
            f"checks {sorted(missing)} have no passing evidence for HEAD tree {tree[:12]}. "
            "Run scripts/harness/checks.py on the committed code.",
        )
    return Decision.allow()


def _applicable_checks(
    repo: Path, policy: dict[str, Any], paths: list[str] | None = None
) -> set[str]:
    checks = policy.get("checks", [])
    if not checks:
        return set()
    if paths is None:
        try:
            paths = gitstate.branch_paths(repo, policy["git"]["base_branch"])
        except gitstate.GitError:
            paths = []
    return {
        c["name"] for c in checks if not c.get("when") or globs.select(paths, c["when"])
    }


def rule_approval_required(
    call: ToolCall, repo: Path
) -> tuple[Decision, tuple[Path, dict[str, Any]] | None]:
    if not is_remote_write(call):
        return Decision.allow(), None
    active = state.active_approval(repo)
    if active is None:
        return (
            Decision.deny(
                "approval-required",
                f"`{call.name}` writes to the tracker/SCM and no approval window is open. Show the user the "
                "exact batch (items, fields, links) with a batch id such as HB-7Q2K, and ask them to reply "
                "`approve HB-7Q2K`. Their reply opens the window; you cannot open it yourself.",
            ),
            None,
        )
    return Decision.allow(), active


def rule_generated_files(
    call: ToolCall, repo: Path, policy: dict[str, Any]
) -> Decision:
    patterns = policy.get("generated", [])
    if not patterns:
        return Decision.allow()
    if call.name in EDIT_TOOLS:
        for path in call.file_paths:
            rel = _relative(repo, path)
            if globs.matches(rel, patterns):
                return Decision.deny(
                    "generated-files",
                    f"{rel} is generated. Change its source and re-run the generator instead of editing it.",
                )
    if call.name in SHELL_TOOLS:
        written = shell_writes_matching(call, repo, patterns)
        if written:
            return Decision.deny(
                "generated-files",
                f"{written} is generated; this command would edit it by hand.",
            )
    return Decision.allow()


def commit_rules(call: ToolCall, repo: Path, policy: dict[str, Any]) -> Decision:
    if call.name not in SHELL_TOOLS:
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
            decision = rule(target_root, policy, staged)
            if not decision.allowed:
                return decision
    return Decision.allow()


def rule_tests_with_code(
    repo: Path, policy: dict[str, Any], staged: list[str]
) -> Decision:
    for group in policy.get("tests_required", []):
        sources = globs.select(
            staged, group.get("source", []), group.get("exclude", [])
        )
        if not sources:
            continue
        tests = globs.select(staged, group.get("tests", []))
        if not tests:
            branch = gitstate.branch_paths(repo, policy["git"]["base_branch"])
            tests = globs.select(branch, group.get("tests", []))
        if not tests:
            return Decision.deny(
                "tests-with-code",
                f"this commit changes {len(sources)} source file(s) (e.g. {sources[0]}) and neither the commit nor "
                f"the branch changes a test matching {group.get('tests')}. New code ships with tests.",
            )
    return Decision.allow()


def rule_guarded_paths(
    repo: Path, policy: dict[str, Any], staged: list[str]
) -> Decision:
    guarded = [
        g for g in policy.get("guarded_paths", []) if globs.select(staged, [g["path"]])
    ]
    if not guarded:
        return Decision.allow()
    try:
        tree = gitstate.index_tree(repo)
    except gitstate.GitError as exc:
        return Decision.deny(
            "guarded-paths", f"cannot compute the tree being committed: {exc}"
        )
    for guard in guarded:
        kind, _, name = guard["evidence"].partition(":")
        if kind == "check" and name not in state.passed_checks(repo, tree):
            return Decision.deny(
                "guarded-paths",
                f"{guard['path']} changed; check `{name}` needs passing evidence for this exact tree. "
                "Stage the change, run scripts/harness/checks.py --staged, then commit.",
            )
        if kind == "manual" and not state.has_manual(repo, name, tree):
            return Decision.deny(
                "guarded-paths",
                f"{guard['path']} changed and has no automated suite. After the user validates it by hand, they "
                f"reply `harness manual-check {name} ok` with the change staged; that records the evidence.",
            )
    return Decision.allow()


def evaluate(call: ToolCall, repo: Path, policy: dict[str, Any]) -> Decision:
    for decision in (
        rule_human_owned(call, repo),
        rule_protected_items(call, policy),
        rule_draft_reviewed_prs(call, repo, policy),
    ):
        if not decision.allowed:
            return decision
    decision, approval = rule_approval_required(call, repo)
    if not decision.allowed:
        return decision
    for rule in (rule_generated_files, commit_rules):
        decision = rule(call, repo, policy)
        if not decision.allowed:
            return decision
    if approval is not None:
        state.log_write(approval[0], approval[1], call.name)
    return Decision.allow()
