"""A document of the catalog is published only as the draft the user approved, and only that one.

An approval covers the content it approved: the Vision Doc's approval is not the PRD's. The hook
compares a published document with the reviewed draft, ignoring only the two parts publishing
changes (the `Status` line and `Change history`). Every test runs on the local tracker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.result import Ok
from harness import cli, hook, modes, state, workflow
from tests.settings_fixture import write_settings

GATEWAY = "mcp__plugin_monolithic-dev-harness_workflow-integrations__"
CONVERSATION = "chat-a"
ROOT = "EPIC-0001"


def draft(title: str, body: str) -> str:
    return (
        f"# {title}\n\nStatus: Draft\n\n## Body\n\n{body}\n\n## Change history\n\n"
        "| Date | Change | By |\n|---|---|---|\n| 2026-11-11 | Draft | Ana |\n"
    )


def approved(text: str) -> str:
    """The draft as it is published once approved: the two parts publishing changes."""
    return (
        text.replace("Status: Draft", "Status: Approved")
        + "| 2026-11-12 | Approved by Ana | Ana |\n"
    )


VISION = draft("Vision Doc — Atlas", "People lose track of their orders.")
PRD = draft("PRD — Atlas", "Orders shall be searchable.")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    write_settings(project, artifacts_path="Artifacts")
    (project / "Artifacts").mkdir()
    return project


def written(project: Path, name: str, text: str) -> str:
    path = project / "Artifacts" / name
    path.write_text(text, encoding="utf-8")
    return f"Artifacts/{name}"


def approve_directly(project: Path, name: str, approval: str = "HB-DOC") -> None:
    """An approval bound to the file as it reads now, as the `approve-document` answer opens."""
    match workflow.file_digest(project / name):
        case Ok(digest):
            state.open_approval(
                project, approval, 20, binds={"artifacts": [[name, digest]]}
            )
        case failure:
            raise AssertionError(f"cannot read {name}: {failure!r}")


def ask_and_approve(
    project: Path, name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The user's gate, as the skill runs it: show, ask `approve-document`, the user answers 1."""
    assert (
        cli.main(["workflow", "show", "--artifact", name, "--repo", str(project)]) == 0
    )
    present = [
        "decision",
        "present",
        "--gate",
        "approve-document",
        "--artifact",
        name,
        "--host",
        "text",
        "--repo",
        str(project),
    ]
    assert cli.main(present) == 0
    capsys.readouterr()
    hook.handle_prompt(
        "claude",
        {"cwd": str(project), "prompt": "1", "session_id": CONVERSATION},
    )
    assert "the user approved" in capsys.readouterr().out


def publication(
    project: Path,
    kind: str,
    content: str,
    capsys: pytest.CaptureFixture[str],
    tool: str = "tracker_publish_artifact",
    ref: str = ROOT,
) -> str | None:
    """The reason the hook refuses this publication, or None when it allows it."""
    hook.handle_pre_tool(
        "claude",
        "pre-tool",
        {
            "cwd": str(project),
            "tool_name": GATEWAY + tool,
            "tool_input": {
                "ref": ref,
                "kind": kind,
                "title": f"{kind} — Atlas",
                "content": content,
                "revision": "r1",
                **({"artifactId": "A-1"} if tool == "tracker_revise_artifact" else {}),
            },
            "session_id": CONVERSATION,
        },
    )
    out = capsys.readouterr().out.strip()
    return (
        json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        if out
        else None
    )


def test_after_the_vision_doc_gate_alone_the_prd_is_refused_until_its_own_gate(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert isinstance(modes.enter(repo, "discovery", ROOT), Ok)
    vision = written(repo, "vision.md", VISION)
    prd = written(repo, "prd.md", PRD)
    ask_and_approve(repo, vision, capsys)

    assert publication(repo, "vision-doc", approved(VISION), capsys) is None
    refused = publication(repo, "prd", approved(PRD), capsys)

    assert refused is not None
    assert "[harness approval-required]" in refused
    assert "prd" in refused
    assert "approve-document" in refused

    ask_and_approve(repo, prd, capsys)

    assert publication(repo, "prd", approved(PRD), capsys) is None
    assert publication(repo, "vision-doc", approved(VISION), capsys) is None


@pytest.mark.parametrize(
    "tool", ["tracker_publish_artifact", "tracker_revise_artifact"]
)
def test_a_document_is_published_as_the_approved_draft_with_only_its_status_and_history_changed(
    tool: str, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    approve_directly(repo, written(repo, "prd.md", PRD))

    assert publication(repo, "prd", approved(PRD), capsys, tool) is None
    assert publication(repo, "prd", PRD, capsys, tool) is None


@pytest.mark.parametrize(
    "tool", ["tracker_publish_artifact", "tracker_revise_artifact"]
)
@pytest.mark.parametrize(
    "content",
    [
        approved(PRD).replace("searchable", "sortable"),
        approved(PRD).replace("## Body", "## Body\n\nAnd more."),
        approved(VISION),
        "",
    ],
    ids=["reworded", "extra text", "another document", "empty"],
)
def test_a_document_that_differs_from_the_approved_draft_is_refused_with_guidance(
    tool: str, content: str, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    approve_directly(repo, written(repo, "prd.md", PRD))

    refused = publication(repo, "prd", content, capsys, tool)

    assert refused is not None
    assert "no approved draft holds" in refused
    assert "approve-document" in refused


def test_a_draft_edited_after_its_approval_is_no_longer_the_approved_one(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    name = written(repo, "prd.md", PRD)
    approve_directly(repo, name)
    edited = PRD.replace("searchable", "sortable")
    written(repo, "prd.md", edited)

    assert publication(repo, "prd", approved(PRD), capsys) is not None
    assert publication(repo, "prd", approved(edited), capsys) is not None


def test_a_general_approval_does_not_cover_a_document(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state.open_approval(repo, "HB-GENERAL", 20)

    refused = publication(repo, "prd", approved(PRD), capsys)

    assert refused is not None
    assert "approve-document" in refused


def test_an_artifact_outside_the_catalog_is_covered_as_before(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Feature's closeout is covered by its `move-item` approval, which binds no document."""
    state.open_approval(
        repo, "HB-MOVE", 20, binds={"target": ["item", "FEAT-1"], "bound": True}
    )

    allowed = publication(repo, "resolution_report", "Closed.", capsys, ref="FEAT-1")
    elsewhere = publication(repo, "resolution_report", "Closed.", capsys, ref="FEAT-2")

    assert allowed is None
    assert elsewhere is not None
    assert "no approval covers it" in elsewhere


def test_a_kind_that_is_not_text_is_not_a_catalog_document_and_breaks_nothing(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    refused = publication(repo, ["prd"], approved(PRD), capsys)  # type: ignore[arg-type]

    assert refused is not None
    assert "no approval covers it" in refused
