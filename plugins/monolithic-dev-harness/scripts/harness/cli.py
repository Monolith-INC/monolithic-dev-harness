#!/usr/bin/env python3
"""`harness` command: version, checks, bootstrap, sessions, and onboarded trackers.

harness version
harness doctor [--repo <dir>] [--tools]
harness bootstrap --repo <dir> [--inspect | --propose | --apply-digest <hash>]
harness session start <work item> [--workflow <name>] | status | pause | resume | close
harness work-session route --request <text> | start --request <text> | list | select <id> | pause|stop|resume|complete <id>
                    | track [<id>] --work-item <key> | link [<id>] --work-item <key>
harness workflow start | render | checkpoint | list | status | requirements | routes | prepare | back | pause | resume | cancel | complete --session-id <id>
harness preference show | language <en|pt-br>
harness tracker list | show <name> | stage <folder> [--value KEY=VALUE ...] | tree
harness adoption assess | plan | status | materialize ...
harness knowledge <operation> ...
"""

from __future__ import annotations

import argparse
import json
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
    cli_workflow,  # noqa: E402
    documents,
    gitstate,
    knowledge,
    local_tracker,
    preferences,
    process_cli,
    project_paths,
    sessions,
    settings,
    state,
    tracker_tree,
)
from harness.cli_common import pairs, print_result, resolve_repo  # noqa: E402
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


def _installation_host(report: Report, host: str, result: Result[bool]) -> str:
    match result:
        case Ok(True):
            report.line(
                "ok",
                host,
                "user registration/configuration verified; runtime activation requires host trust and reload",
            )
        case Ok(False):
            report.line(
                "skip",
                host,
                "no user registration; project installations are covered by the inventory",
            )
        case Err(failure):
            report.line("FAIL", host, failure.message)
    return host


def doctor(args: argparse.Namespace) -> int:
    match getattr(args, "runtime_status", False):
        case True:
            print(
                json.dumps(
                    runtime_status(project_paths.root(Path(args.repo))), indent=2
                )
            )
            return 0
        case False:
            pass
    match (
        getattr(args, "installations", False),
        getattr(args, "json", False),
        getattr(args, "repair_id", ()),
        getattr(args, "apply_repairs", None),
    ):
        case False, False, [], None:
            pass
        case False, False, (), None:
            pass
        case _:
            from harness.installation_doctor import run

            return run(args)
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
    from harness.installation_scope import _context
    from host_adapters.installation_contract import adapter_for
    from host_adapters.subagents import ADAPTERS

    tuple(
        _installation_host(
            report,
            host,
            bind(adapter_for(host), lambda adapter: adapter.verify_user(_context(()))),
        )
        for host in ADAPTERS
    )

    from harness.installation_inventory import findings, scan

    installation_inventory = scan(_context((project_paths.root(Path(args.repo)),)))
    installation_findings = findings(installation_inventory)
    report.line(
        "FAIL" if installation_inventory.errors or installation_findings else "ok",
        "installation inventory",
        f"{len(installation_inventory.components)} components, {len(installation_findings)} findings, {len(installation_inventory.errors)} uninspected locations; use harness doctor --installations for details and repairs",
    )

    print("Repository")
    repo = project_paths.root(Path(args.repo))
    if not settings.governed(repo):
        report.line("skip", str(repo), "not opted in (run `harness bootstrap`)")
    else:
        _repository(report, repo, args)

    print(
        "healthy (installation and repository configuration; live question capture not checked)"
        if report.failures == 0
        else f"{report.failures} problem(s) found"
    )
    return 0 if report.failures == 0 else 1


def runtime_status(repo: Path) -> dict:
    from harness import onboarding, work_sessions

    return {
        "scope": "configuration_and_local_state_only",
        "configuration": settings.describe(settings.load(repo)),
        "gateway_reachability": "unverified; use the existing gateway for a bounded read",
        "native_question_capture": "unverified; requires an actual matched human reply",
        "checks": state.harness_mode(repo),
        "work_mode": onboarding.mode(repo),
        "tracking": state.tracking_mode(repo),
        "sessions": [
            work_sessions.as_json(session)
            for result in (work_sessions.list_sessions(repo),)
            if isinstance(result, Ok)
            for session in result.value
        ],
    }


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
    if settings.git_delivery(repo):
        report.line("ok", "session", sessions.describe(sessions.resolve(repo)))
    else:
        report.line("skip", "session", "Git-based delivery is not selected")
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
        repo = project_paths.root(Path.cwd())
        args += ["--repo", str(repo)]
    script = PLUGIN_ROOT / "scripts" / "harness" / "bootstrap.py"
    return subprocess.call([sys.executable, str(script), *args])


