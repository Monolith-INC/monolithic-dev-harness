from pathlib import Path

from core.result import Err, Ok
from harness.installation_ignore import remove, update


def value(result):
    assert isinstance(result, Ok)
    return result.value


def test_update_preserves_text_and_escapes_git_patterns(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "weird !#[ ]*?\\ "
    original = "# existing\nvalue  \n"

    rendered = value(update(original, project, (source,)))

    assert rendered.startswith(original)
    assert "/weird\\ \\!\\#\\[" in rendered
    assert "\\*\\?" in rendered
    assert "/.harness/install" not in rendered.splitlines()
    assert "/.harness/bin" not in rendered.splitlines()
    assert "/.harness/installation.json" in rendered


def test_update_is_idempotent_and_remove_preserves_outside_text(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    original = "keep\n"
    rendered = value(update(original, project, (project / "a.txt",)))

    assert value(update(rendered, project, (project / "a.txt",))) == rendered
    assert value(remove(rendered, project)) == original


def test_update_remove_restores_exact_line_endings(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    for original in ("", "foo", "foo\n", "foo\r\n"):
        rendered = value(update(original, project, (project / "a.txt",)))
        assert value(remove(rendered, project)) == original
        assert value(update(rendered, project, (project / "a.txt",))) == rendered


def test_rejects_outside_paths_and_malformed_or_repeated_blocks(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    assert isinstance(update("", project, (tmp_path / "outside",)), Err)
    malformed = "# >>> monolithic-dev-harness install excludes bad >>>\n"
    assert isinstance(remove(malformed, project), Err)
    repeated = value(update("", project, (project / "a",)))
    assert isinstance(remove(repeated + repeated, project), Err)


def test_remove_only_owns_the_matching_project_block(tmp_path: Path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    text = value(update("before\n", first, (first / "one",)))
    combined = text + value(update("other\n", second, (second / "two",)))

    removed = value(remove(combined, first))

    assert "# >>> monolithic-dev-harness install excludes" in removed
    assert "/two" in removed
    assert "before\n" in removed
