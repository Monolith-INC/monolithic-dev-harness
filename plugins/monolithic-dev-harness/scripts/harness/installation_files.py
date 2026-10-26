"""Filesystem boundaries and fingerprint-checked installation edits."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, attempt
from host_adapters.installation_contract import ProjectAsset

MARKER = "monolithic-dev-harness"
BEGIN = "# BEGIN monolithic-dev-harness\n"
END = "# END monolithic-dev-harness\n"
_ABSENT = object()


def _read(path: Path) -> str | None:
    return path.read_text() if path.is_file() else None


def _atomic(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".harness-new")
    match temporary.exists() or temporary.is_symlink():
        case True:
            raise ValueError(f"pending write already exists: {temporary}")
        case False:
            with os.fdopen(
                os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    path.stat().st_mode & 0o777 if path.exists() else 0o600,
                ),
                "w",
                encoding="utf-8",
            ) as stream:
                stream.write(text)
            temporary.replace(path)
            return path


def _safe(path: Path, project: Path) -> Path:
    match (
        path.is_relative_to(project) and ".." not in path.parts,
        any(
            parent.is_symlink()
            for parent in (path, *path.parents)
            if parent != project and parent.is_relative_to(project)
        ),
    ):
        case True, False:
            return path
        case _:
            raise ValueError(f"asset path escapes project or crosses a symlink: {path}")


def _record(asset: ProjectAsset, project: Path, previous: dict[str, dict]) -> dict:
    match asset.kind:
        case "symlink":
            match asset.path.is_symlink(), asset.path.exists():
                case True, _ if asset.path.readlink() == asset.target:
                    _safe(asset.path.parent, project)
                    return previous.get(
                        str(asset.path),
                        {
                            "path": str(asset.path),
                            "kind": "symlink",
                            "target": str(asset.target),
                        },
                    )
                case False, False:
                    _safe(asset.path, project)
                    return {
                        "path": str(asset.path),
                        "kind": "symlink",
                        "target": str(asset.target),
                    }
                case _:
                    raise ValueError(f"unrelated asset already exists: {asset.path}")
        case "file" | "executable":
            _safe(asset.path, project)
            _file_collision(asset, previous)
            match _tracked(asset.path, project):
                case True:
                    raise ValueError(
                        f"local installation cannot modify a tracked file: {asset.path}; choose user scope or remove it from version control yourself"
                    )
                case False:
                    return {
                        "path": str(asset.path),
                        "kind": asset.kind,
                        "before": _restore(previous[str(asset.path)])[1]
                        if str(asset.path) in previous
                        else _read(asset.path),
                        "after": asset.text,
                    }
        case _:
            raise ValueError("unknown installation asset kind")


def _file_collision(asset: ProjectAsset, previous: dict) -> bool:
    match asset.path.exists(), asset.path.is_file():
        case True, False:
            raise ValueError(
                f"unrelated directory occupies an asset path: {asset.path}"
            )
        case True, True if (
            (asset.kind == "executable" or asset.path.parent.name == "agents")
            and str(asset.path) not in previous
            and "# managed by monolithic-dev-harness"
            not in asset.path.read_text().splitlines()[:3]
        ):
            raise ValueError(
                f"unrelated file occupies a managed asset name: {asset.path}"
            )
        case _:
            return True


def _tracked(path: Path, project: Path) -> bool:
    return (
        bool(shutil.which("git"))
        and subprocess.run(
            (
                "git",
                "-C",
                str(project),
                "ls-files",
                "--error-unmatch",
                "--",
                str(path.relative_to(project)),
            ),
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def _apply(record: dict) -> Path:
    path = Path(record["path"])
    match record["kind"]:
        case "symlink":
            path.parent.mkdir(parents=True, exist_ok=True)
            match path.is_symlink():
                case True:
                    return path
                case False:
                    path.symlink_to(record["target"])
                    return path
        case _:
            return _write_asset(record)


def _write_asset(record: dict) -> Path:
    path = _atomic(Path(record["path"]), record["after"])
    match record["kind"]:
        case "executable":
            path.chmod(0o700)
            return path
        case _:
            return path


def _exclude_path(project: Path) -> Path | None:
    match shutil.which("git"):
        case None:
            return None
        case _:
            result = subprocess.run(
                (
                    "git",
                    "-C",
                    str(project),
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-path",
                    "info/exclude",
                ),
                capture_output=True,
                text=True,
                check=False,
            )
            return Path(result.stdout.strip()) if result.returncode == 0 else None


def _exclude_record(project: Path, paths: tuple[Path, ...]) -> dict | None:
    from harness.installation_ignore import update

    match _exclude_path(project):
        case None:
            return None
        case Path() as path:
            before = _read(path) or ""
            return {
                "path": str(path),
                "after": _require_ok(update(before, project, paths)),
            }


def _exclude_restore(
    project: Path, record: dict | None
) -> tuple[tuple[Path, str], ...]:
    from harness.installation_ignore import remove

    match record:
        case None:
            return ()
        case {"path": str() as recorded} if (
            Path(recorded) == _exclude_path(project) and not Path(recorded).is_symlink()
        ):
            return (
                (
                    Path(recorded),
                    _require_ok(remove(_read(Path(recorded)) or "", project)),
                ),
            )
        case _:
            raise ValueError(
                "Git exclude location changed; inspect the installation receipt"
            )


def _revert(current: Any, before: Any, after: Any) -> Any:
    match current in (after, before):
        case True:
            return before
        case False:
            match current, after:
                case dict(), dict():
                    values = tuple(
                        (
                            key,
                            _revert(
                                current.get(key, _ABSENT),
                                before.get(key, _ABSENT)
                                if isinstance(before, dict)
                                else _ABSENT,
                                after[key],
                            )
                            if key in after
                            and (
                                not isinstance(before, dict)
                                or before.get(key, _ABSENT) != after[key]
                            )
                            else value,
                        )
                        for key, value in current.items()
                    )
                    return {key: value for key, value in values if value is not _ABSENT}
                case list(), list():
                    added = tuple(
                        value
                        for value in after
                        if not isinstance(before, list) or value not in before
                    )
                    match all(isinstance(value, dict) for value in after) and (
                        all(value in current for value in added)
                        or not any(
                            _owned_reference(value)
                            for value in current
                            if value not in after
                        )
                    ):
                        case True:
                            return [value for value in current if value not in added]
                        case False:
                            raise ValueError(
                                "owned list entries changed; inspect receipt before repair"
                            )
                case _:
                    raise ValueError(
                        "owned setting changed; inspect receipt before repair"
                    )


def _owned_reference(value: Any) -> bool:
    match value:
        case str():
            return MARKER in value
        case dict():
            return any(_owned_reference(item) for item in value.values())
        case list():
            return any(_owned_reference(item) for item in value)
        case _:
            return False


def _subset(current: Any, expected: Any) -> bool:
    return (
        current == expected
        or isinstance(current, dict)
        and isinstance(expected, dict)
        and all(
            key in expected and _subset(value, expected[key])
            for key, value in current.items()
        )
    )


def _restore_toml(text: str, record: dict) -> str:
    import tomllib

    original = record["before"] or ""
    match text.count(BEGIN), text.count(END):
        case 0, 0 if _revert(
            tomllib.loads(text), tomllib.loads(original), tomllib.loads(record["after"])
        ) == tomllib.loads(text):
            return text
        case 1, 1 if text.index(BEGIN) < text.index(END):
            actual = text.split(BEGIN, 1)[1].split(END, 1)[0]
            expected = record["after"].split(BEGIN, 1)[1].split(END, 1)[0]
            match _subset(tomllib.loads(actual), tomllib.loads(expected)):
                case True:
                    old_block = (
                        BEGIN + original.split(BEGIN, 1)[1].split(END, 1)[0] + END
                        if BEGIN in original
                        else ""
                    )
                    return text.replace(BEGIN + actual + END, old_block)
                case False:
                    raise ValueError("owned TOML block changed")
        case _:
            raise ValueError("owned TOML block changed")


def _restore(record: dict) -> tuple[Path, str | None]:
    path = Path(record["path"])
    match record["kind"]:
        case "symlink":
            match (
                path.is_symlink() and str(path.readlink()) == record["target"],
                path.exists() or path.is_symlink(),
            ):
                case (True, _) | (False, False):
                    return path, None
                case _:
                    raise ValueError(f"owned link changed: {path}")
        case _:
            match path.is_symlink():
                case True:
                    raise ValueError(f"owned file was replaced by a symlink: {path}")
                case False:
                    pass
            current = _read(path)
            match current:
                case None:
                    return path, None
                case text if text == record["after"]:
                    return path, record["before"]
                case text if path.suffix in (".json", ".jsonc"):
                    from harness.installation_inventory import json_document

                    restored = _revert(
                        json_document(text),
                        json_document(record["before"] or "{}"),
                        json_document(record["after"]),
                    )
                    return path, (
                        json.dumps(restored, indent=2) + "\n"
                    ) if restored or record["before"] is not None else None
                case text if path.suffix == ".toml" and BEGIN in record["after"]:
                    return path, _restore_toml(text, record)
                case _:
                    raise ValueError(f"owned file changed: {path}")


def _remove(path: Path, text: str | None) -> Path:
    match text:
        case None:
            path.unlink(missing_ok=True)
            return path
        case _:
            return _atomic(path, text)


def _safe_receipt_path(path: Path, project: Path) -> Path:
    # A final symlink is an owned asset, but its ancestors must stay inside scope.
    _safe(path.parent, project)
    match path.is_relative_to(project):
        case True:
            return path
        case False:
            raise ValueError("receipt asset escapes project")


def _serialize(value: Any) -> Any:
    from dataclasses import asdict, is_dataclass

    match value:
        case Path():
            return str(value)
        case tuple() | list():
            return [_serialize(item) for item in value]
        case dict():
            return {key: _serialize(item) for key, item in value.items()}
        case _ if is_dataclass(value):
            return _serialize(asdict(value))
        case _:
            return value


def _fingerprint(component) -> bool:
    match component.path.is_symlink():
        case True:
            return (
                not component.digest
                or hashlib.sha256(os.readlink(component.path).encode()).hexdigest()
                == component.digest
            )
        case False:
            match component.path.is_file():
                case True:
                    return (
                        bool(component.digest)
                        and hashlib.sha256(component.path.read_bytes()).hexdigest()
                        == component.digest
                    )
                case False:
                    return (
                        (
                            hashlib.sha256(
                                (
                                    component.path
                                    / component.detail.removeprefix("manifest:")
                                ).read_bytes()
                            ).hexdigest()
                            == component.digest
                        )
                        if component.detail.startswith("manifest:")
                        else component.path.is_dir()
                    )


def _repair_writes(repairs: tuple) -> tuple[tuple[Path, str], ...]:
    from harness.installation_cleanup import rewrite_document

    paths = tuple(
        dict.fromkeys(
            repair.component.path
            for repair in repairs
            if repair.action == "remove_entry"
        )
    )
    return tuple(
        (
            path,
            _require_ok(
                rewrite_document(
                    path.read_text(),
                    path.suffix,
                    tuple(
                        dict.fromkeys(
                            repair.component.selector
                            for repair in repairs
                            if repair.action == "remove_entry"
                            and repair.component.path == path
                        )
                    ),
                )
            ),
        )
        for path in paths
    )


def _require_ok(result):
    match result:
        case Ok(value):
            return value
        case Err(failure):
            raise ValueError(f"{failure.code}: {failure.message}")


def apply_repairs(repairs: tuple, context) -> Result[tuple[Path, ...]]:
    return attempt(
        lambda: _apply_repairs(repairs, context),
        "repair_failed",
        "repair preflight or application failed",
        OSError,
        ValueError,
    )


def _apply_repairs(repairs: tuple, context) -> tuple[Path, ...]:
    import shutil

    from harness.installation_inventory import scan

    current = scan(context)
    match all(
        repair.component in current.components
        and repair.action in ("remove_entry", "remove_path", "archive_backup")
        and (
            repair.component.owned
            or (repair.action == "archive_backup" and repair.component.kind == "backup")
        )
        and _fingerprint(repair.component)
        and _safe_removal(repair.component.path, context)
        for repair in repairs
    ):
        case True:
            writes = _repair_writes(repairs)
            archives = tuple(
                (repair.component.path, _archive_destination(repair.component, context))
                for repair in repairs
                if repair.action == "archive_backup"
            )
            tuple(_atomic(path, text) for path, text in writes)
            tuple(_archive(source, destination) for source, destination in archives)
            removals = tuple(
                dict.fromkeys(
                    repair.component.path
                    for repair in repairs
                    if repair.action == "remove_path"
                )
            )
            # Never follow a final symlink or delete a parent of another scope/project.
            tuple(
                path.unlink(missing_ok=True)
                if path.is_symlink() or path.is_file()
                else shutil.rmtree(path)
                for path in sorted(
                    removals, key=lambda value: len(value.parts), reverse=True
                )
                if path.exists() or path.is_symlink()
            )
            return (
                tuple(path for path, _ in writes)
                + removals
                + tuple(destination for _, destination in archives)
            )
        case _:
            raise ValueError(
                "installation inventory changed or has uninspected locations; rescan before applying repairs"
            )


def _archive_destination(component, context) -> Path:
    root = (
        next(
            (
                project / ".harness/recovery"
                for project in context.projects
                if component.scope == "local" and component.path.is_relative_to(project)
            ),
            None,
        )
        if component.scope == "local"
        else context.home / ".local/state/monolithic-dev-harness/recovery"
    )
    match root:
        case Path():
            destination = root / (
                hashlib.sha256(str(component.path).encode()).hexdigest()[:16]
                + "-"
                + component.path.name
            )
            match (
                destination.exists()
                or destination.is_symlink()
                or not _safe_removal(destination, context)
            ):
                case True:
                    raise ValueError(
                        "backup archive destination exists or crosses a symlink; inspect recovery storage"
                    )
                case False:
                    return destination
        case None:
            raise ValueError("backup is outside the selected project scopes")


def _archive(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.move(str(source), str(destination))
    destination.chmod(0o600)
    return destination


def _safe_removal(path: Path, context) -> bool:
    return (
        path.is_absolute()
        and ".." not in path.parts
        and not (path / ".git").exists()
        and not any(
            path == root or path in root.parents
            for root in (context.home, *context.projects)
        )
        and not any(parent.is_symlink() for parent in path.parents)
    )


def check_package_destination(path: Path) -> bool:
    from harness.installation_inventory import _package_manifest

    match (
        path.is_symlink() or any(parent.is_symlink() for parent in path.parents),
        path.exists(),
    ):
        case True, _:
            raise ValueError(f"package destination is a symlink: {path}")
        case False, False:
            return True
        case False, True if (
            path.is_dir()
            and not (path / ".git").exists()
            and (not any(path.iterdir()) or _package_manifest(path) is not None)
        ):
            return True
        case _:
            raise ValueError(
                f"unrelated files occupy the package destination: {path}; preserve them and choose a dedicated installation directory"
            )


def remove_empty_directory(path: Path) -> Path | None:
    try:
        match path.is_dir(), path.is_symlink():
            case True, False if not any(path.iterdir()):
                path.rmdir()
                return path
            case _:
                return None
    except OSError:
        return None
