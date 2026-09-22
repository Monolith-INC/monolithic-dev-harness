from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
for _path in (_REPO_ROOT, _SCRIPTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from pathlib import Path

from scripts.integrations.gateway import process_message


def main() -> None:
    root = os.environ.get("CODEX_PROJECT_ROOT", "").strip()
    project_root = Path(root) if root else None
    for line in sys.stdin:
        if line.strip():
            response = process_message(line, project_root=project_root)
            if response:
                print(response, flush=True)


if __name__ == "__main__":
    main()
