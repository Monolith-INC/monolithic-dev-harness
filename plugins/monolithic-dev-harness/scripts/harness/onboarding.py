"""Sessionless onboarding controls, separate from governance and work records."""

from __future__ import annotations

from pathlib import Path

from core.result import Ok, Result, attempt, bind, err, fmap, require
from harness import commands, decisions, state, workflow

RELATIVE_PATH = Path(".harness/state/onboarding.json")
OPERATIONS = {
    "onboarding": (
        "status",
        "skip",
        "dismiss",
        "restart",
        "reset",
        "drop",
        "pause",
        "resume",
    ),
    "mode": ("status", "free", "structured"),
}


def status(repo: Path) -> dict[str, str]:
    match state.read_json(repo / RELATIVE_PATH):
        case {"mode": "free", "status": ("skipped" | "dismissed") as progress}:
            return {"mode": "free", "status": progress}
        case {
            "mode": "structured",
            "status": ("pending" | "skipped" | "dismissed" | "paused") as progress,
        }:
            return {"mode": "structured", "status": progress}
        case _:
            return {"mode": "structured", "status": "pending"}


def mode(repo: Path) -> str:
    return status(repo)["mode"]


def free_payload(repo: Path, request: str) -> dict:
    """Startup guidance without creating or selecting any session."""
    return {
        "state": "free",
        "mode": "free",
        "request": request,
        "session_id": None,
        "discover_entry": "",
        "next": guidance(repo),
    }


def guidance(repo: Path) -> str:
    match mode(repo):
        case "free":
            return (
                "Free mode: help with the user's request directly, without creating a work "
                "session or workflow. Required decisions and write approvals still apply. "
                "Use `harness mode structured` to return to guided work."
            )
        case _:
            return (
                "Structured mode: follow the harness onboarding and guided work flow."
            )


def control(repo: Path, family: str, operation: str) -> Result[dict[str, str]]:
    return bind(
        require(repo.is_dir(), "onboarding_invalid", f"{repo} is not a directory"),
        lambda _: _control(repo, family, operation),
    )


def _control(repo: Path, family: str, operation: str) -> Result[dict[str, str]]:
    match family, operation:
        case (("onboarding" | "mode"), "status"):
            return Ok({**status(repo), "instruction": guidance(repo)})
        case "onboarding", ("skip" | "dismiss" | "drop") as progress:
            return _free(
                repo,
                {"skip": "skipped", "dismiss": "dismissed", "drop": "dismissed"}[
                    progress
                ],
            )
        case "mode", "free":
            return _free(repo, "skipped")
        case "onboarding", "restart" | "reset":
            return bind(
                workflow.restart_preparation(repo),
                lambda _: bind(
                    decisions.cancel_onboarding(repo),
                    lambda _: _save(repo, {"mode": "structured", "status": "pending"}),
                ),
            )
        case "onboarding", "pause":
            return _save(repo, {"mode": "structured", "status": "paused"})
        case "onboarding", "resume":
            return _save(repo, {"mode": "structured", "status": "pending"})
        case "mode", "structured":
            return _save(repo, {**status(repo), "mode": "structured"})
        case _:
            return err("onboarding_invalid", "unknown onboarding or mode operation")


def _free(repo: Path, progress: str) -> Result[dict[str, str]]:
    return bind(
        decisions.cancel_onboarding(repo),
        lambda _: _save(repo, {"mode": "free", "status": progress}),
    )


def _save(repo: Path, value: dict[str, str]) -> Result[dict[str, str]]:
    """Isolated storage edge; the existing atomic writer owns filesystem side effects."""
    return fmap(
        attempt(
            lambda: state.write_json(repo / RELATIVE_PATH, value),
            "onboarding_unwritable",
            "onboarding state",
            OSError,
        ),
        lambda _: {**value, "instruction": guidance(repo)},
    )


def recovery_command(command: str, cwd: Path, repo: Path) -> bool:
    """Only an exact control for this repo can pass the pending guard."""
    match commands.harness_args(command, cwd):
        case ("decision", "present", *args) if (
            commands.option(tuple(args), "--gate") == "harness-controls"
        ):
            return (
                sum(arg == "--repo" or arg.startswith("--repo=") for arg in args) <= 1
                and (cwd / (commands.option(tuple(args), "--repo") or ".")).resolve()
                == repo.resolve()
            )
        case (family, operation):
            return _valid_control(family, operation) and cwd.resolve() == repo.resolve()
        case (family, operation, "--repo", destination):
            return (
                _valid_control(family, operation)
                and (cwd / destination).resolve() == repo.resolve()
            )
        case (family, "--repo", destination, operation):
            return (
                _valid_control(family, operation)
                and (cwd / destination).resolve() == repo.resolve()
            )
        case (family, operation, str() as option) if option.startswith("--repo="):
            return (
                _valid_control(family, operation)
                and (cwd / option.removeprefix("--repo=")).resolve() == repo.resolve()
            )
        case (family, str() as option, operation) if option.startswith("--repo="):
            return (
                _valid_control(family, operation)
                and (cwd / option.removeprefix("--repo=")).resolve() == repo.resolve()
            )
        case _:
            return False


def _valid_control(family: str, operation: str) -> bool:
    return operation in OPERATIONS.get(family, ())
