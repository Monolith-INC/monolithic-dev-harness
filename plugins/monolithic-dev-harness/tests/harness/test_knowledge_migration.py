"""Legacy migration is explicit, preserves history, and never overwrites a destination."""

import json
from pathlib import Path

from project_knowledge import freshness, migration, service

from core.result import Err, Ok
from harness import knowledge
from tests.settings_fixture import write_settings


def _legacy(repo: Path) -> Path:
    write_settings(repo)
    knowledge.initialize(repo)
    write_settings(repo, git={"base_branch": "develop"})
    knowledge.refresh(repo)
    return repo / ".harness/knowledge/stores/project"


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_migration_archives_all_legacy_bytes_and_retrieves_current_unit(
    tmp_path: Path,
) -> None:
    source = _legacy(tmp_path / "repo")
    before = _files(source)
    destination = tmp_path / "new-store"

    result = migration.migrate(source, destination)

    assert isinstance(result, Ok)
    assert _files(source) == before
    assert _files(destination / ".legacy") == before
    mapping = json.loads((destination / "migration-manifest.json").read_text())
    identifier = mapping["units"]["project/harness-settings"]["id"]
    assert identifier == "project/harness-settings"
    fetched = service.fetch(destination, identifier)
    assert isinstance(fetched, Ok)
    assert "harness-settings" in fetched.value
    assert "derived" in fetched.value
    assert isinstance(service.find(destination, "workflow"), Ok)
    assert ".harness/settings.json" in fetched.value
    assert freshness.verified_fresh(source.parents[3], destination)
    settings_path = source.parents[3] / ".harness/settings.json"
    settings_path.write_text(settings_path.read_text() + "\n", encoding="utf-8")
    assert not freshness.verified_fresh(source.parents[3], destination)


def test_migration_refuses_to_overwrite_existing_destination(tmp_path: Path) -> None:
    source = _legacy(tmp_path / "repo")
    destination = tmp_path / "new-store"
    destination.mkdir()
    marker = destination / "existing.txt"
    marker.write_text("keep this", encoding="utf-8")
    before = _files(source)

    result = migration.migrate(source, destination)

    assert isinstance(result, Err)
    assert _files(source) == before
    assert marker.read_text(encoding="utf-8") == "keep this"


def test_migration_rejects_source_symlinks_without_touching_data(
    tmp_path: Path,
) -> None:
    source = _legacy(tmp_path / "repo")
    (source / "unsafe.json").symlink_to(tmp_path / "missing")
    destination = tmp_path / "new-store"

    result = migration.migrate(source, destination)

    assert isinstance(result, Err)
    assert not destination.exists()
    assert (source / "unsafe.json").is_symlink()


def test_migration_rejects_a_revision_with_a_broken_digest(tmp_path: Path) -> None:
    source = _legacy(tmp_path / "repo")
    catalog = json.loads((source / "catalog.json").read_text())
    revision_id = catalog["units"]["project/harness-settings"]["current"]
    path = source / "revisions" / f"{revision_id.removeprefix('sha256:')}.json"
    revision = json.loads(path.read_text())
    revision["title"] = "Tampered"
    path.write_text(json.dumps(revision), encoding="utf-8")
    destination = tmp_path / "new-store"

    result = migration.migrate(source, destination)

    assert isinstance(result, Err)
    assert not destination.exists()
