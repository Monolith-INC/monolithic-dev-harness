"""Inspect and prepare reviewed first-run settings without assuming a tracker."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, require
from harness import preferences, settings, state
from integrations import registry, scm

_GITHUB = re.compile(r"(?:github\.com[:/])(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$")
_AZURE_HTTP = re.compile(
    r"dev\.azure\.com/(?P<organization>[^/]+)/(?P<project>[^/]+)/_git/(?P<repository>[^/]+)"
)
_AZURE_SSH = re.compile(
    r"ssh\.dev\.azure\.com:v3/(?P<organization>[^/]+)/(?P<project>[^/]+)/(?P<repository>[^/]+)"
)


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


def inferred_scm(repo: Path) -> dict[str, Any]:
    url = _git(repo, "remote", "get-url", "origin")
    match _GITHUB.search(url), _AZURE_HTTP.search(url) or _AZURE_SSH.search(url):
        case re.Match() as found, _:
            return {
                "name": "github",
                "values": {
                    "owner": found.group("owner"),
                    "repo": found.group("repo"),
                },
            }
        case _, re.Match() as found:
            return {"name": "azure-repos", "values": found.groupdict()}
        case _:
            return {}


def inferred_base(repo: Path) -> str:
    remote = _git(
        repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
    )
    return remote.removeprefix("origin/") or _git(repo, "branch", "--show-current")


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
    def describe(raw: dict[str, Any]) -> Result[dict[str, Any]]:
        selected = _selection(raw, "tracker")
        manifest = registry.find(
            repo, str(selected.get("name", "")), str(selected.get("source", "shipped"))
        )
        tracker_missing = (
            _missing(_values(selected), manifest.value.required_settings)
            if isinstance(manifest, Ok)
            else ("tracker",)
        )
        current_scm = _selection(raw, "scm")
        source = current_scm or inferred_scm(repo) or {"name": "local", "values": {}}
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
            *(f"scm.{item}" for item in scm_missing),
            *(
                ("git.base_branch",)
                if not _git_settings(raw).get("base_branch") and not inferred_base(repo)
                else ()
            ),
            *(("artifacts_path",) if not raw.get("artifacts_path") else ()),
        )
        return fmap(
            preferences.language(),
            lambda language: {
                "status": "ready"
                if raw and not missing and isinstance(settings.parse(raw), Ok)
                else "incomplete"
                if raw
                else "missing",
                "language": language,
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
                "inferred_scm": inferred_scm(repo),
                "inferred_base_branch": inferred_base(repo),
                "missing": list(missing),
            },
        )

    return bind(_raw(repo), describe)


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
        old_scm = (
            _selection(raw, "scm")
            or inferred_scm(repo)
            or {"name": "local", "values": {}}
        )
        chosen_tracker = tracker_name or str(old_tracker.get("name", ""))
        chosen_scm = scm_name or str(old_scm.get("name", ""))
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
                "base_branch": base_branch
                or _git_settings(raw).get("base_branch")
                or inferred_base(repo),
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
                    bool(revised["git"]["base_branch"]),
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
                        lambda _: attempt(
                            lambda: _write(repo, candidate),
                            "setup_unwritable",
                            str(settings.path(repo)),
                            OSError,
                            subprocess.TimeoutExpired,
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
