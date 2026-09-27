"""Bring a tracker the harness does not ship into a repository, for a person to review and trust.

    stage   copy a folder (tracker.json + adapter.py + references) into .harness/trackers/<name>/
    show    everything a person needs to decide: what it writes, how it links, what it runs,
            its files, and the exact line to type to trust it as it reads now

Staging checks the folder against the contract first and refuses links, which could pull files
from outside the folder into the repository. Nothing here trusts a tracker: only the user's typed
`harness trust-tracker <name> <digest>` does (see `trust.py`), and the settings select it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from core.result import Ok, Result, attempt, bind, require

from . import registry, trust
from .contracts import Manifest


def stage(repo: Path, source: Path) -> Result[Path]:
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
                lambda manifest: _copy(repo, source, manifest),
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
        f"  settings: {list(manifest.settings)} (required: {list(manifest.required_settings)})",
        f"  files: {list(files)}",
        f"  digest: {digest}",
        f"  trusted as it reads now: {'yes' if trusted else 'no'}",
        "",
        "Read adapter.py in full before trusting it: it runs inside the harness.",
        "To trust it exactly as it reads now, the user types this line themselves:",
        f"  harness trust-tracker {manifest.name} {digest[: trust.DIGEST_PREFIX_LENGTH]}",
        "Then a person selects it in .harness/settings.json:",
        f'  "tracker": {{"name": "{manifest.name}", "source": "onboarded", "values": {{...}}}}',
    )
    return "\n".join(lines)


def _runs(manifest: Manifest, repo: Path) -> str:
    match manifest.connection.get("kind"):
        case "mcp":
            command, args = registry.connection_command(
                manifest, {key: f"<{key}>" for key in manifest.settings}, repo
            )
            return " ".join((command, *args))
        case _:
            return "nothing; its adapter runs inside the harness"
