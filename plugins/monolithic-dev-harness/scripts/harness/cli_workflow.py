"""The `harness work-session`, `workflow`, `decision`, and `suspension` commands."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from core.result import Err, Failure, Ok, Result, attempt, bind, err, fmap, require
from harness import (
    decisions,
    discovery,
    preferences,
    prepared_workflows,
    questions,
    settings,
    state,
    work_sessions,
    workflow,
)
from harness.cli_common import pairs, print_result, resolve_repo
from host_adapters.interactions import present
from integrations import registry

COMMANDS = ("work-session", "workflow", "decision", "suspension")


def add_parsers(sub: argparse._SubParsersAction) -> None:
    work_session_parser = sub.add_parser(
        "work-session",
        help="start, choose, pause, stop, or resume project work sessions",
    )
    work_session_parser.add_argument(
        "operation",
        choices=(
            "start",
            "list",
            "route",
            "select",
            "status",
            "pause",
            "stop",
            "resume",
            "complete",
        ),
    )
    work_session_parser.add_argument("session_id", nargs="?")
    work_session_parser.add_argument(
        "--request", help="the exact request for a new work session"
    )
    work_session_parser.add_argument("--repo", default=".")
    workflow_parser = sub.add_parser(
        "workflow", help="save, navigate, pause, resume, cancel, or complete a workflow"
    )
    workflow_parser.add_argument(
        "operation",
        choices=(
            "start",
            "render",
            "checkpoint",
            "status",
            "list",
            "routes",
            "prepare",
            "back",
            "pause",
            "resume",
            "cancel",
            "complete",
        ),
    )
    workflow_parser.add_argument("--repo", default=".")
    workflow_parser.add_argument(
        "--session-id", help="save or load this project's independent work session"
    )
    workflow_parser.add_argument(
        "--request",
        help="start a workflow or include the exact request in a prepared handoff",
    )
    workflow_parser.add_argument("--point", type=int)
    workflow_parser.add_argument("--stage", choices=workflow.STAGES)
    workflow_parser.add_argument("--label")
    workflow_parser.add_argument("--artifact", action="append")
    workflow_parser.add_argument("--decision", action="append")
    workflow_parser.add_argument("--pending")
    workflow_parser.add_argument("--next-action")
    workflow_parser.add_argument("--write-id", action="append")
    workflow_parser.add_argument("--route", help="prepared route to inspect")
    workflow_parser.add_argument(
        "--prepared-stage", help="stage within a prepared route to inspect"
    )
    workflow_parser.add_argument(
        "--available",
        action="append",
        help="a tracker or SCM tool this host offers (repeat); a prepared step is ready only "
        "when the host confirmed every tool it needs",
    )

    decision_parser = sub.add_parser(
        "decision", help="present a host-adapted decision and wait for the human"
    )
    decision_parser.add_argument("operation", choices=("present", "status"))
    decision_parser.add_argument("--repo", default=".")
    decision_parser.add_argument(
        "--session-id", help="scope the question to a project work session"
    )
    decision_parser.add_argument(
        "--host", choices=("codex", "claude", "cursor", "text"), default="text"
    )
    decision_parser.add_argument("--blocking-available", action="store_true")
    decision_parser.add_argument("--async-available", action="store_true")
    decision_parser.add_argument("--question")
    decision_parser.add_argument("--option", action="append")
    decision_parser.add_argument("--artifact", action="append")
    decision_parser.add_argument("--approval", action="store_true")
    suspension_parser = sub.add_parser(
        "suspension",
        help="show or end a suspension of the harness checks (type `harness suspend` to start one)",
    )
    suspension_parser.add_argument("operation", choices=("status", "resume"))
    suspension_parser.add_argument("--repo", default=".")


def run(args: argparse.Namespace) -> int:
    match args.command:
        case "work-session":
            return work_session_command(args)
        case "workflow":
            return workflow_command(args)
        case "decision":
            return decision_command(args)
        case _:
            return suspension_command(args)


def work_session_command(args: argparse.Namespace) -> int:
    project = Path(args.repo).resolve()
    match args.operation:
        case "start":
            result = bind(
                discovery.onboarding_ready(project),
                lambda _: fmap(
                    work_sessions.start(project, args.request or ""),
                    work_sessions.as_json,
                ),
            )
        case "list":
            result = fmap(
                work_sessions.list_sessions(project),
                lambda sessions: [
                    work_sessions.as_json(session) for session in sessions
                ],
            )
        case "route":
            result = work_sessions.route(project, args.request or "")
        case "select" | "status":
            result = fmap(
                work_sessions.select(project, args.session_id or ""),
                work_sessions.as_json,
            )
        case "resume":
            result = bind(
                discovery.onboarding_ready(project),
                lambda _: bind(
                    discovery.verify(project, args.session_id or ""),
                    lambda _: fmap(
                        work_sessions.transition(
                            project, args.session_id or "", "resume"
                        ),
                        work_sessions.as_json,
                    ),
                ),
            )
        case "pause" | "stop" | "complete":
            result = fmap(
                work_sessions.transition(
                    project, args.session_id or "", args.operation
                ),
                work_sessions.as_json,
            )
        case _:
            return 2
    return print_result(
        fmap(result, lambda value: json.dumps(value, ensure_ascii=False, indent=2))
    )


def suspension_command(args: argparse.Namespace) -> int:
    """Status and resume only: suspending is recorded from the user's own prompt."""
    if not Path(args.repo).is_dir():
        print(f"{args.repo} is not a directory", file=sys.stderr)
        return 2
    repo = resolve_repo(args.repo)
    changed = (
        attempt(
            lambda: state.set_harness_mode(repo, "active"),
            "state_unwritable",
            "harness mode",
            OSError,
        )
        if args.operation == "resume"
        else Ok(None)
    )
    return print_result(
        fmap(changed, lambda _: json.dumps({"mode": state.harness_mode(repo)}))
    )


