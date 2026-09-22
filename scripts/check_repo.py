#!/usr/bin/env python3
"""Repository consistency checks that do not need the network.

    check_repo.py

- every file the plugin must ship is tracked by git;
- every tracked *.json file parses;
- the example policy validates against the policy schema (needs `jsonschema`);
- every skill's frontmatter `name` matches its folder;
- every document under docs/ has title / status / owner / last_reviewed frontmatter;
- every relative Markdown link in README.md, CHANGELOG.md, THIRD_PARTY_NOTICES.md, and docs/
  points at a file or folder that exists.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "monolithic-dev-harness"
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FRONTMATTER_KEYS = ("title", "status", "owner", "last_reviewed")
# Files the hosts load from the plugin. A global gitignore once kept hooks/ and .mcp.json out of a
# release, so their presence in git is checked, not assumed.
REQUIRED_PLUGIN_FILES = (
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".mcp.json",
    "cursor.mcp.json",
    "hooks/hooks.json",
    "hooks/cursor.hooks.json",
    "bin/harness",
    "scripts/harness/hook.py",
)


def tracked(pattern: str) -> list[Path]:
    out = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            pattern,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / line for line in out.splitlines() if line]


def check_required_files(problems: list[str]) -> None:
    tracked_files = set(
        subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "plugins/monolithic-dev-harness"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    )
    for rel in REQUIRED_PLUGIN_FILES:
        if f"plugins/monolithic-dev-harness/{rel}" not in tracked_files:
            problems.append(
                f"plugins/monolithic-dev-harness/{rel} is not tracked by git"
            )


def check_json(problems: list[str]) -> None:
    for path in tracked("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{path.relative_to(ROOT)}: invalid JSON ({exc})")
    try:
        import jsonschema
    except ImportError:
        problems.append(
            "jsonschema is not installed; cannot validate the example policy"
        )
        return
    schema = json.loads((PLUGIN / "config/policy.schema.json").read_text())
    example = json.loads((PLUGIN / "examples/policy.example.json").read_text())
    try:
        jsonschema.validate(example, schema)
    except jsonschema.ValidationError as exc:
        problems.append(
            f"examples/policy.example.json does not match the schema: {exc.message}"
        )


def check_skills(problems: list[str]) -> None:
    for skill in sorted((PLUGIN / "skills").iterdir()):
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(
            r"^name:\s*(\S+)",
            text.split("---")[1] if text.startswith("---") else "",
            re.M,
        )
        if not match or match.group(1) != skill.name:
            problems.append(
                f"skills/{skill.name}/SKILL.md: frontmatter name must be {skill.name!r}"
            )


def check_docs(problems: list[str]) -> None:
    for path in sorted((ROOT / "docs").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        head = text.split("---")[1] if text.startswith("---") else ""
        missing = [
            key
            for key in FRONTMATTER_KEYS
            if not re.search(rf"^{key}:\s*\S", head, re.M)
        ]
        if missing:
            problems.append(
                f"{path.relative_to(ROOT)}: frontmatter missing {', '.join(missing)}"
            )


def check_links(problems: list[str]) -> None:
    documents = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "THIRD_PARTY_NOTICES.md",
    ]
    documents += sorted((ROOT / "docs").rglob("*.md"))
    for path in documents:
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for target in LINK.findall(text):
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                continue
            file_part = target.split("#", 1)[0]
            if file_part and not (path.parent / file_part).exists():
                problems.append(f"{path.relative_to(ROOT)}: broken link {target}")


def main() -> int:
    problems: list[str] = []
    for check in (
        check_required_files,
        check_json,
        check_skills,
        check_docs,
        check_links,
    ):
        check(problems)
    for problem in problems:
        print(f"FAIL {problem}")
    if problems:
        return 1
    print("repository checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
