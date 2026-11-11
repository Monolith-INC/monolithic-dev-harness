"""Load and validate a mode: a folder under `modes/` with `mode.toml`, `workflow.md` and `rules.md`.

The manifest's shape comes from `config/mode.schema.json`. The rest is checked here: each hook id
is known, each operation is a gateway tool, each skill is a plugin skill, and both files exist.

A mode in force is a work session that records its name and ROOT, plus `mode.json`, a pointer that
names that session. Reading the mode is total and repairs: see `resolve`.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, err, fmap, sequence
from core.schema import load_schema, validate
from harness import settings, state, work_sessions

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
MODES_ROOT = PLUGIN_ROOT / "modes"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
SCHEMA_PATH = PLUGIN_ROOT / "config" / "mode.schema.json"
MANIFEST = "mode.toml"
REQUIRED_FILES = ("workflow.md", "rules.md")
# One plain folder name: it never holds a separator, and cannot be empty, `.` or `..`.
PLAIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
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
        _plain(name),
        lambda _: bind(
            _manifest(folder),
            lambda data: bind(
                _schema_checked(data),
                lambda checked: bind(
                    sequence(_checks(folder, checked)),
                    lambda _: Ok(_mode(folder, checked)),
                ),
            ),
        ),
    )


def available(root: Path = MODES_ROOT) -> tuple[str, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))


def _plain(name: str) -> Result[None]:
    """A mode is a folder directly under `modes/`, so its name is one plain folder name."""
    if PLAIN_NAME.fullmatch(name):
        return Ok(None)
    return err(
        "invalid_mode",
        f"mode name {name!r} is not a plain folder name: letters, digits, '.', '_' and '-', "
        "starting with a letter or digit",
    )


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
    # Imported here: the gateway imports the rule chain, which imports this module.
    from integrations.gateway import TOOLS_BY_NAME

    skill_names = _skill_names()
    return (
        _named_for(folder, data["name"]),
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


def _named_for(folder: Path, name: str) -> Result[None]:
    if name == folder.name:
        return Ok(None)
    return err(
        "invalid_mode",
        f"mode {folder.name}: name is {name!r}, which must be its folder name",
    )


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
    """The mode in force: its pointer's fields, and the manifest the pointer names."""

    mode: str
    session_id: str
    root: str
    entered: str
    manifest: Mode


@dataclass(frozen=True)
class Resolution:
    """What a read of the mode found. `notice` is one line for the agent when the read repaired
    the mode or could not, and empty otherwise. It never names the work session."""

    active: Active | None
    notice: str = ""


def enter(repo: Path, name: str, root: str = "") -> Result[Active]:
    """Start a mode: a work session the human is never asked about, recorded as the active mode."""
    return bind(
        _governed(repo),
        lambda _: bind(
            load(name, MODES_ROOT),
            lambda mode: bind(
                _unentered(repo, mode.name),
                lambda _: _start(repo, mode, root, _now()),
            ),
        ),
    )


def active(repo: Path) -> Active | None:
    """The active mode, or None. Total: it never raises, and it repairs what it finds."""
    return resolve(repo).active


def resolve(repo: Path) -> Resolution:
    """Read the mode, and repair it when its pointer or its work session is not as it should be.

    The mode's work session is its durable record and `mode.json` only points at it, so the pointer
    can always be regenerated. A repair that cannot be done means no mode for this call, with a
    notice, and the next call tries again. The hook asks once at the start of a call, so the
    notice reaches the agent once.
    """
    match attempt(
        lambda: _resolved(repo), "mode_unresolved", "the mode cannot be read"
    ):
        case Ok(found):
            return found
        case _:
            return Resolution(None)


