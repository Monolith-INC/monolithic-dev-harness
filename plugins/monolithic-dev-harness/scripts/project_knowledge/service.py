"""Read-only boundary for the project knowledge engine."""

from pathlib import Path

from project_knowledge import present, store

from core.result import Result, attempt, bind, require

DEFAULT_MAX_TOKENS = 2000


def catalog(root: Path) -> Result[str]:
    return attempt(
        lambda: present.catalog(store.KnowledgeStore(root).catalog()),
        "knowledge_unavailable",
        "Could not read the knowledge catalog",
        OSError,
        UnicodeError,
        store.StoreError,
    )


def find(root: Path, terms: str) -> Result[str]:
    return bind(
        require(bool(terms.strip()), "knowledge_query_invalid", "Enter search terms."),
        lambda _: attempt(
            lambda: present.find(terms, *store.KnowledgeStore(root).find(terms)),
            "knowledge_unavailable",
            "Could not search the knowledge store",
            OSError,
            UnicodeError,
            store.StoreError,
        ),
    )


def fetch(
    root: Path,
    identifier: str,
    *,
    anchor: str | None = None,
    start_line: int | None = None,
    start_column: int = 0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Result[str]:
    return bind(
        require(
            1 <= max_tokens <= 20000
            and (start_line is None or start_line >= 1)
            and start_column >= 0,
            "knowledge_request_invalid",
            "The fetch range or token limit is invalid.",
        ),
        lambda _: attempt(
            lambda: present.fetch(
                store.KnowledgeStore(root).fetch(
                    identifier,
                    anchor=anchor,
                    start_line=start_line,
                    start_column=start_column,
                    max_tokens=max_tokens,
                )
            ),
            "knowledge_unavailable",
            "Could not fetch the knowledge unit",
            OSError,
            UnicodeError,
            store.StoreError,
            ValueError,
        ),
    )


def links(root: Path, identifier: str, direction: str = "both") -> Result[str]:
    return attempt(
        lambda: present.links(
            identifier, store.KnowledgeStore(root).links(identifier, direction)
        ),
        "knowledge_unavailable",
        "Could not read the knowledge links",
        OSError,
        UnicodeError,
        store.StoreError,
    )
