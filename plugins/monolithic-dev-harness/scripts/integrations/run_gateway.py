"""Start the `workflow-integrations` MCP server on stdio for the repository the host runs in."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from harness import gitstate  # noqa: E402
from integrations.gateway import process_message  # noqa: E402


def project_root() -> Path:
    named = next(
        (
            os.environ[key]
            for key in ("CLAUDE_PROJECT_DIR", "CURSOR_PROJECT_DIR")
            if os.environ.get(key, "").strip()
        ),
        "",
    )
    start = Path(named) if named else Path.cwd()
    return gitstate.repo_root(start) or start


def main() -> None:
    root = project_root()
    replies = (process_message(line, root) for line in sys.stdin if line.strip())
    tuple(print(reply, flush=True) for reply in replies if reply)


if __name__ == "__main__":
    main()