def decision_command(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    match args.operation:
        case "status":
            print(decisions.status(repo, args.session_id))
            return 0
        case "present":
            key = decisions.new_key()
            wording = questions.problems(
                {
                    "questions": [
                        {
                            "question": args.question or "",
                            "header": "Review",
                            "options": [
                                {"label": option, "description": ""}
                                for option in args.option or ()
                            ],
                        }
                    ]
                }
            )
            if wording:
                print(questions.rewrite_reason(wording), file=sys.stderr)
                return 2
            shown = present(
                {
                    "id": key,
                    "header": "Review",
                    "question": args.question or "",
                    "options": [
                        {"label": option, "description": ""}
                        for option in args.option or ()
                    ],
                },
                args.host,
                args.blocking_available,
                args.async_available,
            )
            return print_result(
                bind(
                    _workflow_artifacts(repo, args.artifact),
                    lambda artifacts: fmap(
                        decisions.begin(
                            repo,
                            key,
                            args.question or "",
                            tuple(args.option or ()),
                            shown["transport"],
                            artifacts,
                            args.approval,
                            work_session_id=args.session_id,
                        ),
                        lambda _: json.dumps(
                            {**shown, "decision_id": key, "state": "waiting_for_human"}
                        ),
                    ),
                )
            )
        case _:
            return 2


def _workflow_result(
    repo: Path, result: Result[workflow.Workflow], session_id: str | None = None
) -> int:
    return print_result(
        bind(
            result,
            lambda current: fmap(
                workflow.save(repo, current, session_id),
                lambda _: json.dumps(asdict(current), indent=2, sort_keys=True),
            ),
        )
    )


def _workflow_point(repo: Path, args: argparse.Namespace) -> Result[workflow.Workflow]:
    return bind(
        workflow.load(repo, args.session_id),
        lambda current: bind(
            _workflow_artifacts(repo, args.artifact),
            lambda artifacts: workflow.add_point(
                current,
                args.label or "",
                args.stage or "",
                artifacts,
                pairs(args.decision),
                args.pending or "",
                args.next_action or "",
                tuple(args.write_id or ()),
            ),
        ),
    )


def _workflow_artifacts(
    repo: Path, names: list[str] | None
) -> Result[tuple[tuple[str, str], ...]]:
    from core.result import sequence

    return sequence(_workflow_artifact(repo, name) for name in names or ())


def _workflow_artifact(repo: Path, name: str) -> Result[tuple[str, str]]:
    target = (repo / name).resolve()
    return bind(
        require(
            target.is_relative_to(repo.resolve()),
            "invalid_workflow",
            "artifact must be inside this repository",
        ),
        lambda _: fmap(workflow.file_digest(target), lambda digest: (name, digest)),
    )


def _workflow_resume(
    repo: Path, point_id: int | None, session_id: str | None = None
) -> Result[workflow.Workflow]:
    def checked(current: workflow.Workflow) -> Result[workflow.Workflow]:
        return bind(
            workflow.resume(current, point_id),
            lambda selected: bind(
                require(
                    not workflow.stale_artifacts(repo, selected.current),
                    "stale_workflow",
                    "a reviewed document changed; go Back and review its new revision",
                ),
                lambda _: (
                    fmap(
                        registry.selected(repo, settings.load(repo)),
                        lambda _: selected,
                    )
                    if selected.current.stage != "setup"
                    else Ok(selected)
                ),
            ),
        )

    return bind(
        discovery.verify(repo, session_id),
        lambda _: bind(workflow.load(repo, session_id), checked),
    )


def _workflow_start(
    repo: Path, request: str, session_id: str | None = None
) -> Result[workflow.Workflow]:
    def begin(_: object) -> Result[workflow.Workflow]:
        return bind(
            bind(
                discovery.onboarding_ready(repo),
                lambda _: preferences.language_for(repo),
            ),
            lambda language: bind(
                require(
                    bool(language),
                    "language_unset",
                    "choose English or Português (Brasil) before starting",
                ),
                lambda _: workflow.start(request, language),
            ),
        )

    match workflow.load(repo, session_id):
        case Ok(current) if current.status in workflow.TERMINAL_STATUSES:
            return bind(workflow.archive_terminal(repo, session_id), begin)
        case Ok():
            return Err(Failure("workflow_exists", "a workflow is already saved"))
        case Err(failure) if failure.code == "workflow_absent":
            if session_id is None:
                return begin(None)
            return bind(
                work_sessions.select(repo, session_id),
                lambda session: bind(
                    require(
                        not request or request.strip() == session.request,
                        "invalid_workflow",
                        "the workflow request must match its work session",
                    ),
                    begin,
                ),
            )
        case Err() as failure:
            return failure


def workflow_command(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    if decisions.blocking(repo, args.session_id) and args.operation not in (
        "status",
        "list",
        "pause",
        "cancel",
        "back",
        "routes",
        "prepare",
    ):
        return print_result(
            Err(
                Failure(
                    "decision_pending",
                    "wait for the human's answer before advancing the workflow",
                )
            )
        )
    match args.operation, args.session_id:
        case operation, None if operation not in (
            "status",
            "list",
            "routes",
            "prepare",
        ):
            return print_result(
                err(
                    "work_session_required",
                    "complete onboarding, then select a work session and pass --session-id before project work",
                )
            )
        case _:
            pass
    match args.operation:
        case "render":
            return print_result(
                bind(
                    require(
                        args.stage == "discover",
                        "invalid_request",
                        "runtime rendering supports the discover stage",
                    ),
                    lambda _: fmap(
                        discovery.render(repo, args.session_id),
                        lambda package: json.dumps(
                            package, ensure_ascii=False, indent=2
                        ),
                    ),
                )
            )
        case "routes":
            return print_result(
                fmap(
                    prepared_workflows.routes(),
                    lambda found: json.dumps(found, indent=2, sort_keys=True),
                )
            )
        case "prepare":
            return print_result(
                fmap(
                    prepared_workflows.prepare_stage(
                        repo,
                        args.route or "",
                        args.prepared_stage or "",
                        original_request=args.request or "",
                        available_operations=args.available,
                    ),
                    lambda package: json.dumps(
                        package, ensure_ascii=False, indent=2, sort_keys=True
                    ),
                )
            )
        case "status":
            return print_result(
                fmap(
                    workflow.load(repo, args.session_id),
                    lambda current: json.dumps(
                        asdict(current), indent=2, sort_keys=True
                    ),
                )
            )
        case "list":
            return print_result(
                fmap(
                    workflow.load(repo, args.session_id),
                    lambda current: json.dumps(
                        {
                            "current_point": current.current.id,
                            "status": current.status,
                            "checkpoints": [
                                {
                                    "id": point.id,
                                    "label": point.label,
                                    "stage": point.stage,
                                    "current": index == current.cursor,
                                    "pending": point.pending,
                                    "next_action": point.next_action,
                                    "artifacts": [name for name, _ in point.artifacts],
                                }
                                for index, point in enumerate(current.points)
                            ],
                        },
                        indent=2,
                        sort_keys=True,
                    ),
                )
            )
        case "start":
            return _workflow_result(
                repo,
                _workflow_start(repo, args.request or "", args.session_id),
                args.session_id,
            )
        case "checkpoint":
            return _workflow_result(repo, _workflow_point(repo, args), args.session_id)
        case "pause":
            return _workflow_result(
                repo,
                bind(workflow.load(repo, args.session_id), workflow.pause),
                args.session_id,
            )
        case "back":
            result = bind(
                workflow.load(repo, args.session_id),
                lambda current: workflow.navigate(current, args.point),
            )
            match result:
                case Ok():
                    state.revoke_approvals(repo, args.session_id)
                case _:
                    pass
            return _workflow_result(repo, result, args.session_id)
        case "resume":
            result = _workflow_resume(repo, args.point, args.session_id)
            match result:
                case Ok():
                    state.revoke_approvals(repo, args.session_id)
                case _:
                    pass
            return _workflow_result(repo, result, args.session_id)
        case "cancel":
            result = bind(workflow.load(repo, args.session_id), workflow.cancel)
            match result:
                case Ok():
                    state.revoke_approvals(repo, args.session_id)
                case _:
                    pass
            return _workflow_result(repo, result, args.session_id)
        case "complete":
            return _workflow_result(
                repo,
                bind(workflow.load(repo, args.session_id), workflow.complete),
                args.session_id,
            )
        case _:
            return 2
