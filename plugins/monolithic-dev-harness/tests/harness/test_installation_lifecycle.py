"""Installation acceptance uses disposable homes/projects only."""

import json
from pathlib import Path

import pytest

from core.result import Err, Ok
from harness.installation_lifecycle import install_local, remove_receipt

PLUGIN = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_installation_home(tmp_path, monkeypatch):
    home = tmp_path / "isolated-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("HARNESS_HOME", raising=False)
    monkeypatch.delenv("HARNESS_BIN_DIR", raising=False)
    return home


def test_local_roundtrip_preserves_foreign_config(tmp_path):
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"foreign": {"command": "keep"}}}))
    assert isinstance(install_local(tmp_path, PLUGIN, ("claude",)), Ok)
    assert "backlog-orchestrator" in config.read_text()
    assert (tmp_path / ".harness/installation.json").is_file()
    assert isinstance(remove_receipt(tmp_path / ".harness/installation.json"), Ok)
    assert json.loads(config.read_text()) == {
        "mcpServers": {"foreign": {"command": "keep"}}
    }


def test_uninstall_preserves_foreign_config_added_after_install(tmp_path):
    assert isinstance(install_local(tmp_path, PLUGIN, ("claude",)), Ok)
    path = tmp_path / ".mcp.json"
    path.write_text(
        json.dumps({**json.loads(path.read_text()), "newForeignSetting": True})
    )
    assert isinstance(remove_receipt(tmp_path / ".harness/installation.json"), Ok)
    assert json.loads(path.read_text()) == {"newForeignSetting": True}


def test_collision_is_preflighted_before_any_asset_write(tmp_path):
    skill = next(path for path in (PLUGIN / "skills").iterdir() if path.is_dir())
    (tmp_path / ".claude/skills" / skill.name).mkdir(parents=True)
    assert isinstance(install_local(tmp_path, PLUGIN, ("claude",)), Err)
    assert not (tmp_path / ".mcp.json").exists()


def test_receipt_refuses_modified_owned_hook(tmp_path):
    assert isinstance(install_local(tmp_path, PLUGIN, ("codex",)), Ok)
    path = tmp_path / ".codex/hooks.json"
    path.write_text(path.read_text().replace("pre-tool", "changed-tool"))
    assert isinstance(remove_receipt(tmp_path / ".harness/installation.json"), Err)
    assert "changed-tool" in path.read_text()


def test_second_install_keeps_original_before_snapshot(tmp_path):
    assert isinstance(install_local(tmp_path, PLUGIN, ("zed",)), Ok)
    assert isinstance(install_local(tmp_path, PLUGIN, ("zed",)), Ok)
    assert isinstance(remove_receipt(tmp_path / ".harness/installation.json"), Ok)
    assert not (tmp_path / ".zed/settings.json").exists()


def test_all_scope_discovers_host_known_project_and_preserves_on_preflight_error(
    tmp_path, monkeypatch
):
    from harness.installation_lifecycle import uninstall
    from host_adapters import installation_layouts

    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        installation_layouts, "_native_commands", lambda host, context: ()
    )
    assert isinstance(install_local(project, PLUGIN, ("claude",)), Ok)
    (home / ".claude.json").write_text(json.dumps({"projects": {str(project): {}}}))
    (home / ".codex").mkdir()
    bad = home / ".codex/config.toml"
    bad.write_text("[")
    assert isinstance(uninstall("all", ()), Err)
    assert (project / ".harness/installation.json").is_file()
    assert "backlog-orchestrator" in (project / ".mcp.json").read_text()
    bad.unlink()
    assert isinstance(uninstall("all", ()), Ok)
    assert not (project / ".harness/installation.json").exists()
    assert not (project / ".mcp.json").exists()


def test_user_receipt_restores_only_owned_changes_and_protects_snapshot(
    tmp_path, monkeypatch
):
    from harness.installation_lifecycle import begin_user, record_user, uninstall
    from host_adapters import installation_layouts

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        installation_layouts, "_native_commands", lambda host, context: ()
    )
    path = home / ".config/zed/settings.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"foreign":1}')
    assert isinstance(begin_user(("zed",)), Ok)
    path.write_text(
        json.dumps(
            {
                "foreign": 1,
                "context_servers": {
                    "harness": {
                        "command": "sh",
                        "args": ["/opt/monolithic-dev-harness/bin/harness-python"],
                    }
                },
            }
        )
    )
    assert isinstance(record_user(PLUGIN, ("zed",)), Ok)
    receipt = home / ".local/share/monolithic-dev-harness/installation.json"
    assert receipt.stat().st_mode & 0o077 == 0
    path.write_text(json.dumps({**json.loads(path.read_text()), "later": 2}))
    assert isinstance(uninstall("user", ()), Ok)
    assert json.loads(path.read_text()) == {"foreign": 1, "later": 2}


