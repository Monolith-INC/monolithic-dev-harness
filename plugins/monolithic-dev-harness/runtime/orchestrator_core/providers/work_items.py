"""Pure provider translations for the neutral artifact contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..ingest import ArtifactRecord, ingest_azure_record


AGILE_LABEL_BY_TYPE = {
    "Epic": "agile:epic",
    "Feature": "agile:feature",
    "User Story": "agile:user-story",
    "Task": "agile:task",
}
TYPE_BY_AGILE_LABEL = {label: item_type for item_type, label in AGILE_LABEL_BY_TYPE.items()}


@dataclass(frozen=True)
class ProviderCreateRequest:
    provider: str
    payload: dict[str, Any]


@runtime_checkable
class ArtifactProviderAdapter(Protocol):
    name: str

    def create_request(self, artifact: ArtifactRecord, *, container_id: str) -> ProviderCreateRequest:
        ...

    def read_result(self, payload: dict[str, Any]) -> ArtifactRecord:
        ...


def _labels(payload: dict[str, Any]) -> tuple[str, ...]:
    raw = payload.get("labels") or payload.get("labelNames") or ()
    if isinstance(raw, dict):
        raw = raw.get("nodes") or raw.get("values") or ()
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(
        str(entry.get("name") if isinstance(entry, dict) else entry).strip()
        for entry in raw
        if str(entry.get("name") if isinstance(entry, dict) else entry).strip()
    )


class AzureWorkItemAdapter:
    name = "azure-devops"

    def create_request(self, artifact: ArtifactRecord, *, container_id: str) -> ProviderCreateRequest:
        payload: dict[str, Any] = {
            "project": container_id,
            "workItemType": artifact.type,
            "fields": [
                {"name": "System.Title", "value": artifact.title},
                {"name": "System.Description", "value": artifact.body},
            ],
        }
        if artifact.parent_id:
            payload["parentId"] = artifact.parent_id
        return ProviderCreateRequest(self.name, payload)

    def read_result(self, payload: dict[str, Any]) -> ArtifactRecord:
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
        parent = fields.get("System.Parent") or payload.get("parentId")
        return ingest_azure_record(
            provider=self.name,
            work_item_type=str(fields.get("System.WorkItemType") or payload.get("workItemType") or ""),
            title=str(fields.get("System.Title") or payload.get("title") or ""),
            description=str(fields.get("System.Description") or payload.get("description") or ""),
            story_points=fields.get("Microsoft.VSTS.Scheduling.StoryPoints"),
            parent_id=str(parent) if parent is not None else None,
            provider_id=str(payload.get("id") or fields.get("System.Id") or ""),
        )


class LinearWorkItemAdapter:
    name = "linear"

    def create_request(self, artifact: ArtifactRecord, *, container_id: str) -> ProviderCreateRequest:
        label = AGILE_LABEL_BY_TYPE.get(artifact.type)
        if label is None:
            raise ValueError(f"unsupported Linear Agile type: {artifact.type}")
        payload: dict[str, Any] = {
            "team": container_id,
            "title": artifact.title,
            "description": artifact.body,
            "labels": [label],
        }
        if artifact.parent_id:
            payload["parentId"] = artifact.parent_id
        return ProviderCreateRequest(self.name, payload)

    def read_result(self, payload: dict[str, Any]) -> ArtifactRecord:
        agile_types = [TYPE_BY_AGILE_LABEL[label] for label in _labels(payload) if label in TYPE_BY_AGILE_LABEL]
        if len(agile_types) != 1:
            raise ValueError("Linear issue must have exactly one managed agile:* type label")
        parent = payload.get("parentId")
        if parent is None and isinstance(payload.get("parent"), dict):
            parent = payload["parent"].get("id") or payload["parent"].get("identifier")
        return ArtifactRecord(
            type=agile_types[0],
            title=str(payload.get("title") or ""),
            body=str(payload.get("description") or ""),
            story_points=float(payload["estimate"]) if isinstance(payload.get("estimate"), (int, float)) else None,
            parent_id=str(parent) if parent is not None else None,
            provider=self.name,
            provider_id=str(payload.get("identifier") or payload.get("id") or ""),
            source=self.name,
            filename=None,
            frontmatter={},
            raw=str(payload.get("description") or ""),
        )
