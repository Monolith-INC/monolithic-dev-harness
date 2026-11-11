"""Load and validate a mode: a folder under `modes/` with `mode.toml`, `workflow.md` and `rules.md`.

The manifest's shape comes from `config/mode.schema.json`. The rest is checked here: each hook id
is known, each operation is a gateway tool, each skill is a plugin skill, and both files exist.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, sequence
from core.schema import load_schema, validate
from harness import state, work_sessions
from integrations.gateway import TOOLS_BY_NAME

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
MODES_ROOT = PLUGIN_ROOT / "modes"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
SCHEMA_PATH = PLUGIN_ROOT / "config" / "mode.schema.json"
MANIFEST = "mode.toml"
REQUIRED_FILES = ("workflow.md", "rules.md")
HOOK_IDS = frozenset({"orient", "operations", "knowledge_first"})
IDLE = timedelta(hours=4)


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


@dataclass(frozen=True)
class Active:
    mode: str
    session_id: str
    root: str
    entered: str
    touched: str


def enter(repo: Path, name: str, root: str = "") -> Result[Active]:
    """Start a mode: a work session the human is never asked about, recorded as the active mode."""
    return bind(
        load(name, MODES_ROOT),
        lambda mode: bind(
            _unentered(repo, mode.name),
            lambda _: bind(
                work_sessions.create(repo, f"{mode.name} mode"),
                lambda session: _record_entry(repo, mode.name, session.id, root),
            ),
        ),
    )


def active(repo: Path) -> Active | None:
    """The active mode, or None. A record idle past `IDLE` is cleared and its session completed."""
    record = _record(repo)
    if record is None:
        return None
    if _idle(record):
        _end(repo, record)
        return None
    return record


def touch(repo: Path) -> None:
    """Keep the active mode fresh; the orient hook calls this on each prompt."""
    match active(repo):
        case None:
            pass
        case current:
            state.write_json(
                state.mode_record(repo),
                asdict(replace(current, touched=_now())),
            )


def leave(repo: Path) -> Result[None]:
    match active(repo):
        case None:
            return err("mode_inactive", "no mode is active")
        case current:
            _end(repo, current)
            return Ok(None)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _moment(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _idle(record: Active) -> bool:
    moment = _moment(record.touched)
    return moment is not None and datetime.now(UTC) - moment > IDLE


def _record(repo: Path) -> Active | None:
    match state.read_json(state.mode_record(repo)):
        case {
            "mode": str(mode),
            "session_id": str(session_id),
            "root": str(root),
            "entered": str(entered),
            "touched": str(touched),
        } if _moment(touched) is not None:
            return Active(mode, session_id, root, entered, touched)
        case _:
            return None


def _unentered(repo: Path, name: str) -> Result[None]:
    match active(repo):
        case None:
            return Ok(None)
        case current:
            return err(
                "mode_active",
                f"mode {current.mode} is active; leave it before entering {name}",
            )


def _record_entry(repo: Path, mode: str, session_id: str, root: str) -> Result[Active]:
    now = _now()
    entry = Active(mode, session_id, root, now, now)
    return fmap(
        attempt(
            lambda: _save_entry(repo, entry),
            "mode_unwritable",
            f"could not record mode {mode}",
            OSError,
        ),
        lambda _: entry,
    )


def _save_entry(repo: Path, entry: Active) -> None:
    work_sessions.remember_current(repo, entry.session_id)
    state.write_json(state.mode_record(repo), asdict(entry))


def _end(repo: Path, current: Active) -> None:
    # A session that cannot complete has already ended; clearing the record is what matters.
    work_sessions.transition(repo, current.session_id, "complete")
    state.mode_record(repo).unlink(missing_ok=True)