def test_same_name_foreign_server_mention_does_not_grant_ownership(tmp_path):
    config = tmp_path / ".mcp.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "workflow-integrations": {
                        "command": "foreign",
                        "description": "monolithic-dev-harness",
                    }
                }
            }
        )
    )
    assert isinstance(install_local(tmp_path, PLUGIN, ("claude",)), Err)
    assert "foreign" in config.read_text()


def test_project_symlink_ancestor_and_replaced_file_are_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".codex").symlink_to(outside)
    assert isinstance(install_local(project, PLUGIN, ("codex",)), Err)
    assert tuple(outside.iterdir()) == ()


def test_git_private_install_and_remove_preserve_original_excludes(tmp_path):
    import subprocess

    subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
    exclude = tmp_path / ".git/info/exclude"
    original = exclude.read_text()
    assert isinstance(install_local(tmp_path, PLUGIN, ("codex",)), Ok)
    checked = subprocess.run(
        (
            "git",
            "-C",
            str(tmp_path),
            "check-ignore",
            ".codex/hooks.json",
        ),
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0 and ".codex/hooks.json" in checked.stdout
    assert isinstance(remove_receipt(tmp_path / ".harness/installation.json"), Ok)
    assert exclude.read_text() == original


def test_conflicting_native_agent_and_directory_are_preflighted(tmp_path):
    (tmp_path / ".codex/agents").mkdir(parents=True)
    foreign = tmp_path / ".codex/agents/mdh_thermo_review.toml"
    foreign.write_text('name = "foreign"')
    assert isinstance(install_local(tmp_path, PLUGIN, ("codex",)), Err)
    assert foreign.read_text() == 'name = "foreign"'
    assert not (tmp_path / ".codex/hooks.json").exists()


def test_foreign_setting_between_project_upgrades_survives_uninstall(tmp_path):
    assert isinstance(install_local(tmp_path, PLUGIN, ("zed",)), Ok)
    path = tmp_path / ".zed/settings.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "theme": "keep"}))
    assert isinstance(install_local(tmp_path, PLUGIN, ("zed",)), Ok)
    assert isinstance(remove_receipt(tmp_path / ".harness/installation.json"), Ok)
    assert json.loads(path.read_text()) == {"theme": "keep"}


def test_foreign_setting_between_user_upgrades_and_host_union_survive(
    tmp_path, monkeypatch
):
    from harness.installation_lifecycle import begin_user, record_user, uninstall
    from host_adapters import installation_layouts

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        installation_layouts, "_native_commands", lambda host, context: ()
    )
    paths = (home / ".config/zed/settings.json", home / ".kimi-code/config.toml")
    assert isinstance(begin_user(("zed",)), Ok)
    paths[0].parent.mkdir(parents=True)
    effect = {
        "context_servers": {
            "effect": {
                "command": "sh",
                "args": ["/opt/monolithic-dev-harness/bin/harness-python"],
            }
        }
    }
    paths[0].write_text(json.dumps(effect))
    assert isinstance(record_user(PLUGIN, ("zed",)), Ok)
    paths[0].write_text(json.dumps({**effect, "theme": "keep"}))
    assert isinstance(begin_user(("zed",)), Ok)
    assert isinstance(record_user(PLUGIN, ("zed",)), Ok)
    # A later installation changes host selection but must keep earlier ownership.
    assert isinstance(begin_user(("kimi",)), Ok)
    paths[1].parent.mkdir(parents=True)
    paths[1].write_text(
        '# BEGIN monolithic-dev-harness\n[[hooks]]\nevent="Stop"\ncommand="sh /opt/monolithic-dev-harness/scripts/harness/hook.py"\n# END monolithic-dev-harness\n'
    )
    assert isinstance(record_user(PLUGIN, ("kimi",)), Ok)
    assert isinstance(uninstall("user", ()), Ok)
    assert json.loads(paths[0].read_text()) == {"theme": "keep"}
    assert not paths[1].exists()


