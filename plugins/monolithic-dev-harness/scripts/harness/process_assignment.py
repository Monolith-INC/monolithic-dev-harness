"""Small, fail-closed policy for process assignments."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from core.result import Ok, Result, err, fmap, require

from . import rules


@dataclass(frozen=True)
class Assignment:
    role: str
    owned_paths: tuple[str, ...]
    model: str
    effort: str


def authorize_model(assignment: Assignment, observed_model: str) -> Result[Assignment]:
    return fmap(
        require(
            observed_model == assignment.model,
            "process_model_mismatch",
            "observed model does not match the assignment",
        ),
        lambda _: assignment,
    )


def _path(value: Any) -> str | None:
    match value:
        case str() as text if (
            text
            and "\x00" not in text
            and not text.startswith("/")
            and "\\" not in text
        ):
            pure = PurePosixPath(text)
            parts = pure.parts
            return (
                text
                if parts
                and "." not in parts
                and ".." not in parts
                and text == pure.as_posix()
                and not any(c in text for c in "*?[]{}")
                and not any(
                    part in (".harness", ".git", ".codex", ".agents") for part in parts
                )
                else None
            )
        case _:
            return None


def decode_assignment(value: Any) -> Result[Assignment]:
    match value:
        case {
            "role": str() as role,
            "owned_paths": list() | tuple() as paths,
            "model": str() as model,
            "effort": str() as effort,
        } if set(value) == {"role", "owned_paths", "model", "effort"}:
            normalized = tuple(map(_path, paths))
            match role, model, effort, normalized:
                case ("reviewer", model, effort, paths) if (
                    model.strip()
                    and effort in ("low", "medium", "high")
                    and all(path is not None for path in paths)
                    and not paths
                ):
                    return Ok(Assignment(role, (), model.strip(), effort))
                case ("worker", model, effort, paths) if (
                    model.strip()
                    and effort in ("low", "medium", "high")
                    and paths
                    and all(path is not None for path in paths)
                    and len(set(paths)) == len(paths)
                ):
                    return Ok(Assignment(role, tuple(paths), model.strip(), effort))
                case _:
                    return err(
                        "invalid_assignment", "invalid role, paths, model, or effort"
                    )
        case _:
            return err(
                "invalid_assignment",
                "assignment must contain exactly role, owned_paths, model, and effort",
            )


def _safe_shell(command: str, repo: Path) -> bool:
    try:
        words = tuple(shlex.split(command, posix=True))
    except ValueError:
        return False
    return _safe_words(command, words, repo)


def _safe_words(command: str, words: tuple[str, ...], repo: Path) -> bool:
    match any(
        char in command
        for char in (
            "\n",
            "\r",
            "\x00",
            "`",
            "$",
            ";",
            "&",
            "|",
            ">",
            "<",
            "(",
            ")",
            "\\",
        )
    ):
        case True:
            return False
        case False:
            return _safe_words_without_syntax(words, repo)


def _safe_words_without_syntax(words: tuple[str, ...], repo: Path) -> bool:
    match words:
        case ("pwd",):
            return True
        case ("cat", "--", *paths) if paths:
            return all(_safe_target(path, repo) for path in paths)
        case ("rg", "--no-config", "-n", "--", pattern, *paths) if pattern and paths:
            return all(_safe_target(path, repo) for path in paths)
        case ("sed", "-n", expression, "--", path) if _sed_expression(
            expression
        ) and _safe_target(path, repo):
            return True
        case _:
            return False


def _sed_expression(expression: str) -> bool:
    match expression.removesuffix("p").split(","):
        case [start, end] if (
            expression.endswith("p") and start.isdigit() and end.isdigit()
        ):
            return True
        case _:
            return False


def _safe_target(value: str, repo: Path) -> bool:
    target = (repo / value).resolve()
    return target == repo.resolve() or repo.resolve() in target.parents


def authorize_call(
    repo: Path, assignment: Assignment, call: rules.ToolCall
) -> rules.Decision | None:
    allowed = call.kind == "read" or (
        call.kind == "shell" and _safe_shell(call.command, repo)
    )
    cwd_ok = Path(call.cwd or repo).resolve() == repo.resolve()
    worker_paths = tuple((repo / path).resolve() for path in assignment.owned_paths)
    requested = tuple((repo / path).resolve() for path in call.file_paths)
    lexical_paths = tuple(
        relative
        for path in call.file_paths
        for relative in (_lexical_relative(repo, path),)
        if relative is not None
    )
    owned = (
        bool(requested)
        and len(lexical_paths) == len(call.file_paths)
        and all(relative in assignment.owned_paths for relative in lexical_paths)
        and all(
            any(path == permitted for permitted in worker_paths) for path in requested
        )
        and all(
            repo.resolve() in path.parents or path == repo.resolve()
            for path in requested
        )
        and all(_no_symlink(repo, path) for path in call.file_paths)
    )
    match assignment.role, allowed, call.kind, owned, cwd_ok:
        case "reviewer", True, "read" | "shell", _, True:
            return None
        case "worker", True, "read" | "shell", _, True:
            return None
        case "worker", _, "edit", True, True:
            return None
        case _:
            return rules.Decision.deny(
                "assignment-policy", "call is outside the process assignment"
            )


def _no_symlink(repo: Path, path: str) -> bool:
    parts = PurePosixPath(_lexical_relative(repo, path) or "").parts
    return all(
        not repo.joinpath(*parts[:index]).is_symlink()
        for index in range(1, len(parts) + 1)
    )


def _lexical_relative(repo: Path, path: str) -> str | None:
    candidate = Path(path)
    try:
        relative = (
            candidate.relative_to(repo.resolve())
            if candidate.is_absolute()
            else candidate
        )
        return relative.as_posix()
    except ValueError:
        return None
