import json
from types import SimpleNamespace

from harness.installation_doctor import preview, run


def _args(project, **changes):
    return SimpleNamespace(
        repo=str(project),
        project=[str(project)],
        scope="all",
        repair_id=[],
        apply_repairs=None,
        **changes,
    )


def test_doctor_reports_duplicates_and_applies_only_selected_entry(
    tmp_path, monkeypatch, capsys
):
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setenv("HOME", str(home))
    for base in (home, project):
        path = base / ".cursor/mcp.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "shared-effect": {
                            "command": "sh",
                            "args": ["/opt/monolithic-dev-harness/bin/harness-python"],
                        },
                        "foreign": {"command": "keep"},
                    }
                }
            )
        )
    report = preview((project,))
    assert any(issue["code"] == "duplicate-components" for issue in report["findings"])
    selected = next(
        repair["id"]
        for repair in report["repairs"]
        if repair["component"]["scope"] == "user"
    )
    args = _args(project)
    args.repair_id = [selected]
    assert run(args) == 1
    plan = json.loads(capsys.readouterr().out)
    args.apply_repairs = plan["selection_digest"]
    assert run(args) == 0
    capsys.readouterr()
    assert json.loads((home / ".cursor/mcp.json").read_text()) == {
        "mcpServers": {"foreign": {"command": "keep"}}
    }
    assert "shared-effect" in (project / ".cursor/mcp.json").read_text()


def test_doctor_refuses_stale_selection_without_writes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    args = _args(tmp_path)
    args.repair_id = ["not-current"]
    args.apply_repairs = "stale"
    before = tuple(tmp_path.rglob("*"))
    assert run(args) == 2
    assert "stale" in capsys.readouterr().out
    assert tuple(tmp_path.rglob("*")) == before


def test_unknown_backup_is_preserved_by_purge_but_can_be_explicitly_archived(
    tmp_path, monkeypatch, capsys
):
    from core.result import Ok
    from harness.installation_lifecycle import uninstall
    from host_adapters import installation_layouts

    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        installation_layouts, "_native_commands", lambda host, context: ()
    )
    profile = project / ".zed"
    profile.mkdir()
    (profile / "settings.json").write_text("{}")
    backup = profile / "settings.json.pre-harness"
    backup.write_text("private recovery settings")
    assert isinstance(uninstall("local", (project,), purge=True), Ok)
    assert backup.read_text() == "private recovery settings"
    report = preview((project,))
    repair = next(
        item for item in report["repairs"] if item["action"] == "archive_backup"
    )
    args = _args(project)
    args.repair_id = [repair["id"]]
    assert run(args) == 1
    selection = json.loads(capsys.readouterr().out)
    args.apply_repairs = selection["selection_digest"]
    assert run(args) == 0
    assert "repaired" in json.loads(capsys.readouterr().out)
    archived = next((project / ".harness/recovery").iterdir())
    assert archived.read_text() == "private recovery settings"
    assert not backup.exists()
    assert archived.stat().st_mode & 0o077 == 0
    assert not (home / ".local").exists()
