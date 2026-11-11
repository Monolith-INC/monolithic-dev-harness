"""Load and validate a mode: a folder under `modes/` with `mode.toml`, `workflow.md` and `rules.md`.

The manifest's shape comes from `config/mode.schema.json`. The rest is checked here: each hook id
is known, each operation is a gateway tool, each skill is a plugin skill, and both files exist.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, sequence
from core.schema import load_schema, validate
from integrations.gateway import TOOLS_BY_NAME

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
MODES_ROOT = PLUGIN_ROOT / "modes"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
SCHEMA_PATH = PLUGIN_ROOT / "config" / "mode.schema.json"
MANIFEST = "mode.toml"
REQUIRED_FILES = ("workflow.md", "rules.md")
HOOK_IDS = frozenset({"orient", "operations", "knowledge_first"})


@dataclass(frozen=True)
class SkillRef:
    name: str
    when: str


@dataclass(frozen=True)
class Mode:
    name: str
    goal: str
    expectations: tuple[str, ...]
    entry_skill: str
    skills: tuple[SkillRef, ...]
    operations: tuple[str, ...]
    hooks: tuple[str, ...]
    knowledge: str
    exit: tuple[str, ...]
    root: Path


def load(name: str, root: Path = MODES_ROOT) -> Result[Mode]:
    folder = root / name
    return bind(
        _manifest(folder),
        lambda data: bind(
            _schema_checked(data),
            lambda checked: bind(
                sequence(_checks(folder, checked)),
                lambda _: Ok(_mode(folder, checked)),
            ),
        ),
    )


def available(root: Path = MODES_ROOT) -> tuple[str, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))


def _manifest(folder: Path) -> Result[dict[str, Any]]:
    return bind(
        attempt(
            lambda: (folder / MANIFEST).read_text(encoding="utf-8"),
            "invalid_mode",
            f"mode {folder.name}: cannot read {MANIFEST}",
            OSError,
        ),
        lambda text: attempt(
            lambda: tomllib.loads(text),
            "invalid_mode",
            f"mode {folder.name}: {MANIFEST} is not valid TOML",
            tomllib.TOMLDecodeError,
        ),
    )


def _schema_checked(data: dict[str, Any]) -> Result[dict[str, Any]]:
    return bind(load_schema(SCHEMA_PATH), lambda schema: validate(schema, data, "mode"))


def _checks(folder: Path, data: dict[str, Any]) -> tuple[Result[None], ...]:
    skill_names = _skill_names()
    return (
        _unknown("hooks", data["hooks"], HOOK_IDS, "a known hook id"),
        _unknown(
            "operations",
            data["operations"],
            TOOLS_BY_NAME,
            "a gateway tool",
        ),
        _unknown("entry_skill", [data["entry_skill"]], skill_names, "a plugin skill"),
        _unknown(
            "skills",
            [skill["name"] for skill in data["skills"]],
            skill_names,
            "a plugin skill",
        ),
        *(_file_present(folder, filename) for filename in REQUIRED_FILES),
    )


def _skill_names() -> frozenset[str]:
    if not SKILLS_ROOT.is_dir():
        return frozenset()
    return frozenset(
        path.name for path in SKILLS_ROOT.iterdir() if (path / "SKILL.md").is_file()
    )


def _unknown(field: str, names: Iterable[str], known: Any, what: str) -> Result[None]:
    rejected = [name for name in names if name not in known]
    if rejected:
        return err(
            "invalid_mode",
            f"{field} names {rejected[0]!r}, which is not {what}",
        )
    return Ok(None)


def _file_present(folder: Path, filename: str) -> Result[None]:
    if (folder / filename).is_file():
        return Ok(None)
    return err("invalid_mode", f"mode {folder.name}: {filename} is missing")


def _mode(folder: Path, data: dict[str, Any]) -> Mode:
    return Mode(
        name=data["name"],
        goal=data["goal"],
        expectations=tuple(data["expectations"]),
        entry_skill=data["entry_skill"],
        skills=tuple(
            SkillRef(skill["name"], skill["when"]) for skill in data["skills"]
        ),
        operations=tuple(data["operations"]),
        hooks=tuple(data["hooks"]),
        knowledge=data["knowledge"],
        exit=tuple(data["exit"]),
        root=folder,
    )
