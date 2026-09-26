"""The repository's settings: `.harness/settings.json`, the only settings file.

People write it; the harness reads it once per process and passes the value along. Defaults for
omitted sections live here and nowhere else. The file's presence is what opts a repository in.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, err
from core.schema import load_schema, validate

SETTINGS_RELATIVE_PATH = Path(".harness") / "settings.json"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.schema.json"


@dataclass(frozen=True)
class Selection:
    """Which tracker or SCM the repository uses, and the values it was told to use."""

    name: str
    source: str
    values: Mapping[str, str]


@dataclass(frozen=True)
class Check:
    name: str
    run: str
    when: tuple[str, ...]


@dataclass(frozen=True)
class TestsRequired:
    source: tuple[str, ...]
    tests: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class GuardedPath:
    path: str
    kind: str
    name: str


@dataclass(frozen=True)
class Settings:
    tracker: Selection
    scm: Selection
    branch_template: str
    protected_work_items: frozenset[str]
    artifacts_path: str
    base_branch: str
    approval_minutes: int
    checks: tuple[Check, ...]
    tests_required: tuple[TestsRequired, ...]
    generated: tuple[str, ...]
    guarded_paths: tuple[GuardedPath, ...]
    require_draft: bool
    require_review_verdict: bool

    @property
    def check_names(self) -> frozenset[str]:
        return frozenset(check.name for check in self.checks)


def path(repo: Path) -> Path:
    return repo / SETTINGS_RELATIVE_PATH


def governed(repo: Path) -> bool:
    return path(repo).is_file()


def load(repo: Path) -> Result[Settings]:
    """The repository's settings, or why they cannot be used."""
    return bind(
        bind(_read(path(repo)), _conforming),
        lambda raw: bind(_parse(raw), _consistent),
    )


def parse(raw: Mapping[str, Any]) -> Result[Settings]:
    """Settings from an already-read value (bootstrap checks a candidate file this way)."""
    return bind(bind(_conforming(raw), _parse), _consistent)


def _read(file: Path) -> Result[Any]:
    return attempt(
        lambda: json.loads(file.read_text(encoding="utf-8")),
        "invalid_settings",
        f"{SETTINGS_RELATIVE_PATH} could not be read",
        OSError,
        ValueError,
    )


def _conforming(raw: Any) -> Result[Mapping[str, Any]]:
    return bind(
        load_schema(SCHEMA_PATH), lambda schema: validate(schema, raw, "settings")
    )


def _selection(raw: Mapping[str, Any]) -> Selection:
    return Selection(
        str(raw["name"]),
        str(raw.get("source", "shipped")),
        MappingProxyType(dict(raw.get("values", {}))),
    )


def _parse(raw: Mapping[str, Any]) -> Result[Settings]:
    pull_requests = raw.get("pull_requests", {})
    return Ok(
        Settings(
            tracker=_selection(raw["tracker"]),
            scm=_selection(raw["scm"]),
            branch_template=str(raw["branch_template"]),
            protected_work_items=frozenset(
                str(item) for item in raw.get("protected_work_items", [])
            ),
            artifacts_path=str(raw.get("artifacts_path", "")),
            base_branch=str(raw.get("git", {}).get("base_branch", "develop")),
            approval_minutes=int(raw.get("approvals", {}).get("window_minutes", 20)),
            checks=tuple(
                Check(str(item["name"]), str(item["run"]), tuple(item.get("when", ())))
                for item in raw.get("checks", [])
            ),
            tests_required=tuple(
                TestsRequired(
                    tuple(item["source"]),
                    tuple(item["tests"]),
                    tuple(item.get("exclude", ())),
                )
                for item in raw.get("tests_required", [])
            ),
            generated=tuple(raw.get("generated", ())),
            guarded_paths=tuple(
                GuardedPath(str(item["path"]), *str(item["evidence"]).split(":", 1))
                for item in raw.get("guarded_paths", [])
            ),
            require_draft=bool(pull_requests.get("require_draft", True)),
            require_review_verdict=bool(
                pull_requests.get("require_review_verdict", True)
            ),
        )
    )


def _consistent(settings: Settings) -> Result[Settings]:
    unknown = tuple(
        guard.path
        for guard in settings.guarded_paths
        if guard.kind == "check" and guard.name not in settings.check_names
    )
    return (
        Ok(settings)
        if not unknown
        else err(
            "invalid_settings",
            f"guarded path(s) {list(unknown)} name a check that is not in checks",
        )
    )


def describe(result: Result[Settings]) -> str:
    """One line for a person: what is wrong with the settings, or that they are fine."""
    match result:
        case Ok():
            return "settings are valid"
        case Err(failure):
            return failure.message
