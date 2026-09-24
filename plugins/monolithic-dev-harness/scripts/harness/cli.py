#!/usr/bin/env python3
"""`harness` command: version, environment checks, and repository bootstrap.

harness version
harness doctor [--repo <dir>] [--azure --project <project>]
harness bootstrap [--repo <dir>] [--policy-from <file>] [...]   (defaults: current repo, example policy)
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

from harness import gitstate, knowledge  # noqa: E402
from harness.config import POLICY_RELATIVE_PATH  # noqa: E402

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

    print("Configuration")
    org = os.environ.get("AZURE_DEVOPS_ORG", "")
    report.line(
        "ok" if org else "warn",
        "AZURE_DEVOPS_ORG",
        org or "not set in this shell; the MCP server needs it",
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
    else:
        governed = (repo / POLICY_RELATIVE_PATH).is_file()
        report.line(
            "ok" if governed else "skip",
            str(repo),
            "governed" if governed else "not opted in (run `harness bootstrap`)",
        )

    if args.azure:
        print("Azure DevOps")
        if not args.project:
            report.line("FAIL", "health check", "--project is required with --azure")
        else:
            check = (
                PLUGIN_ROOT / "skills" / "azure-devops" / "scripts" / "health-check.mjs"
            )
            result = _run(["node", str(check), "--project", args.project], timeout=100)
            ok = bool(result and result.returncode == 0)
            detail = (
                (result.stdout or result.stderr).strip() if result else "node not found"
            )
            report.line("ok" if ok else "FAIL", "health check", detail)

    print("healthy" if report.failures == 0 else f"{report.failures} problem(s) found")
    return 0 if report.failures == 0 else 1


def bootstrap(extra: list[str]) -> int:
    args = list(extra)
    if "--repo" not in args:
        repo = gitstate.repo_root(Path.cwd())
        if repo is None:
            print("not inside a git repository; pass --repo <dir>", file=sys.stderr)
            return 2
        args += ["--repo", str(repo)]
    if "--policy-from" not in args:
        args += ["--policy-from", str(PLUGIN_ROOT / "examples" / "policy.example.json")]
    script = PLUGIN_ROOT / "scripts" / "harness" / "bootstrap.py"
    return subprocess.call([sys.executable, str(script), *args])


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
        "--azure",
        action="store_true",
        help="also run the Azure DevOps health check (opens OAuth)",
    )
    doc.add_argument("--project", help="Azure DevOps project for --azure")
    sub.add_parser(
        "bootstrap",
        help="opt a repository in (arguments pass through to bootstrap.py)",
        add_help=False,
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
    return bootstrap(extra)


if __name__ == "__main__":
    raise SystemExit(main())
