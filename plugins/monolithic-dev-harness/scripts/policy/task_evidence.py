"""Task-specific completion evidence; supports code and approved documentary work."""

from __future__ import annotations

import json
from pathlib import Path

from core.result import Err, Ok, Result, attempt, bind, err, fmap, value_or
from harness import code_content, local_artifacts, state, workflow


def approved_note(repo: Path, path: Path, key: str, kind: str = "") -> bool:
    match local_artifacts.note(path):
        case local_artifacts.Note() as note:
            return (
                key in note.work_items
                and (not kind or note.kind == kind)
                and note.digest
                in state.pinned_notes(repo).get(str(path.resolve()), set())
            )
        case _:
            return False


def _inside(repo: Path, name: str) -> bool:
    return not Path(name).is_absolute() and (repo / name).resolve().is_relative_to(
        repo.resolve()
    )


def _valid(repo: Path, task, parent, scope: str, value: dict) -> bool:
    match value:
        case {
            "task": str() as key,
            "work_session": str() as owner,
            "plan": str() as plan,
            "plan_digest": str() as digest,
            "step": str() as step,
            "deliverables": dict() as files,
            "checks": list() as checks,
            "manual": list() as manual,
        } if (
            key == task.key
            and owner == scope
            and files
            and step.strip()
            and _inside(repo, plan)
        ):
            return (
                approved_note(repo, repo / plan, parent.key, "implementation-plan")
                and workflow.document_digest((repo / plan).read_bytes()) == digest
                and step in (repo / plan).read_text()
                and all(
                    isinstance(name, str)
                    and isinstance(expected, str)
                    and _inside(repo, name)
                    and workflow.file_digest(repo / name) == Ok(expected)
                    for name, expected in files.items()
                )
                and all(
                    name in state.passed_checks(repo, code_content.current(repo))
                    for name in checks
                )
                and all(
                    state.has_manual(repo, name, code_content.current(repo))
                    for name in manual
                )
                and bool(
                    checks
                    or manual
                    or all(
                        approved_note(repo, repo / name, parent.key) for name in files
                    )
                )
            )
        case _:
            return False


def completion(repo: Path, ops, task, parent, scope: str) -> Result[dict]:
    return bind(
        ops.list_artifacts(task.id),
        lambda artifacts: _find(repo, task, parent, scope, artifacts),
    )


def _find(repo, task, parent, scope, artifacts) -> Result[dict]:
    match next(
        (
            decoded
            for artifact in artifacts
            if artifact.kind == "verification"
            for result in (
                attempt(
                    lambda content=artifact.content: json.loads(content),
                    "invalid_task_evidence",
                    "Task evidence is not JSON",
                    ValueError,
                ),
            )
            if isinstance(result, Ok) and isinstance(result.value, dict)
            for decoded in (result.value,)
            if value_or(
                attempt(
                    lambda evidence=decoded: _valid(
                        repo, task, parent, scope, evidence
                    ),
                    "invalid_task_evidence",
                    "Task evidence cannot be read",
                    OSError,
                    ValueError,
                    TypeError,
                ),
                False,
            )
        ),
        None,
    ):
        case dict() as evidence:
            return Ok(evidence)
        case _:
            return err(
                "task_evidence_missing",
                f"Task {task.key} needs a verification artifact naming its session, approved plan/step, current deliverable digests and actual checks, manual evidence or approved documents.",
            )


def audit(repo: Path, ops, parent: str) -> Result[tuple[dict, ...]]:
    from harness.workflow_requirements import linked_session

    return bind(
        ops.get_work_item(parent),
        lambda story: fmap(
            ops.list_children(story.id),
            lambda children: tuple(
                {
                    "task": task.key,
                    "state": task.state.value,
                    "evidence": _audit_result(
                        completion(
                            repo,
                            ops,
                            task,
                            story,
                            linked_session(repo, story.key) or "",
                        )
                    ),
                }
                for task in children
                if task.kind.value == "task"
            ),
        ),
    )


def _audit_result(result: Result) -> dict:
    match result:
        case Ok():
            return {"ready": True}
        case Err(failure):
            return {"ready": False, "reason": failure.message}
