#!/usr/bin/env python3
"""`harness` command: version, checks, bootstrap, sessions, and onboarded trackers.

harness version
harness doctor [--repo <dir>] [--tools] [--azure]
harness bootstrap [--repo <dir>] [--settings-from <file>]   (defaults: current repo, example settings)
harness session start <work item> [--workflow <name>] | status | pause | resume | close
harness tracker list | show <name> | stage <folder> [--value KEY=VALUE ...]
harness knowledge <operation> ...
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from core.result import Err, Failure, Ok, Result, bind, fmap  # noqa: E402
from harness import gitstate, knowledge, sessions, settings, state  # noqa: E402
from integrations import branches, onboarding, registry, transport  # noqa: E402

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
        "ok" if py >= (3, 10) else "FAIL",
        "python3",
        f"{py.major}.{py.minor} (3.10+ required)",
    )
    for tool, why in (
        ("git", "hooks read git state"),
        ("npx", "runs the Azure DevOps MCP server"),
    ):
        found = shutil.which(tool)
        report.line(
            "ok" if found else ("FAIL" if tool == "git" else "warn"),
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

    print("Repository")
    repo = gitstate.repo_root(Path(args.repo))
    if repo is None:
        report.line("skip", "git repository", f"{args.repo} is not inside one")
    elif not settings.governed(repo):
        report.line("skip", str(repo), "not opted in (run `harness bootstrap`)")
    else:
        _repository(report, repo, args)

    print("healthy" if report.failures == 0 else f"{report.failures} problem(s) found")
    return 0 if report.failures == 0 else 1


def _repository(report: Report, repo: Path, args: argparse.Namespace) -> None:
    loaded = settings.load(repo)
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
        case Err(failure):
            report.line("FAIL", "tracker", failure.message)
    for problem in registry.problems(repo):
        report.line("warn", "tracker folder", problem.message)
    report.line("ok", "tracking", state.tracking_mode(repo))
    report.line("ok", "session", sessions.describe(sessions.resolve(repo)))
    if args.tools and isinstance(selected, Ok):
        report.line(*_tools(repo, selected.value))
    if args.azure and isinstance(selected, Ok):
        report.line(*_azure_health(selected.value))


def _tools(repo: Path, active: registry.Active) -> tuple[str, str, str]:
    """Whether the tracker's server offers every tool its manifest names (starts the server)."""
    if active.manifest.connection.get("kind") != "mcp":
        return ("skip", "tracker tools", "the tracker has no server")
    command, args = registry.connection_command(active.manifest, active.values, repo)
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


def _azure_health(active: registry.Active) -> tuple[str, str, str]:
    if active.manifest.name != "azure-devops":
        return ("skip", "health check", "the selected tracker is not Azure DevOps")
    check = PLUGIN_ROOT / "skills" / "azure-devops" / "scripts" / "health-check.mjs"
    arguments = (
        "--org",
        active.values.get("organization", ""),
        "--project",
        active.values.get("project", ""),
    )
    try:
        result = subprocess.run(
            ["node", str(check), *arguments],
            capture_output=True,
            text=True,
            timeout=100,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ("FAIL", "health check", str(exc))
    return (
        "ok" if result.returncode == 0 else "FAIL",
        "health check",
        (result.stdout or result.stderr).strip(),
    )


def bootstrap(extra: list[str]) -> int:
    args = list(extra)
    if "--repo" not in args:
        repo = gitstate.repo_root(Path.cwd())
        if repo is None:
            print("not inside a git repository; pass --repo <dir>", file=sys.stderr)
            return 2
        args += ["--repo", str(repo)]
    if "--settings-from" not in args:
        args += [
            "--settings-from",
            str(PLUGIN_ROOT / "examples" / "settings.example.json"),
        ]
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
                        _startable(repo, args.work_item or ""),
                        lambda ref: sessions.start(repo, ref, args.workflow),
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


def _started(session: sessions.Session) -> str:
    return (
        f"{session.id}: {session.work_item} bound to {session.checkout.branch} (active)"
    )


def _startable(repo: Path, work_item: str) -> Result[str]:
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
                    lambda branch_id: _matching(repo, loaded, work_item, branch_id),
                ),
            ),
        ),
    )


def _matching(
    repo: Path, loaded: Result[settings.Settings], work_item: str, branch_id: str
) -> Result[str]:
    if work_item.strip().upper() != branch_id.upper():
        return Err(
            _failure(
                f"this branch is for {branch_id}, not {work_item}; check out the work item's branch first"
            )
        )
    return bind(
        registry.open_selected(repo, loaded),
        lambda ops: fmap(ops.get_work_item(branch_id), lambda item: item.key),
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
    return 2


def _pairs(values: list[str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(
        (key.strip(), value.strip())
        for key, _, value in (item.partition("=") for item in values or ())
    )


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
    doc.add_argument(
        "--azure",
        action="store_true",
        help="also run the Azure DevOps health check with the settings' values (opens OAuth)",
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
    session_parser.add_argument("--repo", default=".")
    tracker_parser = sub.add_parser(
        "tracker", help="list trackers, stage a new one, or show one for review"
    )
    tracker_parser.add_argument("operation", choices=("list", "show", "stage"))
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
    if args.command == "tracker":
        return tracker_command(args)
    return bootstrap(extra)


if __name__ == "__main__":
    raise SystemExit(main())
