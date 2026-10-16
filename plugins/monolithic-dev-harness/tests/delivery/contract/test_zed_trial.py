"""Zed project-root detection in the orchestrator core."""

from __future__ import annotations

from pathlib import Path


def test_orchestrator_project_root_honors_zed_worktree(
    monkeypatch, tmp_path: Path
) -> None:
    import orchestrator_core.project_config as project_config

    monkeypatch.setenv("ZED_WORKTREE_ROOT", str(tmp_path))
    monkeypatch.delenv("CODEX_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("CURSOR_PROJECT_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert project_config.project_root() == tmp_path


def test_project_root_prefers_codex_over_zed(monkeypatch, tmp_path: Path) -> None:
    import orchestrator_core.project_config as project_config

    other = tmp_path / "zed-root"
    other.mkdir()
    monkeypatch.setenv("CODEX_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ZED_WORKTREE_ROOT", str(other))
    assert project_config.project_root() == tmp_path
