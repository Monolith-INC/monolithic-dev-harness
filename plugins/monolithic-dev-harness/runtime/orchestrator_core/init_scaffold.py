from __future__ import annotations

from pathlib import Path

from .project_config import plugin_dir


def scaffold_workspace(project_root: Path) -> None:
    """Create the directories the plugin needs for its own state.

    Only `.agentic/workflow_prompts/` and `.agile-backlog-toolkit/`, both plugin-owned. This
    deliberately creates nothing else: where a user's artifacts go is their decision, and
    the plugin never provisions a directory structure in a project on their behalf.
    """
    mailbox = project_root / ".agentic" / "workflow_prompts"
    mailbox.mkdir(parents=True, exist_ok=True)
    gitkeep = mailbox / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")

    state = plugin_dir(project_root)
    state.mkdir(parents=True, exist_ok=True)

    print(f"[+] Scaffolded mailbox: {mailbox}")
    print(f"[+] Scaffolded plugin state: {state}")
