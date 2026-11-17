"""Present the toolkit's bounded knowledge ladder without an MCP dependency.

Adapted from Monolith-INC/monolithic-code-review-toolkit,
adapters/knowledge/mcrt_knowledge_mcp.py at commit
3af148b44421521bb453be0abea05750e45f6f8a (MIT).
"""

from collections.abc import Mapping, Sequence
from typing import Any

from project_knowledge.store import Hit


def _table(rows: Sequence[Mapping[str, str]], columns: tuple[str, ...]) -> str:
    return "\n".join(
        (
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
            *(
                "| "
                + " | ".join(str(row.get(c, "")).replace("|", "\\|") for c in columns)
                + " |"
                for row in rows
            ),
        )
    )


def catalog(rows: Sequence[Mapping[str, str]]) -> str:
    match rows:
        case [] | ():
            return "The catalog is empty for those filters. Drop filters to see the whole store."
        case _:
            return "\n".join(
                (
                    f"{len(rows)} unit(s). Derived and stated knowledge may support project rules; assumed knowledge may not.",
                    "",
                    _table(
                        rows,
                        ("id", "type", "area", "provenance", "updated", "read_when"),
                    ),
                    "",
                    "Next: use `harness knowledge find`, then `harness knowledge fetch`.",
                )
            )


def _guidance(terms: str, guidance: Mapping[str, Any]) -> str:
    facets = guidance.get("facets") or {}
    return "\n".join(
        (
            f"No hits for `{terms}` — {guidance.get('reason', 'no matching content')}.",
            "",
            f"The store holds {guidance.get('unit_count', 0)} unit(s); {guidance.get('candidates_after_filters', 0)} passed your filters.",
            *(
                f"- Available `{name}`: "
                + ", ".join(f"`{value}`" for value in facets[name])
                for name in ("type", "area", "status")
                if facets.get(name)
            ),
            *(
                (
                    "- Terms that do exist: "
                    + ", ".join(f"`{value}`" for value in guidance["near_miss_terms"]),
                )
                if guidance.get("near_miss_terms")
                else ()
            ),
            *(
                (
                    "- Units in scope: "
                    + ", ".join(f"`{value}`" for value in guidance["nearest_units"]),
                )
                if guidance.get("nearest_units")
                else ()
            ),
            "",
            "Reformulate with one of the terms above, or widen the filters.",
        )
    )


def find(terms: str, hits: Sequence[Hit], guidance: Mapping[str, Any]) -> str:
    match hits:
        case [] | ():
            return _guidance(terms, guidance)
        case _:
            return "\n".join(
                (
                    f"{len(hits)} hit(s) for `{terms}`, best first.",
                    "",
                    *(
                        f"### `{hit.unit_id}{'#' + hit.anchor if hit.anchor else ''}` — {hit.title}\n"
                        f"lines {hit.start_line}-{hit.end_line} · score {hit.score} · matched terms: "
                        f"{', '.join(hit.matched_terms)}\n> {hit.snippet}\n"
                        for hit in hits
                    ),
                    "Fetch one with `harness knowledge fetch` rather than reading the whole unit.",
                )
            )


def fetch(result: Mapping[str, Any]) -> str:
    continuation = result.get("continuation") or {}
    return "\n".join(
        (
            f"`{result['id']}` · version `{result['version']}` · provenance `{result['provenance']}` · status `{result['status']}` · updated {result['updated'] or 'unknown'}",
            "",
            *(
                (
                    "Assumed knowledge is inconclusive and cannot support a finding on its own.",
                    "",
                )
                if result["provenance"] == "assumed"
                else ()
            ),
            result["content"],
            *(
                (
                    "",
                    f"--- truncated at the token ceiling. {continuation['remaining_lines']} line(s) remain. Continue with start_line={continuation['start_line']}, start_column={continuation['start_column']}.",
                )
                if result["truncated"]
                else ()
            ),
        )
    )


def links(identifier: str, edges: Mapping[str, Sequence[str]]) -> str:
    names = (
        ("out", "references"),
        ("out_unresolved", "unresolved references"),
        ("in", "referenced by"),
    )
    return "\n".join(
        (
            f"Links for `{identifier}`:",
            *(
                f"- {title}: "
                + (", ".join(f"`{item}`" for item in edges[key]) or "none")
                for key, title in names
                if key in edges
            ),
        )
    )