def test_interrupted_user_install_can_remove_owned_effects_without_losing_foreign(
    tmp_path, monkeypatch
):
    from harness.installation_lifecycle import begin_user, uninstall
    from host_adapters import installation_layouts

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        installation_layouts, "_native_commands", lambda host, context: ()
    )
    assert isinstance(begin_user(("zed",)), Ok)
    path = home / ".config/zed/settings.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "foreign": "keep",
                "context_servers": {
                    "owned": {
                        "command": "sh",
                        "args": ["/opt/monolithic-dev-harness/bin/harness-python"],
                    }
                },
            }
        )
    )
    assert isinstance(uninstall("user", (), purge=True), Ok)
    assert json.loads(path.read_text()) == {"foreign": "keep"}


def test_user_install_refuses_shared_config_symlink_before_writing(
    tmp_path, monkeypatch
):
    from harness.installation_lifecycle import begin_user

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    original = tmp_path / "original.json"
    original.write_text("{}")
    profile = home / ".config/zed"
    profile.mkdir(parents=True)
    (profile / "settings.json").symlink_to(original)
    assert isinstance(begin_user(("zed",)), Err)
    assert original.read_text() == "{}"
    assert not (home / ".local/share/monolithic-dev-harness/installation.json").exists()


def test_uninstall_keeps_foreign_files_beside_owned_runtime(tmp_path, monkeypatch):
    from harness.installation_lifecycle import uninstall
    from host_adapters import installation_layouts

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        installation_layouts, "_native_commands", lambda host, context: ()
    )
    root = home / ".local/share/monolithic-dev-harness"
    manifest = (
        root / "marketplace/plugins/monolithic-dev-harness/.claude-plugin/plugin.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "monolithic-dev-harness", "version": "1"}))
    foreign = root / "my-important-notes.txt"
    foreign.write_text("keep")
    assert isinstance(uninstall("user", (), purge=True), Ok)
    assert foreign.read_text() == "keep"
    assert not (root / "marketplace").exists()


def test_explicit_project_registration_repairs_remain_uninstallable(
    tmp_path, monkeypatch
):
    from harness.installation_cleanup import plan_cleanup
    from harness.installation_files import apply_repairs
    from harness.installation_inventory import scan
    from host_adapters.installation_contract import InstallationContext

    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert isinstance(install_local(project, PLUGIN, ("codex",)), Ok)
    context = InstallationContext(home, (project,))
    repairs = plan_cleanup(scan(context), "local", (project,)).value
    registrations = tuple(
        repair for repair in repairs if repair.action == "remove_entry"
    )
    assert registrations
    assert isinstance(apply_repairs(registrations, context), Ok)
    assert isinstance(remove_receipt(project / ".harness/installation.json"), Ok)
    assert not (project / ".codex/hooks.json").exists()


def test_changed_owned_mcp_arguments_are_not_reinterpreted_as_foreign(tmp_path):
    assert isinstance(install_local(tmp_path, PLUGIN, ("claude",)), Ok)
    path = tmp_path / ".mcp.json"
    current = json.loads(path.read_text())
    current["mcpServers"]["workflow-integrations"]["args"][-1] = "/custom/script.py"
    path.write_text(json.dumps(current))
    assert isinstance(remove_receipt(tmp_path / ".harness/installation.json"), Err)
    assert "/custom/script.py" in path.read_text()


def test_foreign_receipt_is_preserved_before_package_publication(tmp_path):
    folder = tmp_path / ".harness"
    folder.mkdir()
    receipt = folder / "installation.json"
    receipt.write_text('{"product":"another-application","schema":1}')
    assert isinstance(install_local(tmp_path, PLUGIN, ("codex",)), Err)
    assert json.loads(receipt.read_text())["product"] == "another-application"
    assert not (tmp_path / ".codex/hooks.json").exists()


def test_user_preflight_preserves_foreign_server_with_canonical_name(
    tmp_path, monkeypatch
):
    from harness.installation_lifecycle import begin_user

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    path = home / ".config/zed/settings.json"
    path.parent.mkdir(parents=True)
    original = {
        "context_servers": {"workflow-integrations": {"command": "foreign", "args": []}}
    }
    path.write_text(json.dumps(original))
    assert isinstance(begin_user(("zed",)), Err)
    assert json.loads(path.read_text()) == original


def test_receipt_proves_new_backup_ownership_for_doctor(tmp_path, monkeypatch):
    from harness.installation_inventory import findings, scan
    from harness.installation_lifecycle import begin_user, record_user
    from host_adapters.installation_contract import InstallationContext

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert isinstance(begin_user(("zed",)), Ok)
    path = home / ".config/zed/settings.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "context_servers": {
                    "effect": {
                        "command": "sh",
                        "args": ["/opt/monolithic-dev-harness/bin/harness-python"],
                    }
                }
            }
        )
    )
    backup = path.with_name(path.name + ".pre-harness")
    backup.write_text("{}")
    assert isinstance(record_user(PLUGIN, ("zed",)), Ok)
    inventory = scan(InstallationContext(home))
    assert any(
        component.path == backup and component.kind == "receipt-backup"
        for component in inventory.components
    )
    assert not any(issue.code == "legacy-backups" for issue in findings(inventory))


