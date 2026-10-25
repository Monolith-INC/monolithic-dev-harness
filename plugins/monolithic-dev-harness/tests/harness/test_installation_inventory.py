import json
from pathlib import Path

import harness.installation_inventory as inventory
from harness.installation_inventory import findings, scan
from host_adapters.installation_contract import (
    InstallationAdapter,
    InstallationContext,
    Location,
)


def test_scan_reads_declared_product_manifest_and_ignores_unmarked(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "plugin.json"
    manifest.write_text(
        json.dumps({"name": "monolithic-dev-harness", "version": "1.0"})
    )
    unrelated = tmp_path / "unrelated.json"
    unrelated.write_text(
        json.dumps({"mcpServers": {"same-name": {"command": "other"}}})
    )
    monkeypatch.setattr(inventory, "ADAPTERS", {"fake": "fake"})
    monkeypatch.setattr(
        inventory,
        "adapter_for",
        lambda host: __import__("core.result", fromlist=["Ok"]).Ok(
            InstallationAdapter(
                "fake",
                lambda _: (
                    Location(manifest, "user", "installation"),
                    Location(unrelated, "user", "settings"),
                ),
            )
        ),
    )
    result = scan(InstallationContext(tmp_path))
    assert len(result.components) == 1
    assert result.components[0].owned
    assert result.components[0].digest


def test_findings_reports_unexpected_versions_and_duplicates(
    tmp_path: Path, monkeypatch
) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text(json.dumps({"name": "monolithic-dev-harness", "version": "1"}))
    second.write_text(json.dumps({"name": "monolithic-dev-harness", "version": "2"}))
    monkeypatch.setattr(inventory, "ADAPTERS", {"fake": "fake"})
    monkeypatch.setattr(
        inventory,
        "adapter_for",
        lambda host: __import__("core.result", fromlist=["Ok"]).Ok(
            InstallationAdapter(
                "fake",
                lambda _: (
                    Location(first, "user", "installation"),
                    Location(second, "user", "installation"),
                ),
            )
        ),
    )
    result = scan(InstallationContext(tmp_path))
    assert {item.code for item in findings(result, "3")} == {
        "mixed-version",
    }


def test_absent_locations_are_not_errors(tmp_path):
    assert not scan(InstallationContext(tmp_path)).errors


def test_real_mcp_selector_never_selects_parent_or_foreign(tmp_path):
    profile = tmp_path / ".cursor"
    profile.mkdir()
    path = profile / "mcp.json"
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "owned": {
                        "command": "sh",
                        "args": ["/opt/monolithic-dev-harness/bin/harness-python"],
                    },
                    "foreign": {"command": "keep"},
                }
            }
        )
    )
    result = scan(InstallationContext(tmp_path))
    assert [c.selector for c in result.components if c.path == path] == [
        ("mcpServers", "owned")
    ]


def test_live_skill_link_is_owned_but_foreign_link_is_ignored(tmp_path):
    root = tmp_path / "monolithic-dev-harness"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": "monolithic-dev-harness", "version": "1"})
    )
    (root / "skills/owned").mkdir(parents=True)
    links = tmp_path / ".agents/skills"
    links.mkdir(parents=True)
    (links / "owned").symlink_to(root / "skills/owned")
    (links / "foreign").symlink_to(tmp_path)
    result = scan(InstallationContext(tmp_path))
    assert any(c.path == links / "owned" and c.owned for c in result.components)
    assert not any(c.path == links / "foreign" for c in result.components)


def test_package_is_one_root_and_one_version_is_healthy(tmp_path):
    root = tmp_path / ".local/share/monolithic-dev-harness"
    manifest = (
        root / "marketplace/plugins/monolithic-dev-harness/.claude-plugin/plugin.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "monolithic-dev-harness", "version": "1"}))
    result = scan(InstallationContext(tmp_path))
    assert [c.path for c in result.components if c.kind == "installation"] == [
        root / "marketplace"
    ]
    assert not findings(result)


def test_mixed_foreign_hook_group_owns_only_handler(tmp_path):
    path = tmp_path / ".claude/settings.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "hooks": [
                                {"command": "foreign"},
                                {
                                    "command": "sh /opt/monolithic-dev-harness/scripts/harness/hook.py"
                                },
                            ]
                        }
                    ]
                }
            }
        )
    )
    result = scan(InstallationContext(tmp_path))
    assert [c.selector for c in result.components if c.path == path] == [
        ("hooks", "PreToolUse", 0, "hooks", 1)
    ]


def test_jsonc_preserves_url_strings_and_reports_invalid_config(tmp_path):
    path = tmp_path / ".cursor/mcp.json"
    path.parent.mkdir()
    path.write_text('{"url":"https://example.com/#foo", // hello\n "mcpServers":{}}')
    assert not scan(InstallationContext(tmp_path)).errors
    path.write_text("{")
    assert scan(InstallationContext(tmp_path)).errors


def test_foreign_descriptions_and_environment_markers_are_not_ownership(tmp_path):
    path = tmp_path / ".cursor/mcp.json"
    path.parent.mkdir()
    original = {
        "mcpServers": {
            "foreign": {
                "command": "echo",
                "args": ["/opt/monolithic-dev-harness/bin/harness-python"],
                "description": "monolithic-dev-harness",
                "env": {"NOTE": "/opt/monolithic-dev-harness"},
            }
        }
    }
    path.write_text(json.dumps(original))
    assert not scan(InstallationContext(tmp_path)).components
    assert json.loads(path.read_text()) == original