def leave(repo: Path) -> Result[None]:
    """End the mode, in whatever state it is: complete every work session that records one and
    remove the pointer, so a mode that could not be recovered can still be left."""
    sessions = tuple(
        dict.fromkeys((*_pointed_session(repo), *_recorded_sessions(repo)))
    )
    if not sessions and not state.mode_record(repo).exists():
        return err("mode_inactive", "no mode is active")
    return fmap(
        attempt(
            lambda: _end(repo, sessions),
            "mode_unwritable",
            "could not end the mode",
            OSError,
        ),
        lambda _: None,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _moment(text: str) -> datetime | None:
    """The instant `text` names, or None when it is not an ISO time that carries a time zone."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _resolved(repo: Path) -> Resolution:
    match _pointer(repo):
        case Ok(Active() as current):
            return _alive(repo, current)
        case Ok(None):
            return _regenerated(repo)
        case _:
            _set_aside(repo)
            return _regenerated(repo)


def _pointer(repo: Path) -> Result[Active | None]:
    """The pointer's mode, None when there is no pointer, an error when it cannot be used: it is
    unreadable or malformed, or names a mode that does not load."""
    path = state.mode_record(repo)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Ok(None)
    except (OSError, ValueError) as exc:
        return err("mode_damaged", f"the mode record cannot be read: {exc}")
    return bind(
        attempt(
            lambda: json.loads(text),
            "mode_damaged",
            "the mode record is not valid JSON",
            ValueError,
        ),
        _pointed,
    )


def _pointed(payload: Any) -> Result[Active]:
    match payload:
        case {
            "mode": str(mode),
            "session_id": str(session_id),
            "root": str(root),
            "entered": str(entered),
        } if _moment(entered) is not None:
            return fmap(
                load(mode, MODES_ROOT),
                lambda manifest: Active(mode, session_id, root, entered, manifest),
            )
        case _:
            return err("mode_damaged", "the mode record is malformed")


def _set_aside(repo: Path) -> None:
    """Keep a pointer that cannot be used beside the new one, as damaged session links are."""
    path = state.mode_record(repo)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path.replace(path.with_name(f"{path.name}.damaged-{stamp}"))


def _alive(repo: Path, current: Active) -> Resolution:
    """The pointer is fine; its session must be live. Paused: resume it, since nobody pauses a mode
    on purpose. Ended or missing: a new session for the same mode and ROOT, since where the work
    stands is derived from ROOT and nothing is lost."""
    match work_sessions.select(repo, current.session_id):
        case Ok(session) if session.status == work_sessions.Status.ACTIVE:
            return Resolution(current)
        case Ok(session) if session.status == work_sessions.Status.PAUSED:
            return _repaired(
                current.mode,
                fmap(_resume(repo, current.session_id), lambda _: current),
            )
        case _:
            return _repaired(
                current.mode,
                _start(repo, current.manifest, current.root, current.entered),
            )


def _regenerated(repo: Path) -> Resolution:
    """No usable pointer: it comes back from the one unended session that records a mode."""
    match work_sessions.recording_mode(repo):
        case ():
            return Resolution(None)
        case (session,):
            return _repaired(session.mode, _adopted(repo, session))
        case (first, *_):
            return Resolution(None, _unrecovered(first.mode))


def _adopted(repo: Path, session: work_sessions.Session) -> Result[Active]:
    return bind(
        load(session.mode, MODES_ROOT),
        lambda manifest: bind(
            _live(repo, session),
            lambda _: _point(
                repo,
                Active(
                    session.mode,
                    session.id,
                    session.mode_root,
                    session.created_at,
                    manifest,
                ),
            ),
        ),
    )


def _live(repo: Path, session: work_sessions.Session) -> Result[None]:
    if session.status != work_sessions.Status.PAUSED:
        return Ok(None)
    return _resume(repo, session.id)


def _resume(repo: Path, identifier: str) -> Result[None]:
    """Resume a paused session. One that a call running at the same moment already resumed is as
    good: hooks of parallel tool calls each repair what they find."""
    match work_sessions.transition(repo, identifier, "resume"):
        case Err() as failed if not _running(repo, identifier):
            return failed
        case _:
            return Ok(None)


def _running(repo: Path, identifier: str) -> bool:
    match work_sessions.select(repo, identifier):
        case Ok(session):
            return session.status == work_sessions.Status.ACTIVE
        case _:
            return False


def _repaired(name: str, result: Result[Active]) -> Resolution:
    match result:
        case Ok(restored):
            return Resolution(restored, f"Recovered the {name} mode.")
        case _:
            return Resolution(None, _unrecovered(name))


def _unrecovered(name: str) -> str:
    return (
        f"The {name} mode could not be recovered; run `harness modes leave` to end it."
    )


def _governed(repo: Path) -> Result[None]:
    """The mode hooks act only where the harness governs, so a mode entered elsewhere does nothing."""
    if settings.governed(repo):
        return Ok(None)
    return err(
        "not_governed",
        f"the harness does not govern {repo}, so a mode would do nothing there; "
        "run bootstrap to set the project up first",
    )


def _unentered(repo: Path, name: str) -> Result[None]:
    match resolve(repo):
        case Resolution(active=None, notice=""):
            return Ok(None)
        case Resolution(active=Active() as current):
            return err(
                "mode_active",
                f"mode {current.mode} is active; leave it before entering {name}",
            )
        case Resolution(notice=text):
            return err("mode_active", f"{text} Leave it before entering {name}.")


def _start(repo: Path, mode: Mode, root: str, entered: str) -> Result[Active]:
    """A new work session that records the mode and ROOT, and the pointer to it. A pointer that
    cannot be written ends the session again, so a failed entry is not recovered as a mode."""
    return bind(
        work_sessions.create(repo, f"{mode.name} mode", mode=mode.name, mode_root=root),
        lambda session: _pointed_or_ended(
            repo, Active(mode.name, session.id, root, entered, mode)
        ),
    )


def _pointed_or_ended(repo: Path, entry: Active) -> Result[Active]:
    result = _point(repo, entry)
    if isinstance(result, Err):
        work_sessions.transition(repo, entry.session_id, "complete")
    return result


def _point(repo: Path, entry: Active) -> Result[Active]:
    """Write the pointer and make its session the project's current one. Entering a mode and
    repairing one both end here, so the harness's own code is the only writer of `mode.json`."""
    return fmap(
        attempt(
            lambda: _save_entry(repo, entry),
            "mode_unwritable",
            f"could not record mode {entry.mode}",
            OSError,
        ),
        lambda _: entry,
    )


def _save_entry(repo: Path, entry: Active) -> None:
    work_sessions.remember_current(repo, entry.session_id)
    state.write_json(
        state.mode_record(repo),
        {
            "mode": entry.mode,
            "session_id": entry.session_id,
            "root": entry.root,
            "entered": entry.entered,
        },
    )


def _pointed_session(repo: Path) -> tuple[str, ...]:
    """The session a pointer names, read without trusting the rest of it."""
    try:
        match json.loads(state.mode_record(repo).read_text(encoding="utf-8")):
            case {"session_id": str(session_id)}:
                return (session_id,)
            case _:
                return ()
    except (OSError, ValueError):
        return ()


def _recorded_sessions(repo: Path) -> tuple[str, ...]:
    return tuple(session.id for session in work_sessions.recording_mode(repo))


def _end(repo: Path, sessions: tuple[str, ...]) -> None:
    # A session that cannot complete has already ended; removing the pointer is what matters.
    for identifier in sessions:
        work_sessions.transition(repo, identifier, "complete")
    state.mode_record(repo).unlink(missing_ok=True)