def test_symlinked_package_ancestor_cannot_publish_outside_scope(tmp_path, monkeypatch):
    from harness.installation_lifecycle import begin_user

    outside = tmp_path / "outside"
    outside.mkdir()
    parent = tmp_path / "install-parent"
    parent.symlink_to(outside)
    monkeypatch.setenv("HARNESS_HOME", str(parent / "harness"))
    assert isinstance(begin_user(()), Err)
    assert tuple(outside.iterdir()) == ()


def test_shared_package_survives_scoped_removal_until_all_registrations_removed(
    tmp_path, monkeypatch
):
    from harness.installation_lifecycle import uninstall
    from harness.installation_receipts import registered_projects
    from host_adapters import installation_layouts

    home = tmp_path / "shared-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        installation_layouts, "_native_commands", lambda host, context: ()
    )
    root = home / ".local/share/monolithic-dev-harness"
    manifest = (
        root / "marketplace/plugins/monolithic-dev-harness/.claude-plugin/plugin.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "monolithic-dev-harness", "version": "current"})
    )
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    assert isinstance(install_local(first, PLUGIN, ("claude",)), Ok)
    assert isinstance(install_local(second, PLUGIN, ("codex",)), Ok)
    assert set(registered_projects()) == {first, second}
    assert not (first / ".harness/install").exists()
    assert not (first / ".harness/bin").exists()
    assert isinstance(uninstall("local", (first,), purge=True), Ok)
    assert manifest.exists()
    assert (second / ".codex/hooks.json").exists()
    assert registered_projects() == (second,)
    assert isinstance(uninstall("user", (), purge=True), Ok)
    assert manifest.exists()
    assert (second / ".codex/hooks.json").exists()
    assert isinstance(uninstall("all", (), purge=True), Ok)
    assert not manifest.exists()
    assert not (second / ".codex/hooks.json").exists()
    assert registered_projects() == ()


def test_shared_storage_is_not_a_user_registration_conflict(tmp_path, monkeypatch):
    from harness.installation_inventory import findings, scan
    from host_adapters.installation_contract import InstallationContext

    home = tmp_path / "shared-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    manifest = (
        home
        / ".local/share/monolithic-dev-harness/marketplace/plugins/monolithic-dev-harness/.claude-plugin/plugin.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "monolithic-dev-harness", "version": "0.7.0-rc.8"})
    )
    project = tmp_path / "project"
    project.mkdir()
    assert isinstance(install_local(project, PLUGIN, ("claude",)), Ok)
    assert not any(
        issue.code == "overlapping-scopes"
        for issue in findings(scan(InstallationContext(home, (project,))))
    )
    assert not (home / ".claude").exists()
    assert not (home / ".codex").exists()


def test_independent_projects_are_not_duplicate_registrations(tmp_path, monkeypatch):
    from harness.installation_inventory import findings, scan
    from host_adapters.installation_contract import InstallationContext

    home = tmp_path / "shared-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    assert isinstance(install_local(first, PLUGIN, ("codex",)), Ok)
    assert isinstance(install_local(second, PLUGIN, ("codex",)), Ok)
    inventory = scan(InstallationContext(home, (first, second)))
    assert not any(
        issue.code == "duplicate-components" for issue in findings(inventory)
    )
    assert {
        component.project
        for component in inventory.components
        if component.scope == "local"
    } == {first, second}
