from __future__ import annotations

from pathlib import Path


MAILBOX_DIRNAME = ".agentic/workflow_prompts"


def mailbox_dir(project_root: Path) -> Path:
    return project_root / ".agentic" / "workflow_prompts"


def prompt_path(project_root: Path, skill_name: str) -> Path:
    return mailbox_dir(project_root) / f"{skill_name}.prompt.md"


def error_log_path(project_root: Path, skill_name: str) -> Path:
    return mailbox_dir(project_root) / f"{skill_name}.error.log"


def write_prompt(project_root: Path, skill_name: str, content: str) -> Path:
    path = prompt_path(project_root, skill_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_error_log(project_root: Path, skill_name: str, message: str) -> Path:
    path = error_log_path(project_root, skill_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message, encoding="utf-8")
    return path


def clear_error_log(project_root: Path, skill_name: str) -> None:
    path = error_log_path(project_root, skill_name)
    if path.exists():
        path.unlink()


def read_error_log(project_root: Path, skill_name: str) -> str | None:
    path = error_log_path(project_root, skill_name)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")
