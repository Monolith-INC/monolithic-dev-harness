#!/usr/bin/env python3
"""`harness` command: version, checks, bootstrap, sessions, and onboarded trackers.

harness version
harness doctor [--repo <dir>] [--tools]
harness bootstrap --repo <dir> [--inspect | --propose | --apply-digest <hash>]
harness session start <work item> [--workflow <name>] | status | pause | resume | close
harness work-session route --request <text> | start --request <text> | list | select <id> | pause|stop|resume|complete <id>
harness workflow start | checkpoint | list | status | routes | prepare | back | pause | resume | cancel | complete [--session-id <id>]
harness preference show | language <en|pt-br>
harness tracker list | show <name> | stage <folder> [--value KEY=VALUE ...]
harness adoption assess | plan | status | materialize ...
harness knowledge <operation> ...
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from core.result import (  # noqa: E402
    Err,
    Failure,
    Ok,
    Result,
    attempt,
    bind,
    fmap,
    require,
)
from harness import (  # noqa: E402
    adoption,
    bmad,
    decisions,
    gitstate,
    knowledge,
    local_tracker,
    preferences,
    prepared_workflows,
    sessions,
    settings,
    state,
    work_sessions,
    workflow,
)
from host_adapters.interactions import present  # noqa: E402
from integrations import (  # noqa: E402
    branches,
    onboarding,
    readiness,
    registry,
    transport,
)
from integrations.contracts import TrackerOps, WorkItem  # noqa: E402

PLUGIN_ID = "monolithic-dev-harness@monolithic-dev-harness"


def version() -> str:
    manifest = json.loads(
        (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    return manifest["version"]


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


class Report:
    def __init__(self) -> None:
        self.failures = 0

    def line(self, status: str, label: str, detail: str = "") -> None:
        if status == "FAIL":
            self.failures += 1
        print(f"  [{status:>4}] {label}{f' — {detail}' if detail else ''}")


def doctor(args: argparse.Namespace) -> int:
    report = Report()
    print(f"monolithic-dev-harness {version()} ({PLUGIN_ROOT})")

    print("Tools")
    py = sys.version_info
    report.line(
        "ok" if py >= (3, 12) else "FAIL",
        "python",
        f"{py.major}.{py.minor} at {sys.executable} (3.12+ required)",
    )
    for tool, why in (
        ("git", "needed only for versioned delivery"),
        ("npx", "runs the Azure DevOps MCP server"),
    ):
        found = shutil.which(tool)
        report.line(
            "ok" if found else "warn",
            tool,
            found or f"not found; {why}",
        )

    print("Hosts")
    if shutil.which("claude"):
        listed = _run(["claude", "plugin", "list", "--json"])
        installed = bool(
            listed and listed.returncode == 0 and PLUGIN_ID in listed.stdout
        )
        report.line(
            "ok" if installed else "warn",
            "Claude Code",
            "plugin installed" if installed else "plugin not installed",
        )
    else:
        report.line("skip", "Claude Code", "claude CLI not on PATH")
    cursor_dir = Path(
        os.environ.get(
            "CURSOR_PLUGIN_DIR",
            Path.home() / ".cursor/plugins/local/monolithic-dev-harness",
        )
    )
    report.line(
        "ok" if (cursor_dir / ".cursor-plugin" / "plugin.json").is_file() else "skip",
        "Cursor",
        str(cursor_dir) if cursor_dir.exists() else "plugin not installed",
    )
    match shutil.which("codex"):
        case None:
            report.line("skip", "Codex", "codex CLI not on PATH")
        case _:
            codex_plugins = _run(["codex", "plugin", "list", "--json"])
            codex_installed = bool(
                codex_plugins
                and codex_plugins.returncode == 0
                and PLUGIN_ID in codex_plugins.stdout
            )
            report.line(
                "ok" if codex_installed else "warn",
                "Codex",
                "plugin installed" if codex_installed else "plugin not installed",
            )

    print("Repository")
    repo = gitstate.repo_root(Path(args.repo)) or Path(args.repo).resolve()
    if not settings.governed(repo):
        report.line("skip", str(repo), "not opted in (run `harness bootstrap`)")
    else:
        _repository(report, repo, args)

    print("healthy" if report.failures == 0 else f"{report.failures} problem(s) found")
    return 0 if report.failures == 0 else 1


def _repository(report: Report, repo: Path, args: argparse.Namespace) -> None:
    loaded = settings.load(repo)
    report.line(
        "ok" if bmad.ready(repo) else "warn",
        "bmad",
        "set up (_bmad/config.toml)"
        if bmad.ready(repo)
        else "not set up; run `harness bootstrap` again to prepare it",
    )
    if state.harness_mode(repo) == "suspended":
        report.line(
            "warn",
            "harness checks",
            "suspended (type `harness resume` in the chat to restore them)",
        )
    report.line(
        "ok" if isinstance(loaded, Ok) else "FAIL",
        "settings",
        settings.describe(loaded),
    )
    selected = registry.selected(repo, loaded)
    match selected:
        case Ok(active):
            report.line(
                "ok", "tracker", f"{active.manifest.label} ({active.manifest.source})"
            )
            if active.manifest.name == "local":
                storage = local_tracker.describe(repo, active.manifest)
                report.line(
                    "ok" if storage["ready"] else "FAIL",
                    "local tracker folders",
                    str(storage["path"]),
                )
        case Err(failure):
            report.line("FAIL", "tracker", failure.message)
    for problem in registry.problems(repo):
        report.line("warn", "tracker folder", problem.message)
    report.line("ok", "tracking", state.tracking_mode(repo))
    if gitstate.repo_root(repo) is not None:
        report.line("ok", "session", sessions.describe(sessions.resolve(repo)))
    else:
        report.line("skip", "session", "version control is not in use")
    if args.tools and isinstance(selected, Ok):
        report.line(*_tools(repo, selected.value))


def _tools(repo: Path, active: registry.Active) -> tuple[str, str, str]:
    """Check tracker MCP tools, except Azure's private provider transport."""
    match active.manifest.name, active.manifest.connection.get("kind"):
        case "azure-devops", _:
            return (
                "skip",
                "tracker tools",
                "Azure provider tools are private to workflow-integrations; verify through that gateway",
            )
        case _, kind if kind != "mcp":
            return ("skip", "tracker tools", "the tracker has no server")
        case _:
            command, args = registry.connection_command(
                active.manifest, active.values, repo
            )
            listed = transport.list_tools(transport.process_exchange(command, args, 60))
            match fmap(
                listed,
                lambda tools: (
                    set(active.manifest.tools.values())
                    - {str(tool.get("name")) for tool in tools}
                ),
            ):
                case Ok(missing) if missing:
                    return (
                        "FAIL",
                        "tracker tools",
                        f"the server does not offer {sorted(missing)}",
                    )
                case Ok(_):
                    return (
                        "ok",
                        "tracker tools",
                        "the server offers every tool the manifest names",
                    )
                case Err(failure):
                    return ("FAIL", "tracker tools", failure.message)


