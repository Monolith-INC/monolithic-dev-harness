"""The pinned knowledge engine reads project units without modifying them."""

from pathlib import Path

from project_knowledge import present, service, stem, store

from core.result import Err, Ok


def _unit(root: Path) -> Path:
    unit = root / "2-structure" / "secrets.md"
    unit.parent.mkdir(parents=True)
    unit.write_text(
        "---\nid: project/secrets\ntitle: Storage\nprovenance: stated\n"
        "status: current\n---\n\n## Access\nSecrets belong in the vault.\n",
        encoding="utf-8",
    )
    return unit


def test_singular_finds_plural_and_does_not_change_store(tmp_path: Path) -> None:
    unit = _unit(tmp_path)
    before = unit.read_bytes()
    knowledge = store.KnowledgeStore(tmp_path)

    hits, guidance = knowledge.find("secret")

    assert hits and hits[0].unit_id == "project/secrets"
    assert guidance == {}
    assert unit.read_bytes() == before


def test_missing_query_gives_guidance_and_fetch_is_bounded(tmp_path: Path) -> None:
    _unit(tmp_path)
    knowledge = store.KnowledgeStore(tmp_path)

    hits, guidance = knowledge.find("no-such-term")
    result = knowledge.fetch("project/secrets", max_tokens=4)

    assert not hits and guidance
    assert result["truncated"]
    assert result["continuation"]


def test_normalize_english_and_portuguese_plurals() -> None:
    assert stem.normalize_token("SECRETS") == stem.normalize_token("secret")
    assert stem.normalize_token("políticas") == stem.normalize_token("politica")
    assert stem.normalize_token("funções") == stem.normalize_token("funcao")
    assert stem.normalize_token("categories") == stem.normalize_token("category")
    assert stem.normalize_token("stores") == stem.normalize_token("store")
    assert stem.normalize_token("features") == stem.normalize_token("feature")
    assert stem.normalize_token("boxes") == stem.normalize_token("box")
    assert stem.normalize_token("técnicas") == stem.normalize_token("técnico")
    assert stem.normalize_token("stores") == stem.normalize_token("store")
    assert stem.normalize_token("features") == stem.normalize_token("feature")


def test_duplicate_identifiers_report_an_error(tmp_path: Path) -> None:
    _unit(tmp_path)
    duplicate = tmp_path / "duplicate.md"
    duplicate.write_text(
        "---\nid: project/secrets\ntitle: Duplicate\nprovenance: stated\n---\n\nOther text.\n",
        encoding="utf-8",
    )

    assert isinstance(service.catalog(tmp_path), Err)


def test_ladder_displays_sources_matches_and_continuation(tmp_path: Path) -> None:
    _unit(tmp_path)
    knowledge = store.KnowledgeStore(tmp_path)
    hits, guidance = knowledge.find("secret")
    _, missing = knowledge.find("unknown")

    assert "project/secrets" in present.catalog(knowledge.catalog())
    assert "matched terms" in present.find("secret", hits, guidance)
    assert "Reformulate" in present.find("unknown", (), missing)
    assert "truncated" in present.fetch(
        knowledge.fetch("project/secrets", max_tokens=4)
    )
    assert "references" in present.links(
        "project/secrets", knowledge.links("project/secrets")
    )


def test_service_returns_results_and_typed_failures(tmp_path: Path) -> None:
    _unit(tmp_path)

    assert isinstance(service.catalog(tmp_path), Ok)
    assert isinstance(service.find(tmp_path, "secret"), Ok)
    assert isinstance(service.find(tmp_path, " "), Err)
    assert isinstance(service.fetch(tmp_path, "project/secrets"), Ok)
    assert isinstance(service.fetch(tmp_path, "project/secrets", max_tokens=-1), Err)
    assert isinstance(service.fetch(tmp_path, "missing"), Err)
    assert isinstance(service.links(tmp_path, "project/secrets"), Ok)


def test_store_does_not_read_a_symlink_outside_its_root(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("private data", encoding="utf-8")
    (root / "escaped.md").symlink_to(outside)

    result = service.catalog(root)

    assert isinstance(result, Ok)
    assert "escaped" not in result.value


def test_fetch_continuation_resumes_inside_long_first_line(tmp_path: Path) -> None:
    path = tmp_path / "unit.md"
    path.write_text("---\nid: unit\n---\n" + "x" * 33 + "\nend\n", encoding="utf-8")
    engine = store.KnowledgeStore(tmp_path)
    first = engine.fetch("unit", start_line=4, max_tokens=4)
    continuation = first["continuation"]
    second = engine.fetch(
        "unit",
        start_line=continuation["start_line"],
        start_column=continuation["start_column"],
        max_tokens=20,
    )

    assert first["content"] + second["content"] == "x" * 33 + "\nend"
