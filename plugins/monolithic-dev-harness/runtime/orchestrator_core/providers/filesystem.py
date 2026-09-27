from __future__ import annotations

from pathlib import Path

from core.result import Err, Ok
from integrations.planning import EstimableItem, as_float, read_capacity_file

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
        if not self.configured:
            return ProviderResult.failure(self.NO_PATH)
        match read_capacity_file(
            self.artifacts_dir / CAPACITY_FILENAME.format(iteration=iteration_ref),
            iteration_ref,
        ):
            case Ok(reading):
                return ProviderResult.success(
                    reading.capacity, warnings=reading.warnings
                )
            case Err(failure):
                return ProviderResult.failure(failure.message)

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        """Collect ticket drafts whose frontmatter names this iteration.

        A draft with no `iteration` key is included when `iteration_ref` is empty, so the
        common case of a directory with no sprint metadata still produces a useful total.
        """
        if not self.configured:
            return ProviderResult.failure(self.NO_PATH)

        items: list[EstimableItem] = []
        warnings: list[str] = []
        seen: set[Path] = set()

        for reldir in TICKET_DIRS:
            directory = self.artifacts_dir / reldir
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.md")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    raw = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    warnings.append(f"unreadable: {path}: {exc}")
                    continue
                frontmatter, _ = parse_frontmatter(raw)
                item_iteration = frontmatter.get("iteration")
                item_iteration = (
                    str(item_iteration) if item_iteration is not None else None
                )
                if iteration_ref and item_iteration != iteration_ref:
                    continue
                items.append(
                    EstimableItem(
                        item_id=str(frontmatter.get("provider_id") or path.stem),
                        title=str(frontmatter.get("title") or path.stem),
                        item_type=str(
                            frontmatter.get("work_item_type")
                            or frontmatter.get("type")
                            or ""
                        ),
                        points=as_float(frontmatter.get("story_points")),
                        estimated_hours=as_float(frontmatter.get("effort_hours")),
                        remaining_hours=as_float(frontmatter.get("remaining_hours")),
                        completed_hours=as_float(frontmatter.get("completed_hours")),
                        activity=str(frontmatter["activity"])
                        if frontmatter.get("activity")
                        else None,
                        assigned_to=str(frontmatter["assigned_to"])
                        if frontmatter.get("assigned_to")
                        else None,
                        state=str(frontmatter.get("state") or ""),
                        iteration=item_iteration,
                    )
                )

        if not items:
            warnings.append(f"no drafts found under {self.artifacts_dir}")
        return ProviderResult.success(items, warnings=tuple(warnings))
