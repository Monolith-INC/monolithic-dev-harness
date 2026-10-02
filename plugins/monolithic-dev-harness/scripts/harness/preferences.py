"""User-level harness preferences shared across repositories; never stored in a checkout."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap
from harness import state

LANGUAGES = ("en", "pt-br")
LANGUAGE_STATE = Path(".harness/state/language.json")


def path() -> Path:
    configured = os.environ.get("HARNESS_USER_STATE_DIR")
    base = (
        Path(configured)
        if configured
        else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "monolithic-dev-harness"
    )
    return base / "preferences.json"


def read() -> Result[dict[str, Any]]:
    file = path()
    match file.is_file():
        case False:
            return Ok({})
        case True:
            return bind(
                attempt(
                    lambda: json.loads(file.read_text(encoding="utf-8")),
                    "invalid_preferences",
                    str(file),
                    OSError,
                    ValueError,
                ),
                lambda value: (
                    Ok(value)
                    if isinstance(value, dict)
                    else err(
                        "invalid_preferences", "user preferences must be an object"
                    )
                ),
            )


def language() -> Result[str]:
    return bind(
        read(),
        lambda value: (
            Ok(value.get("language", ""))
            if value.get("language", "") in ("", *LANGUAGES)
            else err("invalid_preferences", "saved language must be en or pt-br")
        ),
    )


def language_confirmed(repo: Path) -> Result[bool]:
    chosen = state.read_json(repo / LANGUAGE_STATE)
    return Ok(bool(chosen and chosen.get("language") in LANGUAGES))


def set_language(chosen: str, repo: Path | None = None) -> Result[Path]:
    match chosen:
        case "en" | "pt-br":
            return bind(
                read(),
                lambda current: bind(
                    attempt(
                        lambda: _write({**current, "language": chosen}),
                        "preferences_unwritable",
                        str(path()),
                        OSError,
                    ),
                    lambda saved: fmap(
                        attempt(
                            lambda: _write_project_language(repo, chosen),
                            "preferences_unwritable",
                            str(repo / LANGUAGE_STATE),
                            OSError,
                        )
                        if repo is not None
                        else Ok(None),
                        lambda _: saved,
                    ),
                ),
            )
        case _:
            return err("invalid_preferences", "choose en or pt-br")


def _write_project_language(repo: Path, chosen: str) -> None:
    state.ensure_local_exclude(repo)
    state.write_json(repo / LANGUAGE_STATE, {"language": chosen})


def _write(value: dict[str, Any]) -> Path:
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(file)
    return file
