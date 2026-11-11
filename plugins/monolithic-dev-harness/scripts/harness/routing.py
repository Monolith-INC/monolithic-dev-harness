"""Where discovery stands, read from the documents on its Epic (ROOT) and never stored.

`step` takes the latest revision of each document kind on ROOT and follows the routing table of
`modes/discovery/workflow.md`: the first row whose condition holds is the step. Re-entering the
mode on the same ROOT therefore resumes at the same step, and nothing is left to go stale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from core.result import Ok, Result, bind, err, fmap, require
from harness import documents_catalog, modes, settings
from integrations.contracts import ArtifactRef, TrackerOps

StepKind = Literal["vision", "vision-resume", "gate-g1", "prd", "gate-g2", "exit"]
# The modes whose step comes from the documents on their ROOT.
ROUTED = frozenset({"discovery"})
LABELS: dict[str, str] = {
    "vision": "Step 1, Vision Doc",
    "vision-resume": "Step 1, Vision Doc (resume)",
    "gate-g1": "Gate G1, approve the Vision Doc",
    "prd": "Step 2, PRD",
    "gate-g2": "Gate G2, approve the PRD",
    "exit": "Exit",
}
# `r2`, `2`: the number of a revision. Anything else has no number and is ordered as listed.
_REVISION = re.compile(r"[A-Za-z]?(\d+)")


@dataclass(frozen=True)
class Step:
    kind: StepKind
    detail: str


def describe(found: Step) -> str:
    """The step in one line: its name, then what holds and what to do."""
    return f"{LABELS[found.kind]}: {found.detail}"


def routed(mode: str) -> bool:
    return mode in ROUTED


def current(repo: Path, active: modes.Active) -> Result[Step]:
    """The step of the active mode, reading its ROOT through the selected tracker."""
    from integrations import registry

    if not routed(active.mode):
        return err("no_steps", f"the {active.mode} mode has no steps to read")
    return bind(
        registry.open_selected(repo, settings.load(repo)),
        lambda ops: step(ops, active.root),
    )


def step(ops: TrackerOps, root: str) -> Result[Step]:
    """The next step, from the artifacts on `root`; with no ROOT yet, step 1."""
    if not root:
        return Ok(
            Step(
                "vision",
                "there is no discovery Epic (ROOT) yet: interview the user first",
            )
        )
    return bind(
        documents_catalog.load(),
        lambda catalog: bind(
            require(
                {"vision-doc", "prd"} <= catalog.keys(),
                "invalid_documents",
                "the document catalog has no `vision-doc` and `prd`",
            ),
            lambda _: fmap(
                ops.list_artifacts(root),
                lambda found: _routed(catalog, root, _latest(found)),
            ),
        ),
    )


def _latest(artifacts: tuple[ArtifactRef, ...]) -> dict[str, ArtifactRef]:
    """The latest revision of each kind: the highest number, and among revisions with no number
    the one listed last."""
    latest: dict[str, tuple[tuple[int, int], ArtifactRef]] = {}
    for position, artifact in enumerate(artifacts):
        rank = (_number(artifact.revision), position)
        if artifact.kind not in latest or rank > latest[artifact.kind][0]:
            latest[artifact.kind] = (rank, artifact)
    return {kind: artifact for kind, (_, artifact) in latest.items()}


def _number(revision: str) -> int:
    match = _REVISION.fullmatch(revision.strip())
    return int(match.group(1)) if match else -1


def _routed(
    catalog: dict[str, documents_catalog.Document],
    root: str,
    latest: dict[str, ArtifactRef],
) -> Step:
    vision = latest.get("vision-doc")
    if vision is None:
        return Step(
            "vision", f"{root} has no Vision Doc yet: interview the user for it"
        )
    if gaps := _gaps(catalog["vision-doc"], vision):
        return Step(
            "vision-resume",
            f"the Vision Doc ({vision.revision}) has incomplete sections: "
            f"{', '.join(gaps)}; fill only those",
        )
    if not documents_catalog.approved(vision.content):
        return Step(
            "gate-g1",
            f"the Vision Doc ({vision.revision}) is complete and not approved: "
            "show it and ask for approval",
        )
    prd = latest.get("prd")
    if prd is None:
        return Step(
            "prd",
            "the Vision Doc is approved and there is no PRD yet: map what the Vision Doc "
            "already states, then interview only the gaps",
        )
    if gaps := _gaps(catalog["prd"], prd):
        return Step(
            "prd",
            f"the PRD ({prd.revision}) has incomplete sections: "
            f"{', '.join(gaps)}; fill only those",
        )
    if not documents_catalog.approved(prd.content):
        return Step(
            "gate-g2",
            f"the PRD ({prd.revision}) is complete and not approved: "
            "show it and ask for approval",
        )
    return Step(
        "exit",
        f"the PRD ({prd.revision}) is approved: tell the user the next discovery steps come in "
        "a later slice, then run `harness modes leave`",
    )


def _gaps(document: documents_catalog.Document, artifact: ArtifactRef) -> list[str]:
    """The sections that are not complete, each with how: `Risks (placeholder)`."""
    return [
        f"{section} ({state})"
        for section, state in documents_catalog.status(
            document, artifact.content
        ).items()
        if state != "complete"
    ]
