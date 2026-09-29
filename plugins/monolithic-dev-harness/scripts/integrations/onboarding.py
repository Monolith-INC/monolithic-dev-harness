"""Bring a tracker the harness does not ship into a repository, for a person to review and trust.

    stage   copy a folder (tracker.json + adapter.py + references) into .harness/trackers/<name>/,
            with the values its settings need (organization, project, ...) kept in values.json
    show    everything a person needs to decide: what it writes, how it links, what it runs,
            its files and values, and how to ask the user
    select  make a trusted tracker the repository's tracker, with its staged values

Staging checks the folder against the contract first and refuses links, which could pull files
from outside the folder into the repository. Nothing here trusts or selects a tracker on its own:
the hooks do, only after the user clicks Trust or Use it on a question about it (or, in Cursor,
replies with its short id). The values live inside the folder, so trusting it covers them too.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

from core.result import Ok, Result, attempt, bind, err, require
from harness import settings

from . import registry, trust
from .contracts import Manifest

VALUES = "values.json"


def stage(
    repo: Path, source: Path, values: Mapping[str, str] | None = None
) -> Result[Path]:
    links = (
        tuple(path for path in source.rglob("*") if path.is_symlink())
        if source.is_dir()
        else ()
    )
    return bind(
        require(source.is_dir(), "invalid_tracker", f"{source} is not a folder"),
        lambda _: bind(
            require(
                not links,
                "invalid_tracker",
                f"the folder holds links ({links[0].name if links else ''}); copy real files in",
            ),
            lambda _: bind(
                registry.read_manifest(source, "onboarded"),
                lambda manifest: bind(
                    bind(
                        _known_values(manifest, dict(values or {})),
                        lambda known: _complete(manifest, known),
                    ),
                    lambda known: bind(
                        _copy(repo, source, manifest),
                        lambda folder: _write_values(folder, known),
                    ),
                ),
            ),
        ),
    )


def _copy(repo: Path, source: Path, manifest: Manifest) -> Result[Path]:
    destination = repo / registry.ONBOARDED_RELATIVE_PATH / manifest.name
    shipped = registry.SHIPPED_ROOT / manifest.name
    return bind(
        require(
            not shipped.exists(),
            "tracker_exists",
            f"{manifest.name!r} is a shipped tracker; give the onboarded one its own name",
        ),
        lambda _: bind(
            require(
                not destination.exists(),
                "tracker_exists",
                f"{destination} already exists; remove it to stage again",
            ),
            lambda _: attempt(
                lambda: Path(shutil.copytree(source, destination, symlinks=True)),
                "unwritable",
                f"could not copy into {destination}",
                OSError,
            ),
        ),
    )


def _known_values(manifest: Manifest, values: dict[str, str]) -> Result[dict[str, str]]:
    unknown = sorted(key for key in values if key not in manifest.settings)
    return (
        Ok(values)
        if not unknown
        else err(
            "invalid_settings",
            f"{manifest.name} takes no setting named {unknown}; it takes {list(manifest.settings)}",
        )
    )


def _write_values(folder: Path, values: dict[str, str]) -> Result[Path]:
    def write() -> Path:
        (folder / VALUES).write_text(
            json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return folder

    return attempt(write, "unwritable", f"could not write {folder / VALUES}", OSError)


def staged_values(folder: Path) -> dict[str, str]:
    """The values staged with the tracker; none when it was staged without any."""
    try:
        raw = json.loads((folder / VALUES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return (
        {str(key): str(value) for key, value in raw.items()}
        if isinstance(raw, dict)
        else {}
    )


def staged(repo: Path) -> tuple[Manifest, ...]:
    """Every onboarded folder whose manifest reads, trusted or not."""
    root = repo / registry.ONBOARDED_RELATIVE_PATH
    folders = sorted(path.parent for path in root.glob(f"*/{registry.MANIFEST}"))
    return tuple(
        result.value
        for result in (
            registry.read_manifest(folder, "onboarded") for folder in folders
        )
        if isinstance(result, Ok)
    )


def named_in(repo: Path, text: str) -> str | None:
    """The one tracker a question names, by label or name; None when it names none or several.

    Candidates are the staged trackers and any tracker the user still trusts (so trust can be
    withdrawn after its folder is gone). When one match lies inside a longer one ("Acme" inside
    "Acme Boards"), the longer one is meant.
    """
    words = {
        **{name: (name,) for name in trust.trusted_names(repo)},
        **{manifest.name: (manifest.label, manifest.name) for manifest in staged(repo)},
    }
    hits = {
        name: max(found, key=len)
        for name, candidates in words.items()
        if (
            found := [
                word
                for word in candidates
                if re.search(
                    rf"(?<![\w-]){re.escape(word)}(?![\w-])", text, re.IGNORECASE
                )
            ]
        )
    }
    longest = [
        name
        for name, word in hits.items()
        if not any(
            other != word and word.lower() in other.lower() for other in hits.values()
        )
    ]
    return longest[0] if len(longest) == 1 else None


def by_short_id(repo: Path, short: str) -> tuple[Manifest, str] | None:
    """The staged tracker, and its digest, whose current version has this short reply id."""
    versions = ((manifest, trust.digest(manifest.root)) for manifest in staged(repo))
    return next(
        (
            (manifest, digest)
            for manifest, digest in versions
            if trust.short_id(manifest.name, digest) == short.upper()
        ),
        None,
    )


def select(repo: Path, name: str) -> Result[str]:
    """Make a trusted onboarded tracker the repository's tracker, with its staged values."""
    folder = repo / registry.ONBOARDED_RELATIVE_PATH / name
    return bind(
        require(
            trust.is_trusted(repo, name, folder),
            "untrusted_tracker",
            f"the {name} tracker is not trusted as it reads now; ask the user to trust it first",
        ),
        lambda _: bind(
            registry.read_manifest(folder, "onboarded"),
            lambda manifest: bind(
                _complete(manifest, staged_values(folder)),
                lambda values: bind(
                    settings.write_tracker(
                        repo, {"name": name, "source": "onboarded", "values": values}
                    ),
                    lambda _: Ok(manifest.label),
                ),
            ),
        ),
    )


