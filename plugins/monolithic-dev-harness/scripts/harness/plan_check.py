"""Advisory plan inspection; never substitutes for a human scope review."""

import re
from pathlib import Path

from core.result import Result, attempt, fmap


def inspect(text: str) -> dict:
    return {
        "words": len(text.split()),
        "estimated_tokens": (len(text.encode("utf-8")) + 3) // 4,
        "token_method": "UTF-8 bytes / 4 estimate; not a model tokenizer",
        "scope_signals": list(
            dict.fromkeys(
                re.findall(
                    r"\b(?:authentication|invitations|migration|offline|sync|Android|Linux|browser|payments)\b",
                    text,
                    flags=re.IGNORECASE,
                )
            )
        ),
        "instruction": "Review independent capabilities for decomposition; signals are advisory, not a feature count.",
    }


def check(path: Path) -> Result[dict]:
    return fmap(
        attempt(
            lambda: path.read_text(encoding="utf-8"),
            "plan_unreadable",
            "read plan",
            OSError,
            UnicodeError,
        ),
        inspect,
    )
