"""Inspect and prepare reviewed first-run settings without assuming a tracker."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, require
from harness import (
    decisions,
    local_tracker,
    preferences,
    settings,
    state,
    workflow,
)
from integrations import registry, scm


def _raw(repo: Path) -> Result[dict[str, Any]]:
    file = settings.path(repo)
    match file.is_file():
        case False:
            return Ok({})
        case True:
            return bind(
                attempt(
                    lambda: json.loads(file.read_text(encoding="utf-8")),
                    "invalid_settings",
                    str(file),
                    OSError,
                    ValueError,
                ),
                lambda value: (
                    Ok(value)
                    if isinstance(value, dict)
                    else err("invalid_settings", "settings must be an object")
                ),
            )


def _git(repo: Path, *arguments: str) -> str:
    return match_git(
        attempt(
            lambda: subprocess.run(
                ["git", "-C", str(repo), *arguments],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ),
            "git_unavailable",
            "repository information is unavailable",
            OSError,
            subprocess.TimeoutExpired,
        )
    )


def match_git(result: Result[subprocess.CompletedProcess[str]]) -> str:
    match result:
        case Ok(command) if command.returncode == 0:
            return command.stdout.strip()
        case _:
            return ""


def inferred_base(repo: Path) -> str:
    remote = _git(
        repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
    )
    return remote.removeprefix("origin/") or _git(repo, "branch", "--show-current")


def _repository_snapshot(repo: Path) -> dict[str, Any]:
    present = _git(repo, "rev-parse", "--is-inside-work-tree") == "true"
    head = _git(repo, "rev-parse", "--verify", "HEAD") if present else ""
    return {
        "git_present": present,
        "has_committed_head": bool(head),
        "head": head,
        "branch": _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
        if present
        else "",
    }


def _workflow_snapshot(repo: Path) -> dict[str, Any]:
    match workflow.load(repo):
        case Ok(current):
            return {
                "status": current.status,
                "request": current.request,
                "stage": current.current.stage,
                "pending": current.current.pending,
                "point": current.current.id,
                "label": current.current.label,
                "next_action": current.current.next_action,
                "artifacts": [
                    {"path": str((repo / name).resolve()), "digest": digest}
                    for name, digest in current.current.artifacts
                ],
                "stale_artifacts": list(
                    workflow.stale_artifacts(repo, current.current)
                ),
            }
        case _ if workflow.path(repo).exists():
            return {
                "status": "invalid",
                "error": "saved workflow could not be loaded; inspect it before starting another",
            }
        case _:
            return {}


def _handoff(
    repo: Path, raw: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    pending = decisions.record(repo)
    return {
        "project_root": str(repo.resolve()),
        "working_directory": str(repo.resolve()),
        "command": str(Path(__file__).resolve().parents[2] / "bin" / "harness"),
        "paths": {
            "settings": str(settings.path(repo).resolve()),
            "workflow": str(workflow.path(repo).resolve()),
            "preferences": str(preferences.path().resolve()),
            "artifacts": str((repo / str(raw["artifacts_path"])).resolve())
            if raw.get("artifacts_path")
            else "",
        },
        "environment": {
            "HARNESS_USER_STATE_DIR": str(preferences.path().resolve().parent)
        },
        "original_request": current.get("request", ""),
        "next_action": current.get("next_action", ""),
        "workflow_status": current.get("status", "absent"),
        "harness_suspended": state.harness_mode(repo) == "suspended",
        "waiting_for_answer": decisions.waiting(repo),
        "pending_question": {
            key: pending.get(key) for key in ("id", "question", "options", "transport")
        }
        if pending and decisions.waiting(repo)
        else None,
        "instruction": "Use this project and environment for every operation. Preserve the saved original request and current checkpoint. Do not repeat confirmed setup choices, restart an existing run, or advance while a question is unanswered. Report invalid saved state instead of replacing it. A suspended harness does not authorize automatically resuming the run.",
    }


def _selection(raw: Mapping[str, Any], name: str) -> dict[str, Any]:
    selected = raw.get(name)
    return selected if isinstance(selected, dict) else {}


def _values(raw: Mapping[str, Any]) -> dict[str, str]:
    values = raw.get("values")
    return (
        {str(key): "" if value is None else str(value) for key, value in values.items()}
        if isinstance(values, dict)
        else {}
    )


def _git_settings(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    selected = raw.get("git")
    return selected if isinstance(selected, dict) else {}


def _missing(values: Mapping[str, str], keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        key
        for key in keys
        if not str(values.get(key, "")).strip()
        or str(values[key]).strip().lower().startswith("your-")
    )


def inspect(repo: Path) -> Result[dict[str, Any]]:
    repo = repo.resolve()
    if not repo.is_dir():
        return err("project_missing", f"project directory does not exist: {repo}")

    def describe(raw: dict[str, Any]) -> Result[dict[str, Any]]:
        current_workflow = _workflow_snapshot(repo)
        selected = _selection(raw, "tracker")
        manifest = registry.find(
            repo, str(selected.get("name", "")), str(selected.get("source", "shipped"))
        )
        tracker_missing = (
            _missing(_values(selected), manifest.value.required_settings)
            if isinstance(manifest, Ok)
            else ("tracker",)
        )
        local_storage = (
            local_tracker.describe(repo, manifest.value)
            if isinstance(manifest, Ok) and selected.get("name") == "local"
            else {}
        )
        current_scm = _selection(raw, "scm")
        source = current_scm or {"name": "local", "values": {}}
        scm_name = str(source.get("name", ""))
        scm_missing = (
            _missing(_values(source), scm.REQUIRED_VALUES[scm_name])
            if scm_name in scm.REQUIRED_VALUES
            else ()
            if scm_name == "local"
            else ("scm",)
        )
        missing = (
            *(f"tracker.{item}" for item in tracker_missing),
            *(
                ("tracker.storage",)
                if local_storage and not local_storage["ready"]
                else ()
            ),
            *(f"scm.{item}" for item in scm_missing),
            *(
                ("git.base_branch",)
                if scm_name != "local"
                and not _git_settings(raw).get("base_branch")
                and not inferred_base(repo)
                else ()
            ),
            *(("artifacts_path",) if not raw.get("artifacts_path") else ()),
        )
        return bind(
            preferences.language_for(repo),
            lambda language: fmap(
                preferences.language_confirmed(repo),
                lambda language_confirmed: {
                    "status": "ready"
                    if raw and not missing and isinstance(settings.parse(raw), Ok)
                    else "incomplete"
                    if raw
                    else "missing",
                    "language": language,
                    "handoff": _handoff(repo, raw, current_workflow),
                    "language_confirmed": language_confirmed,
                    "trackers": [
                        {
                            "name": item.name,
                            "label": item.label,
                            "required_values": list(item.required_settings),
                        }
                        for item in registry.usable(repo)
                    ],
                    "current_tracker": selected,
                    "current_scm": current_scm,
                    "tracker_storage": local_storage,
                    "repository": _repository_snapshot(repo),
                    "workflow": current_workflow,
                    "missing": list(missing),
                },
            ),
        )

    return bind(_raw(repo), describe)


def prepare_local_tracker(repo: Path) -> Result[dict[str, object]]:
    loaded = settings.load(repo)
    return bind(
        loaded,
        lambda chosen: bind(
            require(
                chosen.tracker.name == "local",
                "invalid_request",
                "the selected tracker is not local",
            ),
            lambda _: bind(
                registry.selected(repo, loaded),
                lambda active: local_tracker.prepare(repo, active.manifest),
            ),
        ),
    )


def _merged_selection(
    existing: Mapping[str, Any], name: str, values: Mapping[str, str]
) -> dict[str, Any]:
    return {
        "name": name,
        **(
            {"source": existing["source"]}
            if name == existing.get("name") and "source" in existing
            else {}
        ),
        "values": {
            **(_values(existing) if name == existing.get("name") else {}),
            **values,
        },
    }


def propose(
    repo: Path,
    tracker_name: str = "",
    tracker_values: Mapping[str, str] | None = None,
    scm_name: str = "",
    scm_values: Mapping[str, str] | None = None,
    artifacts_path: str = "",
    base_branch: str = "",
) -> Result[dict[str, Any]]:
    def candidate(raw: dict[str, Any]) -> Result[dict[str, Any]]:
        old_tracker = _selection(raw, "tracker")
        old_scm = _selection(raw, "scm") or {"name": "local", "values": {}}
        chosen_tracker = tracker_name or str(old_tracker.get("name", ""))
        chosen_scm = scm_name or str(old_scm.get("name", ""))
        chosen_base = (
            base_branch
            or _git_settings(raw).get("base_branch", "")
            or (inferred_base(repo) if chosen_scm != "local" else "")
        )
        revised = {
            **raw,
            "schemaVersion": 1,
            "tracker": _merged_selection(
                old_tracker, chosen_tracker, tracker_values or {}
            ),
            "scm": _merged_selection(old_scm, chosen_scm, scm_values or {}),
            "branch_template": raw.get("branch_template", "feature/{key}-{slug}"),
            "artifacts_path": artifacts_path or raw.get("artifacts_path", ""),
            "git": {
                **_git_settings(raw),
                **({"base_branch": chosen_base} if chosen_base else {}),
            },
        }
        return bind(
            require(
                bool(revised["artifacts_path"]),
                "setup_missing",
                "choose where plans and drafts will be stored",
            ),
            lambda _: bind(
                require(
                    chosen_scm == "local" or bool(chosen_base),
                    "setup_missing",
                    "choose the repository base branch",
                ),
                lambda _: bind(
                    settings.parse(revised),
                    lambda chosen: bind(
                        registry.selected(repo, Ok(chosen)),
                        lambda _: bind(
                            require(
                                chosen_scm == "local"
                                or chosen_scm in scm.REQUIRED_VALUES
                                and not _missing(
                                    _values(revised["scm"]),
                                    scm.REQUIRED_VALUES.get(chosen_scm, ()),
                                ),
                                "setup_missing",
                                "source-control provider and its required values are missing",
                            ),
                            lambda _: Ok(revised),
                        ),
                    ),
                ),
            ),
        )

    return bind(_raw(repo), candidate)


def digest(candidate: Mapping[str, Any]) -> str:
    encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _source_digest(repo: Path, current: Mapping[str, Any]) -> str:
    return digest({"exists": settings.path(repo).is_file(), "settings": dict(current)})


def review(repo: Path, **choices: Any) -> Result[dict[str, Any]]:
    return bind(
        _raw(repo),
        lambda original: fmap(
            propose(repo, **choices),
            lambda candidate: {
                "candidate": candidate,
                "digest": digest(candidate),
                "source_digest": _source_digest(repo, original),
            },
        ),
    )


def apply(
    repo: Path,
    candidate: Mapping[str, Any],
    approved_digest: str,
    source_digest: str,
) -> Result[Path]:
    return bind(
        require(
            digest(candidate) == approved_digest,
            "setup_changed",
            "the reviewed settings changed; show the new proposal before applying it",
        ),
        lambda _: bind(
            _raw(repo),
            lambda current: bind(
                require(
                    _source_digest(repo, current) == source_digest,
                    "setup_changed",
                    "repository settings changed after review; show a new proposal",
                ),
                lambda _: bind(
                    settings.parse(candidate),
                    lambda chosen: bind(
                        registry.selected(repo, Ok(chosen)),
                        lambda _: bind(
                            attempt(
                                lambda: _write(repo, candidate),
                                "setup_unwritable",
                                str(settings.path(repo)),
                                OSError,
                                subprocess.TimeoutExpired,
                            ),
                            lambda file: (
                                fmap(prepare_local_tracker(repo), lambda _: file)
                                if chosen.tracker.name == "local"
                                else Ok(file)
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _write(repo: Path, candidate: Mapping[str, Any]) -> Path:
    state.ensure_local_exclude(repo)
    target = settings.path(repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    return settings.write_reviewed_setup(target, candidate)
