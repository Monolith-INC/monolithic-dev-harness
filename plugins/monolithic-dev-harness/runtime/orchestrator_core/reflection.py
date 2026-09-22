from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MISTAKES_FILENAME = "mistakes.json"


@dataclass
class ReflectionState:
    attempt: int = 0
    last_critiques: tuple[str, ...] = ()
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "last_critiques": list(self.last_critiques),
            "blocked": self.blocked,
        }


@dataclass(frozen=True)
class ReflectionDecision:
    critiques: list[str]
    reflection: ReflectionState
    mode: str
    blocked: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "critiques": self.critiques,
            "reflection": self.reflection.to_dict(),
            "mode": self.mode,
            "blocked": self.blocked,
        }


def advance_reflection(
    state: ReflectionState,
    critiques: list[str],
    *,
    max_attempts: int = 3,
) -> ReflectionState:
    attempt = state.attempt + 1
    normalized = tuple(critiques)
    identical = bool(normalized) and normalized == state.last_critiques
    blocked = bool(critiques) and (attempt >= max_attempts or identical)
    return ReflectionState(attempt=attempt, last_critiques=normalized, blocked=blocked)


def evaluate_reflection(
    critiques: list[str],
    *,
    state: ReflectionState | None = None,
    max_attempts: int = 3,
    has_draft: bool = True,
) -> ReflectionDecision:
    current = state or ReflectionState()
    if not has_draft:
        return ReflectionDecision(critiques=[], reflection=current, mode="instructions", blocked=False)
    if not critiques:
        return ReflectionDecision(critiques=[], reflection=current, mode="completed", blocked=False)
    next_state = advance_reflection(current, critiques, max_attempts=max_attempts)
    blocked = next_state.blocked
    mode = "blocked_requires_review" if blocked else "correcao"
    return ReflectionDecision(critiques=critiques, reflection=next_state, mode=mode, blocked=blocked)


def mistakes_path(state_dir: Path) -> Path:
    """The mistakes record, in the plugin's own state directory.

    This is plugin memory used by the retry loop, not a user work product, so it lives
    under `.agile-backlog-toolkit/` and never in a location the user owns.
    """
    return state_dir / MISTAKES_FILENAME


def load_mistakes(state_dir: Path, *, skill_name: str | None = None) -> list[dict[str, Any]]:
    path = mistakes_path(state_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    mistakes = data.get("mistakes", [])
    if skill_name:
        return [m for m in mistakes if m.get("skill") == skill_name]
    return mistakes


def append_mistake(
    state_dir: Path,
    *,
    flaw: str,
    skill_name: str,
    artifact: str,
) -> bool:
    path = mistakes_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8")).get("mistakes", [])
        except (OSError, json.JSONDecodeError):
            existing = []
    existing.append({"flaw": flaw, "skill": skill_name, "artifact": artifact})
    try:
        path.write_text(json.dumps({"mistakes": existing}, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True
