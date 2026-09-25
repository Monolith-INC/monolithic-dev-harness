"""Azure Boards and Azure Repos through the `@azure-devops/mcp` server.

The server groups operations by area: one tool per area, and an `action` argument that selects the
operation (`wit_query` + `wiql`, `wit_work_item_write` + `create`, ...). Work items come back in the
REST shape (`id`, `fields["System.Title"]`, ...), pull requests with `pullRequestId` and
`refs/heads/` branch names. These adapters translate both ways, so the gateway's contracts stay
provider-neutral.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

from scripts.integrations.adapters import (
    ScmAdapter,
    TrackerAdapter,
    _artifact,
    _items,
    _pull_request,
    _review_thread,
    _work_item,
)
from scripts.integrations.contracts import (
    ArtifactRef,
    IntegrationError,
    PullRequest,
    ReviewThread,
    WorkItem,
)

WORK_ITEM_FIELDS = (
    "System.Id",
    "System.Title",
    "System.WorkItemType",
    "System.State",
    "System.Description",
    "System.Parent",
)
_BATCH_LIMIT = 200
_COMMENT_LIMIT = 200
# A WIQL condition names a field (`[System.State]`, `[Custom.Team]`); anything else, brackets or
# not, is search text.
_WIQL_FIELD = re.compile(r"\[[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+\]")
# `status` is a numeric enum on some payloads; the server also sends the name.
_PR_STATUS = {0: "notSet", 1: "active", 2: "abandoned", 3: "completed"}
_THREAD_STATUS = {
    0: "unknown",
    1: "active",
    2: "fixed",
    3: "wontFix",
    4: "closed",
    5: "byDesign",
    6: "pending",
}
_PR_DESCRIPTION_LIMIT = 4000


def _number(ref: str | int, what: str) -> int:
    text = str(ref).strip().lstrip("#")
    if not text.isdigit():
        raise IntegrationError(
            "invalid_request", f"{what} must be a numeric id, got {ref!r}."
        )
    return int(text)


def wiql_for(query: str) -> str:
    """A full WIQL statement from a statement, a WIQL condition, or plain search text."""
    text = query.strip()
    if text.upper().startswith("SELECT"):
        return text
    if _WIQL_FIELD.search(text):
        condition = text
    else:
        condition = "[System.Title] CONTAINS '{}'".format(text.replace("'", "''"))
    return (
        "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project "
        f"AND ({condition}) ORDER BY [System.ChangedDate] DESC"
    )


def _records(value: Any) -> list[dict[str, Any]]:
    """Work item records from a list, a `value`/`workItems` wrapper, or a batch response."""
    if isinstance(value, dict) and ("fields" in value or "id" in value):
        candidates: list[Any] = [value]
    else:
        candidates = _items(value)
    records: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict) and isinstance(item.get("body"), str):
            try:
                item = json.loads(item["body"])
            except json.JSONDecodeError:
                continue
        if isinstance(item, dict):
            records.append(item)
    return records


def ado_work_item(value: dict[str, Any], mappings: dict[str, Any]) -> WorkItem:
    fields = value.get("fields")
    if not isinstance(fields, dict):
        return _work_item(value, mappings)
    parent = fields.get("System.Parent")
    html = ((value.get("_links") or {}).get("html") or {}).get("href")
    item = _work_item(
        {
            "id": value.get("id") or fields.get("System.Id"),
            "title": fields.get("System.Title"),
            "type": fields.get("System.WorkItemType"),
            "state": fields.get("System.State"),
            "description": fields.get("System.Description"),
            "parentId": str(parent) if parent else None,
            "url": html or value.get("url"),
        },
        mappings,
    )
    return replace(item, provider_data=value)


def _status_name(value: Any, names: dict[int, str]) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return names.get(value, str(value))
    return str(value)


def ado_pull_request(value: Any) -> PullRequest:
    if not isinstance(value, dict) or "pullRequestId" not in value:
        return _pull_request(value)
    number = value["pullRequestId"]
    # `repo_pull_request[get]` nests the repository; the create action returns its name as a string.
    repository = value.get("repository")
    web = repository.get("webUrl") if isinstance(repository, dict) else None
    return replace(
        _pull_request(
            {
                "id": number,
                "number": number,
                "title": value.get("title"),
                "url": f"{web}/pullrequest/{number}" if web else value.get("url"),
                "sourceBranch": str(value.get("sourceRefName") or "").removeprefix(
                    "refs/heads/"
                ),
                "targetBranch": str(value.get("targetRefName") or "").removeprefix(
                    "refs/heads/"
                ),
                "state": _status_name(value.get("status"), _PR_STATUS)
                or value.get("statusName"),
            }
        ),
        provider_data=value,
    )


def ado_review_thread(value: Any) -> ReviewThread:
    if not isinstance(value, dict) or "comments" not in value:
        return _review_thread(value)
    comments = [item for item in value.get("comments") or [] if isinstance(item, dict)]
    first = comments[0] if comments else {}
    author = first.get("author")
    context = value.get("threadContext") or {}
    start = context.get("rightFileStart") or {}
    return replace(
        _review_thread(
            {
                "id": value.get("id"),
                "file": context.get("filePath"),
                "line": start.get("line"),
                "reviewer": author.get("displayName")
                if isinstance(author, dict)
                else author,
                "comment": first.get("content"),
                "status": _status_name(value.get("status"), _THREAD_STATUS)
                or value.get("statusName")
                or "active",
            }
        ),
        provider_data=value,
    )


class AzureDevOpsTrackerAdapter(TrackerAdapter):
    """Azure Boards. Needs `project` in the tracker config: without it the server would prompt."""

    def _ado(self, tool: str, action: str, **arguments: Any) -> Any:
        project = self.config.get("project")
        if not project:
            raise IntegrationError(
                "invalid_config",
                "tracker.project is not set in .harness/integrations.json. "
                "Set it to the Azure DevOps project name (or re-run bootstrap).",
            )
        payload = {k: v for k, v in arguments.items() if v is not None}
        return self.client.call(tool, {"action": action, "project": project, **payload})

    def _batch(self, ids: list[int]) -> list[WorkItem]:
        items: list[WorkItem] = []
        for start in range(0, len(ids), _BATCH_LIMIT):
            chunk = ids[start : start + _BATCH_LIMIT]
            result = self._ado(
                "wit_work_item", "get_batch", ids=chunk, fields=list(WORK_ITEM_FIELDS)
            )
            items.extend(
                ado_work_item(item, self.mappings) for item in _records(result)
            )
        return items

    def _query_ids(self, wiql: str) -> list[int]:
        result = self._ado("wit_query", "wiql", wiql=wiql, top=_BATCH_LIMIT)
        ids: list[int] = []
        for item in _items(result):
            if isinstance(item, dict) and str(item.get("id", "")).isdigit():
                ids.append(int(item["id"]))
        return ids

    def get_work_item(self, ref: str) -> WorkItem:
        result = self._ado(
            "wit_work_item", "get", id=_number(ref, "work item"), expand="Relations"
        )
        records = _records(result)
        if not records:
            raise IntegrationError("not_found", f"Work item {ref} was not returned.")
        return ado_work_item(records[0], self.mappings)

    def search_work_items(
        self, query: str, cursor: str | None = None
    ) -> dict[str, Any]:
        # The server caps a WIQL result; say so rather than implying the result is complete.
        ids = self._query_ids(wiql_for(query))
        items = self._batch(ids)
        return {
            "items": [item.__dict__ for item in items],
            "nextCursor": None,
            "truncated": len(ids) >= _BATCH_LIMIT,
        }

    def create_work_item(
        self, kind: str, title: str, description: str, parent_ref: str | None = None
    ) -> WorkItem:
        work_type = self._provider_kind(kind)
        if parent_ref:
            result = self._ado(
                "wit_work_item_write",
                "add_child",
                parentId=_number(parent_ref, "parent"),
                workItemType=work_type,
                items=[
                    {"title": title, "description": description, "format": "Markdown"}
                ],
            )
        else:
            result = self._ado(
                "wit_work_item_write",
                "create",
                workItemType=work_type,
                fields=[
                    {"name": "System.Title", "value": title},
                    {
                        "name": "System.Description",
                        "value": description,
                        "format": "Markdown",
                    },
                ],
            )
        created = [record for record in _records(result) if record.get("id")]
        if not created:
            raise IntegrationError(
                "provider_error", "Azure DevOps did not return the created work item."
            )
        # Read it back so callers get the stored state, not the echo of the request.
        return self.get_work_item(str(created[0]["id"]))

    def transition_work_item(self, ref: str, state: str) -> WorkItem:
        self._ado(
            "wit_work_item_write",
            "update",
            id=_number(ref, "work item"),
            updates=[
                {
                    "op": "add",
                    "path": "/fields/System.State",
                    "value": self._provider_state(state),
                }
            ],
        )
        return self.get_work_item(ref)

    def list_children(self, ref: str) -> list[WorkItem]:
        parent = _number(ref, "parent")
        wiql = f"SELECT [System.Id] FROM WorkItems WHERE [System.Parent] = {parent}"
        return self._batch(self._query_ids(wiql))

    def list_artifacts(self, ref: str, kind: str | None = None) -> list[ArtifactRef]:
        result = self._ado(
            "wit_work_item",
            "list_comments",
            workItemId=_number(ref, "work item"),
            top=_COMMENT_LIMIT,
        )
        artifacts = [_artifact(item) for item in _items(result)]
        return [item for item in artifacts if kind is None or item.kind == kind]

    def _create_artifact(
        self, ref: str, envelope: str, *, kind: str, title: str, revision: str
    ) -> Any:
        return self._ado(
            "wit_work_item_comment_write",
            "add",
            workItemId=_number(ref, "work item"),
            text=envelope,
            format="Markdown",
        )

    def link_development_artifact(
        self, ref: str, artifact_url: str, artifact_type: str = "pull_request"
    ) -> dict[str, Any]:
        return self._ado(
            "wit_work_item_link_write",
            "link",
            updates=[
                {
                    "id": _number(ref, "work item"),
                    "type": "hyperlink",
                    "url": artifact_url,
                    "comment": artifact_type,
                }
            ],
        )


class AzureReposScmAdapter(ScmAdapter):
    """Azure Repos. Needs `project` and `repository` (name or id) in the SCM config."""

    def _ado(self, tool: str, action: str, **arguments: Any) -> Any:
        if self.client is None:
            raise IntegrationError(
                "provider_unavailable", "SCM MCP client is not configured."
            )
        project, repository = self.config.get("project"), self.config.get("repository")
        if not project or not repository:
            raise IntegrationError(
                "invalid_config",
                "scm.project and scm.repository must be set in .harness/integrations.json.",
            )
        payload = {k: v for k, v in arguments.items() if v is not None}
        return self.client.call(
            tool,
            {
                "action": action,
                "project": project,
                "repositoryId": repository,
                **payload,
            },
        )

    def _raw_pull_request(self, ref: str) -> Any:
        return self._ado(
            "repo_pull_request", "get", pullRequestId=_number(ref, "pull request")
        )

    def get_pull_request(self, ref: str) -> PullRequest:
        return ado_pull_request(self._raw_pull_request(ref))

    def create_pull_request(
        self,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str,
        draft: bool = True,
    ) -> PullRequest:
        created = self._ado(
            "repo_pull_request_write",
            "create",
            title=title,
            description=description[:_PR_DESCRIPTION_LIMIT],
            sourceRefName=f"refs/heads/{source_branch.removeprefix('refs/heads/')}",
            targetRefName=f"refs/heads/{target_branch.removeprefix('refs/heads/')}",
            isDraft=draft,
        )
        # The create action returns a trimmed payload with no URL, so read the pull request back.
        number = created.get("pullRequestId") if isinstance(created, dict) else None
        if number is None:
            raise IntegrationError(
                "provider_error",
                "Azure DevOps did not return the created pull request.",
            )
        try:
            return self.get_pull_request(str(number))
        except IntegrationError as exc:
            # The pull request exists; say which one, so nobody creates it again.
            raise IntegrationError(
                exc.code,
                f"created pull request {number}, but reading it back failed: {exc}",
                retryable=exc.retryable,
            ) from exc

    def list_review_threads(self, ref: str) -> list[ReviewThread]:
        result = self._ado(
            "repo_pull_request_thread",
            "list",
            pullRequestId=_number(ref, "pull request"),
        )
        return [ado_review_thread(item) for item in _items(result)]

    def reply_to_thread(
        self, pr_ref: str, thread_ref: str, content: str
    ) -> dict[str, Any]:
        result = self._ado(
            "repo_pull_request_thread_write",
            "reply",
            pullRequestId=_number(pr_ref, "pull request"),
            threadId=_number(thread_ref, "thread"),
            content=content,
        )
        return result if isinstance(result, dict) else {"result": result}

    def link_work_item(self, pr_ref: str, work_item_ref: str) -> dict[str, Any]:
        # The link needs the repository and project GUIDs, which the pull request carries.
        pull_request = self._raw_pull_request(pr_ref)
        repository = (
            pull_request.get("repository") if isinstance(pull_request, dict) else None
        )
        if not isinstance(repository, dict) or not repository.get("id"):
            raise IntegrationError(
                "provider_error",
                f"Pull request {pr_ref} did not include its repository.",
            )
        project_id = (repository.get("project") or {}).get("id")
        if not project_id:
            raise IntegrationError(
                "provider_error",
                f"Pull request {pr_ref} did not include its project id.",
            )
        result = self._ado(
            "wit_work_item_link_write",
            "link_to_pull_request",
            repositoryId=repository["id"],
            projectId=project_id,
            workItemId=_number(work_item_ref, "work item"),
            pullRequestId=_number(pr_ref, "pull request"),
        )
        return result if isinstance(result, dict) else {"result": result}
