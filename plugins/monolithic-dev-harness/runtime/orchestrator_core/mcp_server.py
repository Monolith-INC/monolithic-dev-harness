from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .engine import OrchestratorEngine


def default_skills_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2] / "skills"
    )  # <plugin>/runtime/orchestrator_core → <plugin>/skills


def resolve_skills_dir() -> Path:
    env = os.environ.get("ORCHESTRATOR_SKILLS_DIR", "").strip()
    if env:
        path = Path(env)
        return path.resolve()
    return default_skills_dir()


def resolve_project_root() -> Path:
    from .project_config import project_root

    return project_root()


def resolve_state_dir(project_root: Path) -> Path:
    """`.harness/backlog/` -- the plugin's own state directory, never a user location."""
    from .project_config import plugin_dir

    return plugin_dir(project_root)


def process_message(line: str, engine: OrchestratorEngine) -> str:
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return ""
    if not isinstance(msg, dict) or "id" not in msg or "method" not in msg:
        return ""
    msg_id = msg["id"]
    method = msg["method"]
    response: dict = {"jsonrpc": "2.0", "id": msg_id}
    try:
        if method == "initialize":
            response["result"] = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "agile-backlog-toolkit-orchestrator",
                    "version": "0.1.0",
                },
            }
        elif method == "tools/list":
            response["result"] = {"tools": engine.list_tools()}
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name")
            args = params.get("arguments") or {}
            result = engine.run_tool_call(name, args)
            response["result"] = {
                "content": result.to_mcp_content(),
                **({} if result.ok else {"isError": True}),
            }
        elif method == "notifications/initialized":
            return ""
        else:
            response["error"] = {
                "code": -32601,
                "message": f"Method not found: {method}",
            }
    except Exception as exc:
        response["error"] = {"code": -32603, "message": str(exc)}
    return json.dumps(response)


def main() -> None:
    project_root = resolve_project_root()
    skills_dir = resolve_skills_dir()
    state_dir = resolve_state_dir(project_root)
    engine = OrchestratorEngine(
        skills_dir,
        project_root=project_root,
        state_dir=state_dir,
        quiet=True,
    )
    for line in sys.stdin:
        if line.strip():
            res = process_message(line, engine)
            if res:
                print(res, flush=True)


if __name__ == "__main__":
    main()
