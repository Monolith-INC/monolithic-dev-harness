#!/usr/bin/env python3
"""Create and remove disposable copies of the acceptance-test project."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from pathlib import Path

MARKER_NAME = ".monolithic-dev-harness-trial.json"
ROOT_PREFIX = "monolithic-dev-harness-trial-"
RUN_PREFIX = "monolithic-dev-harness-test-run-"
HOST_CONTEXT_VARIABLES = frozenset(
    {
        "CODEX_THREAD_ID",
        "CODEX_SESSION_ID",
        "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
        "CODEX_APP_TOOLS_PIPE_PATH",
        "CODEX_TASK_WORKSPACE_VERIFYING_IDENTITY",
        "CODEX_SAGE_BACKFILL_TRACKER_TAB_REUSE",
        "CODEX_SHELL",
    }
)
TEMPLATE = Path(__file__).resolve().parents[1] / "test-project-template"
PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "monolithic-dev-harness"

PROFILES: dict[str, dict] = {
    "unconfigured": {},
    "local-planning": {
        "schemaVersion": 1,
        "tracker": {"name": "local"},
        "scm": {"name": "local"},
        "branch_template": "{key}-{slug}",
        "artifacts_path": "docs/planning",
    },
}


def prepare(
    profile: str = "unconfigured",
    overrides: dict | None = None,
    *,
    root_prefix: str = ROOT_PREFIX,
    kind: str = "prepared",
) -> Path:
    if profile not in PROFILES:
        raise ValueError(f"Unknown starting profile: {profile}")
    settings = copy.deepcopy(PROFILES[profile])
    if overrides:
        settings = merge(settings, overrides)
    trial_root = Path(tempfile.mkdtemp(prefix=root_prefix))
    project = trial_root / "project"
    runner_temp = trial_root / "runner-tmp"
    preference_home = trial_root / "preferences"
    codex_home = trial_root / "codex-home"
    auth_source = (
        Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
    )
    try:
        runner_temp.mkdir(mode=0o700)
        preference_home.mkdir(mode=0o700)
        codex_home.mkdir(mode=0o700)
        runner_temp.chmod(0o700)
        preference_home.chmod(0o700)
        codex_home.chmod(0o700)
        if auth_source.is_file():
            (codex_home / "auth.json").symlink_to(auth_source.resolve())
        marker = {
            "format": 2,
            "token": uuid.uuid4().hex,
            "project": str(project),
            "profile": profile,
            "kind": kind,
            "process_id": os.getpid() if kind == "run" else None,
            "settings_sha256": hashlib.sha256(
                json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "runner_temp": str(runner_temp),
            "preference_home": str(preference_home),
            "codex_home": str(codex_home),
            "auth_source": str(auth_source.resolve()) if auth_source.is_file() else "",
        }
        (trial_root / MARKER_NAME).write_text(json.dumps(marker), encoding="utf-8")
        shutil.copytree(TEMPLATE, project)
        run_git(project, "init", "--quiet")
        run_git(project, "config", "user.name", "Acceptance Trial")
        run_git(project, "config", "user.email", "acceptance-trial@localhost")
        if settings:
            settings_path = project / ".harness" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            prepare_local_tracker(project)
        run_git(project, "add", "--all")
        run_git(project, "commit", "--quiet", "-m", "Starting project")
    except BaseException:
        shutil.rmtree(trial_root)
        raise
    return project


def merge(base: dict, overrides: dict) -> dict:
    """Return settings with nested overrides, leaving both inputs unchanged."""
    return {
        key: merge(base[key], value)
        if key in base and isinstance(base[key], dict) and isinstance(value, dict)
        else copy.deepcopy(value)
        for key, value in (base | overrides).items()
    }


def prepare_local_tracker(project: Path) -> None:
    """Use the harness setup path to initialize and verify the selected local tracker."""
    sys.path.insert(0, str(PLUGIN / "scripts"))
    from core.result import Err, Ok
    from harness import setup

    match setup.prepare_local_tracker(project):
        case Err(failure):
            if failure.code == "invalid_request":
                return
            raise ValueError(f"Local tracker setup failed: {failure.message}")
        case Ok(storage) if storage.get("ready"):
            return
        case Ok(storage):
            raise ValueError(f"Local tracker setup is incomplete: {storage}")


def run_git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True)


def discard(project_arg: str) -> Path:
    project, trial_root, _ = _trial_metadata(project_arg)
    shutil.rmtree(trial_root)
    return trial_root


def _trial_metadata(project_arg: str) -> tuple[Path, Path, dict]:
    supplied = Path(project_arg).expanduser()
    if supplied.is_symlink():
        raise ValueError("Refusing to discard a symbolic link.")
    project = supplied.resolve(strict=True)
    trial_root = project.parent
    temp_root = Path(tempfile.gettempdir()).resolve()
    if project.name != "project" or trial_root.parent != temp_root:
        raise ValueError(
            "Refusing: path is not a direct trial project under the system temp folder."
        )
    if trial_root.is_symlink() or not trial_root.name.startswith(
        (ROOT_PREFIX, RUN_PREFIX)
    ):
        raise ValueError("Refusing: trial folder was not created by this helper.")
    marker_path = trial_root / MARKER_NAME
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if (
        not isinstance(marker, dict)
        or marker.get("format") not in (1, 2)
        or marker.get("project") != str(project)
    ):
        raise ValueError(
            "Refusing: trial ownership marker does not match this project."
        )
    return project, trial_root, marker


def runner_environment(project_arg: str) -> dict[str, str]:
    _, trial_root, marker = _trial_metadata(project_arg)
    if marker.get("format") != 2:
        raise ValueError("This trial copy has no isolated runner environment.")
    paths = {
        "TMPDIR": ("runner_temp", trial_root / "runner-tmp"),
        "HARNESS_USER_STATE_DIR": ("preference_home", trial_root / "preferences"),
        "CODEX_HOME": ("codex_home", trial_root / "codex-home"),
    }
    for key, (field, expected) in paths.items():
        supplied = Path(str(marker.get(field, "")))
        if supplied != expected or supplied.is_symlink():
            raise ValueError(f"Trial {key} path does not match its owned folder.")
        status = supplied.stat()
        if status.st_uid != os.getuid() or status.st_mode & 0o777 != 0o700:
            raise ValueError(f"Trial {key} folder must be user-owned with mode 0700.")
    return {key: str(expected) for key, (_, expected) in paths.items()}


def cleanup_abandoned_runs() -> tuple[Path, ...]:
    """Remove only owned test-run folders whose recorded launcher is no longer alive."""
    removed: list[Path] = []
    temp_root = Path(tempfile.gettempdir()).resolve()
    for trial_root in temp_root.glob(f"{RUN_PREFIX}*"):
        if trial_root.is_symlink() or not trial_root.is_dir():
            continue
        marker_path = trial_root / MARKER_NAME
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if (
                not isinstance(marker, dict)
                or marker.get("format") != 2
                or marker.get("kind") != "run"
                or marker.get("project") != str(trial_root / "project")
            ):
                continue
            pid = marker.get("process_id")
            if not isinstance(pid, int):
                continue
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                shutil.rmtree(trial_root)
                removed.append(trial_root)
            except PermissionError:
                continue
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return tuple(removed)


def run_trial(profile: str, settings_override: dict | None, command: list[str]) -> int:
    if not command:
        raise ValueError("Provide the trial command after --.")
    cleanup_abandoned_runs()
    project = prepare(profile, settings_override, root_prefix=RUN_PREFIX, kind="run")
    try:
        completed = subprocess.run(
            command,
            cwd=project,
            env={
                **{
                    key: value
                    for key, value in os.environ.items()
                    if key not in HOST_CONTEXT_VARIABLES
                },
                **runner_environment(str(project)),
            },
            check=False,
        )
        return completed.returncode
    finally:
        discard(str(project))


def summarize_transcript(transcript_path: str) -> dict:
    """Count only file reads explicitly exposed as read events in a JSONL transcript."""
    source = Path(transcript_path).expanduser()
    read_kinds = {"file_read", "read_file", "read"}
    commands: dict[str, dict] = {}
    reads: list[str] = []
    item_types: Counter[str] = Counter()
    invalid_json_lines = 0
    for line_number, line in enumerate(
        source.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid_json_lines += 1
            continue
        item = event.get("item", {}) if isinstance(event, dict) else {}
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", "unknown"))
        item_types[kind] += 1
        if kind == "command_execution":
            item_id = str(item.get("id", f"line-{line_number}"))
            commands[item_id] = item
        if kind in read_kinds:
            path = item.get("path") or item.get("file_path")
            reads.append(str(path) if path else "(path not recorded)")
    completed_commands = tuple(
        item
        for item in commands.values()
        if item.get("status") == "completed" and item.get("exit_code") == 0
    )
    uncertain_commands = tuple(
        item
        for item in commands.values()
        if item.get("status") != "completed" or item.get("exit_code") != 0
    )
    shell_reads = tuple(
        path
        for item in completed_commands
        for path in _simple_shell_read_paths(str(item.get("command", "")))
    )
    uncertain_shell_reads = tuple(
        path
        for item in uncertain_commands
        for path in _simple_shell_read_paths(str(item.get("command", "")))
    )
    return {
        "transcript": str(source.resolve()),
        "command_execution_items": len(commands),
        "failed_command_execution_items": sum(
            item.get("status") == "failed" or item.get("exit_code") not in (None, 0)
            for item in commands.values()
        ),
        "explicit_file_read_requests": len(reads),
        "unique_read_paths": len(
            {path for path in reads if path != "(path not recorded)"}
        ),
        "non_json_lines": invalid_json_lines,
        "simple_shell_read_requests": len(shell_reads),
        "simple_shell_read_paths": list(shell_reads),
        "unique_simple_shell_read_paths": len(set(shell_reads)),
        "unverified_shell_read_operands": list(uncertain_shell_reads),
        "read_paths": reads,
        "item_types": dict(sorted(item_types.items())),
        "note": "Direct file displays are counted only for completed commands with exit code 0. Failed or incomplete command operands are listed as unverified; indirect reads and searches are not counted.",
    }


def _simple_shell_read_paths(command: str) -> tuple[str, ...]:
    """Recognize direct file-display commands in simple shell command sequences."""
    try:
        outer = shlex.split(command)
        command_option = next(
            (
                index
                for index, token in enumerate(outer)
                if token.startswith("-") and "c" in token[1:]
            ),
            -1,
        )
        script = (
            outer[command_option + 1]
            if command_option >= 0 and command_option + 1 < len(outer)
            else command
        )
        lexer = shlex.shlex(script, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return ()
    if not tokens:
        return ()
    commands = _shell_segments(tokens)
    return tuple(
        path for segment in commands for path in _display_command_paths(segment)
    )


def _shell_segments(tokens: list[str]) -> tuple[tuple[str, ...], ...]:
    separators = {";", "&&", "||", "|", "&"}
    segments: list[tuple[str, ...]] = []
    current: list[str] = []
    for token in tokens:
        match token in separators:
            case True if current:
                segments.append(tuple(current))
                current = []
            case True:
                continue
            case False:
                current.append(token)
    if current:
        segments.append(tuple(current))
    return tuple(segments)


def _display_command_paths(segment: tuple[str, ...]) -> tuple[str, ...]:
    if not segment:
        return ()
    name = Path(segment[0]).name
    match name:
        case "cat" | "bat" | "less" | "more":
            operands = tuple(
                token
                for token in segment[1:]
                if not token.startswith("-") and token != "-"
            )
            return operands
        case "head" | "tail":
            operands = _without_option_arguments(
                segment[1:], {"-n", "--lines", "-c", "--bytes"}
            )
            return tuple(
                token
                for token in operands
                if not token.startswith("-") and token != "-"
            )
        case "sed":
            operands = _without_option_arguments(
                segment[1:], {"-e", "--expression", "-f", "--file"}
            )
            positional = tuple(token for token in operands if not token.startswith("-"))
            return positional[1:] if len(positional) > 1 else ()
        case _:
            return ()


def _without_option_arguments(
    tokens: tuple[str, ...], options_with_values: set[str]
) -> tuple[str, ...]:
    result: list[str] = []
    skip_next = False
    for token in tokens:
        match skip_next, token in options_with_values:
            case True, _:
                skip_next = False
            case False, True:
                skip_next = True
            case False, False:
                result.append(token)
    return tuple(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    prepare_parser = commands.add_parser(
        "prepare", help="create a fresh disposable project copy"
    )
    prepare_parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default="unconfigured",
        help="starting project settings",
    )
    prepare_parser.add_argument(
        "--settings",
        help="JSON file whose values override the selected profile",
    )
    discard_parser = commands.add_parser(
        "discard", help="remove a helper-created project copy"
    )
    discard_parser.add_argument("project_path")
    environment_parser = commands.add_parser(
        "environment", help="print isolated environment for a disposable trial"
    )
    environment_parser.add_argument("project_path")
    run_parser = commands.add_parser(
        "run", help="run a command in a disposable project and clean it up afterwards"
    )
    run_parser.add_argument(
        "--profile", choices=tuple(PROFILES), default="unconfigured"
    )
    run_parser.add_argument("--settings")
    run_parser.add_argument("run_command", nargs=argparse.REMAINDER)
    summary_parser = commands.add_parser(
        "summarize",
        help="count explicit file reads and command items in a JSONL transcript",
    )
    summary_parser.add_argument("transcript_path")
    args = parser.parse_args()
    try:
        match args.operation:
            case "prepare":
                overrides = (
                    json.loads(Path(args.settings).read_text(encoding="utf-8"))
                    if args.settings
                    else None
                )
                if overrides is not None and not isinstance(overrides, dict):
                    raise ValueError("Settings override must contain a JSON object.")
                print(prepare(args.profile, overrides))
            case "discard":
                print(f"Discarded {discard(args.project_path)}")
            case "environment":
                print(
                    json.dumps(
                        runner_environment(args.project_path),
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
            case "run":
                overrides = (
                    json.loads(Path(args.settings).read_text(encoding="utf-8"))
                    if args.settings
                    else None
                )
                if overrides is not None and not isinstance(overrides, dict):
                    raise ValueError("Settings override must contain a JSON object.")
                command = (
                    args.run_command[1:]
                    if args.run_command[:1] == ["--"]
                    else args.run_command
                )
                return run_trial(args.profile, overrides, command)
            case "summarize":
                print(
                    json.dumps(
                        summarize_transcript(args.transcript_path),
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
    except (
        OSError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"Acceptance trial error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
