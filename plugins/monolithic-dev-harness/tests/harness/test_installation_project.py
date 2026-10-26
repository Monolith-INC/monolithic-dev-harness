import json
from pathlib import Path

from core.result import Err, Ok
from host_adapters.installation_project import assets


def test_all_supported_hosts_return_plans_without_writes(tmp_path: Path):
    plugin = Path(__file__).parents[2]
    project = tmp_path / "project"
    project.mkdir()
    before = tuple(project.rglob("*"))
    assert all(
        isinstance(assets(host, project, plugin), Ok)
        for host in ("claude", "codex", "cursor", "kimi", "zed")
    )
    assert tuple(project.rglob("*")) == before


def test_unknown_host_is_result_error(tmp_path: Path):
    result = assets("unknown", tmp_path, tmp_path)
    assert isinstance(result, Err) and result.failure.code == "unsupported_host"


def test_claude_plan_preserves_unrelated_mcp(tmp_path: Path):
    project = tmp_path / "p"
    project.mkdir()
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"foreign": {"command": "keep"}}})
    )
    result = assets("claude", project, Path(__file__).parents[2])
    assert isinstance(result, Ok)
    mcp = next(asset for asset in result.value if asset.path == project / ".mcp.json")
    assert "foreign" in mcp.text and "backlog-orchestrator" in mcp.text


def test_repeated_plan_is_stable(tmp_path: Path):
    plugin = Path(__file__).parents[2]
    first = assets("zed", tmp_path, plugin)
    second = assets("zed", tmp_path, plugin)
    assert (
        isinstance(first, Ok) and isinstance(second, Ok) and first.value == second.value
    )


def test_codex_plan_contains_managed_toml_block(tmp_path: Path):
    result = assets("codex", tmp_path, Path(__file__).parents[2])
    assert isinstance(result, Ok)
    config = next(asset for asset in result.value if asset.path.name == "config.toml")
    assert "BEGIN monolithic-dev-harness" in config.text


def test_real_codex_plan_has_three_servers_and_real_custom_agents(tmp_path):
    import tomllib
    from pathlib import Path

    from core.result import Ok
    from host_adapters.installation_project import assets

    plugin = Path(__file__).resolve().parents[2]
    project = tmp_path / "project with spaces"
    project.mkdir()
    result = assets("codex", project, plugin)
    assert isinstance(result, Ok)
    by_path = {item.path.relative_to(project).as_posix(): item for item in result.value}
    assert set(tomllib.loads(by_path[".codex/config.toml"].text)["mcp_servers"]) == {
        "backlog-orchestrator",
        "workflow-orchestrator",
        "workflow-integrations",
    }
    assert len([p for p in by_path if p.startswith(".codex/agents/")]) == 2
    assert all(item.path != plugin for item in result.value)


def test_real_zed_plan_uses_context_servers(tmp_path):
    import json
    from pathlib import Path

    from host_adapters.installation_project import assets

    plugin = Path(__file__).resolve().parents[2]
    result = assets("zed", tmp_path, plugin)
    text = next(
        asset.text
        for asset in result.value
        if asset.path == tmp_path / ".zed/settings.json"
    )
    assert len(json.loads(text)["context_servers"]) == 3


def test_real_kimi_plan_is_hooks_not_mcp_namespace(tmp_path):
    import tomllib
    from pathlib import Path

    from host_adapters.installation_project import assets

    result = assets("kimi", tmp_path, Path(__file__).resolve().parents[2])
    text = next(
        asset.text
        for asset in result.value
        if asset.path == tmp_path / ".kimi-code/config.toml"
    )
    assert len(tomllib.loads(text)["hooks"]) == 3


def test_local_install_preserves_unrelated_same_named_server(tmp_path):
    project = tmp_path / "p"
    project.mkdir()
    (project / ".mcp.json").write_text(
        json.dumps(
            {"mcpServers": {"workflow-integrations": {"command": "foreign-command"}}}
        )
    )
    assert isinstance(assets("claude", project, Path(__file__).parents[2]), Err)


def test_hook_merge_is_idempotent_and_preserves_foreign_handler(tmp_path):
    project = tmp_path / "p"
    (project / ".codex").mkdir(parents=True)
    path = project / ".codex/hooks.json"
    path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"hooks": [{"type": "command", "command": "foreign-check"}]}
                    ]
                }
            }
        )
    )
    first = assets("codex", project, Path(__file__).parents[2]).value
    text = next(a.text for a in first if a.path == path)
    path.write_text(text)
    second = assets("codex", project, Path(__file__).parents[2]).value
    assert next(a.text for a in second if a.path == path) == text
    assert "foreign-check" in text