def session_command(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    match args.operation:
        case "status":
            return print_result(Ok(sessions.describe(sessions.resolve(repo))))
        case "start":
            return print_result(
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
            return print_result(
                fmap(
                    sessions.transition(repo, operation),
                    lambda session: f"{session.id}: {session.phase.value}",
                )
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
    repo = resolve_repo(args.repo)
    match args.operation:
        case "list":
            usable = "\n".join(
                f"{manifest.name} ({manifest.source}): {manifest.label}"
                for manifest in registry.usable(repo)
            )
            broken = "\n".join(
                f"not usable: {problem.message}" for problem in registry.problems(repo)
            )
            return print_result(
                Ok("\n".join(part for part in (usable, broken) if part))
            )
        case "show":
            return print_result(onboarding.show(repo, args.target or ""))
        case "stage":
            return print_result(
                bind(
                    onboarding.stage(
                        repo, Path(args.target or ""), dict(pairs(args.value))
                    ),
                    lambda folder: onboarding.show(repo, folder.name),
                )
            )
        case "preflight":
            return _tracker_preflight(repo)
        case "tree":
            return print_result(
                bind(
                    registry.selected(repo, settings.load(repo)),
                    lambda active: tracker_tree.render(repo, active.manifest),
                )
            )
    return 2


def _tracker_preflight(repo: Path) -> int:
    from integrations import gateway_client

    def checked(active: registry.Active) -> Result[dict]:
        match active.manifest.connection.get("kind"):
            case "mcp":
                return gateway_client.call(repo, "tracker_preflight", {})
            case _:
                return fmap(
                    readiness.check(active, transport.unavailable("no server")), asdict
                )

    match bind(registry.selected(repo, settings.load(repo)), checked):
        case Ok(result):
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["ready"] else 1
        case Err(failure):
            print(failure.message, file=sys.stderr)
            return 2


def adoption_command(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
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
    return print_result(
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


def preference_command(args: argparse.Namespace) -> int:
    match args.operation:
        case "show":
            return print_result(
                fmap(preferences.language(), lambda value: value or "unset")
            )
        case "language":
            return print_result(
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


def parser() -> argparse.ArgumentParser:
    """Every `harness` command and its arguments."""
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
        "--runtime-status",
        action="store_true",
        help="report separate local modes and unverified runtime dimensions without starting any provider",
    )
    doc.add_argument(
        "--installations",
        action="store_true",
        help="inventory all supported hosts and show explicit repair selections",
    )
    doc.add_argument(
        "--json", action="store_true", help="machine-readable installation inventory"
    )
    doc.add_argument("--scope", choices=("user", "local", "all"), default="all")
    doc.add_argument("--project", action="append", default=[])
    doc.add_argument(
        "--repair-id",
        action="append",
        default=[],
        help="select an individual repair from the current inventory",
    )
    doc.add_argument(
        "--apply-repairs",
        help="apply selected repairs only when this selection digest matches",
    )
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
    preference_parser = sub.add_parser(
        "preference", help="show or set user-level preferences"
    )
    preference_parser.add_argument("operation", choices=("show", "language"))
    preference_parser.add_argument("value", nargs="?")
    preference_parser.add_argument("--repo")
    documents.add_parser(sub)
    process_cli.add_parser(sub)
    tracker_parser = sub.add_parser(
        "tracker",
        help="list or inspect trackers, check readiness, stage a new one, or print the work-item tree",
    )
    tracker_parser.add_argument(
        "operation", choices=("list", "show", "stage", "preflight", "tree")
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
    cli_workflow.add_parsers(sub)
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
    return parser


def main(argv: list[str] | None = None) -> int:
    command_line = parser()
    args, extra = command_line.parse_known_args(argv)
    match args.command, extra:
        case "workflow" | "process" as family, [*unknown] if unknown:
            command_line.error(
                "unrecognized " + family + " arguments: " + " ".join(unknown)
            )
        case _:
            pass
    if args.command in cli_workflow.COMMANDS:
        return cli_workflow.run(args)
    match args.command:
        case "process":
            return process_cli.run(args)
        case _:
            pass
    if args.command == "version":
        print(version())
        return 0
    if args.command == "doctor":
        return doctor(args)
    if args.command == "knowledge":
        return knowledge_command(args)
    if args.command == "session":
        return session_command(args)
    if args.command == "preference":
        return preference_command(args)
    if args.command == "tracker":
        return tracker_command(args)
    if args.command == "document":
        return documents.command(args)
    if args.command == "adoption":
        return adoption_command(args)
    return bootstrap(extra)


if __name__ == "__main__":
    raise SystemExit(main())
