#!/usr/bin/env python3
"""Create and remove disposable copies of the acceptance-test project."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

MARKER_NAME = ".monolithic-dev-harness-trial.json"
ROOT_PREFIX = "monolithic-dev-harness-trial-"
TEMPLATE = Path(__file__).resolve().parents[1] / "test-project-template"


def prepare() -> Path:
    trial_root = Path(tempfile.mkdtemp(prefix=ROOT_PREFIX))
    project = trial_root / "project"
    marker = {"format": 1, "token": uuid.uuid4().hex, "project": str(project)}
    (trial_root / MARKER_NAME).write_text(json.dumps(marker), encoding="utf-8")
    try:
        shutil.copytree(TEMPLATE, project)
        run_git(project, "init", "--quiet")
        run_git(project, "config", "user.name", "Acceptance Trial")
        run_git(project, "config", "user.email", "acceptance-trial@localhost")
        run_git(project, "add", "--all")
        run_git(project, "commit", "--quiet", "-m", "Starting project")
    except BaseException:
        shutil.rmtree(trial_root)
        raise
    return project


def run_git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True)


def discard(project_arg: str) -> Path:
    supplied = Path(project_arg).expanduser()
    if supplied.is_symlink():
        raise ValueError("Refusing to discard a symbolic link.")
    project = supplied.resolve(strict=True)
    trial_root = project.parent
    temp_root = Path(tempfile.gettempdir()).resolve()
    if project.name != "project" or trial_root.parent != temp_root:
        raise ValueError(
            "Refusing: path is not a direct trial project under the system temp folder."
        )
    if trial_root.is_symlink() or not trial_root.name.startswith(ROOT_PREFIX):
        raise ValueError("Refusing: trial folder was not created by this helper.")
    marker_path = trial_root / MARKER_NAME
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if (
        not isinstance(marker, dict)
        or marker.get("format") != 1
        or marker.get("project") != str(project)
    ):
        raise ValueError(
            "Refusing: trial ownership marker does not match this project."
        )
    shutil.rmtree(trial_root)
    return trial_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="create a fresh disposable project copy")
    discard_parser = commands.add_parser(
        "discard", help="remove a helper-created project copy"
    )
    discard_parser.add_argument("project_path")
    args = parser.parse_args()
    try:
        match args.command:
            case "prepare":
                print(prepare())
            case "discard":
                print(f"Discarded {discard(args.project_path)}")
    except (
        OSError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"Acceptance trial error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
