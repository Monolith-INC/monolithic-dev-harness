from __future__ import annotations

from pathlib import Path

from .mailbox import mailbox_dir
from .project_config import plugin_dir


def scaffold_workspace(project_root: Path) -> None:
    """Create the directories the plugin needs for its own state.

    Only `.harness/state/prompts/` and `.harness/backlog/`, both plugin-owned. This
    deliberately creates nothing else: where a user's artifacts go is their decision, and
    the plugin never provisions a directory structure in a project on their behalf.
    """
    mailbox = mailbox_dir(project_root)
    mailbox.mkdir(parents=True, exist_ok=True)

    state = plugin_dir(project_root)
    state.mkdir(parents=True, exist_ok=True)

    print(f"[+] Scaffolded mailbox: {mailbox}")
    print(f"[+] Scaffolded plugin state: {state}")