def _complete(manifest: Manifest, values: dict[str, str]) -> Result[dict[str, str]]:
    """Every value the tracker requires, non-blank; checked when staging, and again on select."""
    missing = [
        key for key in manifest.required_settings if not values.get(key, "").strip()
    ]
    return (
        Ok(values)
        if not missing
        else err(
            "invalid_settings",
            f"the {manifest.name} tracker needs a value for {missing}; stage it with "
            + " ".join(f"--value {key}=..." for key in missing),
        )
    )


def show(repo: Path, name: str) -> Result[str]:
    folder = repo / registry.ONBOARDED_RELATIVE_PATH / name
    return bind(
        require(
            folder.is_dir(),
            "unknown_tracker",
            f"no onboarded tracker named {name!r}; stage it first",
        ),
        lambda _: bind(
            registry.read_manifest(folder, "onboarded"),
            lambda manifest: Ok(_summary(repo, manifest)),
        ),
    )


def _summary(repo: Path, manifest: Manifest) -> str:
    digest = trust.digest(manifest.root)
    trusted = trust.is_trusted(repo, manifest.name, manifest.root)
    files = tuple(
        sorted(
            path.relative_to(manifest.root).as_posix()
            for path in manifest.root.rglob("*")
            if path.is_file()
        )
    )
    lines = (
        f"Tracker {manifest.name}: {manifest.label}",
        f"  documented at: {manifest.document['docs']}",
        f"  runs: {_runs(manifest, repo)}",
        f"  writes (need approval): server {manifest.writes.server or '-'}, tools {list(manifest.writes.tools)}",
        f"  ids: {manifest.ids.pattern}; branch key: {manifest.ids.branch_key}",
        f"  mentions link items: {manifest.ids.mentions_link}; forms: {list(manifest.ids.mention)}",
        f"  planning reads: {[reply.key for reply in manifest.planning] or 'its own files'}",
        f"  settings: {list(manifest.settings)} (required: {list(manifest.required_settings)})",
        f"  files: {list(files)}",
        f"  values: {_values_line(staged_values(manifest.root))}",
        f"  digest: {digest}",
        f"  trusted as it reads now: {'yes' if trusted else 'no'}",
        "",
        "Walk the user through this and adapter.py in full: the adapter runs inside the harness.",
        'Then ask one question that names the tracker, with the options "Trust" and "Not now",',
        f'for example: "Trust the {_phrase(manifest.label)} as I just described it?"',
        'If they trust it, ask a second question with the options "Use it" and',
        f'"Keep the current one", for example: "Use {manifest.label} as this project\'s tracker now?"',
        "The harness records each click; you cannot trust or select a tracker yourself.",
        f"In Cursor, which has no buttons, the user replies: approve {trust.short_id(manifest.name, digest)}",
        f"and then, to use it: use {trust.short_id(manifest.name, digest)}",
    )
    return "\n".join(lines)


def _phrase(label: str) -> str:
    return label if label.lower().endswith("tracker") else f"{label} tracker"


def _values_line(values: Mapping[str, str]) -> str:
    return (
        ", ".join(f"{key} = {value}" for key, value in sorted(values.items())) or "none"
    )


def _runs(manifest: Manifest, repo: Path) -> str:
    match manifest.connection.get("kind"):
        case "mcp":
            command, args = registry.connection_command(
                manifest, {key: f"<{key}>" for key in manifest.settings}, repo
            )
            return " ".join((command, *args))
        case _:
            return "nothing; its adapter runs inside the harness"
