"""Where a work item's documents live and what each one is called.

Every document belongs to one work item. Its name is `<document-type>-<scope>.md`, where the scope
names the item the way the agile-backlog-toolkit names ticket files, with the item's type in front:
`<work-item-type>-<number>-<title-slug>` (`user-story-0001-show-task-counts`). Each item has a
folder named by its scope inside the artifacts path, nested under its parents' folders, so a
Story's plan, specs and preparation documents sit together under its Feature and Epic:

    <artifacts>/epic-0001-…/feature-0002-…/user-story-0003-…/implementation-plan-user-story-0003-….md

A document written before its item exists already carries the item's final name: on the local
tracker the item's number is reserved when its ticket draft (`Tickets/Ready/<number>-<slug>.md`, the
toolkit's ticket file name) or its folder is named, and creating the item gives it that number, so
nothing is renamed afterwards. Remote trackers assign ids only on creation.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from core.result import Err, Ok, Result, bind, err, fmap, require
from harness import local_artifacts, local_tracker, settings
from harness.local_tracker import key_number, title_slug
from integrations import registry
from integrations.contracts import LogicalState, TrackerOps, WorkItem, WorkItemKind

# Epic → Feature → Story → Task is at most four levels; a longer chain is a loop in the tracker.
_MAX_DEPTH = 4
_DOCUMENT_TYPE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_FOLDER = re.compile(r"^(?:epic|feature|user-story|task|bug)-(\d+)-(.+)$")
_KINDS = ("epic", "feature", "user-story", "task", "bug")


def scope(item: WorkItem) -> str:
    """`<work-item-type>-<number>-<title-slug>`, the name of the item's folder and documents."""
    kind = item.kind.value.replace("_", "-")
    return f"{kind}-{key_number(item.key or item.id)}-{title_slug(item.title)}"


def document_name(document_type: str, scope_name: str) -> str:
    return f"{document_type}-{scope_name}.md"


def item_path(artifacts: Path, chain: tuple[WorkItem, ...], document_type: str) -> Path:
    """The document's path, `chain` running from the top-most parent down to its item. An item
    whose folder exists keeps it, and its documents keep that name, even after a rename."""
    folder = artifacts
    for item in chain:
        folder = folder / _existing_scope(folder, item)
    return folder / document_name(document_type, folder.name)


def _existing_scope(parent: Path, item: WorkItem) -> str:
    kind = item.kind.value.replace("_", "-")
    number = key_number(item.key or item.id)
    return next(
        (
            found.name
            for found in sorted(parent.glob(f"{kind}-{number}-*"))
            if found.is_dir()
        ),
        scope(item),
    )


def lineage(ops: TrackerOps, key: str) -> Result[tuple[WorkItem, ...]]:
    """The item and its parents, top-most first."""

    def climb(chain: tuple[WorkItem, ...]) -> Result[tuple[WorkItem, ...]]:
        parent = chain[0].parent_id
        if not parent:
            return Ok(chain)
        if len(chain) >= _MAX_DEPTH:
            return err(
                "document_lineage",
                f"{key} has more than {_MAX_DEPTH} levels of parents; check its parent links",
            )
        return bind(ops.get_work_item(parent), lambda item: climb((item, *chain)))

    return bind(ops.get_work_item(key), lambda item: climb((item,)))


def path(repo: Path, args: argparse.Namespace) -> Result[Path]:
    return bind(
        require(
            bool(_DOCUMENT_TYPE.match(args.type or "")),
            "document_type",
            "--type is the document's type in lowercase words joined by hyphens, "
            "e.g. implementation-plan, spec, risk-assessment",
        ),
        lambda _: bind(
            _artifacts(repo), lambda artifacts: _located(repo, artifacts, args)
        ),
    )


def _located(repo: Path, artifacts: Path, args: argparse.Namespace) -> Result[Path]:
    match args.item, args.new:
        case str() as key, None if key:
            return fmap(
                bind(
                    registry.open_selected(repo, settings.load(repo)),
                    lambda ops: lineage(ops, key),
                ),
                lambda chain: item_path(artifacts, chain, args.type),
            )
        case None, "story":
            # The toolkit's short name for a User Story.
            return _located(
                repo,
                artifacts,
                argparse.Namespace(**{**vars(args), "new": "user-story"}),
            )
        case None, str() as kind if kind not in _KINDS:
            return err("document_target", f"--new is one of {', '.join(_KINDS)}")
        case None, str() as kind if (args.title or "").strip():
            return _planned(repo, artifacts, args, WorkItemKind(kind.replace("-", "_")))
        case _:
            return err(
                "document_target",
                "name the work item with --item <key>, or a planned one with --new <type> "
                "--title <title> (and --parent <key> when it has one)",
            )


