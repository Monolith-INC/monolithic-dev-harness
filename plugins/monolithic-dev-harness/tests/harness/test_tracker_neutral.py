"""The agent works from the gateway contract only: no agent-facing file names a tracker product,
its field names or its notes. What one tracker needs lives in `trackers/<name>/`.

Setup (choosing a tracker) and BMad's own vendored help may name products; nothing else may.
"""

from __future__ import annotations

import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
TRACKER_TERMS = re.compile(
    r"\bLinear\b|\bAzure (?:DevOps|Boards|id|ID|URL|work item|item|description)\b"
    r"|System\.[A-Z]\w+|Microsoft\.VSTS|azure-mechanics|azure-ingest|\bwit_\w+"
)
# Choosing a tracker is setup's job; BMad's vendored help is BMad's own text.
EXEMPT = (
    "skills/bootstrap/",
    "skills/onboard-tracker/",
    "references/project-config.md",
    "skills/bmod-method/",
    "skills/bmad-",
)


def _agent_facing() -> list[Path]:
    found = []
    for folder in ("skills", "references", "common"):
        for path in (PLUGIN / folder).rglob("*"):
            relative = path.relative_to(PLUGIN).as_posix()
            if path.suffix in (".md", ".json") and not relative.startswith(EXEMPT):
                found.append(path)
    return found


def test_no_agent_facing_file_names_a_tracker() -> None:
    offending = [
        f"{path.relative_to(PLUGIN)}:{number}: {match.group(0)}"
        for path in _agent_facing()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for match in [TRACKER_TERMS.search(line)]
        if match
    ]
    assert offending == []


def test_the_azure_notes_live_with_the_azure_tracker() -> None:
    notes = PLUGIN / "trackers" / "azure-devops" / "notes"
    assert {p.name for p in notes.iterdir()} >= {
        "gateway.md",
        "mechanics.md",
        "ingest.md",
    }
    assert not (PLUGIN / "skills" / "azure-devops").exists()
