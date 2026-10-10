"""Validate a published breakdown receipt; it authorizes no code or implementation completion."""

import json

from core.result import Ok, Result, attempt, bind, err, require
from integrations.contracts import ArtifactRef, TrackerOps, WorkItem, WorkItemKind


def current(artifacts: tuple[ArtifactRef, ...]) -> Result[ArtifactRef]:
    """Numeric revisions of one title supersede older receipts without ambiguous winners."""
    return bind(
        require(
            len({a.title for a in artifacts}) == 1
            and all(a.revision.isascii() and a.revision.isdigit() for a in artifacts),
            "workflow_policy",
            "planning receipts need one title and numeric revisions",
        ),
        lambda _: _latest(artifacts),
    )


def _latest(artifacts: tuple[ArtifactRef, ...]) -> Result[ArtifactRef]:
    match tuple(
        a
        for a in artifacts
        if int(a.revision) == max(int(r.revision) for r in artifacts)
    ):
        case (receipt,):
            return Ok(receipt)
        case _:
            return err("workflow_policy", "planning receipt revision is ambiguous")


def verify(ops: TrackerOps, item: WorkItem, artifact: ArtifactRef) -> Result[object]:
    return bind(
        attempt(
            lambda: json.loads(artifact.content),
            "workflow_policy",
            "read planning completion receipt",
            ValueError,
        ),
        lambda receipt: bind(
            require(
                _bound(receipt, item),
                "workflow_policy",
                "planning completion receipt must name this breakdown task and its parent",
            ),
            lambda _: bind(
                ops.get_work_item(item.parent_id),
                lambda parent: bind(
                    require(
                        parent.kind == WorkItemKind.USER_STORY,
                        "workflow_policy",
                        "breakdown completion needs a story parent",
                    ),
                    lambda _: bind(
                        ops.list_children(parent.id),
                        lambda children: require(
                            _published(receipt, item, children),
                            "workflow_policy",
                            "planning completion receipt must match all published implementation children",
                        ),
                    ),
                ),
            ),
        ),
    )


def _bound(receipt: object, item: WorkItem) -> bool:
    match receipt:
        case {
            "purpose": "breakdown",
            "item_id": str() as key,
            "parent_id": str() as parent,
            "children": list() as children,
        }:
            return (
                item.kind == WorkItemKind.TASK
                and item.title.casefold().startswith(("breakdown —", "breakdown -"))
                and key == item.id
                and parent == item.parent_id
                and bool(parent)
                and bool(children)
                and all(isinstance(key, str) for key in children)
            )
        case _:
            return False


def _published(receipt: dict, item: WorkItem, children: tuple[WorkItem, ...]) -> bool:
    return (
        len(receipt["children"]) == len(set(receipt["children"]))
        and set(receipt["children"])
        == {child.id for child in children if child.id != item.id}
        and any(child.id == item.id for child in children)
        and all(
            child.parent_id == item.parent_id and child.kind == WorkItemKind.TASK
            for child in children
        )
    )
