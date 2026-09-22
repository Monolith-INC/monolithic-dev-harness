from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def capture_hook_payload(
    *,
    client: str,
    payload: dict[str, Any],
    capture_dir: str | Path | None,
    project_root: str,
) -> Path | None:
    if not capture_dir:
        return None

    output_dir = Path(capture_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%S%f")
    output_path = output_dir / f"{timestamp}-{client}.json"
    output_path.write_text(
        json.dumps(
            {
                "client": client,
                "project_root": project_root,
                "captured_at": now.isoformat(),
                "payload": payload,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return output_path
