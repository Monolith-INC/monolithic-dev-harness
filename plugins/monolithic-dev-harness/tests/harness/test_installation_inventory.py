import json
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    ("hook_metadata", "discovered"),
    ((frozenset({"state"}), True), (frozenset(), False)),
    ids=("declared", "undeclared"),
)
def test_adapter_hook_metadata_is_not_read_as_event_groups(
    tmp_path, monkeypatch, hook_metadata, discovered
):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": ".*",
                            "hooks": [
                                {
                                    "command": "sh /opt/monolithic-dev-harness"
                                    "/scripts/harness/hook.py"
                                }
                            ],
                        }
                    ],
                    "state": {"trusted": {"trusted_hash": "sha256:example"}},
                }
            }
        )
    )
    monkeypatch.setattr(inventory, "ADAPTERS", {"fake": "fake"})
    monkeypatch.setattr(
        inventory,
        "adapter_for",
        lambda host: __import__("core.result", fromlist=["Ok"]).Ok(
            InstallationAdapter(
                "fake",
                lambda _: (Location(settings, "user", "settings"),),
                hook_metadata=hook_metadata,
            )
        ),
    )
    result = scan(InstallationContext(tmp_path))
    assert (
        tuple((component.kind, component.selector) for component in result.components),
        bool(result.errors),
    ) == (
        ((("hook", ("hooks", "PreToolUse", 0)),), False) if discovered else ((), True)
    )


def test_zed_jsonc_trailing_commas_preserve_servers_and_string_contents(tmp_path):
    (tmp_path / ".config/zed").mkdir(parents=True)
    (tmp_path / ".config/zed/settings.json").write_text(
        '{"context_servers": {'
        '"workflow-integrations": {"command": "sh",'
        '"args": ["/opt/monolithic-dev-harness/bin/harness-python",],},},'
        '"kept": "https://example.com/,} // /* \\"quoted\\"",'
        '"nested": [true, false, null, 1, {"value": "x",},],'
        "/* trailing comment */}"
    )
    assert scan(InstallationContext(tmp_path)).errors == ()
    assert tuple(
        (component.host, component.kind, component.selector)
        for component in scan(InstallationContext(tmp_path)).components
    ) == (("zed", "mcp", ("context_servers", "workflow-integrations")),)
    assert (
        inventory.json_document((tmp_path / ".config/zed/settings.json").read_text())[
            "kept"
        ]
        == 'https://example.com/,} // /* "quoted"'
    )


@pytest.mark.parametrize("text", ("{,}", "[,]", "[1,,]", '{"key":,}', "[true false,]"))
def test_jsonc_trailing_comma_support_still_rejects_invalid_documents(text):
    with pytest.raises(json.JSONDecodeError):
        inventory.json_document(text)


def test_claude_project_installations_in_the_users_file_are_local(tmp_path):
    (tmp_path / ".claude/plugins").mkdir(parents=True)
    (tmp_path / ".claude/plugins/installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "monolithic-dev-harness@monolithic-dev-harness": [
                        {"scope": "local", "projectPath": "/work/app", "version": "1"},
                        {"scope": "user", "version": "2"},
                    ]
                },
            }
        )
    )
    assert tuple(
        (component.scope, component.project, component.selector)
        for component in scan(InstallationContext(tmp_path)).components
        if component.kind == "registration"
    ) == (
        (
            "local",
            Path("/work/app"),
            ("plugins", "monolithic-dev-harness@monolithic-dev-harness", 0),
        ),
        ("user", None, ("plugins", "monolithic-dev-harness@monolithic-dev-harness", 1)),
    )
