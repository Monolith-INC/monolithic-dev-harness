from __future__ import annotations

import json
import re
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from .contracts import (
    ArtifactRef,
    IntegrationError,
    LogicalState,
    PullRequest,
    ReviewThread,
    WorkItem,
    WorkItemKind,
)
from .mcp_client import client_from_connection

_ARTIFACT_ENVELOPE_PREFIX = "codex-workflows-artifact:v1"


class TrackerAdapter(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.client = client_from_connection(config["connection"])
        self.bindings = config.get("bindings", {})
        self.mappings = config.get("mappings", {})

    @abstractmethod
    def get_work_item(self, ref: str) -> WorkItem: ...

    @abstractmethod
    def search_work_items(
        self, query: str, cursor: str | None = None
    ) -> dict[str, Any]: ...

    @abstractmethod
    def create_work_item(
        self, kind: str, title: str, description: str, parent_ref: str | None = None
    ) -> WorkItem: ...

    @abstractmethod
    def transition_work_item(self, ref: str, state: str) -> WorkItem: ...

    @abstractmethod
    def publish_artifact(
        self, ref: str, kind: str, title: str, content: str, revision: str
    ) -> ArtifactRef: ...

    @abstractmethod
    def list_artifacts(
        self, ref: str, kind: str | None = None
    ) -> list[ArtifactRef]: ...

    def list_children(self, ref: str) -> list[WorkItem]:
        result = self._call("list_children", {"parent": ref})
        return [_work_item(item, self.mappings) for item in _items(result)]

    def link_development_artifact(
        self, ref: str, artifact_url: str, artifact_type: str = "pull_request"
    ) -> dict[str, Any]:
        return self._call(
            "link_development_artifact",
            {"work_item": ref, "url": artifact_url, "type": artifact_type},
        )

    def resolve_branch_key(self, branch: str) -> str | None:
        pattern = self.config.get("branchPattern") or self.config.get("branch_template")
        if not isinstance(pattern, str):
            return None
        escaped = re.escape(pattern)
        escaped = escaped.replace(
            re.escape("{key}"), r"(?P<key>[A-Za-z][A-Za-z0-9_-]*-?[0-9]+|[0-9]+)"
        )
        escaped = escaped.replace(re.escape("{category}"), r"[A-Za-z0-9_-]+")
        escaped = escaped.replace(re.escape("{slug}"), r"[A-Za-z0-9_-]+")
        escaped = escaped.replace(re.escape("{user}"), r"[A-Za-z0-9_-]+")
        match = re.fullmatch(escaped, branch)
        return match.group("key") if match else None

    def _call(self, operation: str, arguments: dict[str, Any]) -> Any:
        tool = self.bindings.get(operation)
        if not isinstance(tool, str) or not tool:
            raise IntegrationError(
                "unsupported_capability",
                f"Tracker operation is not configured: {operation}",
            )
        return self.client.call(tool, arguments)


class LinearTrackerAdapter(TrackerAdapter):
    def get_work_item(self, ref: str) -> WorkItem:
        return _work_item(self._call("get_work_item", {"id": ref}), self.mappings)

    def search_work_items(
        self, query: str, cursor: str | None = None
    ) -> dict[str, Any]:
        return _page(
            self._call("search_work_items", {"query": query, "cursor": cursor}),
            self.mappings,
        )

    def create_work_item(
        self, kind: str, title: str, description: str, parent_ref: str | None = None
    ) -> WorkItem:
        args = {
            "kind": self._provider_kind(kind),
            "title": title,
            "description": description,
        }
        if parent_ref:
            args["parentId"] = parent_ref
        return _work_item(self._call("create_work_item", args), self.mappings)

    def transition_work_item(self, ref: str, state: str) -> WorkItem:
        return _work_item(
            self._call(
                "transition_work_item",
                {"id": ref, "state": self._provider_state(state)},
            ),
            self.mappings,
        )

    def list_artifacts(self, ref: str, kind: str | None = None) -> list[ArtifactRef]:
        artifacts = [
            _artifact(item)
            for item in _items(
                self._call("list_artifacts", {"issueId": ref, "kind": kind})
            )
        ]
        return [item for item in artifacts if kind is None or item.kind == kind]

    def list_children(self, ref: str) -> list[WorkItem]:
        result = self._call("list_children", {"parentId": ref, "parent": ref})
        items = [item for item in _items(result) if isinstance(item, dict)]
        selected = [
            item
            for item in items
            if str(item.get("parentId") or item.get("parent_id") or "") == ref
        ]
        return [_work_item(item, self.mappings) for item in (selected or items)]

    def publish_artifact(
        self, ref: str, kind: str, title: str, content: str, revision: str
    ) -> ArtifactRef:
        from .publish import publish_artifact_idempotent

        envelope = _encode_artifact_envelope(
            kind=kind, title=title, revision=revision, content=content
        )
        result = publish_artifact_idempotent(
            list_fn=lambda: self.list_artifacts(ref, kind),
            create_fn=lambda: _artifact(
                self._call(
                    "publish_artifact",
                    {
                        "issueId": ref,
                        "kind": kind,
                        "title": title,
                        "content": envelope,
                        "body": envelope,
                        "revision": revision,
                    },
                ),
                fallback_kind=kind,
                fallback_title=title,
                fallback_revision=revision,
            ),
            title=title,
            revision=revision,
        )
        artifact = result["artifact"]
        return ArtifactRef(
            artifact.id,
            artifact.kind or kind,
            artifact.title or title,
            artifact.revision or revision,
            artifact.url,
            dict(artifact.provider_data),
            result["outcome"],
            result["attempts"],
        )

    def _provider_kind(self, kind: str) -> str:
        return str(self.mappings.get("kinds", {}).get(kind, kind))

    def _provider_state(self, state: str) -> str:
        return str(self.mappings.get("states", {}).get(state, state))


class AzureDevOpsTrackerAdapter(TrackerAdapter):
    def get_work_item(self, ref: str) -> WorkItem:
        return _work_item(
            self._call(
                "get_work_item", {"id": int(ref) if str(ref).isdigit() else ref}
            ),
            self.mappings,
        )

    def search_work_items(
        self, query: str, cursor: str | None = None
    ) -> dict[str, Any]:
        return _page(
            self._call("search_work_items", {"query": query, "cursor": cursor}),
            self.mappings,
        )

    def create_work_item(
        self, kind: str, title: str, description: str, parent_ref: str | None = None
    ) -> WorkItem:
        args = {
            "type": self.mappings.get("kinds", {}).get(kind, kind),
            "title": title,
            "description": description,
        }
        if parent_ref:
            args["parentId"] = (
                int(parent_ref) if str(parent_ref).isdigit() else parent_ref
            )
        return _work_item(self._call("create_work_item", args), self.mappings)

    def transition_work_item(self, ref: str, state: str) -> WorkItem:
        return _work_item(
            self._call(
                "transition_work_item",
                {"id": ref, "state": self._provider_state(state)},
            ),
            self.mappings,
        )

    def list_artifacts(self, ref: str, kind: str | None = None) -> list[ArtifactRef]:
        artifacts = [
            _artifact(item)
            for item in _items(self._call("list_artifacts", {"id": ref, "kind": kind}))
        ]
        return [item for item in artifacts if kind is None or item.kind == kind]

    def list_children(self, ref: str) -> list[WorkItem]:
        parent_id = int(ref) if str(ref).isdigit() else ref
        result = self._call(
            "list_children",
            {
                "ids": [parent_id],
                "parentId": parent_id,
                "query": f"SELECT [System.Id] FROM WorkItems WHERE [System.Parent] = {parent_id}",
            },
        )
        return [_work_item(item, self.mappings) for item in _items(result)]

    def publish_artifact(
        self, ref: str, kind: str, title: str, content: str, revision: str
    ) -> ArtifactRef:
        from .publish import publish_artifact_idempotent

        envelope = _encode_artifact_envelope(
            kind=kind, title=title, revision=revision, content=content
        )
        result = publish_artifact_idempotent(
            list_fn=lambda: self.list_artifacts(ref, kind),
            create_fn=lambda: _artifact(
                self._call(
                    "publish_artifact",
                    {
                        "id": int(ref) if str(ref).isdigit() else ref,
                        "kind": kind,
                        "title": title,
                        "content": envelope,
                        "text": envelope,
                        "revision": revision,
                    },
                ),
                fallback_kind=kind,
                fallback_title=title,
                fallback_revision=revision,
            ),
            title=title,
            revision=revision,
        )
        artifact = result["artifact"]
        return ArtifactRef(
            artifact.id,
            artifact.kind or kind,
            artifact.title or title,
            artifact.revision or revision,
            artifact.url,
            dict(artifact.provider_data),
            result["outcome"],
            result["attempts"],
        )

    def _provider_state(self, state: str) -> str:
        return str(self.mappings.get("states", {}).get(state, state))


class ScmAdapter:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        connection = config.get("connection") or {}
        self.client = (
            client_from_connection(connection) if connection.get("command") else None
        )
        self.bindings = config.get("bindings", {})

    def _call(self, operation: str, arguments: dict[str, Any]) -> Any:
        tool = self.bindings.get(operation)
        if not isinstance(tool, str) or not tool:
            raise IntegrationError(
                "unsupported_capability",
                f"SCM operation is not configured: {operation}",
            )
        if self.client is None:
            raise IntegrationError(
                "provider_unavailable", "SCM MCP client is not configured."
            )
        return self.client.call(tool, arguments)

    def get_pull_request(self, ref: str) -> PullRequest:
        return _pull_request(self._call("get_pull_request", {"id": ref}))

    def create_pull_request(
        self, title: str, description: str, source_branch: str, target_branch: str
    ) -> PullRequest:
        return _pull_request(
            self._call(
                "create_pull_request",
                {
                    "title": title,
                    "description": description,
                    "source": source_branch,
                    "target": target_branch,
                },
            )
        )

    def list_review_threads(self, ref: str) -> list[ReviewThread]:
        return [
            _review_thread(item)
            for item in _items(self._call("list_review_threads", {"id": ref}))
        ]

    def reply_to_thread(
        self, pr_ref: str, thread_ref: str, content: str
    ) -> dict[str, Any]:
        return self._call(
            "reply_to_thread",
            {"pull_request": pr_ref, "thread": thread_ref, "content": content},
        )

    def link_work_item(self, pr_ref: str, work_item_ref: str) -> dict[str, Any]:
        return self._call(
            "link_work_item", {"pull_request": pr_ref, "work_item": work_item_ref}
        )


class GitHubScmAdapter(ScmAdapter):
    """GitHub transport using the authenticated ``gh`` CLI."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.client = None
        self.bindings = config.get("bindings", {})

    def _run(self, args: list[str]) -> Any:
        try:
            result = subprocess.run(
                ["gh", *args], capture_output=True, text=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise IntegrationError(
                "provider_unavailable", f"GitHub CLI unavailable: {exc}"
            ) from exc
        if result.returncode != 0:
            raise IntegrationError(
                "provider_error", (result.stderr or result.stdout).strip()
            )
        try:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            return result.stdout.strip()

    def _repo_args(self) -> list[str]:
        owner, repo = self.config.get("owner"), self.config.get("repo")
        return ["-R", f"{owner}/{repo}"] if owner and repo else []

    def _run_text(self, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["gh", *args], capture_output=True, text=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise IntegrationError(
                "provider_unavailable", f"GitHub CLI unavailable: {exc}"
            ) from exc
        if result.returncode != 0:
            raise IntegrationError(
                "provider_error", (result.stderr or result.stdout).strip()
            )
        return result.stdout

    def get_pull_request(self, ref: str) -> PullRequest:
        value = self._run(
            [
                "pr",
                "view",
                ref,
                *self._repo_args(),
                "--json",
                "number,title,url,headRefName,baseRefName,state",
            ]
        )
        return _pull_request(value)

    def create_pull_request(
        self, title: str, description: str, source_branch: str, target_branch: str
    ) -> PullRequest:
        value = self._run_text(
            [
                "pr",
                "create",
                *self._repo_args(),
                "--title",
                title,
                "--body",
                description,
                "--head",
                source_branch,
                "--base",
                target_branch,
            ]
        )
        url = value.strip().splitlines()[-1] if value.strip() else ""
        return self.get_pull_request(url.rsplit("/", 1)[-1] if url else source_branch)

    def list_review_threads(self, ref: str) -> list[ReviewThread]:
        owner, repo = self.config.get("owner"), self.config.get("repo")
        value = self._run(["api", f"repos/{owner}/{repo}/pulls/{ref}/comments"])
        return [_review_thread(item) for item in _items(value)]

    def reply_to_thread(
        self, pr_ref: str, thread_ref: str, content: str
    ) -> dict[str, Any]:
        owner, repo = self.config.get("owner"), self.config.get("repo")
        return self._run(
            [
                "api",
                "-X",
                "POST",
                f"repos/{owner}/{repo}/pulls/{pr_ref}/comments/{thread_ref}/replies",
                "-f",
                f"body={content}",
            ]
        )

    def link_work_item(self, pr_ref: str, work_item_ref: str) -> dict[str, Any]:
        current = self._run(
            ["pr", "view", pr_ref, *self._repo_args(), "--json", "body"]
        )
        body = (
            str((current or {}).get("body") or "") if isinstance(current, dict) else ""
        )
        marker = f"Work item: {work_item_ref}"
        if marker not in body:
            updated = (
                f"{body.rstrip()}\n\n{marker}\n" if body.strip() else f"{marker}\n"
            )
            self._run_text(
                ["pr", "edit", pr_ref, *self._repo_args(), "--body", updated]
            )
        return {
            "linked": True,
            "mechanism": "pull-request-body",
            "workItem": work_item_ref,
            "pullRequest": pr_ref,
        }


class AzureReposScmAdapter(ScmAdapter):
    """Azure Repos transport through the configured MCP bindings."""

    def get_pull_request(self, ref: str) -> PullRequest:
        return _pull_request(
            self._call(
                "get_pull_request",
                {
                    "id": int(ref) if str(ref).isdigit() else ref,
                    "repositoryId": self.config.get("repository"),
                    "project": self.config.get("project"),
                },
            )
        )

    def create_pull_request(
        self, title: str, description: str, source_branch: str, target_branch: str
    ) -> PullRequest:
        return _pull_request(
            self._call(
                "create_pull_request",
                {
                    "title": title,
                    "description": description,
                    "source": source_branch,
                    "target": target_branch,
                    "sourceRefName": f"refs/heads/{source_branch}",
                    "targetRefName": f"refs/heads/{target_branch}",
                    "repositoryId": self.config.get("repository"),
                    "project": self.config.get("project"),
                },
            )
        )

    def list_review_threads(self, ref: str) -> list[ReviewThread]:
        value = self._call(
            "list_review_threads",
            {
                "id": int(ref) if str(ref).isdigit() else ref,
                "pullRequestId": int(ref) if str(ref).isdigit() else ref,
                "repositoryId": self.config.get("repository"),
                "project": self.config.get("project"),
            },
        )
        return [_review_thread(item) for item in _items(value)]

    def reply_to_thread(
        self, pr_ref: str, thread_ref: str, content: str
    ) -> dict[str, Any]:
        return self._call(
            "reply_to_thread",
            {
                "pull_request": pr_ref,
                "thread": thread_ref,
                "content": content,
                "pullRequestId": int(pr_ref) if str(pr_ref).isdigit() else pr_ref,
                "repositoryId": self.config.get("repository"),
                "project": self.config.get("project"),
            },
        )

    def link_work_item(self, pr_ref: str, work_item_ref: str) -> dict[str, Any]:
        return self._call(
            "link_work_item",
            {
                "pull_request": pr_ref,
                "work_item": work_item_ref,
                "pullRequestId": int(pr_ref) if str(pr_ref).isdigit() else pr_ref,
                "workItemId": int(work_item_ref)
                if str(work_item_ref).isdigit()
                else work_item_ref,
                "repositoryId": self.config.get("repository"),
                "project": self.config.get("project"),
            },
        )


def tracker_adapter(config: dict[str, Any]) -> TrackerAdapter:
    from .local_tracker import LocalTrackerAdapter

    adapter = config.get("adapter")
    if adapter == "linear":
        return LinearTrackerAdapter(config)
    if adapter == "azure_devops":
        return AzureDevOpsTrackerAdapter(config)
    if adapter == "local_tracker":
        return LocalTrackerAdapter(config)
    raise IntegrationError("invalid_config", f"Unsupported tracker adapter: {adapter}")


def scm_adapter(config: dict[str, Any]) -> ScmAdapter:
    adapter = config.get("adapter")
    if adapter == "github":
        return GitHubScmAdapter(config)
    if adapter == "azure_repos":
        return AzureReposScmAdapter(config)
    raise IntegrationError("invalid_config", f"Unsupported SCM adapter: {adapter}")


def _items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "nodes", "value", "workItems", "artifacts", "threads"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def _page(value: Any, mappings: dict[str, Any]) -> dict[str, Any]:
    items = [_work_item(item, mappings) for item in _items(value)]
    return {
        "items": [item.__dict__ for item in items],
        "nextCursor": value.get("nextCursor") if isinstance(value, dict) else None,
    }


def _work_item(value: Any, mappings: dict[str, Any]) -> WorkItem:
    if not isinstance(value, dict):
        raise IntegrationError(
            "provider_error", "Provider returned an invalid work-item payload."
        )
    kind_raw = (
        str(value.get("kind") or value.get("type") or "task").lower().replace(" ", "_")
    )
    state_raw = (
        str(value.get("state") or value.get("status") or "backlog")
        .lower()
        .replace(" ", "_")
    )
    kind = _reverse_mapping(kind_raw, mappings.get("kinds", {}), WorkItemKind.TASK)
    state = _reverse_mapping(
        state_raw, mappings.get("states", {}), LogicalState.BACKLOG
    )
    return WorkItem(
        str(value.get("id") or value.get("identifier") or ""),
        str(value.get("key") or value.get("identifier") or value.get("id") or ""),
        str(value.get("title") or value.get("name") or ""),
        WorkItemKind(kind),
        LogicalState(state),
        value.get("url"),
        str(value.get("description") or ""),
        value.get("parentId"),
        value,
    )


def _reverse_mapping(value: str, mapping: dict[str, Any], fallback: str) -> str:
    if value in mapping:
        return value
    for logical, provider in mapping.items():
        if str(provider).lower().replace(" ", "_") == value:
            return logical
    return fallback


def _encode_artifact_envelope(
    *, kind: str, title: str, revision: str, content: str
) -> str:
    header = json.dumps(
        {"kind": kind, "title": title, "revision": revision}, sort_keys=True
    )
    return f"{_ARTIFACT_ENVELOPE_PREFIX} {header}\n{content}"


def _parse_artifact_envelope(text: str) -> dict[str, str] | None:
    if not isinstance(text, str) or not text.startswith(_ARTIFACT_ENVELOPE_PREFIX):
        return None
    rest = text[len(_ARTIFACT_ENVELOPE_PREFIX) :].lstrip()
    header_line, _, body = rest.partition("\n")
    try:
        header = json.loads(header_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(header, dict):
        return None
    return {
        "kind": str(header.get("kind") or "artifact"),
        "title": str(header.get("title") or ""),
        "revision": str(header.get("revision") or ""),
        "content": body,
    }


def _artifact(
    value: Any,
    *,
    fallback_kind: str = "artifact",
    fallback_title: str = "",
    fallback_revision: str = "",
) -> ArtifactRef:
    if isinstance(value, str):
        value = {"body": value, "content": value}
    if not isinstance(value, dict):
        raise IntegrationError(
            "provider_error", "Provider returned an invalid artifact payload."
        )
    text = str(
        value.get("content")
        or value.get("body")
        or value.get("text")
        or value.get("comment")
        or ""
    )
    parsed = _parse_artifact_envelope(text)
    if parsed is not None:
        return ArtifactRef(
            str(value.get("id") or value.get("url") or ""),
            parsed["kind"],
            parsed["title"],
            parsed["revision"],
            value.get("url"),
            {**value, "content": parsed["content"]},
        )
    return ArtifactRef(
        str(value.get("id") or value.get("url") or ""),
        str(value.get("kind") or fallback_kind or "artifact"),
        str(value.get("title") or fallback_title or ""),
        str(value.get("revision") or fallback_revision or ""),
        value.get("url"),
        value,
    )


def _pull_request(value: Any) -> PullRequest:
    if not isinstance(value, dict):
        raise IntegrationError(
            "provider_error", "Provider returned an invalid pull-request payload."
        )
    return PullRequest(
        str(value.get("id") or value.get("number") or ""),
        str(value.get("number") or value.get("id") or ""),
        str(value.get("title") or ""),
        str(value.get("url") or ""),
        str(
            value.get("source")
            or value.get("sourceBranch")
            or value.get("headRefName")
            or ""
        ),
        str(
            value.get("target")
            or value.get("targetBranch")
            or value.get("baseRefName")
            or ""
        ),
        str(value.get("state") or ""),
        value,
    )


def _review_thread(value: Any) -> ReviewThread:
    if not isinstance(value, dict):
        raise IntegrationError(
            "provider_error", "Provider returned an invalid review-thread payload."
        )
    return ReviewThread(
        str(value.get("id") or ""),
        value.get("file"),
        value.get("line"),
        str(value.get("reviewer") or ""),
        str(value.get("comment") or value.get("content") or ""),
        str(value.get("status") or "active"),
        value,
    )
