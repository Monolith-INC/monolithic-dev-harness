import shutil
from pathlib import Path

from core.result import Err, Ok
from host_adapters import installation_layouts
from host_adapters.installation_contract import InstallationContext


def context(tmp_path: Path) -> InstallationContext:
    tuple((tmp_path / name).mkdir(exist_ok=True) for name in (".claude", ".codex"))
    return InstallationContext(
        home=tmp_path,
        environment=(
            ("HARNESS_HOME", str(tmp_path / ".local/share/monolithic-dev-harness")),
            ("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude")),
            ("CODEX_HOME", str(tmp_path / ".codex")),
        ),
    )


def test_claude_native_removal_requires_installed_plugin_and_owned_marketplace(
    monkeypatch, tmp_path
):
    root = tmp_path / ".local/share/monolithic-dev-harness/marketplace"
    monkeypatch.setattr(shutil, "which", lambda _: "/bin/claude")
    monkeypatch.setattr(
        installation_layouts,
        "_listing",
        lambda _, args: (
            [{"pluginId": "monolithic-dev-harness@monolithic-dev-harness"}]
            if args == ("plugin", "list")
            else [{"name": "monolithic-dev-harness", "installLocation": str(root)}]
        ),
    )

    result = installation_layouts._native_removal("claude", context(tmp_path)).value

    assert result == (
        (
            "/bin/claude",
            "plugin",
            "uninstall",
            "monolithic-dev-harness@monolithic-dev-harness",
        ),
        ("/bin/claude", "plugin", "marketplace", "remove", "monolithic-dev-harness"),
    )


def test_available_only_marketplace_does_not_count_as_installed(monkeypatch, tmp_path):
    root = tmp_path / ".local/share/monolithic-dev-harness/marketplace"
    monkeypatch.setattr(shutil, "which", lambda _: "/bin/claude")
    monkeypatch.setattr(
        installation_layouts,
        "_listing",
        lambda _, args: (
            {
                "installed": [],
                "available": [
                    {"pluginId": "monolithic-dev-harness@monolithic-dev-harness"}
                ],
            }
            if args == ("plugin", "list")
            else [{"name": "monolithic-dev-harness", "installLocation": str(root)}]
        ),
    )

    assert installation_layouts._native_removal("claude", context(tmp_path)).value == (
        ("/bin/claude", "plugin", "marketplace", "remove", "monolithic-dev-harness"),
    )


def test_foreign_same_name_marketplace_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda _: "/bin/codex")
    monkeypatch.setattr(
        installation_layouts,
        "_listing",
        lambda _, args: (
            {"installed": [], "available": []}
            if args == ("plugin", "list")
            else {
                "marketplaces": [
                    {
                        "name": "monolithic-dev-harness",
                        "root": str(tmp_path / "foreign"),
                    }
                ]
            }
        ),
    )

    assert isinstance(
        installation_layouts._native_removal("codex", context(tmp_path)), Err
    )


def test_plugin_id_matcher_and_absent_native_binary(monkeypatch, tmp_path):
    assert installation_layouts._installed_harness(
        {"pluginId": "monolithic-dev-harness@monolithic-dev-harness"}
    )
    monkeypatch.setattr(shutil, "which", lambda _: None)

    result = installation_layouts._verify_user("claude", context(tmp_path))

    assert result == Ok(False)


def test_product_manifest_elsewhere_is_not_marketplace_ownership(tmp_path):
    import json

    separate = tmp_path / "separately-managed-checkout"
    manifest = separate / "plugins/monolithic-dev-harness/.claude-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "monolithic-dev-harness", "version": "1"}))
    assert not installation_layouts._owned_marketplace(
        {"root": str(separate)}, "codex", context(tmp_path)
    )