def bootstrap(extra: list[str]) -> int:
    args = list(extra)
    if "--repo" not in args:
        repo = gitstate.repo_root(Path.cwd()) or Path.cwd().resolve()
        args += ["--repo", str(repo)]
    script = PLUGIN_ROOT / "scripts" / "harness" / "bootstrap.py"
    return subprocess.call([sys.executable, str(script), *args])


def _print(result: Result[str]) -> int:
    match result:
        case Ok(text):
            print(text)
            return 0
        case Err(failure):
            print(failure.message, file=sys.stderr)
            return 2


def _repo(value: str) -> Path:
    return gitstate.repo_root(Path(value)) or Path(value).resolve()


def session_command(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    match args.operation:
        case "status":
            return _print(Ok(sessions.describe(sessions.resolve(repo))))
        case "start":
            return _print(
                fmap(
                    bind(
                        _startable(
                            repo,
                            args.work_item or "",
                            args.workflow,
                            args.base_ref or "",
                        ),
                        lambda context: sessions.start(
                            repo,
                            context.work_item,
                            args.workflow,
                            expected_base_ref=context.base_ref,
                            expected_base_commit=context.base_commit,
                            readiness_state=context.state,
                            readiness_artifacts=context.artifacts,
                        ),
                    ),
                    _started,
                )
            )
        case operation:
            return _print(
                fmap(
                    sessions.transition(repo, operation),
                    lambda session: f"{session.id}: {session.phase.value}",
                )
            )


def work_session_command(args: argparse.Namespace) -> int:
    project = Path(args.repo).resolve()
    match args.operation:
        case "start":
            result = fmap(
                work_sessions.start(project, args.request or ""), work_sessions.as_json
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
        case "pause" | "stop" | "resume" | "complete":
            result = fmap(
                work_sessions.transition(
                    project, args.session_id or "", args.operation
                ),
                work_sessions.as_json,
            )
        case _:
            return 2
    return _print(
        fmap(result, lambda value: json.dumps(value, ensure_ascii=False, indent=2))
    )


def _started(session: sessions.Session) -> str:
    return (
        f"{session.id}: {session.work_item} bound to {session.checkout.branch} (active)"
    )


@dataclass(frozen=True)
class _SessionStart:
    work_item: str
    state: str
    artifacts: tuple[str, ...]
    base_ref: str
    base_commit: str


def _startable(
    repo: Path, work_item: str, workflow: str, base_ref: str
) -> Result[_SessionStart]:
    """The work item, once the branch carries its key and the tracker knows it."""
    loaded = settings.load(repo)
    return bind(
        loaded,
        lambda chosen: bind(
            registry.selected(repo, loaded),
            lambda active: bind(
                sessions.checkout(repo),
                lambda checkout: bind(
                    branches.work_item_id(
                        chosen.branch_template,
                        active.manifest.ids.branch_key,
                        checkout.branch,
                    ),
                    lambda branch_id: bind(
                        _matching(repo, loaded, work_item, branch_id),
                        lambda found: bind(
                            _feature_base(repo, workflow, base_ref),
                            lambda base: fmap(
                                found[1].list_artifacts(found[0].id),
                                lambda artifacts: _SessionStart(
                                    found[0].key,
                                    found[0].state.value,
                                    tuple(str(artifact.kind) for artifact in artifacts),
                                    base[0],
                                    base[1],
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _matching(
    repo: Path, loaded: Result[settings.Settings], work_item: str, branch_id: str
) -> Result[tuple[WorkItem, TrackerOps]]:
    match work_item.strip().upper() == branch_id.upper():
        case False:
            return Err(
                _failure(
                    f"this branch is for {branch_id}, not {work_item}; check out the work item's branch first"
                )
            )
        case True:
            return bind(
                registry.open_selected(repo, loaded),
                lambda ops: fmap(
                    ops.get_work_item(branch_id), lambda item: (item, ops)
                ),
            )


def _feature_base(repo: Path, workflow: str, base_ref: str) -> Result[tuple[str, str]]:
    required = workflow == "feature-implementation"
    return bind(
        require(
            not required or bool(base_ref.strip()),
            "invalid_request",
            "feature-implementation sessions require --base-ref naming the Feature branch",
        ),
        lambda _: (
            Ok(("", ""))
            if not base_ref.strip()
            else bind(
                attempt(
                    lambda: gitstate.git(
                        repo, "rev-parse", "--verify", base_ref.strip()
                    ),
                    "invalid_request",
                    f"cannot resolve Feature branch {base_ref!r}",
                    gitstate.GitError,
                ),
                lambda commit: bind(
                    attempt(
                        lambda: gitstate.git(
                            repo, "merge-base", "--is-ancestor", commit, "HEAD"
                        ),
                        "invalid_request",
                        f"this Story branch was not cut from Feature branch {base_ref!r}",
                        gitstate.GitError,
                    ),
                    lambda _: Ok((base_ref.strip(), commit)),
                ),
            )
        ),
    )


def _failure(message: str) -> Failure:
    return Failure("invalid_request", message)


def tracker_command(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    match args.operation:
        case "list":
            usable = "\n".join(
                f"{manifest.name} ({manifest.source}): {manifest.label}"
                for manifest in registry.usable(repo)
            )
            broken = "\n".join(
                f"not usable: {problem.message}" for problem in registry.problems(repo)
            )
            return _print(Ok("\n".join(part for part in (usable, broken) if part)))
        case "show":
            return _print(onboarding.show(repo, args.target or ""))
        case "stage":
            return _print(
                bind(
                    onboarding.stage(
                        repo, Path(args.target or ""), dict(_pairs(args.value))
                    ),
                    lambda folder: onboarding.show(repo, folder.name),
                )
            )
        case "preflight":
            return _tracker_preflight(repo)
    return 2


def _tracker_preflight(repo: Path) -> int:
    def checked(active: registry.Active) -> Result[readiness.Readiness]:
        match active.manifest.connection.get("kind"):
            case "mcp":
                command, arguments = registry.connection_command(
                    active.manifest, active.values, repo
                )
                return readiness.check(
                    active,
                    transport.mcp(
                        command,
                        arguments,
                        float(active.manifest.connection.get("timeout", 30)),
                    ),
                )
            case _:
                return readiness.check(active, transport.unavailable("no server"))

    match bind(registry.selected(repo, settings.load(repo)), checked):
        case Ok(result):
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
            return 0 if result.ready else 1
        case Err(failure):
            print(failure.message, file=sys.stderr)
            return 2


def adoption_command(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    match args.operation:
        case "assess":
            result = _adoption_assessment(repo, args.target or "", args.base_ref or "")
        case "plan":
            result = adoption.create_plan(
                repo,
                args.target or "",
                args.branch or "",
                Path(args.destination or ""),
            )
        case "status":
            result = adoption.status(repo, args.target or "")
        case "materialize":
            result = adoption.materialize(repo, args.target or "")
        case _:
            return 2
    return _print(
        fmap(result, lambda value: json.dumps(value, indent=2, sort_keys=True))
    )


def _adoption_assessment(
    repo: Path, work_item: str, base_ref: str
) -> Result[dict[str, object]]:
    loaded = settings.load(repo)
    return bind(
        registry.open_selected(repo, loaded),
        lambda ops: bind(
            ops.get_work_item(work_item),
            lambda item: bind(
                ops.list_children(item.id),
                lambda children: bind(
                    ops.list_artifacts(item.id),
                    lambda artifacts: adoption.assess(
                        repo, item, children, artifacts, base_ref
                    ),
                ),
            ),
        ),
    )


def _pairs(values: list[str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(
        (key.strip(), value.strip())
        for key, _, value in (item.partition("=") for item in values or ())
    )


def preference_command(args: argparse.Namespace) -> int:
    match args.operation:
        case "show":
            return _print(fmap(preferences.language(), lambda value: value or "unset"))
        case "language":
            return _print(
                fmap(
                    preferences.set_language(
                        args.value or "",
                        Path(args.repo).resolve() if args.repo else None,
                    ),
                    lambda _: f"preferred language: {args.value}",
                )
            )
        case _:
            return 2


def suspension_command(args: argparse.Namespace) -> int:
    """Status and resume only: suspending is recorded from the user's own prompt."""
    if not Path(args.repo).is_dir():
        print(f"{args.repo} is not a directory", file=sys.stderr)
        return 2
    repo = _repo(args.repo)
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
    return _print(
        fmap(changed, lambda _: json.dumps({"mode": state.harness_mode(repo)}))
    )


def decision_command(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    match args.operation:
        case "status":
            print(decisions.status(repo, args.session_id))
            return 0
        case "present":
            key = "HD-" + secrets.token_hex(8)
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
            return _print(
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
    return _print(
        bind(
            result,
            lambda current: fmap(
                workflow.save(repo, current, session_id),
                lambda _: json.dumps(asdict(current), indent=2, sort_keys=True),
            ),
        )
    )


def _workflow_point(repo: Path, args: argparse.Namespace) -> Result[workflow.Workflow]:
    if decisions.waiting(repo, args.session_id):
        return Err(
            Failure(
                "decision_pending",
                "wait for the human's answer before advancing the workflow",
            )
        )
    return bind(
        workflow.load(repo, args.session_id),
        lambda current: bind(
            _workflow_artifacts(repo, args.artifact),
            lambda artifacts: workflow.add_point(
                current,
                args.label or "",
                args.stage or "",
                artifacts,
                _pairs(args.decision),
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

    return bind(workflow.load(repo, session_id), checked)


def _workflow_start(
    repo: Path, request: str, session_id: str | None = None
) -> Result[workflow.Workflow]:
    def begin(_: object) -> Result[workflow.Workflow]:
        return bind(
            preferences.language(),
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
    repo = _repo(args.repo)
    if decisions.waiting(repo, args.session_id) and args.operation not in (
        "status",
        "list",
        "pause",
        "cancel",
        "back",
        "routes",
        "prepare",
    ):
        return _print(
            Err(
                Failure(
                    "decision_pending",
                    "wait for the human's answer before advancing the workflow",
                )
            )
        )
    match args.operation:
        case "routes":
            try:
                print(json.dumps(prepared_workflows.routes(), indent=2, sort_keys=True))
                return 0
            except prepared_workflows.PreparedWorkflowError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        case "prepare":
            try:
                package = prepared_workflows.prepare_stage(
                    repo,
                    args.route or "",
                    args.prepared_stage or "",
                    original_request=args.request or "",
                )
            except prepared_workflows.PreparedWorkflowError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            print(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        case "status":
            return _print(
                fmap(
                    workflow.load(repo, args.session_id),
                    lambda current: json.dumps(
                        asdict(current), indent=2, sort_keys=True
                    ),
                )
            )
        case "list":
            return _print(
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


def knowledge_command(args: argparse.Namespace) -> int:
    try:
        result = {
            "init": lambda: knowledge.initialize(Path(args.repo), args.store),
            "refresh": lambda: knowledge.refresh(Path(args.repo), args.store),
            "catalog": lambda: knowledge.catalog(Path(args.repo), args.store),
            "find": lambda: knowledge.find(
                Path(args.repo),
                tuple(value for value in (args.address, *args.terms) if value),
                args.store,
            ),
            "resolve": lambda: knowledge.resolve(
                Path(args.repo), args.address, args.store
            ),
            "fetch": lambda: knowledge.fetch(Path(args.repo), args.address, args.store),
            "status": lambda: knowledge.status(Path(args.repo), args.store),
        }[args.operation]()
    except knowledge.KnowledgeError as exc:
        print(json.dumps({"outcome": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="harness",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the installed version")
    doc = sub.add_parser(
        "doctor", help="check tools, configuration, hosts, and the current repository"
    )
    doc.add_argument("--repo", default=".")
    doc.add_argument(
        "--tools",
        action="store_true",
        help="also start the tracker's server and check it offers the manifest's tools",
    )
    sub.add_parser(
        "bootstrap",
        help="opt a repository in (arguments pass through to bootstrap.py)",
        add_help=False,
    )
    session_parser = sub.add_parser(
        "session", help="bind a work item to this checkout, or change its session"
    )
    session_parser.add_argument(
        "operation", choices=("start", "status", "pause", "resume", "close")
    )
    session_parser.add_argument("work_item", nargs="?")
    session_parser.add_argument("--workflow", default="implement-story")
    session_parser.add_argument(
        "--base-ref",
        help="required for feature-implementation: Feature branch this Story branch descends from",
    )
    session_parser.add_argument("--repo", default=".")
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
    preference_parser = sub.add_parser(
        "preference", help="show or set user-level preferences"
    )
    preference_parser.add_argument("operation", choices=("show", "language"))
    preference_parser.add_argument("value", nargs="?")
    preference_parser.add_argument("--repo")
    tracker_parser = sub.add_parser(
        "tracker", help="list or inspect trackers, check readiness, or stage a new one"
    )
    tracker_parser.add_argument(
        "operation", choices=("list", "show", "stage", "preflight")
    )
    tracker_parser.add_argument(
        "target", nargs="?", help="a tracker name (show) or folder (stage)"
    )
    tracker_parser.add_argument("--repo", default=".")
    tracker_parser.add_argument(
        "--value",
        action="append",
        metavar="KEY=VALUE",
        help="a value the tracker's settings need (stage only); repeat for each",
    )
    adoption_parser = sub.add_parser(
        "adoption",
        help="assess, approve, and materialize implementation already in progress",
    )
    adoption_parser.add_argument(
        "operation", choices=("assess", "plan", "status", "materialize")
    )
    adoption_parser.add_argument(
        "target",
        help="work-item reference for assess; adoption id for other operations",
    )
    adoption_parser.add_argument(
        "--base-ref", help="intended base branch or ref (assess)"
    )
    adoption_parser.add_argument("--branch", help="new Story branch (plan)")
    adoption_parser.add_argument(
        "--destination", help="new recovery worktree path (plan)"
    )
    adoption_parser.add_argument("--repo", default=".")
    suspension_parser = sub.add_parser(
        "suspension",
        help="show or end a suspension of the harness checks (type `harness suspend` to start one)",
    )
    suspension_parser.add_argument("operation", choices=("status", "resume"))
    suspension_parser.add_argument("--repo", default=".")
    knowledge_parser = sub.add_parser(
        "knowledge", help="query or refresh a harness-owned immutable knowledge store"
    )
    knowledge_parser.add_argument(
        "operation",
        choices=("init", "refresh", "catalog", "find", "resolve", "fetch", "status"),
    )
    knowledge_parser.add_argument("address", nargs="?")
    knowledge_parser.add_argument("terms", nargs="*")
    knowledge_parser.add_argument("--repo", default=".")
    knowledge_parser.add_argument("--store", default="project")
    args, extra = parser.parse_known_args(argv)
    if args.command == "version":
        print(version())
        return 0
    if args.command == "doctor":
        return doctor(args)
    if args.command == "knowledge":
        return knowledge_command(args)
    if args.command == "session":
        return session_command(args)
    if args.command == "work-session":
        return work_session_command(args)
    if args.command == "workflow":
        return workflow_command(args)
    if args.command == "preference":
        return preference_command(args)
    if args.command == "decision":
        return decision_command(args)
    if args.command == "tracker":
        return tracker_command(args)
    if args.command == "adoption":
        return adoption_command(args)
    if args.command == "suspension":
        return suspension_command(args)
    return bootstrap(extra)


if __name__ == "__main__":
    raise SystemExit(main())
