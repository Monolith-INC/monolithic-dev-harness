#!/usr/bin/env python3
"""Opt a repository into the harness.

    bootstrap.py --repo <dir> --settings-from <settings.json>

Writes, once:
  .harness/settings.json   the repository's only settings file, copied from --settings-from after
                           it is checked; an existing one is never replaced (people own it)
  .git/info/exclude        ignores .harness/state/ and the local tracker's .harness/tracker/ in
                           this clone only (the shared .gitignore is never edited)
  .harness/knowledge/      the harness knowledge store, seeded with a pointer to the settings

Then checks that the selected tracker exists and has the values it needs. Review configuration
(.harness/review/sources.json) is interactive: run the `review-setup` skill afterwards. Bootstrap
adds only the Codex project default needed for option-based questions; hooks and MCP servers come
from the plugin itself.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from core.result import Err, Failure, Ok, Result, attempt, bind, fmap  # noqa: E402
from harness import settings, setup, state  # noqa: E402
from integrations import registry  # noqa: E402


def _ensure_codex_config(repo: Path) -> Result[str]:
    """Add the shared Codex picker default without taking over other project settings."""
    path = repo / ".codex" / "config.toml"
    try:
        original = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = original.splitlines()
        features = re.compile(r"^\s*\[features\]\s*$")
        assignment = re.compile(
            r"^\s*default_mode_request_user_input\s*=\s*(true|false)\s*$"
        )
        in_features = False
        found: str | None = None
        insert_at = len(lines)
        for index, line in enumerate(lines):
            if line.lstrip().startswith("["):
                if in_features:
                    insert_at = index
                    in_features = False
                if features.match(line):
                    in_features = True
            if in_features and (match := assignment.match(line)):
                found = match.group(1)
        match found:
            case "true":
                return Ok(f"kept {path}: request_user_input already enabled")
            case "false":
                return Err(
                    Failure(
                        "codex_config_conflict",
                        f"{path} explicitly disables default_mode_request_user_input",
                    )
                )
            case None:
                addition = (
                    "# Shared harness interaction: allow option-based questions in Codex."
                    "\ndefault_mode_request_user_input = true"
                ).splitlines()
                updated = [*lines[:insert_at], *addition, *lines[insert_at:]]
                if not lines:
                    updated = ["[features]", *addition]
                elif not any(features.match(line) for line in lines):
                    updated = [*lines, "", "[features]", *addition]
                content = "\n".join(updated).rstrip() + "\n"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return Ok(f"wrote {path}: enabled request_user_input")
            case _:
                return Err(
                    Failure(
                        "codex_config_conflict",
                        f"{path} has an unreadable request_user_input setting",
                    )
                )
    except OSError as exc:
        return Err(
            Failure("codex_config_unwritable", f"{path} could not be updated: {exc}")
        )


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
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--settings-from",
        help="legacy one-time import of a reviewed settings file",
    )
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--propose", action="store_true")
    parser.add_argument("--apply-digest")
    parser.add_argument("--source-digest")
    parser.add_argument("--tracker")
    parser.add_argument("--tracker-value", action="append", default=[])
    parser.add_argument("--scm")
    parser.add_argument("--scm-value", action="append", default=[])
    parser.add_argument("--artifacts-path")
    parser.add_argument("--base-branch")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"{repo} is not a git repository root", file=sys.stderr)
        return 2
    choices = {
        "tracker_name": args.tracker or "",
        "tracker_values": dict(
            item.partition("=")[::2] for item in args.tracker_value if "=" in item
        ),
        "scm_name": args.scm or "",
        "scm_values": dict(
            item.partition("=")[::2] for item in args.scm_value if "=" in item
        ),
        "artifacts_path": args.artifacts_path or "",
        "base_branch": args.base_branch or "",
    }
    match args.settings_from, args.propose, args.apply_digest:
        case None, False, None:
            return _report(setup.inspect(repo))
        case None, True, None:
            return _report(setup.review(repo, **choices))
        case None, _, str() as approved:
            return _apply_reviewed(repo, choices, approved, args.source_digest or "")
        case str() as source, False, None:
            return _legacy_install(repo, Path(source))
        case _:
            print("choose one bootstrap operation", file=sys.stderr)
            return 2


def _report(result: Result[dict]) -> int:
    match result:
        case Ok(value):
            print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        case Err(failure):
            print(failure.message, file=sys.stderr)
            return 2


def _apply_reviewed(
    repo: Path, choices: dict, approved: str, source_digest: str
) -> int:
    match setup.review(repo, **choices):
        case Err(failure):
            print(failure.message, file=sys.stderr)
            return 2
        case Ok(review):
            match setup.apply(repo, review["candidate"], approved, source_digest):
                case Err(failure):
                    print(failure.message, file=sys.stderr)
                    return 2
                case Ok(file):
                    print(f"wrote {file}")
                    return _finish(repo)


def _legacy_install(repo: Path, source: Path) -> int:
    # State stays out of git before anything can write it: the settings opt the repository in.
    added = state.ensure_local_exclude(repo)
    if added:
        print(f"ignored {', '.join(added)} in .git/info/exclude (this clone only)")
    committed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--", *state.LOCAL_ONLY_PATHS],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    ).stdout.split()
    if committed:
        print(
            "warning: local-only harness records are committed; stop sharing them with "
            f"`git rm -r --cached --ignore-unmatch {' '.join(state.LOCAL_ONLY_PATHS)}`",
            file=sys.stderr,
        )
    match _install(repo, source):
        case Err(failure):
            print(
                f"settings or their tracker cannot be used: {failure.message}",
                file=sys.stderr,
            )
            return 2
        case Ok(note):
            print(note)
    return _finish(repo)


def _finish(repo: Path) -> int:
    match _ensure_codex_config(repo):
        case Err(failure):
            print(
                f"warning: {failure.message}; typed approvals remain available",
                file=sys.stderr,
            )
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
            {
                "next": [
                    "trust this repository in Codex so .codex/config.toml is loaded",
                    "run the review-setup skill",
                    "restart the agent session",
                ]
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
