"""Create configured, disposable copies of the acceptance-test project.

This module is for test runs only. Regular harness setup must not depend on it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPTS = REPOSITORY / "plugins" / "monolithic-dev-harness" / "scripts"

sys.path.insert(0, str(PLUGIN_SCRIPTS))
sys.path.insert(0, str(REPOSITORY / "scripts"))

import acceptance_trial  # noqa: E402

from core.result import Err, Ok, Result, err  # noqa: E402
from harness import settings as harness_settings  # noqa: E402


def create_test_project(configuration_file: str | Path) -> Result[Path]:
    """Return a fresh test-project copy with validated settings applied.

    The configuration file must contain one complete `.harness/settings.json` value.
    Errors are returned as `Err`; a created project is returned as `Ok(path)`.
    """
    configuration = Path(configuration_file).expanduser()
    match _read_configuration(configuration):
        case Err() as failure:
            return failure
        case Ok(raw):
            match harness_settings.parse(raw):
                case Err() as failure:
                    return failure
                case Ok(_):
                    try:
                        acceptance_trial.cleanup_abandoned_runs()
                        return Ok(
                            acceptance_trial.prepare(
                                profile="unconfigured",
                                overrides=raw,
                                root_prefix=acceptance_trial.RUN_PREFIX,
                                kind="run",
                                in_checkout=True,
                            )
                        )
                    except (
                        OSError,
                        ValueError,
                        RuntimeError,
                        subprocess.SubprocessError,
                    ) as failure:
                        return err(
                            "fixture_creation_failed",
                            f"could not create the configured test project: {failure}",
                            retryable=True,
                        )


def discard_test_project(project: str | Path) -> Result[Path]:
    """Remove a fixture created by this test-only tool, if its ownership marker is valid."""
    try:
        return Ok(acceptance_trial.discard(str(project)))
    except (OSError, ValueError, json.JSONDecodeError) as failure:
        return err("fixture_discard_failed", str(failure))


def _read_configuration(configuration: Path) -> Result[dict]:
    if not configuration.is_file():
        return err(
            "missing_configuration",
            f"project configuration file does not exist: {configuration}",
        )
    try:
        raw = json.loads(configuration.read_text(encoding="utf-8"))
    except json.JSONDecodeError as failure:
        return err(
            "invalid_configuration_json",
            f"project configuration is not valid JSON: {failure}",
        )
    except OSError as failure:
        return err(
            "configuration_unreadable",
            f"project configuration could not be read: {failure}",
        )
    return (
        Ok(raw)
        if isinstance(raw, dict)
        else err(
            "invalid_configuration",
            "project configuration must be a JSON object",
        )
    )
