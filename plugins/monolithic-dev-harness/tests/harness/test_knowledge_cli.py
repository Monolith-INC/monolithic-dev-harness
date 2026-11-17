"""Knowledge roots use the selected project's validated settings."""

from pathlib import Path

import pytest

from harness import cli, knowledge, settings
from tests.settings_fixture import MINIMAL, write_settings


def test_configured_knowledge_root_is_project_relative(tmp_path: Path) -> None:
    chosen = settings.parse({**MINIMAL, "knowledge": {"root": "docs/knowledge"}}).value

    assert cli.knowledge_root(tmp_path, chosen) == tmp_path / "docs/knowledge"


def test_knowledge_root_defaults_to_artifacts_path(tmp_path: Path) -> None:
    chosen = settings.parse({**MINIMAL, "artifacts_path": "AI_Codex"}).value

    assert (
        cli.knowledge_root(tmp_path, chosen) == tmp_path / "AI_Codex/Project_Knowledge"
    )


def test_existing_project_keeps_legacy_revision_access(tmp_path: Path, capsys) -> None:
    write_settings(tmp_path)
    revision = knowledge.initialize(tmp_path)["revision"]

    result = cli.main(
        [
            "knowledge",
            "fetch",
            f"project/harness-settings@{revision}",
            "--repo",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert revision in capsys.readouterr().out


def test_explicit_markdown_project_reads_its_selected_store(
    tmp_path: Path, capsys
) -> None:
    write_settings(tmp_path, knowledge={"format": "markdown", "root": "docs/knowledge"})
    path = tmp_path / "docs/knowledge/unit.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nid: unit\nprovenance: stated\n---\n\n## Rules\nUseful rules\n"
    )

    result = cli.main(["knowledge", "find", "rules", "--repo", str(tmp_path)])

    assert result == 0
    assert "`unit#rules`" in capsys.readouterr().out


def test_markdown_project_rejects_legacy_writes(tmp_path: Path, capsys) -> None:
    write_settings(tmp_path, knowledge={"format": "markdown", "root": "docs/knowledge"})

    result = cli.main(["knowledge", "refresh", "--repo", str(tmp_path)])

    assert result != 0
    assert not (tmp_path / ".harness/knowledge/stores").exists()


def test_markdown_project_keeps_explicit_read_only_legacy_access(
    tmp_path: Path, capsys
) -> None:
    write_settings(tmp_path)
    revision = knowledge.initialize(tmp_path)["revision"]
    write_settings(tmp_path, knowledge={"format": "markdown", "root": "docs/knowledge"})

    result = cli.main(
        [
            "knowledge",
            "fetch",
            f"project/harness-settings@{revision}",
            "--repo",
            str(tmp_path),
            "--legacy",
        ]
    )

    assert result == 0
    assert revision in capsys.readouterr().out


def test_markdown_project_refuses_legacy_mutation_through_compatibility_flag(
    tmp_path: Path, capsys
) -> None:
    write_settings(tmp_path, knowledge={"format": "markdown", "root": "docs/knowledge"})

    result = cli.main(["knowledge", "refresh", "--repo", str(tmp_path), "--legacy"])

    assert result != 0
    assert "read-only" in capsys.readouterr().err
    assert not (tmp_path / ".harness/knowledge/stores").exists()


def test_migration_cli_requires_destination_and_preserves_legacy_source(
    tmp_path: Path, capsys
) -> None:
    write_settings(tmp_path)
    knowledge.initialize(tmp_path)
    source = tmp_path / ".harness/knowledge/stores/project"
    before = {
        str(path.relative_to(source)): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }

    missing_destination = cli.main(["knowledge", "migrate", "--repo", str(tmp_path)])
    assert missing_destination != 0
    assert "--destination" in capsys.readouterr().err

    result = cli.main(
        [
            "knowledge",
            "migrate",
            "--repo",
            str(tmp_path),
            "--destination",
            "new-store",
        ]
    )

    assert result == 0
    assert {
        str(path.relative_to(source)): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == before
    assert (tmp_path / "new-store/migration-manifest.json").is_file()
    assert settings.load(tmp_path).value.knowledge_format == "legacy"


@pytest.mark.parametrize("store_id", ("../../outside", "/tmp/outside"))
def test_migration_cli_rejects_escaping_store_ids(
    tmp_path: Path, capsys, store_id: str
) -> None:
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    marker = outside / "keep.txt"
    marker.write_text("preserve", encoding="utf-8")

    result = cli.main(
        [
            "knowledge",
            "migrate",
            "--repo",
            str(tmp_path),
            "--store",
            store_id,
            "--destination",
            "new-store",
        ]
    )

    assert result != 0
    assert "store id is invalid" in capsys.readouterr().err
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert not (tmp_path / "new-store").exists()


def test_migration_cli_rejects_symlinked_legacy_store_without_touching_target(
    tmp_path: Path, capsys
) -> None:
    stores = tmp_path / ".harness/knowledge/stores"
    stores.mkdir(parents=True)
    external = tmp_path / "external-store"
    external.mkdir()
    marker = external / "keep.txt"
    marker.write_text("preserve", encoding="utf-8")
    (stores / "project").symlink_to(external, target_is_directory=True)

    result = cli.main(
        [
            "knowledge",
            "migrate",
            "--repo",
            str(tmp_path),
            "--destination",
            "new-store",
        ]
    )

    assert result != 0
    assert "symbolic links" in capsys.readouterr().err
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert not (tmp_path / "new-store").exists()


def test_markdown_fetch_reports_continuation_and_rejects_other_store(
    tmp_path: Path, capsys
) -> None:
    write_settings(tmp_path, knowledge={"format": "markdown", "root": "docs/knowledge"})
    path = tmp_path / "docs/knowledge/unit.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nid: unit\n---\n" + "x" * 40)

    assert (
        cli.main(
            ["knowledge", "fetch", "unit", "--repo", str(tmp_path), "--max-tokens", "3"]
        )
        == 0
    )
    assert "Continue with start_line=" in capsys.readouterr().out
    assert (
        cli.main(["knowledge", "catalog", "--repo", str(tmp_path), "--store", "other"])
        != 0
    )
