"""Assess, approve, and safely materialize implementation that predates a harness session.

Assessment is read-only with respect to Git. Plans and approvals are immutable harness state keyed
to exact content. Materialization creates a separate worktree from the approved base and stages one
faithful snapshot there; it never rewrites or stashes the source checkout and never manufactures a
commit history.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, require
from integrations.contracts import ArtifactRef, LogicalState, WorkItem

from . import gitstate, rules, settings, state

SCHEMA = "harness-adoption-assessment:v1"
PLAN_SCHEMA = "harness-adoption-plan:v1"
ID_PREFIX = "HA-"
# What adoption inventories and carries: everything except this clone's own harness records.
SCOPE = (
    "--",
    ".",
    *(f":(exclude){path.rstrip('/')}" for path in state.LOCAL_ONLY_PATHS),
)


class AdoptionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _root(repo: Path) -> Path:
    return state.state_dir(repo) / "adoptions"


def _folder(repo: Path, adoption_id: str) -> Path:
    return _root(repo) / state.safe_name(adoption_id)


def _read(path: Path) -> Result[dict[str, Any]]:
    return (
        Ok(record)
        if (record := state.read_json(path)) is not None
        else err(
            "adoption_not_found", f"adoption record not found or unreadable: {path}"
        )
    )


def _untracked(repo: Path) -> tuple[str, ...]:
    output = gitstate.git(
        repo, "ls-files", "--others", "--exclude-standard", "-z", *SCOPE
    )
    return tuple(sorted(filter(None, output.split("\0"))))


def _changed(repo: Path, *arguments: str) -> tuple[str, ...]:
    output = gitstate.git(repo, "diff", "--name-only", *arguments, *SCOPE)
    return tuple(filter(None, output.splitlines()))


def _patch(repo: Path, *arguments: str) -> bytes:
    return _run(repo, "diff", "--binary", *arguments, *SCOPE)


def _file_digest(path: Path) -> str:
    match path.is_file(), path.is_symlink():
        case True, False:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        case _:
            raise AdoptionError(f"untracked path is not a regular file: {path}")


def _fingerprint(repo: Path) -> dict[str, Any]:
    untracked = _untracked(repo)
    value = {
        "head": gitstate.head_sha(repo),
        "staged": hashlib.sha256(_patch(repo, "--cached")).hexdigest(),
        "unstaged": hashlib.sha256(_patch(repo)).hexdigest(),
        "untracked": {path: _file_digest(repo / path) for path in untracked},
    }
    return {**value, "digest": _digest(value)}


def _commits(repo: Path, base_commit: str) -> tuple[dict[str, Any], ...]:
    output = gitstate.git(repo, "log", "--format=%H%x1f%s", f"{base_commit}..HEAD")
    return tuple(
        {
            "sha": sha,
            "subject": subject,
            "paths": tuple(
                filter(
                    None,
                    gitstate.git(
                        repo,
                        "diff-tree",
                        "--no-commit-id",
                        "--name-only",
                        "-r",
                        sha,
                    ).splitlines(),
                )
            ),
        }
        for line in output.splitlines()
        if (parts := line.split("\x1f", 1))
        for sha, subject in (parts,)
    )


def _task_report(
    task: WorkItem,
    commits: tuple[dict[str, Any], ...],
    evidence_current: bool,
) -> dict[str, Any]:
    mapped = tuple(
        commit for commit in commits if _mentions_key(str(commit["subject"]), task.key)
    )
    classification = _classification(task.state, bool(mapped), evidence_current)
    return {
        "key": task.key,
        "title": task.title,
        "tracker_state": task.state.value,
        "classification": classification,
        "commits": tuple(str(commit["sha"]) for commit in mapped),
        "paths": tuple(
            sorted({str(path) for commit in mapped for path in commit.get("paths", ())})
        ),
        "reason": _classification_reason(classification),
    }


def _classification(
    tracker_state: LogicalState, mapped: bool, evidence_current: bool
) -> str:
    match tracker_state, mapped, evidence_current:
        case LogicalState.DONE, True, True:
            return "completed"
        case LogicalState.DONE, _, _:
            return "unverified"
        case _, True, _:
            return "changed"
        case _:
            return "incomplete"


def _classification_reason(classification: str) -> str:
    return {
        "completed": "tracker marks the Task done, mapped commits exist, and current-tree checks are complete",
        "unverified": "tracker marks the Task done but mapped change or current-tree evidence is missing",
        "changed": "mapped commits exist but the Task is not verified done",
        "incomplete": "no Task-labelled commit or done tracker state was found",
    }[classification]


def _mentions_key(subject: str, key: str) -> bool:
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])",
            subject,
            re.IGNORECASE,
        )
    )


def assess(
    repo: Path,
    work_item: WorkItem,
    tasks: tuple[WorkItem, ...],
    artifacts: tuple[ArtifactRef, ...],
    base_ref: str,
) -> Result[dict[str, Any]]:
    """Persist a deterministic assessment of the current checkout and tracker snapshot."""
    return bind(
        attempt(
            lambda: _assessment(repo.resolve(), work_item, tasks, artifacts, base_ref),
            "adoption_assessment_failed",
            "could not assess the existing implementation",
            OSError,
            subprocess.SubprocessError,
            gitstate.GitError,
            AdoptionError,
        ),
        lambda report: fmap(
            _store_assessment(repo.resolve(), report), lambda _: report
        ),
    )


def _assessment(
    repo: Path,
    work_item: WorkItem,
    tasks: tuple[WorkItem, ...],
    artifacts: tuple[ArtifactRef, ...],
    base_ref: str,
) -> dict[str, Any]:
    identity = sessions_checkout(repo)
    base_commit = gitstate.git(repo, "rev-parse", "--verify", base_ref)
    merge_base = gitstate.git(repo, "merge-base", base_commit, "HEAD")
    commits = _commits(repo, base_commit)
    fingerprint = _fingerprint(repo)
    transfer_patch = _patch(repo, merge_base)
    loaded = settings.load(repo)
    chosen = loaded.value if isinstance(loaded, Ok) else None
    required = rules.applicable_checks(repo, chosen) if chosen is not None else set()
    passed = state.passed_checks(repo, gitstate.head_tree(repo))
    staged = _changed(repo, "--cached")
    unstaged = _changed(repo)
    # HEAD evidence covers the adopted content only when nothing uncommitted or untracked is carried.
    evidence_current = (
        chosen is not None
        and not (staged or unstaged or fingerprint["untracked"])
        and required <= passed
    )
    task_keys = tuple(task.key for task in tasks)
    unmapped_commits = tuple(
        commit
        for commit in commits
        if not any(_mentions_key(str(commit["subject"]), key) for key in task_keys)
    )
    body = {
        "schema": SCHEMA,
        "source": {
            "worktree": identity[0],
            "branch": identity[1],
            "head": fingerprint["head"],
            "base_ref": base_ref,
            "base_commit": base_commit,
            "merge_base": merge_base,
            "contains_base_tip": merge_base == base_commit,
            "fingerprint": fingerprint,
        },
        "transfer": {
            "delta_base": merge_base,
            "patch_digest": hashlib.sha256(transfer_patch).hexdigest(),
        },
        "work_item": {
            "key": work_item.key,
            "title": work_item.title,
            "state": work_item.state.value,
        },
        "artifacts": tuple(sorted({artifact.kind for artifact in artifacts})),
        "evidence": {
            "tree": gitstate.head_tree(repo),
            "required_checks": tuple(sorted(required)),
            "passed_checks": tuple(sorted(passed)),
            "current": evidence_current,
        },
        "changes": {
            "commits": commits,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": tuple(fingerprint["untracked"].keys()),
        },
        "scope_differences": {
            "unmapped_commits": unmapped_commits,
            "unmapped_paths": tuple(
                sorted({*staged, *unstaged, *fingerprint["untracked"].keys()})
            ),
        },
        "tasks": tuple(_task_report(task, commits, evidence_current) for task in tasks),
    }
    adoption_id = ID_PREFIX + _digest(body)[:10].upper()
    return {**body, "id": adoption_id}


def sessions_checkout(repo: Path) -> tuple[str, str]:
    """Worktree and branch without creating or requiring a harness session."""
    output = gitstate.git(
        repo,
        "rev-parse",
        "--show-toplevel",
        "--symbolic-full-name",
        "HEAD",
    ).splitlines()
    match output:
        case [worktree, ref] if ref.startswith("refs/heads/"):
            return str(Path(worktree).resolve()), ref.removeprefix("refs/heads/")
        case _:
            raise AdoptionError("the source checkout must be on a branch")


def _store_assessment(repo: Path, report: dict[str, Any]) -> Result[Path]:
    path = _folder(repo, str(report["id"])) / "assessment.json"
    return attempt(
        lambda: _write_once(path, report),
        "adoption_state_failed",
        "could not persist the adoption assessment",
        OSError,
        AdoptionError,
    )


def _write_once(path: Path, payload: dict[str, Any]) -> Path:
    existing = state.read_json(path)
    match existing:
        case None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return path
        case record if record == json.loads(json.dumps(payload)):
            return path
        case _:
            raise AdoptionError(f"refusing to replace immutable adoption state: {path}")


def assessment(repo: Path, adoption_id: str) -> Result[dict[str, Any]]:
    return _read(_folder(repo, adoption_id) / "assessment.json")


def create_plan(
    repo: Path,
    adoption_id: str,
    target_branch: str,
    destination: Path,
) -> Result[dict[str, Any]]:
    return bind(
        assessment(repo, adoption_id),
        lambda report: bind(
            _valid_destination(repo.resolve(), destination.resolve()),
            lambda target: bind(
                attempt(
                    lambda: gitstate.git(
                        repo, "check-ref-format", "--branch", target_branch.strip()
                    ),
                    "invalid_adoption_plan",
                    "the adoption plan needs a valid target branch",
                    gitstate.GitError,
                ),
                lambda branch: _store_plan(
                    repo.resolve(),
                    report,
                    branch,
                    target,
                ),
            ),
        ),
    )


def _valid_destination(repo: Path, destination: Path) -> Result[Path]:
    inside = destination == repo or repo in destination.parents
    return bind(
        require(
            not inside,
            "invalid_adoption_plan",
            "the recovery worktree must be outside the source checkout",
        ),
        lambda _: bind(
            require(
                not destination.exists(),
                "invalid_adoption_plan",
                f"the recovery worktree destination already exists: {destination}",
            ),
            lambda _: Ok(destination),
        ),
    )


def _store_plan(
    repo: Path,
    report: dict[str, Any],
    target_branch: str,
    destination: Path,
) -> Result[dict[str, Any]]:
    tasks = tuple(report.get("tasks", ()))
    next_task = next(
        (
            str(task.get("key", ""))
            for task in tasks
            if task.get("classification") != "completed"
        ),
        "",
    )
    body = {
        "schema": PLAN_SCHEMA,
        "id": report["id"],
        "assessment_digest": _digest(report),
        "source_fingerprint": report["source"]["fingerprint"]["digest"],
        "base_ref": report["source"]["base_ref"],
        "base_commit": report["source"]["base_commit"],
        "target_branch": target_branch,
        "destination": str(destination),
        "next_task": next_task,
        "unverified_tasks": tuple(
            str(task.get("key", ""))
            for task in tasks
            if task.get("classification") in {"changed", "unverified"}
        ),
        "strategy": "separate-worktree-staged-adoption",
    }
    plan = {**body, "digest": _digest(body)}
    path = _folder(repo, str(report["id"])) / "plan.json"
    return fmap(
        attempt(
            lambda: _write_pending_plan(repo, str(report["id"]), path, plan),
            "adoption_state_failed",
            "could not persist the adoption plan",
            OSError,
            AdoptionError,
        ),
        lambda _: plan,
    )


def _write_pending_plan(
    repo: Path, adoption_id: str, path: Path, payload: dict[str, Any]
) -> Path:
    match state.read_json(_folder(repo, adoption_id) / "approval.json"):
        case dict():
            raise AdoptionError(
                f"adoption plan {adoption_id} is already approved and immutable"
            )
        case _:
            state.write_json(path, payload)
            return path


def plan(repo: Path, adoption_id: str) -> Result[dict[str, Any]]:
    return _read(_folder(repo, adoption_id) / "plan.json")


def plan_for_question(repo: Path, adoption_id: str) -> Result[dict[str, Any]]:
    return bind(
        plan(repo, adoption_id),
        lambda found: bind(
            require(
                not approved(repo, adoption_id, str(found.get("digest", ""))),
                "adoption_already_approved",
                f"adoption plan {adoption_id} is already approved",
            ),
            lambda _: Ok(found),
        ),
    )


def approve(repo: Path, adoption_id: str, digest: str, question: str) -> Result[Path]:
    return bind(
        plan(repo, adoption_id),
        lambda current: bind(
            require(
                str(current.get("digest", "")) == digest,
                "adoption_changed",
                "the adoption plan changed after the question was shown",
            ),
            lambda _: attempt(
                lambda: _write_once(
                    _folder(repo, adoption_id) / "approval.json",
                    {
                        "id": adoption_id,
                        "plan_digest": digest,
                        "question": question,
                        "approved": _now(),
                    },
                ),
                "adoption_state_failed",
                "could not record adoption approval",
                OSError,
                AdoptionError,
            ),
        ),
    )


def approved(repo: Path, adoption_id: str, digest: str) -> bool:
    record = state.read_json(_folder(repo, adoption_id) / "approval.json")
    return bool(record) and record.get("plan_digest") == digest


def status(repo: Path, adoption_id: str) -> Result[dict[str, Any]]:
    return bind(
        assessment(repo, adoption_id),
        lambda report: Ok(_status(repo, adoption_id, report)),
    )


def _status(repo: Path, adoption_id: str, report: dict[str, Any]) -> dict[str, Any]:
    found = state.read_json(_folder(repo, adoption_id) / "plan.json")
    return {
        "id": adoption_id,
        "assessment": report,
        "plan": found,
        "approved": (
            approved(repo, adoption_id, str(found.get("digest", "")))
            if found is not None
            else False
        ),
        "materialized": state.read_json(
            _folder(repo, adoption_id) / "materialized.json"
        ),
    }


def materialize(repo: Path, adoption_id: str) -> Result[dict[str, Any]]:
    return bind(
        assessment(repo, adoption_id),
        lambda report: bind(
            plan(repo, adoption_id),
            lambda found: bind(
                require(
                    approved(repo, adoption_id, str(found.get("digest", ""))),
                    "adoption_not_approved",
                    f"adoption plan {adoption_id} needs the user's Approve adoption click",
                ),
                lambda _: attempt(
                    lambda: _materialized(repo.resolve(), report, found),
                    "adoption_materialization_failed",
                    "could not materialize the approved adoption plan",
                    OSError,
                    subprocess.SubprocessError,
                    gitstate.GitError,
                    AdoptionError,
                ),
            ),
        ),
    )


def _run(repo: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    match result.returncode:
        case 0:
            return result.stdout
        case _:
            raise AdoptionError(
                f"git {' '.join(arguments)} failed: {result.stderr.decode(errors='replace').strip()}"
            )


def _branch_absent(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
        ],
        capture_output=True,
        check=False,
    )
    return result.returncode == 1


def _materialized(
    repo: Path, report: dict[str, Any], plan_record: dict[str, Any]
) -> dict[str, Any]:
    match state.read_json(_folder(repo, str(report["id"])) / "materialized.json"):
        case dict() as record:
            return record
        case _:
            return _materialize(repo, report, plan_record)


def _materialize(
    repo: Path, report: dict[str, Any], plan_record: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint(repo)
    expected = str(plan_record["source_fingerprint"])
    match current["digest"] == expected:
        case False:
            raise AdoptionError(
                "the source checkout changed after assessment; assess and approve it again"
            )
        case True:
            pass
    destination = Path(str(plan_record["destination"]))
    branch = str(plan_record["target_branch"])
    base_ref = str(plan_record["base_ref"])
    base_commit = str(plan_record["base_commit"])
    match destination.exists(), _branch_absent(repo, branch):
        case True, _:
            raise AdoptionError(f"destination now exists: {destination}")
        case _, False:
            raise AdoptionError(f"target branch now exists: {branch}")
        case False, True:
            pass
    match gitstate.git(repo, "rev-parse", "--verify", base_ref) == base_commit:
        case False:
            raise AdoptionError(
                f"base {base_ref} moved after assessment; assess and approve it again"
            )
        case True:
            pass
    patch = _patch(repo, str(report["transfer"]["delta_base"]))
    match hashlib.sha256(patch).hexdigest() == report["transfer"]["patch_digest"]:
        case False:
            raise AdoptionError(
                "the source transfer patch changed after assessment; assess and approve it again"
            )
        case True:
            pass
    _run(repo, "worktree", "add", "-b", branch, str(destination), base_commit)
    try:
        target_tree = _stage_transfer(repo, destination, report, patch)
        match _fingerprint(repo)["digest"] == expected:
            case False:
                raise AdoptionError(
                    "the source checkout changed during materialization"
                )
            case True:
                pass
    except (OSError, subprocess.SubprocessError, gitstate.GitError, AdoptionError):
        _discard(repo, destination, branch)
        raise
    result = {
        "id": report["id"],
        "destination": str(destination),
        "branch": branch,
        "base_commit": base_commit,
        "staged_tree": target_tree,
        "source_unchanged": True,
        "committed": False,
        "materialized": _now(),
    }
    state.write_json(_folder(repo, str(report["id"])) / "materialized.json", result)
    return result


def _stage_transfer(
    repo: Path, destination: Path, report: dict[str, Any], patch: bytes
) -> str:
    match patch:
        case b"":
            pass
        case _:
            _run(destination, "apply", "--binary", "-", input_bytes=patch)
    tuple(
        _copy_untracked(repo, destination, path)
        for path in report["source"]["fingerprint"]["untracked"]
    )
    _run(destination, "add", "-A")
    return gitstate.index_tree(destination)


def _discard(repo: Path, destination: Path, branch: str) -> None:
    """Remove the worktree and branch this attempt created so the approved plan can be retried."""
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "remove", "--force", str(destination)],
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["git", "-C", str(repo), "branch", "-D", branch],
        capture_output=True,
        check=False,
    )


def _copy_untracked(repo: Path, destination: Path, relative: str) -> Path:
    source = repo / relative
    target = destination / relative
    match source.is_file(), source.is_symlink(), target.exists():
        case True, False, False:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            return target
        case True, False, True:
            raise AdoptionError(
                f"untracked source path overlaps the intended base: {relative}"
            )
        case _:
            raise AdoptionError(f"refusing non-regular untracked path: {relative}")
