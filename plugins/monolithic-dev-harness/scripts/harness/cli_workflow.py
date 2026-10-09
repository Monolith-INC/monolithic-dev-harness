"""The `harness work-session`, `workflow`, `decision`, and `suspension` commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from core.result import Err, Failure, Ok, Result, attempt, bind, err, fmap, require
from harness import (
    artifact_manifest,
    decisions,
    discovery,
    gates,
    harness_controls,
    onboarding,
    preferences,
    prepared_workflows,
    questions,
    review_decisions,
    startup,
    state,
    work_lifecycle,
    work_sessions,
    workflow,
)
from harness.cli_common import pairs, print_result, resolve_repo
from host_adapters.interactions import present

COMMANDS = (
    "plan",
    "begin",
    "work-session",
    "workflow",
    "decision",
    "suspension",
    "onboarding",
    "mode",
)


def _control_parser(
    sub: argparse._SubParsersAction, family: str, help_text: str
) -> argparse.ArgumentParser:
    """Argparse mutation is isolated to parser construction."""
    match sub.add_parser(family, help=help_text):
        case parser:
            parser.add_argument("operation", choices=onboarding.OPERATIONS[family])
            parser.add_argument(
                "--repo", default=".", help="project directory; no session required"
            )
            return parser


def add_parsers(sub: argparse._SubParsersAction) -> None:
    _control_parser(
        sub,
        "onboarding",
        "show, skip, dismiss, or restart onboarding without a session",
    )
    _control_parser(
        sub, "mode", "choose free or structured guidance; governance checks still apply"
    )
    plan_parser = sub.add_parser("plan", help="inspect a plan's size and scope signals")
    plan_parser.add_argument("operation", choices=("check",))
    plan_parser.add_argument("file")
    plan_parser.add_argument("--repo", default=".")
    begin_parser = sub.add_parser(
        "begin",
        help="start or continue work on a request in one step: setup check, work session, "
        "workflow, and discovery instructions",
    )
    begin_parser.add_argument(
        "--request", required=True, help="the user's exact request"
    )
    begin_parser.add_argument("--repo", default=".")
    begin_parser.add_argument(
        "--session", help="continue this saved work session (the user chose it)"
    )
    begin_parser.add_argument(
        "--new", action="store_true", help="start a new session even if one matches"
    )
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
            "manifest",
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
    workflow_parser.add_argument(
        "--manifest-output", help="local Markdown reading manifest"
    )
    workflow_parser.add_argument(
        "--document",
        action="append",
        help="JSON entry with path, purpose, read_when and owner",
    )
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
    decision_parser.add_argument("operation", choices=("present", "status", "fallback"))
    decision_parser.add_argument("--repo", default=".")
    decision_parser.add_argument(
        "--session-id", help="scope the question to a project work session"
    )
    decision_parser.add_argument(
        "--host",
        choices=("codex", "claude", "cursor", "text"),
        default="codex" if os.environ.get("CODEX_THREAD_ID") else "text",
    )
    decision_parser.add_argument("--blocking-available", action="store_true")
    decision_parser.add_argument("--async-available", action="store_true")
    decision_parser.add_argument("--native-unavailable", action="store_true")
    decision_parser.add_argument("--question")
    decision_parser.add_argument("--option", action="append")
    decision_parser.add_argument(
        "--detail",
        action="append",
        help="what an option means in practice; one per --option, in the same order",
    )
    decision_parser.add_argument(
        "--recommended",
        help="the option the agent recommends: an option id with --gate, else its label",
    )
    decision_parser.add_argument(
        "--gate",
        help="a standard question from config/gates.toml, in the project's language",
    )
    decision_parser.add_argument(
        "--value", action="append", help="fill one of the gate's {slots}: name=value"
    )
    decision_parser.add_argument("--artifact", action="append")
    decision_parser.add_argument("--approval", action="store_true")
    decision_parser.add_argument(
        "--allow-free-text",
        action="store_true",
        help="accept a native Other response for routing; never for write approval",
    )
    suspension_parser = sub.add_parser(
        "suspension",
        help="show or end a suspension of the harness checks (type `harness suspend` to start one)",
    )
    suspension_parser.add_argument("operation", choices=("status", "resume"))
    suspension_parser.add_argument("--repo", default=".")


def run(args: argparse.Namespace) -> int:
    match args.command:
        case "onboarding" | "mode":
            return print_result(
                fmap(
                    onboarding.control(
                        resolve_repo(args.repo), args.command, args.operation
                    ),
                    lambda value: json.dumps(value, ensure_ascii=False),
                )
            )
        case "plan":
            from harness.plan_check import check

            return print_result(
                fmap(
                    check(resolve_repo(args.repo) / args.file),
                    lambda value: json.dumps(value),
                )
            )
        case "begin":
            return print_result(
                fmap(
                    startup.begin(
                        resolve_repo(args.repo), args.request, args.session, args.new
                    ),
                    lambda value: json.dumps(value, ensure_ascii=False),
                )
            )
        case "work-session":
            return work_session_command(args)
        case "workflow":
            return workflow_command(_with_current_session(args))
        case "decision":
            return decision_command(_with_current_session(args))
        case _:
            return suspension_command(args)


def _current_as_json(project: Path, session: work_sessions.Session) -> dict:
    work_sessions.remember_current(project, session.id)
    return work_sessions.as_json(session)


def _with_current_session(args: argparse.Namespace) -> argparse.Namespace:
    """Nobody has to name the work session: an unnamed one is the project's current session."""
    if args.session_id is None:
        args.session_id = work_sessions.current(Path(args.repo).resolve())
    return args


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
        case "select":
            result = fmap(
                work_sessions.select(project, args.session_id or ""),
                lambda session: _current_as_json(project, session),
            )
        case "status":
            result = fmap(
                work_sessions.select(project, args.session_id or ""),
                work_sessions.as_json,
            )
        case "resume":
            result = fmap(
                work_lifecycle.resume(project, args.session_id or ""),
                work_sessions.as_json,
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
        case "fallback" if not (
            args.question
            or args.option
            or args.detail
            or args.recommended
            or args.gate
            or args.value
            or args.artifact
            or args.approval
            or args.allow_free_text
            or args.blocking_available
        ):
            return _fallback_decision(repo, args)
        case "present":
            key = decisions.new_key()
            match _question_spec(repo, args):
                case Err(failure):
                    print(failure.message, file=sys.stderr)
                    return 2
                case Ok(spec):
                    pass
            wording = questions.problems(
                {
                    "questions": [
                        {
                            "question": spec.question,
                            "header": "Review",
                            "options": _choice_options(spec.options, spec.details),
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
                    "question": spec.question,
                    "options": _choice_options(spec.options, spec.details),
                },
                args.host,
                args.blocking_available
                or (
                    args.host == "codex"
                    and not args.async_available
                    and not args.native_unavailable
                ),
                args.async_available,
                free_text=spec.free_text,
                language=_language(repo),
            )
            binds = (
                {"bound": spec.bound, "target": list(spec.target or ())}
                if spec.approval
                else None
            )
            match spec.gate:
                case "harness-controls":
                    match repo.resolve() == resolve_repo(".").resolve():
                        case False:
                            return print_result(
                                err(
                                    "control_project_mismatch",
                                    "Show lifecycle controls from the target project's workspace. A reply must never change a different project.",
                                )
                            )
                        case True:
                            pass
                    match shown["transport"]:
                        case "chat":
                            harness_controls.stage_chat(
                                repo,
                                key,
                                spec.question,
                                spec.options,
                                os.environ.get("CODEX_THREAD_ID", ""),
                            )
                        case _:
                            pass
                    return print_result(
                        Ok(
                            json.dumps(
                                {
                                    **shown,
                                    "state": "control",
                                    "decision_id": key,
                                    "instruction": "Show this lifecycle control independently of pending work. If native delivery fails, repeat this gate with --async-available, then --native-unavailable. Do not fallback to another pending decision. Real human replies are recorded by the host hook.",
                                }
                            )
                        )
                    )
                case _:
                    pass
            return print_result(
                bind(
                    _workflow_artifacts(repo, args.artifact),
                    lambda artifacts: (
                        _reused(
                            decisions.reusable(
                                repo,
                                spec.question,
                                spec.options,
                                artifacts,
                                spec.approval,
                                work_session_id=args.session_id,
                                target=spec.target,
                            )
                        )
                        or fmap(
                            review_decisions.begin(
                                repo,
                                key,
                                spec.question,
                                spec.options,
                                shown["transport"],
                                artifacts,
                                spec.approval,
                                work_session_id=args.session_id,
                                allow_free_text=spec.free_text,
                                details=spec.details,
                                gate=spec.gate,
                                binds=binds,
                            ),
                            lambda _: json.dumps(
                                {
                                    **shown,
                                    "decision_id": key,
                                    "state": "waiting_for_human",
                                }
                            ),
                        )
                    ),
                )
            )
        case _:
            return 2


def _reused(entry: dict | None) -> Result[str] | None:
    """The human already answered this about the same content: say so instead of asking."""
    match entry:
        case {"id": str() as key, "answer": str() as answer}:
            return Ok(
                json.dumps(
                    {
                        "state": "already_answered",
                        "decision_id": key,
                        "answer": answer,
                        "instruction": "The human already gave this answer about the same, "
                        "unchanged content. Do not ask again; continue with it. Mention the "
                        "earlier choice in one line so the human can reopen it.",
                    }
                )
            )
        case _:
            return None


def _question_spec(repo: Path, args: argparse.Namespace) -> Result[gates.Rendered]:
    """The question to ask: a catalog gate in the project's language, or a one-off question.

    Approvals always come from the catalog, so their wording and what they are tied to are fixed.
    """
    values = dict(pairs(args.value))
    if args.gate:
        if (
            args.question
            or args.option
            or args.detail
            or args.approval
            or args.allow_free_text
        ):
            return err(
                "decision_invalid",
                "a --gate supplies its own question, options, and kind; pass only --value, "
                "--recommended, and --artifact",
            )
        return bind(
            gates.render(args.gate, _language(repo), values, args.recommended),
            lambda rendered: (
                Ok(rendered)
                if not rendered.artifact or args.artifact
                else err(
                    "decision_invalid",
                    f"gate {args.gate} reviews files: pass them with --artifact",
                )
            ),
        )
    if args.approval:
        return err(
            "decision_invalid",
            "approvals come from the catalog: use --gate (see config/gates.toml)",
        )
    if values:
        return err("decision_invalid", "--value fills a --gate's slots")
    return fmap(
        _labelled_options(args),
        lambda labelled: gates.Rendered(
            gate="",
            question=args.question or "",
            options=labelled,
            details=tuple(args.detail or ()),
            free_text=args.allow_free_text,
            approval=False,
            artifact=False,
            bound=False,
            target=None,
        ),
    )


def _labelled_options(args: argparse.Namespace) -> Result[tuple[str, ...]]:
    """Offered options as shown, with the recommended one marked the way Codex marks it."""
    options = tuple(args.option or ())
    if len(args.detail or ()) > len(options):
        return err("decision_invalid", "give at most one --detail per --option")
    match args.recommended:
        case None:
            return Ok(options)
        case str() as recommended if recommended in options:
            return Ok(
                tuple(
                    f"{option} (Recommended)" if option == recommended else option
                    for option in options
                )
            )
        case _:
            return err("decision_invalid", "--recommended must name an offered option")


def _choice_options(
    options: tuple[str, ...], details: tuple[str, ...]
) -> list[dict[str, str]]:
    return [
        {"label": option, "description": details[i] if i < len(details) else ""}
        for i, option in enumerate(options)
    ]


def _language(repo: Path) -> str:
    match preferences.language_for(repo):
        case Ok("pt-br"):
            return "pt-br"
        case _:
            return "en"


def _fallback_decision(repo: Path, args: argparse.Namespace) -> int:
    match decisions.pending(repo, args.session_id):
        case None:
            return print_result(err("decision_invalid", "no question is waiting"))
        case pending:
            return _show_fallback(
                repo,
                args,
                pending,
                present(
                    {
                        "id": pending.id,
                        "header": "Review",
                        "question": pending.question,
                        "options": _choice_options(pending.options, pending.details),
                    },
                    args.host,
                    False,
                    args.async_available and pending.transport == "blocking",
                    free_text=pending.allow_free_text,
                    language=_language(repo),
                ),
            )


def _show_fallback(
    repo: Path,
    args: argparse.Namespace,
    pending: decisions.Pending,
    shown: dict,
) -> int:
    return print_result(
        fmap(
            decisions.fallback(repo, shown["transport"], work_session_id=pending.scope),
            lambda _: json.dumps(
                {**shown, "decision_id": pending.id, "state": "waiting_for_human"}
            ),
        )
    )


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
    # Changed pinned instructions are consequential; absence of a session is not.
    match session_id:
        case None:
            return bind(
                workflow.load(repo), lambda current: workflow.resume(current, point_id)
            )
        case scope:
            return bind(
                discovery.verify(repo, scope),
                lambda _: bind(
                    workflow.load(repo, scope),
                    lambda current: workflow.resume(current, point_id),
                ),
            )


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
        "checkpoint",
        "resume",
        "manifest",
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
            "checkpoint",
            "pause",
            "resume",
            "cancel",
            "back",
            "manifest",
        ):
            return print_result(
                err(
                    "work_session_required",
                    "start or resume a work session before project work",
                )
            )
        case _:
            pass
    match args.operation:
        case "manifest":
            return print_result(
                artifact_manifest.save(
                    repo, args.manifest_output or "", tuple(args.document or ())
                )
            )
        case "render":
            return print_result(
                bind(
                    require(
                        args.stage in {"discover", "discovery"},
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
                work_lifecycle.start_workflow(
                    repo, args.request or "", args.session_id
                ),
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
            return _workflow_result(repo, result, args.session_id)
        case "resume":
            result = _workflow_resume(repo, args.point, args.session_id)
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
