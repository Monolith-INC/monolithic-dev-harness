"""BMad's one-time project setup, run unchanged from the copy bundled with the plugin.

BMad's skills read `_bmad/config.toml` and run their scripts from `_bmad/scripts/`; BMad's own
`setup.py` creates both. The harness runs it with the interpreter it already runs on (Python 3.12+,
see `bin/harness-python`), so nothing is downloaded. It then points BMad's output folder at the
repository's `artifacts_path` through BMad's team layer, `_bmad/custom/config.toml`, and never
overwrites that file once it exists.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
VENDOR_SKILLS = PLUGIN_ROOT / "vendor" / "bmad" / "skills"
SETUP = VENDOR_SKILLS / "bmad" / "scripts" / "setup.py"
TEAM_CONFIG = Path("_bmad") / "custom" / "config.toml"
SETUP_SECONDS = 120


def prepare(repo: Path, artifacts_path: str) -> Result[dict[str, Any]]:
    """Set up or repair `_bmad/` in `repo`; the report says what changed."""
    return bind(
        _setup(repo),
        lambda report: bind(
            _point_output(repo, artifacts_path),
            lambda output: Ok({"setup": report.get("status", ""), "output": output}),
        ),
    )


def ready(repo: Path) -> bool:
    return (repo / "_bmad" / "config.toml").is_file()


def _setup(repo: Path) -> Result[dict[str, Any]]:
    command = [
        sys.executable,
        str(SETUP),
        "--project-root",
        str(repo),
        "--skill",
        str(VENDOR_SKILLS / "bmad"),
        "--root",
        str(PLUGIN_ROOT / "skills"),
        "--root",
        str(VENDOR_SKILLS),
    ]
    return bind(
        attempt(
            lambda: subprocess.run(
                command,
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=SETUP_SECONDS,
            ),
            "bmad_setup_failed",
            "BMad setup could not run",
            OSError,
            subprocess.TimeoutExpired,
        ),
        _report,
    )


def _report(done: subprocess.CompletedProcess[str]) -> Result[dict[str, Any]]:
    try:
        report = json.loads(done.stdout)
    except ValueError:
        report = None
    if done.returncode != 0 or not isinstance(report, dict):
        reason = (done.stderr or done.stdout).strip().splitlines()
        return err(
            "bmad_setup_failed",
            f"BMad setup failed: {reason[-1] if reason else 'no output'}",
        )
    if report.get("problems"):
        return err(
            "bmad_setup_failed",
            "BMad setup reported problems: " + json.dumps(report["problems"]),
        )
    return Ok(report)


def _point_output(repo: Path, artifacts_path: str) -> Result[str]:
    path = repo / TEAM_CONFIG
    if not artifacts_path or path.exists():
        return Ok("unchanged")
    folder = (
        artifacts_path
        if Path(artifacts_path).is_absolute()
        else "{project-root}/" + artifacts_path.strip("/")
    )
    # A TOML basic string takes the same escapes as a JSON string.
    text = (
        "# Written by monolithic-dev-harness bootstrap: BMad writes its documents where the\n"
        "# harness keeps plans (`artifacts_path`). Edit freely; bootstrap never overwrites it.\n"
        f"[core]\noutput_folder = {json.dumps(folder)}\n"
    )
    return attempt(
        lambda: _write(path, text),
        "bmad_setup_failed",
        f"could not write {TEAM_CONFIG}",
        OSError,
    )


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return "artifacts_path"
