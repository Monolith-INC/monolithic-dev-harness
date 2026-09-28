from __future__ import annotations

from pathlib import Path

from core.result import Result, attempt, failures, oks
from integrations.planning import EstimableItem, planning_item, read_capacity_file

from ..ingest import parse_frontmatter
from .base import ProviderResult

# Conventional sub-paths looked for *underneath the path the user supplied*. The plugin
# creates none of them and requires none of them; they are only where it looks first.
TICKET_DIRS = ("Tickets/Ready", "Tickets/InProgress", "Tickets/Done", "Tickets", ".")
CAPACITY_FILENAME = "capacity-{iteration}.json"


class FilesystemProvider:
    """Reads estimation and capacity data from a directory the user nominated.

    The plugin has no opinion about what that directory is or what else lives there. It
    reads markdown frontmatter from it, creates nothing, and refuses with an explanation
    rather than guessing when no path has been configured.
    """

    name = "filesystem"

    NO_PATH = (
        "No artifacts path configured. Ask the user where local artifacts should be written; "
        "they set it as artifacts_path in .harness/settings.json."
    )

    def __init__(self, artifacts_dir: Path | None) -> None:
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None

    @property
    def configured(self) -> bool:
        return self.artifacts_dir is not None

    # -- reads -------------------------------------------------------------

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        """The sprint from `capacity-<iteration>.json`, in the shared capacity format."""
        return (
            ProviderResult.of(
                read_capacity_file(
                    self.artifacts_dir
                    / CAPACITY_FILENAME.format(iteration=iteration_ref),
                    iteration_ref,
                ),
                lambda reading: reading.capacity,
                lambda reading: reading.warnings,
            )
            if self.configured
            else ProviderResult.failure(self.NO_PATH)
        )

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        """Drafts whose front matter names this iteration, in the shared planning-item format.

        A draft with no `iteration` key is included when `iteration_ref` is empty, so the
        common case of a directory with no sprint metadata still produces a useful total.
        """
        if not self.configured:
            return ProviderResult.failure(self.NO_PATH)
        reads = tuple(map(_read, _ticket_paths(self.artifacts_dir)))
        items = [
            item
            for path, text in oks(reads)
            for item in (_ticket(path, text),)
            if not iteration_ref or item.iteration == iteration_ref
        ]
        return ProviderResult.success(
            items,
            warnings=tuple(failure.message for failure in failures(reads))
            + (() if items else (f"no drafts found under {self.artifacts_dir}",)),
        )


def _ticket_paths(root: Path) -> tuple[Path, ...]:
    """Each draft once, in the order the conventional folders are searched."""
    found = (
        path
        for reldir in TICKET_DIRS
        if (root / reldir).is_dir()
        for path in sorted((root / reldir).glob("*.md"))
    )
    return tuple({path.resolve(): path for path in found}.values())


def _read(path: Path) -> Result[tuple[Path, str]]:
    return attempt(
        lambda: (path, path.read_text(encoding="utf-8")),
        "unreadable",
        f"unreadable: {path}",
        OSError,
        UnicodeDecodeError,
    )


def _ticket(path: Path, text: str) -> EstimableItem:
    frontmatter, _ = parse_frontmatter(text)
    return planning_item(
        str(frontmatter.get("provider_id") or path.stem),
        str(frontmatter.get("title") or path.stem),
        str(frontmatter.get("work_item_type") or frontmatter.get("type") or ""),
        frontmatter,
    )
