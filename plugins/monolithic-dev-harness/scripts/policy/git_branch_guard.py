"""Block mutating git on integration trunk branches."""

from __future__ import annotations

from .commands import git_commands
from .events import PolicyDecision
from .git_utils import _run_git_cmd

PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "unstable"})

# Subcommands that change repo history/state and must not run on a trunk checkout.
_MUTATING_SUBCOMMANDS = frozenset(
    {
        "commit",
        "push",
        "merge",
        "rebase",
        "pull",
        "cherry-pick",
        "revert",
        "am",
        "reset",
        "stash",
        "tag",
        "notes",
        "svn",
    }
)

_CHECKOUT_SWITCH = frozenset({"checkout", "switch"})


def evaluate_git_branch_guard(command: str, workspace_root: str) -> PolicyDecision:
    """Deny mutating git / trunk checkouts while on a protected branch.

    Every `git` on the line is checked, not only the first: `git status && git commit` commits.
    """
    commands = git_commands(command)
    if not commands:
        return PolicyDecision.allow()

    current = (
        _run_git_cmd(["git", "branch", "--show-current"], workspace_root) or ""
    ).strip()
    for argv in commands:
        sub = argv[0] if argv else ""
        if sub in _CHECKOUT_SWITCH:
            decision = _evaluate_checkout_switch(argv, current)
            if decision.is_denied():
                return decision
            continue
        if current in PROTECTED_BRANCHES and (
            sub in _MUTATING_SUBCOMMANDS or sub.startswith("commit")
        ):
            return PolicyDecision.deny(
                f"Git `{sub}` is blocked while checked out on protected branch `{current}`. "
                "Create and check out a work-item branch using the convention selected during bootstrap."
            )
    return PolicyDecision.allow()


def is_ticket_branch(name: str | None) -> bool:
    """Compatibility helper; branch conventions are selected at bootstrap."""
    return bool(name and name.strip() and name not in PROTECTED_BRANCHES)


def _evaluate_checkout_switch(argv: list[str], current: str) -> PolicyDecision:
    creating = (
        "-b" in argv
        or "-B" in argv
        or "-c" in argv
        or "-C" in argv
        or "--create" in argv
    )
    target = _checkout_target(argv)

    if creating:
        # Creating/switching to a new branch from trunk is the required escape hatch.
        if target and target in PROTECTED_BRANCHES:
            return PolicyDecision.deny(
                f"Refusing to create protected branch `{target}`. "
                "Use a work-item branch selected during bootstrap."
            )
        return PolicyDecision.allow()

    if target and target in PROTECTED_BRANCHES:
        return PolicyDecision.deny(
            f"Refusing to check out protected branch `{target}`. "
            "Stay on (or create) a ticket branch for implementation work."
        )

    # e.g. git checkout -- file  (path restore) — allow
    if current in PROTECTED_BRANCHES and not target and "--" in argv:
        return PolicyDecision.allow()

    return PolicyDecision.allow()


def _checkout_target(argv: list[str]) -> str | None:
    """Best-effort target ref for checkout/switch."""
    args = argv[1:]
    for flag in ("-b", "-B", "-c", "-C"):
        if flag in args:
            i = args.index(flag)
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                return args[i + 1]

    skip_next = False
    positionals: list[str] = []
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            break
        if token in {"-b", "-B", "-c", "-C", "--branch", "--conflict", "--orphan"}:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        positionals.append(token)
    return positionals[0] if positionals else None
