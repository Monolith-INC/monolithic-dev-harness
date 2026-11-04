"""Prepare a fresh copy of the test project with a published harness release installed.

This module is for test runs only. Regular harness setup must not depend on it.

    project_fixture.py [--version X.Y.Z-rc.N] [--host claude|codex|...]

It copies `test-project-template/` to the next unused `temp/test-NNN/` in this checkout, starts a
Git repository there, and installs the harness into that copy only, the way a user would: it
downloads the release's own `install.sh` from GitHub and runs it with `--scope local`. Without
`--version` it picks the newest release candidate. For Claude Code it then excludes this
checkout's own instruction files (`AGENTS.md` and the like), which Claude Code would otherwise
load from the copy's parent folders. It prints the copy's path; bootstrapping and
the workflow are left to the trial. Old copies are cleared from `temp/` by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from itertools import count
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
TEMPLATE = REPOSITORY / "test-project-template"
TRIALS = REPOSITORY / "temp"
GITHUB = "Monolith-INC/monolithic-dev-harness"
HOSTS = ("claude", "codex", "cursor", "kimi", "zed")
# Instruction files Claude Code loads from a project's parent folders.
INSTRUCTION_FILES = (
    "CLAUDE.md",
    "CLAUDE.local.md",
    "AGENTS.md",
    ".claude/CLAUDE.md",
    ".claude/AGENTS.md",
    ".claude/rules/**",
)

sys.path.insert(0, str(REPOSITORY / "plugins" / "monolithic-dev-harness" / "scripts"))

from core.result import Err, Ok, Result, err  # noqa: E402


def create_test_project(
    version: str | None = None, hosts: tuple[str, ...] = ("claude", "codex")
) -> Result[Path]:
    """A fresh copy in `temp/` with release `version`, or the newest candidate, installed."""
    match _version(version):
        case Err() as failure:
            return failure
        case Ok(chosen):
            pass
    match _download_installer(chosen):
        case Err() as failure:
            return failure
        case Ok(installer):
            pass
    try:
        project = copy_template()
    except (OSError, subprocess.SubprocessError) as failure:
        return err("copy_failed", f"could not copy the test project: {failure}")
    match install(project, installer, chosen, hosts):
        case Ok() if "claude" in hosts:
            seal_from_harness(project)
            return Ok(project)
        case result:
            return result


def seal_from_harness(project: Path) -> Path:
    """Keep what belongs to the tester, not to a user's project, out of Claude Code in the copy.

    Claude Code reads CLAUDE.md and AGENTS.md from every folder above the project, and the copy
    sits inside this checkout, so the harness's own rules would reach the test agent. It also
    loads the tester's own plugins, whose hooks can block the harness. The copy's local Claude
    settings exclude those files and turn those plugins off, for headless and interactive
    sessions alike.
    """
    settings_path = project / ".claude" / "settings.local.json"
    settings = (
        json.loads(settings_path.read_text(encoding="utf-8"))
        if settings_path.is_file()
        else {}
    )
    excluded = [
        f"{folder}/{name}"
        for folder in (project.parent, REPOSITORY)
        for name in INSTRUCTION_FILES
    ]
    settings["claudeMdExcludes"] = sorted(
        {*settings.get("claudeMdExcludes", []), *excluded}
    )
    settings["enabledPlugins"] = {
        **settings.get("enabledPlugins", {}),
        **{plugin: False for plugin in tester_plugins(project)},
    }
    settings_path.parent.mkdir(exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return settings_path


def tester_plugins(project: Path) -> tuple[str, ...]:
    """The Claude Code plugins enabled in the copy other than the harness itself."""
    try:
        listed = json.loads(
            subprocess.run(
                ["claude", "plugin", "list", "--json"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            ).stdout
        )
    except (OSError, TypeError, ValueError, subprocess.SubprocessError):
        return ()
    return tuple(
        str(plugin["id"])
        for plugin in listed
        if isinstance(plugin, dict)
        and plugin.get("enabled")
        and not str(plugin.get("id", "")).startswith("monolithic-dev-harness@")
    )


def copy_template() -> Path:
    """Copy the template to the next unused `temp/test-NNN` and commit it as the starting point."""
    TRIALS.mkdir(exist_ok=True)
    project = next(
        TRIALS / f"test-{number:03d}"
        for number in count(1)
        if not (TRIALS / f"test-{number:03d}").exists()
    )
    shutil.copytree(TEMPLATE, project)
    for arguments in (
        ("init", "--quiet"),
        ("config", "user.name", "Acceptance Trial"),
        ("config", "user.email", "acceptance-trial@localhost"),
        ("add", "--all"),
        ("commit", "--quiet", "-m", "Starting project"),
    ):
        subprocess.run(["git", *arguments], cwd=project, check=True)
    return project


def install(
    project: Path, installer: Path, version: str, hosts: tuple[str, ...]
) -> Result[Path]:
    """Run the release's installer for the copy only, once per host."""
    log = project.parent / f"{project.name}-install.log"
    with log.open("w", encoding="utf-8") as output:
        for host in hosts:
            completed = subprocess.run(
                [
                    "bash",
                    str(installer),
                    "--scope",
                    "local",
                    "--project",
                    str(project),
                    "--host",
                    host,
                    "--version",
                    version,
                    "--yes",
                ],
                cwd=project,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if completed.returncode != 0:
                return err(
                    "install_failed",
                    f"installing {version} for {host} failed; see {log}",
                )
    return Ok(project)


def latest_candidate(releases: list[dict]) -> str | None:
    """The newest published release candidate in GitHub's newest-first release list."""
    return next(
        (
            str(release["tag_name"]).removeprefix("v")
            for release in releases
            if release.get("prerelease") and not release.get("draft")
        ),
        None,
    )


def _version(version: str | None) -> Result[str]:
    if version:
        return Ok(version.removeprefix("v"))
    try:
        releases = json.loads(_github(f"repos/{GITHUB}/releases?per_page=30"))
    except (OSError, ValueError, subprocess.SubprocessError) as failure:
        return err(
            "release_lookup_failed",
            f"could not list releases ({failure}); pass --version to install one by hand",
        )
    chosen = latest_candidate(releases if isinstance(releases, list) else [])
    return (
        Ok(chosen)
        if chosen
        else err("no_candidate", "no release candidate is published; pass --version")
    )


def _download_installer(version: str) -> Result[Path]:
    """The `install.sh` attached to release `version`, fetched through GitHub's REST API as the
    installer itself fetches release files."""
    target = Path(tempfile.mkdtemp(prefix="mdh-installer-")) / "install.sh"
    try:
        release = json.loads(_github(f"repos/{GITHUB}/releases/tags/v{version}"))
        asset = next(
            (
                item["id"]
                for item in release.get("assets", [])
                if item.get("name") == "install.sh"
            ),
            None,
        )
        match asset:
            case None:
                return err(
                    "installer_download_failed", f"release v{version} has no install.sh"
                )
            case identifier:
                target.write_bytes(
                    _github_bytes(f"repos/{GITHUB}/releases/assets/{identifier}")
                )
    except (OSError, ValueError, subprocess.SubprocessError) as failure:
        return err(
            "installer_download_failed",
            f"could not download install.sh for v{version}: {failure}",
        )
    return Ok(target)


def _github(path: str) -> str:
    return _github_bytes(path, "application/vnd.github+json").decode("utf-8")


def _github_bytes(path: str, accept: str = "application/octet-stream") -> bytes:
    match shutil.which("gh"):
        case None:
            return _fetch(f"https://api.github.com/{path}", accept)
        case gh:
            return subprocess.run(
                [gh, "api", "-H", f"Accept: {accept}", path],
                check=True,
                capture_output=True,
            ).stdout


def _fetch(url: str, accept: str) -> bytes:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": accept} | (
        {"Authorization": f"Bearer {token}"} if token else {}
    )
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=headers)
    ) as response:
        return response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--version", help="release to install (default: the newest release candidate)"
    )
    parser.add_argument(
        "--host",
        action="append",
        choices=HOSTS,
        help="host to install for; repeat for several (default: claude and codex)",
    )
    args = parser.parse_args(argv)
    match create_test_project(args.version, tuple(args.host or ("claude", "codex"))):
        case Ok(project):
            print(project)
            return 0
        case Err(failure):
            print(json.dumps(failure.to_dict(), ensure_ascii=False), file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
