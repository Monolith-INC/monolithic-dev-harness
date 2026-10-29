"""Create, install and drive disposable copies of the acceptance-test project.

This module is for test runs only. Regular harness setup must not depend on it.

    project_fixture.py create [--settings FILE] [--version X.Y.Z] [--host claude|codex|...]
    project_fixture.py run PROJECT --runtime claude|codex --briefing FILE [--interactive]
    project_fixture.py answer PROJECT "<the human's reply>"
    project_fixture.py discard PROJECT

`create` copies the test project into this checkout's `temp/` and installs the harness into that
copy: this checkout's source, or a published release with `--version`. The install, the host
configuration homes and the `harness` command all live in the copy's trial folder, so the user's
own installs and host settings are never touched.

`run` starts the agent in the copy with the briefing as its first message. Headless, the agent
keeps its host's normal limits: Claude Code may edit files and run only the allowed commands below;
Codex stays in its workspace sandbox. When the harness waits for the human, `run` prints the
question and exits with WAITING; `answer` resumes the same session with the reply as the user's
message, so a person or a coordinating agent relays the questions. `--interactive` opens the
host's own session instead, where the person answers and approves each action.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPTS = REPOSITORY / "plugins" / "monolithic-dev-harness" / "scripts"

sys.path.insert(0, str(PLUGIN_SCRIPTS))
sys.path.insert(0, str(REPOSITORY / "scripts"))

import acceptance_trial  # noqa: E402

from core.result import Err, Ok, Result, err  # noqa: E402
from harness import settings as harness_settings  # noqa: E402

HOSTS = ("claude", "codex", "cursor", "kimi", "zed")
# Exit status of `run` and `answer` while the harness waits for the human.
WAITING = 3
RUN_RECORD = "run.json"
TRANSCRIPT = "transcript.jsonl"
# What a headless Claude Code run may do without asking: edit files in the copy, run the harness,
# and read. Anything else is refused, as it would be for a user who declined it.
CLAUDE_ALLOWED = (
    "Read",
    "Glob",
    "Grep",
    "Edit",
    "Write",
    "Bash(harness:*)",
    "Bash(ls:*)",
    "Bash(cat:*)",
    "Bash(git status:*)",
    "Bash(git diff:*)",
)


def create_test_project(
    configuration_file: str | Path | None = None,
    *,
    version: str | None = None,
    hosts: tuple[str, ...] = ("claude", "codex"),
) -> Result[Path]:
    """A fresh test-project copy in `temp/` with the harness installed for `hosts`.

    The configuration file, when given, holds one complete `.harness/settings.json` value; without
    it the copy starts unconfigured, as a new user's project does.
    """
    match _settings(configuration_file):
        case Err() as failure:
            return failure
        case Ok(raw):
            pass
    try:
        acceptance_trial.cleanup_abandoned_runs()
        project = acceptance_trial.prepare(
            profile="unconfigured", overrides=raw, in_checkout=True
        )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as failure:
        return err(
            "fixture_creation_failed",
            f"could not create the test project: {failure}",
            retryable=True,
        )
    match install(project, version, hosts):
        case Err() as failure:
            acceptance_trial.discard(str(project))
            return failure
        case Ok():
            return Ok(project)


def install(project: Path, version: str | None, hosts: tuple[str, ...]) -> Result[Path]:
    """Install the harness into the copy for each host, inside the trial's own folders."""
    _, trial_root, _ = acceptance_trial._trial_metadata(str(project))
    log = trial_root / "installer.log"
    source = ("--version", version) if version else ("--source", str(REPOSITORY))
    environment = _environment(project)
    if "codex" in hosts:
        _trust_for_codex(project, Path(environment["CODEX_HOME"]))
    with log.open("w", encoding="utf-8") as output:
        for host in hosts:
            completed = subprocess.run(
                [
                    "bash",
                    str(REPOSITORY / "install.sh"),
                    "--scope",
                    "local",
                    "--project",
                    str(project),
                    "--host",
                    host,
                    *source,
                    "--yes",
                ],
                cwd=project,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if completed.returncode != 0:
                return err(
                    "install_failed",
                    f"installing the harness for {host} failed; see {log}",
                )
    return Ok(log)


def start_run(
    project: Path, runtime: str, briefing: str, *, interactive: bool = False
) -> Result[dict]:
    """Start the agent in the copy with the briefing as its first message."""
    match runtime:
        case "claude" | "codex":
            pass
        case _:
            return err(
                "unsupported_runtime",
                f"{runtime} has no headless run here yet; use claude or codex",
            )
    if interactive:
        completed = subprocess.run(
            [runtime, briefing], cwd=project, env=_environment(project), check=False
        )
        return Ok({"state": "closed", "exit_code": completed.returncode})
    return _headless(project, runtime, _first_command(runtime, briefing))


def answer(project: Path, reply: str) -> Result[dict]:
    """Resume the headless session with the human's reply as their next message."""
    _, trial_root, _ = acceptance_trial._trial_metadata(str(project))
    record_path = trial_root / RUN_RECORD
    if not record_path.is_file():
        return err(
            "no_run", "this copy has no headless run to answer; start one with run"
        )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    return _headless(
        project,
        record["runtime"],
        _resume_command(record["runtime"], record["session"], reply),
    )


def pending_question(project: Path) -> dict | None:
    """The question the harness waits on in the copy, read from its own records."""
    for path in sorted((project / ".harness" / "state").rglob("decision.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict) and record.get("status") == "pending":
            return {
                "id": record.get("id"),
                "question": record.get("question"),
                "options": record.get("options", []),
                "details": record.get("details", []),
                "approval": bool(record.get("approval")),
            }
    return None


def discard_test_project(project: str | Path) -> Result[Path]:
    """Remove a fixture created by this test-only tool, if its ownership marker is valid."""
    try:
        return Ok(acceptance_trial.discard(str(project)))
    except (OSError, ValueError, json.JSONDecodeError) as failure:
        return err("fixture_discard_failed", str(failure))


def _headless(project: Path, runtime: str, command: list[str]) -> Result[dict]:
    _, trial_root, _ = acceptance_trial._trial_metadata(str(project))
    transcript = trial_root / TRANSCRIPT
    completed = subprocess.run(
        command,
        cwd=project,
        env=_environment(project),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    with transcript.open("a", encoding="utf-8") as output:
        output.write(completed.stdout)
    events = tuple(_events(completed.stdout))
    session = _session(runtime, events)
    if session:
        (trial_root / RUN_RECORD).write_text(
            json.dumps({"runtime": runtime, "session": session}), encoding="utf-8"
        )
    question = pending_question(project)
    return Ok(
        {
            "state": "waiting_for_human" if question else "finished",
            "question": question,
            "last_message": _last_message(runtime, events),
            "exit_code": completed.returncode,
            "session": session,
            "transcript": str(transcript),
            "stderr": completed.stderr[-2000:],
        }
    )


def _first_command(runtime: str, briefing: str) -> list[str]:
    match runtime:
        case "claude":
            return [*_claude(), "--", briefing]
        case _:
            return [*_codex(), briefing]


def _resume_command(runtime: str, session: str, reply: str) -> list[str]:
    match runtime:
        case "claude":
            return [*_claude(), "--resume", session, "--", reply]
        case _:
            return [*_codex(), "resume", session, reply]


def _claude() -> list[str]:
    return [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        # Comma-separated in one argument: as separate words the list would swallow what follows.
        "--allowedTools",
        ",".join(CLAUDE_ALLOWED),
    ]


def _codex() -> list[str]:
    return ["codex", "exec", "--json", "--sandbox", "workspace-write"]


def _events(stdout: str):
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event


def _session(runtime: str, events: tuple[dict, ...]) -> str:
    key = "session_id" if runtime == "claude" else "thread_id"
    return next(
        (str(event[key]) for event in events if isinstance(event.get(key), str)), ""
    )


def _last_message(runtime: str, events: tuple[dict, ...]) -> str:
    for event in reversed(events):
        match runtime, event:
            case "claude", {"type": "result", "result": str() as text}:
                return text
            case "codex", {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": str() as text},
            }:
                return text
            case _:
                pass
    return ""


def _environment(project: Path) -> dict[str, str]:
    return {
        **{
            key: value
            for key, value in os.environ.items()
            if key not in acceptance_trial.HOST_CONTEXT_VARIABLES
        },
        **acceptance_trial.runner_environment(str(project)),
    }


def _trust_for_codex(project: Path, codex_home: Path) -> None:
    """Codex loads a project's own configuration only for a trusted project."""
    config = codex_home / "config.toml"
    entry = f'[projects."{project}"]\ntrust_level = "trusted"\n'
    existing = config.read_text(encoding="utf-8") if config.is_file() else ""
    if entry not in existing:
        config.write_text(
            existing + ("\n" if existing else "") + entry, encoding="utf-8"
        )


def _settings(configuration_file: str | Path | None) -> Result[dict | None]:
    if configuration_file is None:
        return Ok(None)
    configuration = Path(configuration_file).expanduser()
    if not configuration.is_file():
        return err(
            "missing_configuration",
            f"project configuration file does not exist: {configuration}",
        )
    try:
        raw = json.loads(configuration.read_text(encoding="utf-8"))
    except json.JSONDecodeError as failure:
        return err(
            "invalid_configuration_json",
            f"project configuration is not valid JSON: {failure}",
        )
    except OSError as failure:
        return err(
            "configuration_unreadable",
            f"project configuration could not be read: {failure}",
        )
    match raw:
        case dict():
            match harness_settings.parse(raw):
                case Err() as failure:
                    return failure
                case Ok():
                    return Ok(raw)
        case _:
            return err(
                "invalid_configuration", "project configuration must be a JSON object"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="operation", required=True)
    create = commands.add_parser(
        "create", help="copy the test project and install the harness"
    )
    create.add_argument(
        "--settings", help="a complete .harness/settings.json to start from"
    )
    create.add_argument(
        "--version", help="install this published release instead of this checkout"
    )
    create.add_argument(
        "--host",
        action="append",
        choices=HOSTS,
        help="host to install for; repeat for several (default: claude and codex)",
    )
    run = commands.add_parser("run", help="start the agent in a copy")
    run.add_argument("project")
    run.add_argument("--runtime", required=True, choices=("claude", "codex"))
    run.add_argument("--briefing", required=True, help="file holding the first message")
    run.add_argument(
        "--interactive",
        action="store_true",
        help="open the host's own session, where the person answers",
    )
    reply = commands.add_parser(
        "answer", help="resume a headless run with the human's reply"
    )
    reply.add_argument("project")
    reply.add_argument("reply")
    discard = commands.add_parser("discard", help="remove a copy and its trial folder")
    discard.add_argument("project")
    args = parser.parse_args(argv)
    match args.operation:
        case "create":
            result = create_test_project(
                args.settings,
                version=args.version,
                hosts=tuple(args.host or ("claude", "codex")),
            )
            return _report(_as_record(result, "project"))
        case "run":
            return _report(
                start_run(
                    Path(args.project).resolve(),
                    args.runtime,
                    Path(args.briefing).read_text(encoding="utf-8"),
                    interactive=args.interactive,
                )
            )
        case "answer":
            return _report(answer(Path(args.project).resolve(), args.reply))
        case _:
            return _report(_as_record(discard_test_project(args.project), "removed"))


def _as_record(result: Result[Path], name: str) -> Result[dict]:
    match result:
        case Ok(path):
            return Ok({name: str(path)})
        case failed:
            return failed


def _report(result: Result[dict]) -> int:
    match result:
        case Ok(value):
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return WAITING if value.get("state") == "waiting_for_human" else 0
        case Err(failure):
            print(json.dumps(failure.to_dict(), ensure_ascii=False), file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
