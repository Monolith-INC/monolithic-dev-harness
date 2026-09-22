"""Deny rewrite-heavy git while merge-story-stack-into-feature stage is active."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from .events import PolicyDecision

STAGE_NAME = "merge-story-stack-into-feature"
_ACTIVE_STAGE_REL = Path(".codex-workflows") / "active-stage"
_ENV_KEY = "CODEX_WORKFLOW_STAGE"

_FORCE_PUSH = re.compile(
    r"(?:^|\s)(?:--force|--force-with-lease|-f)(?:\s|$)",
    re.IGNORECASE,
)


def active_stage(workspace_root: str) -> str:
    """Return the active workflow stage name, or empty string."""
    env = os.environ.get(_ENV_KEY, "").strip()
    if env:
        return env
    path = Path(workspace_root) / _ACTIVE_STAGE_REL
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except OSError:
        return ""
    return ""


def evaluate_git_stack_merge_guard(command: str, workspace_root: str) -> PolicyDecision:
    """Deny rebase and force-push while merge-story-stack-into-feature is active."""
    if active_stage(workspace_root) != STAGE_NAME:
        return PolicyDecision.allow()

    argv = _git_argv(command)
    if argv is None:
        return PolicyDecision.allow()

    sub = argv[0] if argv else ""
    if sub == "rebase":
        return PolicyDecision.deny(
            "git rebase is blocked during merge-story-stack-into-feature. "
            "Use merge commits only for Story→Feature."
        )

    if sub == "push" and _FORCE_PUSH.search(" ".join(argv)):
        return PolicyDecision.deny(
            "Force-push is blocked during merge-story-stack-into-feature. "
            "Push Feature with a non-force update after merge commits."
        )

    return PolicyDecision.allow()


def _git_argv(command: str) -> list[str] | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if not tokens:
        return None
    try:
        idx = next(
            i for i, tok in enumerate(tokens) if tok == "git" or tok.endswith("/git")
        )
    except StopIteration:
        return None
    rest = tokens[idx + 1 :]
    while rest and rest[0].startswith("-"):
        opt = rest.pop(0)
        if opt in {"-C", "-c"} and rest:
            rest.pop(0)
    return rest
