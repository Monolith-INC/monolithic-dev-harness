#!/usr/bin/env python3
"""Opt a repository into the harness.

    bootstrap.py --repo <dir> --settings-from <settings.json>

Writes, once:
  .harness/settings.json   the repository's only settings file, copied from --settings-from after
                           it is checked; an existing one is never replaced (people own it)
  .git/info/exclude        ignores .harness/state/ in this clone only (the shared .gitignore is
                           never edited)
  .harness/knowledge/      the harness knowledge store, seeded with a pointer to the settings

Then checks that the selected tracker exists and has the values it needs. Review configuration
(.harness/review/sources.json) is interactive: run the `review-setup` skill afterwards. Hooks and
MCP servers come from the plugin itself; nothing is wired into the repository's host settings.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from core.result import Err, Ok, Result, attempt, bind, fmap  # noqa: E402
from harness import settings  # noqa: E402
from integrations import registry  # noqa: E402


def _ensure_local_exclude(repo: Path) -> bool:
    """Ignore `.harness/state/` in this clone only: git's own exclude file, not the tracked `.gitignore`."""
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "info/exclude"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return False
    path = Path(result.stdout.strip())
    path = path if path.is_absolute() else repo / path
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if ".harness/state/" in lines:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([*lines, ".harness/state/"]) + "\n", encoding="utf-8")
    return True


def _candidate(source: Path) -> Result[settings.Settings]:
    return bind(
        attempt(
            lambda: json.loads(source.read_text(encoding="utf-8")),
            "invalid_settings",
            f"{source} could not be read",
            OSError,
            ValueError,
        ),
        settings.parse,
    )


def _usable(repo: Path, chosen: settings.Settings) -> Result[registry.Active]:
    """The tracker a settings value selects, checked before the file lands in the repository."""
    return registry.selected(repo, Ok(chosen))


def _install(repo: Path, source: Path) -> Result[str]:
    """Copy the settings in once, only after they and their tracker check out."""
    target = settings.path(repo)
    if target.exists():
        return bind(
            settings.load(repo),
            lambda chosen: fmap(
                _usable(repo, chosen),
                lambda _: (
                    f"kept existing {settings.SETTINGS_RELATIVE_PATH} (people own it)"
                ),
            ),
        )
    return bind(
        bind(_candidate(source), lambda chosen: _usable(repo, chosen)),
        lambda _: fmap(
            attempt(
                lambda: (
                    target.parent.mkdir(parents=True, exist_ok=True)
                    or shutil.copyfile(source, target)
                ),
                "unwritable",
                str(target),
                OSError,
            ),
            lambda _: f"wrote {settings.SETTINGS_RELATIVE_PATH}",
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument(
        "--settings-from",
        required=True,
        help="a settings file to start from (see examples/settings.example.json)",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"{repo} is not a git repository root", file=sys.stderr)
        return 2
    # State stays out of git before anything can write it: the settings opt the repository in.
    if _ensure_local_exclude(repo):
        print("ignored .harness/state/ in .git/info/exclude (this clone only)")
    match _install(repo, Path(args.settings_from)):
        case Err(failure):
            print(
                f"settings or their tracker cannot be used: {failure.message}",
                file=sys.stderr,
            )
            return 2
        case Ok(note):
            print(note)
    active = registry.selected(repo, settings.load(repo)).value
    print(f"tracker: {active.manifest.label} ({active.manifest.source})")
    from harness.knowledge import initialize as initialize_knowledge

    knowledge_result = initialize_knowledge(repo)
    print(
        f"knowledge {knowledge_result['outcome']}: {knowledge_result.get('revision', '')}"
    )
    print(
        json.dumps(
            {"next": ["run the review-setup skill", "restart the agent session"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
