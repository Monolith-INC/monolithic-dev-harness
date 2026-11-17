"""Start the `workflow-integrations` MCP server on stdio for the repository the host runs in."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from harness import project_paths  # noqa: E402
from integrations.gateway import (
    handle_call,  # noqa: E402
    process_message,  # noqa: E402
)
from integrations.gateway_endpoint import serve  # noqa: E402


def project_root(host: str | None = None) -> Path:
    selected_host = host or os.environ.get("MDH_GATEWAY_HOST", "").strip()
    host_variables = {
        "claude": "CLAUDE_PROJECT_DIR",
        "cursor": "CURSOR_PROJECT_DIR",
        "codex": "CODEX_PROJECT_ROOT",
        "kimi": None,
    }
    keys = (
        (host_variables[selected_host],)
        if selected_host in host_variables
        else ("CLAUDE_PROJECT_DIR", "CURSOR_PROJECT_DIR")
    )
    named = next(
        (
            os.environ[key]
            for key in keys
            if key is not None
            if os.environ.get(key, "").strip()
        ),
        "",
    )
    start = Path(named) if named else Path.cwd()
    return project_paths.root(start)


def gateway_host() -> str:
    """Use the legacy shared owner when an older installed config has no host marker."""
    host = os.environ.get("MDH_GATEWAY_HOST", "").strip()
    match host:
        case "":
            return "default"
        case "claude" | "codex" | "cursor" | "kimi":
            return host
        case _:
            raise SystemExit(
                "workflow-integrations has an unsupported MDH_GATEWAY_HOST marker."
            )


def main() -> None:
    host = gateway_host()
    root = project_root(host)
    with serve(
        root,
        lambda operation, arguments: handle_call(operation, arguments, root),
        host,
    ):
        replies = (process_message(line, root) for line in sys.stdin if line.strip())
        tuple(print(reply, flush=True) for reply in replies if reply)


if __name__ == "__main__":
    main()
