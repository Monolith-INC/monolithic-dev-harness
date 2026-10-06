"""Bind BMAD's immutable discovery snapshot to one post-onboarding work session.

Rendering is a subprocess edge. Verification reads the pinned snapshot rather than rendering
again, so upgrades cannot silently replace the instructions of an existing run.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, require, sequence
from harness import preferences, setup, state, work_sessions, workflow

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SKILL = PLUGIN_ROOT / "skills" / "bmad-build"
DRIVER = PLUGIN_ROOT / "scripts" / "harness" / "render_discovery.py"
PIN = "discovery-render.json"


def onboarding_ready(repo: Path) -> Result[dict[str, Any]]:
    return bind(
        setup.inspect(repo),
        lambda report: fmap(
            require(
                report["status"] == "ready"
                and report["language_confirmed"]
                and not report["handoff"]["waiting_for_answer"]
                and report["bmad_runtime"]["ready"],
                "onboarding_incomplete",
                "complete project setup, language confirmation, and bundled runtime before work",
            ),
            lambda _: report,
        ),
    )


def render(repo: Path, session_id: str) -> Result[dict[str, Any]]:
    return bind(
        work_sessions.require_active(repo, session_id),
        lambda session: bind(
            onboarding_ready(repo),
            lambda report: bind(
                workflow.load(repo, session.id),
                lambda current: bind(
                    require(
                        current.request == session.request
                        and current.status == "active",
                        "invalid_workflow",
                        "discovery requires the active workflow for this work session",
                    ),
                    lambda _: bind(
                        _read_context(repo, session, report),
                        lambda context: _reuse_or_render(repo, session, context),
                    ),
                ),
            ),
        ),
    )


def verify(repo: Path, session_id: str) -> Result[dict[str, Any] | None]:
    """Verify a pin when present, including on resume; other stages need no discovery pin."""
    return bind(
        work_sessions.select(repo, session_id),
        lambda session: _verify_optional(repo, session),
    )


def _verify_optional(
    repo: Path, session: work_sessions.Session
) -> Result[dict[str, Any] | None]:
    match (session.folder / PIN).exists():
        case False:
            return Ok(None)
        case True:
            return bind(
                onboarding_ready(repo),
                lambda report: bind(
                    _read_context(repo, session, report),
                    lambda context: _read_pin(repo, session, context),
                ),
            )


def _read_context(
    repo: Path, session: work_sessions.Session, report: dict[str, Any]
) -> Result[dict[str, str]]:
    return attempt(
        lambda: _context(repo, session, report),
        "invalid_discovery_context",
        "could not read discovery inputs",
        OSError,
    )


def _context(
    repo: Path, session: work_sessions.Session, report: dict[str, Any]
) -> dict[str, str]:
    return {
        "project_root": str(repo.resolve()),
        "session_id": session.id,
        "original_request": session.request,
        "language": str(report["language"]),
        "tracker": str(report["current_tracker"]["name"]),
        "scm": str(report["current_scm"].get("name", "local")),
        "preferences_path": str(preferences.path().resolve()),
        "settings_sha256": _digest(repo / ".harness" / "settings.json"),
        "bmad_config_sha256": hashlib.sha256(
            json.dumps(
                {
                    name: _optional_digest(repo / "_bmad" / name)
                    for name in (
                        "config.toml",
                        "custom/config.toml",
                        "custom/config.user.toml",
                        "custom/bmad-build.toml",
                        "custom/bmad-build.user.toml",
                    )
                },
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "route": "full",
        "review": "none",
        "status_command": _command(repo, session.id, "status"),
        "checkpoint_command": _command(repo, session.id, "checkpoint"),
        "python_command": shlex.quote(sys.executable),
        "config_command": shlex.join(
            (
                sys.executable,
                str(repo.resolve() / "_bmad/scripts/resolve_config.py"),
                "--project-root",
                str(repo.resolve()),
                "--key",
                "core.active_initiative",
            )
        ),
        "tickets_command": shlex.join(
            (
                sys.executable,
                str(repo.resolve() / "_bmad/method/scripts/tickets.py"),
                "--project-root",
                str(repo.resolve()),
            )
        ),
    }


def _command(repo: Path, session_id: str, operation: str) -> str:
    return shlex.join(
        (
            "env",
            f"HARNESS_USER_STATE_DIR={preferences.path().resolve().parent}",
            str(PLUGIN_ROOT / "bin" / "harness"),
            "workflow",
            operation,
            "--repo",
            str(repo.resolve()),
            "--session-id",
            session_id,
        )
    )


def _reuse_or_render(
    repo: Path, session: work_sessions.Session, context: dict[str, str]
) -> Result[dict[str, Any]]:
    match (session.folder / PIN).exists():
        case True:
            return _read_pin(repo, session, context)
        case False:
            return bind(
                _invoke(repo, context),
                lambda entry: bind(
                    _validate_entry(repo, entry, context),
                    lambda package: attempt(
                        lambda: _save_pin(session.folder / PIN, package),
                        "discovery_render_failed",
                        "could not pin the discovery snapshot",
                        OSError,
                    ),
                ),
            )


def _invoke(repo: Path, context: dict[str, str]) -> Result[Path]:
    return bind(
        attempt(
            lambda: subprocess.run(
                [
                    sys.executable,
                    str(DRIVER),
                    "--project-root",
                    str(repo.resolve()),
                    "--skill",
                    str(SKILL),
                    *(
                        argument
                        for key, value in context.items()
                        for argument in ("--set", f"workflow.{key}={json.dumps(value)}")
                    ),
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            ),
            "discovery_render_failed",
            "BMAD renderer could not run",
            OSError,
            subprocess.TimeoutExpired,
        ),
        _render_report,
    )


def _render_report(done: subprocess.CompletedProcess[str]) -> Result[Path]:
    match done.returncode, done.stdout.strip().splitlines():
        case 0, [*_, str() as last] if last.startswith("read and follow "):
            return Ok(Path(last.removeprefix("read and follow ")))
        case _:
            return err(
                "discovery_render_failed",
                (done.stderr or done.stdout).strip()
                or "BMAD renderer returned no entry",
            )


def _read_pin(
    repo: Path, session: work_sessions.Session, context: dict[str, str]
) -> Result[dict[str, Any]]:
    return bind(
        _json(session.folder / PIN),
        lambda pin: _verify_pin(repo, pin, context),
    )


def _verify_pin(
    repo: Path, pin: dict[str, Any], context: dict[str, str]
) -> Result[dict[str, Any]]:
    match pin:
        case {
            "version": 1,
            "context": dict() as saved,
            "entry": str() as entry,
            "manifest_sha256": str() as digest,
        } if saved == context:
            return bind(
                _validate_entry(repo, Path(entry), context),
                lambda package: fmap(
                    require(
                        package["manifest_sha256"] == digest,
                        "discovery_snapshot_changed",
                        "the pinned discovery manifest changed; preserve it for review",
                    ),
                    lambda _: package,
                ),
            )
        case _:
            return err(
                "discovery_snapshot_changed",
                "discovery context or pin changed; preserve the original run for review",
            )


def _validate_entry(
    repo: Path, entry: Path, context: dict[str, str]
) -> Result[dict[str, Any]]:
    return bind(
        require(
            entry.is_absolute()
            and entry.name == "workflow.md"
            and entry.resolve().is_relative_to(
                (repo / "_bmad" / "render" / "bmad-build").resolve()
            ),
            "invalid_discovery_snapshot",
            "discovery entry must be in this project's BMAD snapshot directory",
        ),
        lambda _: bind(
            _json(entry.parent / "manifest.json"),
            lambda manifest: _validate_manifest(entry, manifest, context),
        ),
    )


def _validate_manifest(
    entry: Path, manifest: dict[str, Any], context: dict[str, str]
) -> Result[dict[str, Any]]:
    match manifest:
        case {
            "schema_version": 1,
            "project_root": str() as root,
            "skill": "bmad-build",
            "outputs": dict() as outputs,
            "inputs": {"resolved_values": dict() as values},
        } if (
            root == context["project_root"]
            and "workflow.md" in outputs
            and all(
                values.get(f"customization.workflow.{key}") == value
                for key, value in context.items()
            )
        ):
            return fmap(
                sequence(
                    _verify_output(entry.parent, name, digest)
                    for name, digest in outputs.items()
                ),
                lambda _: {
                    "version": 1,
                    "entry": str(entry),
                    "context": context,
                    "manifest_sha256": _digest(entry.parent / "manifest.json"),
                },
            )
        case _:
            return err(
                "invalid_discovery_snapshot",
                "snapshot manifest does not match this project and session",
            )


def _verify_output(directory: Path, name: str, digest: str) -> Result[str]:
    return bind(
        require(
            isinstance(name, str)
            and isinstance(digest, str)
            and (directory / name).resolve().is_relative_to(directory.resolve()),
            "invalid_discovery_snapshot",
            "snapshot output escapes its directory",
        ),
        lambda _: bind(
            attempt(
                lambda: _digest(directory / name),
                "discovery_snapshot_changed",
                f"missing or unreadable snapshot output {name}",
                OSError,
            ),
            lambda actual: fmap(
                require(
                    actual == digest,
                    "discovery_snapshot_changed",
                    f"snapshot output changed: {name}",
                ),
                lambda _: name,
            ),
        ),
    )


def _json(path: Path) -> Result[dict[str, Any]]:
    return bind(
        attempt(
            lambda: json.loads(path.read_text(encoding="utf-8")),
            "invalid_discovery_snapshot",
            str(path),
            OSError,
            ValueError,
        ),
        lambda value: (
            Ok(value)
            if isinstance(value, dict)
            else err("invalid_discovery_snapshot", "snapshot record must be an object")
        ),
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _optional_digest(path: Path) -> str:
    match path.exists():
        case True:
            return _digest(path)
        case False:
            return "absent"


def _save_pin(path: Path, package: dict[str, Any]) -> dict[str, Any]:
    state.write_json(path, package)
    return package