def _planned(
    repo: Path, artifacts: Path, args: argparse.Namespace, kind: WorkItemKind
) -> Result[Path]:
    """The path for an item not created yet, named by the number it will get."""
    return bind(
        registry.selected(repo, settings.load(repo)),
        lambda active: bind(
            require(
                active.manifest.name == "local",
                "document_number_unknown",
                f"{active.manifest.label} assigns an item's id when it is created; write this "
                "document once the item exists, with --item <key>",
            ),
            lambda _: bind(
                _parents(repo, args.parent),
                lambda parents: _planned_path(
                    repo, artifacts, active, parents, kind, args
                ),
            ),
        ),
    )


def _parents(repo: Path, parent: str | None) -> Result[tuple[WorkItem, ...]]:
    if not parent:
        return Ok(())
    return bind(
        registry.open_selected(repo, settings.load(repo)),
        lambda ops: lineage(ops, parent),
    )


def _planned_path(
    repo: Path,
    artifacts: Path,
    active: registry.Active,
    parents: tuple[WorkItem, ...],
    kind: WorkItemKind,
    args: argparse.Namespace,
) -> Result[Path]:
    root = local_tracker.storage_root(repo)
    slug = title_slug(args.title)
    reserved = _reserved(root, active, artifacts)
    number = reserved.get(slug) or (
        max((*reserved.values(), *_used(root, active)), default=0) + 1
    )
    planned = WorkItem(
        id="",
        key=f"{number:04d}",
        title=args.title,
        kind=kind,
        state=LogicalState.BACKLOG,
        parent_id=parents[-1].key if parents else "",
    )
    if args.type == "ticket":
        ready = active.manifest.states[LogicalState.READY]
        return Ok(root / ready / local_tracker.file_name(planned.key, args.title))
    return Ok(item_path(artifacts, (*parents, planned), args.type))


def _used(root: Path, active: registry.Active) -> set[int]:
    return local_tracker.used_numbers(root, active.manifest)


def _reserved(root: Path, active: registry.Active, artifacts: Path) -> dict[str, int]:
    """Slug → number for every draft ticket and every item folder that names one."""
    found: dict[str, int] = {}
    for path, _, _ in local_tracker.drafts(root):
        if numbered := local_tracker.numbered(path.name):
            found[numbered[1]] = numbered[0]
    for folder in artifacts.rglob("*") if artifacts.is_dir() else ():
        if folder.is_dir() and (match := _FOLDER.match(folder.name)):
            found.setdefault(match.group(2), int(match.group(1)))
    return found


def document_path(
    repo: Path, ops: TrackerOps, key: str, document_type: str
) -> Result[Path]:
    """Where an existing item's document of `document_type` lives."""
    return bind(
        _artifacts(repo),
        lambda artifacts: fmap(
            lineage(ops, key), lambda chain: item_path(artifacts, chain, document_type)
        ),
    )


def _artifacts(repo: Path) -> Result[Path]:
    match local_artifacts.artifacts_dir(repo):
        case None:
            return err(
                "artifacts_path_missing",
                "the settings name no artifacts path; run bootstrap to choose one",
            )
        case folder:
            return Ok(folder)


def add_parser(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "document",
        help="print where a work item's document of a given type lives, and its name",
    )
    parser.add_argument("operation", choices=("path",))
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--type",
        help="the document's type, e.g. implementation-plan, spec, risk-assessment",
    )
    parser.add_argument("--item", help="the work item's key in the tracker")
    parser.add_argument(
        "--new",
        metavar="TYPE",
        help=f"a work item not created yet, of this type ({', '.join(_KINDS)}); with --title",
    )
    parser.add_argument("--title", help="the planned item's title (with --new)")
    parser.add_argument("--parent", help="the planned item's parent key (with --new)")


def command(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    match path(repo, args):
        case Ok(found):
            print(found.relative_to(repo) if found.is_relative_to(repo) else found)
            return 0
        case Err(failure):
            print(failure.message, file=sys.stderr)
            return 2
