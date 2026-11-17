"""Pure per-prompt policy for a mode's knowledge-first reminder."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Action = Literal["knowledge_read", "external_read", "other"]
_READ_TOOLS = frozenset({"read", "read_file"})
_SEARCH_TOOLS = frozenset(
    {"grep", "glob", "grep_search", "file_search", "codebase_search"}
)
_KNOWLEDGE_READS = frozenset({"catalog", "find", "fetch", "links"})


@dataclass(frozen=True)
class State:
    searched: bool = False
    reminded: bool = False
    empty_noticed: bool = False


@dataclass(frozen=True)
class Outcome:
    allowed: bool
    message: str
    state: State


def classify(
    tool_name: str,
    paths: tuple[Path, ...],
    store_root: Path,
    harness_arguments: tuple[str, ...] | None = None,
    *,
    expected_repo: Path | None = None,
    command_repo: Path | None = None,
    command_store: Path | None = None,
) -> Action:
    """Classify intent only; the caller records a knowledge read after success.

    Paths and store_root must be absolute and resolved by the host boundary.
    harness_arguments must come from commands.harness_args, which rejects shell
    operators and checks the executable, rather than from a text search. For a
    shell command, the host must independently resolve its actual --repo and
    store against the current project and pass their canonical absolute paths.
    """
    match tool_name.casefold(), harness_arguments:
        case (
            (
                "bash"
                | "shell"
                | "exec_command"
                | "functions.exec_command"
                | "functionsexec_command"
            ),
            ("knowledge", str() as command, *_),
        ) if (
            command in _KNOWLEDGE_READS
            and "--help" not in harness_arguments
            and "-h" not in harness_arguments
            and expected_repo is not None
            and expected_repo.is_absolute()
            and ".." not in expected_repo.parts
            and command_repo == expected_repo
            and store_root.is_absolute()
            and ".." not in store_root.parts
            and command_store == store_root
        ):
            return "knowledge_read"
        case (("webfetch" | "web_fetch"), _):
            return "external_read"
        case name, _ if (
            name in _READ_TOOLS
            and store_root.is_absolute()
            and ".." not in store_root.parts
            and paths == (store_root / "catalog.tsv",)
        ):
            return "knowledge_read"
        case name, _ if name in _READ_TOOLS or name in _SEARCH_TOOLS:
            return (
                "external_read"
                if not paths
                or not store_root.is_absolute()
                or ".." in store_root.parts
                or any(
                    not path.is_absolute()
                    or ".." in path.parts
                    or not path.is_relative_to(store_root)
                    for path in paths
                )
                else "other"
            )
        case _:
            return "other"


def evaluate(state: State, active: bool, available: bool, action: Action) -> Outcome:
    match active, available, action, state:
        case False, _, _, _:
            return Outcome(True, "", state)
        case True, _, "knowledge_read", _:
            return Outcome(True, "", State(True, state.reminded, state.empty_noticed))
        case True, False, "external_read", State(empty_noticed=False):
            return Outcome(
                True,
                "The project knowledge store is empty or unavailable.",
                State(state.searched, state.reminded, True),
            )
        case True, True, "external_read", State(searched=False, reminded=False):
            return Outcome(
                False,
                "Search the knowledge store first: `harness knowledge find <terms>`.",
                State(False, True, state.empty_noticed),
            )
        case _:
            return Outcome(True, "", state)
