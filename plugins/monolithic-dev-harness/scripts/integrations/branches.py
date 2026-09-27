"""Branch names for ticket work: the settings' template with the tracker's key pattern in `{key}`."""

from __future__ import annotations

import re

from core.result import Ok, Result, err

WORD = r"[A-Za-z0-9_-]+"


def expression(template: str, key_pattern: str) -> str:
    """A regular expression for whole branch names that follow the template."""
    return "".join(
        {
            "{key}": f"(?P<key>{key_pattern})",
            "{category}": WORD,
            "{slug}": WORD,
            "{user}": WORD,
        }.get(part, re.escape(part))
        for part in re.split(r"(\{key\}|\{category\}|\{slug\}|\{user\})", template)
    )


def work_item_id(template: str, key_pattern: str, branch: str) -> Result[str]:
    """The work item id a branch name carries, or why the name does not follow the convention."""
    match re.fullmatch(expression(template, key_pattern), branch):
        case None:
            return err(
                "branch_convention",
                f"branch {branch!r} does not follow the convention {template!r} with a work item key",
            )
        case found:
            return Ok(found.group("id"))
