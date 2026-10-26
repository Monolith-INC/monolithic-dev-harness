"""Draw the workflow route as a Mermaid flowchart, so the diagram never disagrees with the route.

route_diagram.py --write <file.mmd>   write the diagram
route_diagram.py --check <file.mmd>   exit 1 when the file differs from the route
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import route  # noqa: E402

HEADER = "%% Generated from the route in config/prepared-workflows.json by route_diagram.py.\n"
_GROUPS = {"story": "For each Story", "delivery": "Story by Story"}


def _words(name: str) -> str:
    return name.replace("_", " ")


def _label(step: route.Step) -> str:
    parts = [f"{step.stage.capitalize()}: {step.id.replace('-', ' ')}"]
    if step.skill:
        parts.append(step.skill)
    if step.gate:
        parts.append(f"asks {step.gate}")
    if step.when:
        parts.append("only when " + " and ".join(_words(n) for n in step.when))
    if step.unless:
        parts.append("skipped when " + " or ".join(_words(n) for n in step.unless))
    if step.end:
        parts.append("ends the work")
    return "<br/>".join(parts).replace('"', "'")


def mermaid(loaded: route.Route) -> str:
    lines = [HEADER.rstrip("\n"), "flowchart TD"]
    group = ""
    for step in loaded.steps:
        node = step.id.replace("-", "_")
        if step.scope != group:
            if group in _GROUPS:
                lines.append("  end")
            if step.scope in _GROUPS:
                lines.append(f'  subgraph {step.scope}["{_GROUPS[step.scope]}"]')
            group = step.scope
        shape = ('{{"', '"}}') if step.gate else ('["', '"]')
        lines.append(f"  {node}{shape[0]}{_label(step)}{shape[1]}")
    if group in _GROUPS:
        lines.append("  end")
    chain = [s.id.replace("-", "_") for s in loaded.steps]
    lines += [f"  {a} --> {b}" for a, b in zip(chain, chain[1:], strict=False)]
    lines.append('  close_entry --> finished(["Done"])')
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("--write", "--check"):
        print(__doc__)
        return 2
    target = Path(argv[1])
    drawn = mermaid(route.load_or_raise())
    if argv[0] == "--write":
        target.write_text(drawn, encoding="utf-8")
        return 0
    current = target.read_text(encoding="utf-8") if target.is_file() else ""
    if current != drawn:
        print(
            f"{target} does not match the route; run route_diagram.py --write {target}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
