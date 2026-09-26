"""Pull requests and review threads: GitHub through the `gh` CLI, Azure Repos through its MCP server.

Both meet `ScmOps`. Azure Repos starts the same MCP server as the Azure DevOps tracker, from that
tracker's manifest, so the command lives in one place.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, require, sequence
from harness.settings import Selection

from . import payloads, registry, transport
from .contracts import PullRequest, PullRequestDraft, ReviewThread, ScmOps, Transport

REQUIRED_VALUES = {
    "github": ("owner", "repo"),
    "azure-repos": ("organization", "project", "repository"),
}
DESCRIPTION_LIMIT = 4000  # Azure Repos rejects longer pull request descriptions
PR_STATUS = {0: "notSet", 1: "active", 2: "abandoned", 3: "completed"}
THREAD_STATUS = {
    0: "unknown",
    1: "active",
    2: "fixed",
    3: "wontFix",
    4: "closed",
    5: "byDesign",
    6: "pending",
}

Runner = Callable[[tuple[str, ...]], Result[str]]


def build(selection: Selection, repo: Path) -> Result[ScmOps]:
    missing = tuple(
        key
        for key in REQUIRED_VALUES[selection.name]
        if not selection.values.get(key, "").strip()
    )
    return bind(
        require(
            not missing,
            "invalid_settings",
            f"scm.values is missing {list(missing)} for {selection.name}",
        ),
        lambda _: (
            Ok(github(selection.values, gh))
            if selection.name == "github"
            else fmap(
                azure_transport(selection.values, repo),
                lambda call: azure_repos(selection.values, call),
            )
        ),
    )


# --- GitHub -----------------------------------------------------------------------------------


def gh(args: tuple[str, ...]) -> Result[str]:
    return bind(
        attempt(
            lambda: subprocess.run(
                ["gh", *args], capture_output=True, text=True, timeout=30
            ),
            "provider_unavailable",
            "the GitHub CLI could not run",
            OSError,
            subprocess.SubprocessError,
        ),
        lambda done: (
            Ok(done.stdout)
            if done.returncode == 0
            else err("provider_error", (done.stderr or done.stdout).strip())
        ),
    )


def _json(text: str) -> Any:
    return transport.decode(text.strip(), {}) if text.strip() else {}


def github(values: Mapping[str, str], run: Runner) -> ScmOps:
    slug = f"{values['owner']}/{values['repo']}"
    fields = "number,title,url,headRefName,baseRefName,state"

    def view(ref: str) -> Result[PullRequest]:
        return fmap(
            run(("pr", "view", ref, "-R", slug, "--json", fields)),
            lambda out: github_pull_request(_json(out)),
        )

    return ScmOps(
        get_pull_request=view,
        create_pull_request=lambda draft: bind(
            run(
                (
                    "pr",
                    "create",
                    "-R",
                    slug,
                    "--title",
                    draft.title,
                    "--body",
                    draft.description,
                    "--head",
                    draft.source_branch,
                    "--base",
                    draft.target_branch,
                    *(("--draft",) if draft.draft else ()),
                )
            ),
            lambda out: view(out.strip().rsplit("/", 1)[-1] or draft.source_branch),
        ),
        list_review_threads=lambda ref: fmap(
            run(("api", f"repos/{slug}/pulls/{ref}/comments")),
            lambda out: tuple(
                github_thread(item) for item in payloads.records(_json(out))
            ),
        ),
        reply_to_thread=lambda pr, thread, content: fmap(
            run(
                (
                    "api",
                    "-X",
                    "POST",
                    f"repos/{slug}/pulls/{pr}/comments/{thread}/replies",
                    "-f",
                    f"body={content}",
                )
            ),
            lambda out: payloads.mapping(_json(out)),
        ),
        link_work_item=lambda pr, item: _github_link(run, slug, pr, item),
    )


def github_pull_request(value: Any) -> PullRequest:
    record = payloads.mapping(value)
    number = payloads.text(record, "number", "id")
    return PullRequest(
        number,
        number,
        payloads.text(record, "title"),
        payloads.text(record, "url"),
        payloads.text(record, "headRefName"),
        payloads.text(record, "baseRefName"),
        payloads.text(record, "state"),
        record,
    )


def github_thread(record: Mapping[str, Any]) -> ReviewThread:
    user = record.get("user") if isinstance(record.get("user"), dict) else {}
    line = record.get("line") or record.get("original_line") or 0
    return ReviewThread(
        payloads.text(record, "id"),
        payloads.text(record, "path"),
        int(line) if isinstance(line, int) else 0,
        payloads.text(user, "login"),
        payloads.text(record, "body"),
        "active",
        record,
    )


def _github_link(
    run: Runner, slug: str, pr: str, item: str
) -> Result[Mapping[str, Any]]:
    marker = f"Work item: {item}"
    reply = {
        "linked": True,
        "mechanism": "pull-request-body",
        "workItem": item,
        "pullRequest": pr,
    }
    return bind(
        fmap(
            run(("pr", "view", pr, "-R", slug, "--json", "body")),
            lambda out: payloads.text(payloads.mapping(_json(out)), "body"),
        ),
        lambda body: (
            Ok(reply)
            if marker in body
            else fmap(
                run(
                    (
                        "pr",
                        "edit",
                        pr,
                        "-R",
                        slug,
                        "--body",
                        f"{body.rstrip()}\n\n{marker}\n".lstrip(),
                    )
                ),
                lambda _: reply,
            )
        ),
    )


# --- Azure Repos ------------------------------------------------------------------------------


def azure_transport(values: Mapping[str, str], repo: Path) -> Result[Transport]:
    return fmap(
        registry.find(repo, "azure-devops", "shipped"),
        lambda manifest: transport.mcp(
            *registry.connection_command(manifest, values, repo),
            float(manifest.connection.get("timeout", 30)),
        ),
    )


def azure_repos(values: Mapping[str, str], call: Transport) -> ScmOps:
    def tool(name: str, action: str, arguments: Mapping[str, Any]) -> Result[Any]:
        return call(
            name,
            {
                "action": action,
                "project": values["project"],
                "repositoryId": values["repository"],
                **arguments,
            },
        )

    def raw(ref: str) -> Result[Any]:
        return bind(
            payloads.number(ref, "pull request"),
            lambda number: tool("repo_pull_request", "get", {"pullRequestId": number}),
        )

    return ScmOps(
        get_pull_request=lambda ref: fmap(raw(ref), azure_pull_request),
        create_pull_request=lambda draft: _azure_create(tool, raw, draft),
        list_review_threads=lambda ref: bind(
            payloads.number(ref, "pull request"),
            lambda number: fmap(
                tool("repo_pull_request_thread", "list", {"pullRequestId": number}),
                lambda reply: tuple(
                    azure_thread(item) for item in payloads.records(reply)
                ),
            ),
        ),
        reply_to_thread=lambda pr, thread, content: bind(
            sequence(
                (payloads.number(pr, "pull request"), payloads.number(thread, "thread"))
            ),
            lambda numbers: fmap(
                tool(
                    "repo_pull_request_thread_write",
                    "reply",
                    {
                        "pullRequestId": numbers[0],
                        "threadId": numbers[1],
                        "content": content,
                    },
                ),
                payloads.mapping,
            ),
        ),
        link_work_item=lambda pr, item: _azure_link(tool, raw, pr, item),
    )


def _branch(name: str) -> str:
    return f"refs/heads/{name.removeprefix('refs/heads/')}"


def _azure_create(tool, raw, draft: PullRequestDraft) -> Result[PullRequest]:
    request = {
        "title": draft.title,
        "description": draft.description[:DESCRIPTION_LIMIT],
        "sourceRefName": _branch(draft.source_branch),
        "targetRefName": _branch(draft.target_branch),
        "isDraft": draft.draft,
    }
    # The create action returns a trimmed payload with no URL, so read the pull request back.
    return bind(
        tool("repo_pull_request_write", "create", request),
        lambda created: bind(
            require(
                isinstance(created, dict) and created.get("pullRequestId") is not None,
                "provider_error",
                "Azure DevOps did not return the created pull request",
            ),
            lambda _: _read_back(raw, str(created["pullRequestId"])),
        ),
    )


def _read_back(raw, number: str) -> Result[PullRequest]:
    match raw(number):
        case Ok(value):
            return Ok(azure_pull_request(value))
        case failed:
            # The pull request exists; say which one, so nobody creates it again.
            return err(
                failed.failure.code,
                f"created pull request {number}, but reading it back failed: {failed.failure.message}",
            )


def _status(value: Any, names: Mapping[int, str]) -> str:
    return (
        names.get(value, str(value))
        if isinstance(value, int) and not isinstance(value, bool)
        else str(value or "")
    )


def azure_pull_request(value: Any) -> PullRequest:
    record = payloads.mapping(value)
    number = payloads.text(record, "pullRequestId")
    repository = (
        record.get("repository") if isinstance(record.get("repository"), dict) else {}
    )
    web = payloads.text(repository, "webUrl")
    return PullRequest(
        number,
        number,
        payloads.text(record, "title"),
        f"{web}/pullrequest/{number}" if web else payloads.text(record, "url"),
        payloads.text(record, "sourceRefName").removeprefix("refs/heads/"),
        payloads.text(record, "targetRefName").removeprefix("refs/heads/"),
        _status(record.get("status"), PR_STATUS) or payloads.text(record, "statusName"),
        record,
    )


def azure_thread(record: Mapping[str, Any]) -> ReviewThread:
    comments = tuple(
        item for item in record.get("comments") or () if isinstance(item, dict)
    )
    first = comments[0] if comments else {}
    author = first.get("author")
    context = (
        record.get("threadContext")
        if isinstance(record.get("threadContext"), dict)
        else {}
    )
    start = (
        context.get("rightFileStart")
        if isinstance(context.get("rightFileStart"), dict)
        else {}
    )
    line = start.get("line", 0)
    return ReviewThread(
        payloads.text(record, "id"),
        payloads.text(context, "filePath"),
        line if isinstance(line, int) else 0,
        payloads.text(author, "displayName")
        if isinstance(author, dict)
        else str(author or ""),
        payloads.text(first, "content"),
        _status(record.get("status"), THREAD_STATUS)
        or payloads.text(record, "statusName")
        or "active",
        record,
    )


def _azure_link(tool, raw, pr: str, item: str) -> Result[Mapping[str, Any]]:
    # The link needs the repository and project ids, which the pull request carries.
    def link(value: Any) -> Result[Mapping[str, Any]]:
        repository = payloads.mapping(value).get("repository")
        repository = repository if isinstance(repository, dict) else {}
        project = (
            repository.get("project")
            if isinstance(repository.get("project"), dict)
            else {}
        )
        return bind(
            sequence(
                (
                    require(
                        bool(repository.get("id")),
                        "provider_error",
                        f"pull request {pr} did not include its repository",
                    ),
                    require(
                        bool(project.get("id")),
                        "provider_error",
                        f"pull request {pr} did not include its project id",
                    ),
                    payloads.number(item, "work item"),
                    payloads.number(pr, "pull request"),
                )
            ),
            lambda checked: fmap(
                tool(
                    "wit_work_item_link_write",
                    "link_to_pull_request",
                    {
                        "repositoryId": repository["id"],
                        "projectId": project["id"],
                        "workItemId": checked[2],
                        "pullRequestId": checked[3],
                    },
                ),
                payloads.mapping,
            ),
        )

    return bind(raw(pr), link)
