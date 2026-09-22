"""Write `.codex-workflows/integrations.json`: the tracker/SCM binding the workflow runtime reads.

Extracted from codex-workflows' installer (`scripts/installer/bootstrap.py`, 75c22f0). The harness only
needs the configuration writer; hooks and MCP servers come from the plugin itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def default_install_dir(project_dest: Path) -> Path:
    """Project-local runtime root (never ~/.codex-workflows)."""
    return project_dest / ".codex-workflows"


def configure_integrations(
    project_dest: Path,
    *,
    tracker: str,
    scm: str,
    branch_template: str,
    tracker_scope: str = "auto",
    config_source: Path | None = None,
    discover: bool = True,
    confirm_mappings: dict | None = None,
    runtime_dir: Path | None = None,
) -> Path:
    """Write provider-neutral setup while keeping provider details adapter-owned."""
    from scripts.integrations.discovery import (
        apply_discovery_to_config,
        discover_provider_capabilities,
        mapping_presets,
    )

    if config_source is not None:
        payload = json.loads(config_source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("integration config must be a JSON object")
        if (
            payload.get("schemaVersion") != 1
            or not isinstance(payload.get("branchTemplate"), str)
            or "{key}" not in payload["branchTemplate"]
        ):
            raise ValueError(
                "integration config must declare schemaVersion 1 and branchTemplate containing {key}"
            )
        if not isinstance(payload.get("tracker"), dict) or not payload["tracker"].get(
            "adapter"
        ):
            raise ValueError("integration config tracker.adapter is required")
        if not isinstance(payload.get("scm"), dict) or not payload["scm"].get(
            "adapter"
        ):
            raise ValueError("integration config scm.adapter is required")
    else:
        if "{key}" not in branch_template:
            raise ValueError("branch template must contain {key}")
        tracker_config = _default_tracker_config(
            tracker, tracker_scope, project_dest, runtime_dir
        )
        tracker_config["branchPattern"] = branch_template
        payload = {
            "schemaVersion": 1,
            "branchTemplate": branch_template,
            "tracker": tracker_config,
            "scm": _default_scm_config(scm, project_dest),
        }

    payload = _with_local_tracker_transport(
        payload, project_dest=project_dest, runtime_dir=runtime_dir
    )

    tracker_cfg = payload["tracker"]
    scm_cfg = payload["scm"]
    tracker_discovery = None
    scm_discovery = None
    discovery_errors: list[str] = []
    if discover:
        try:
            tracker_discovery = discover_provider_capabilities(
                kind="tracker",
                adapter=str(tracker_cfg.get("adapter")),
                connection=tracker_cfg.get("connection") or {},
                preferred_bindings=tracker_cfg.get("bindings") or {},
            )
        except Exception as exc:
            discovery_errors.append(f"tracker discovery failed: {exc}")
            tracker_discovery = None
        try:
            scm_discovery = discover_provider_capabilities(
                kind="scm",
                adapter=str(scm_cfg.get("adapter")),
                connection=scm_cfg.get("connection") or {},
                preferred_bindings=scm_cfg.get("bindings") or {},
            )
        except Exception as exc:
            discovery_errors.append(f"scm discovery failed: {exc}")
            scm_discovery = None
        if tracker_discovery is not None or scm_discovery is not None:
            payload = apply_discovery_to_config(
                payload,
                tracker_discovery=tracker_discovery,
                scm_discovery=scm_discovery,
            )
        if discovery_errors:
            payload = dict(payload)
            payload["discoveryErrors"] = discovery_errors
            print(
                "WARNING: provider capability discovery did not fully succeed:\n  - "
                + "\n  - ".join(discovery_errors),
                file=sys.stderr,
            )
    else:
        presets = mapping_presets(str(tracker_cfg.get("adapter")))
        tracker_cfg = dict(tracker_cfg)
        if not (tracker_cfg.get("mappings") or {}).get("kinds"):
            tracker_cfg["mappings"] = presets
        payload["tracker"] = tracker_cfg

    if confirm_mappings is not None:
        tracker_cfg = dict(payload["tracker"])
        tracker_cfg["mappings"] = confirm_mappings
        payload["tracker"] = tracker_cfg

    path = project_dest / ".codex-workflows" / "integrations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if payload["tracker"].get("adapter") == "local_tracker":
        _initialize_local_tracker(project_dest, payload["tracker"])
    return path


def _default_tracker_config(
    provider: str,
    scope: str,
    project_dest: Path | None = None,
    runtime_dir: Path | None = None,
) -> dict:
    from scripts.integrations.discovery import mapping_presets

    presets = mapping_presets(provider)
    if provider == "linear":
        return {
            "adapter": "linear",
            "scope": scope,
            "connection": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            },
            "mappings": presets,
            "bindings": {
                "get_work_item": "get_issue",
                "search_work_items": "list_issues",
                "create_work_item": "save_issue",
                "list_children": "list_issues",
                "transition_work_item": "save_issue",
                "publish_artifact": "save_comment",
                "list_artifacts": "list_comments",
                "link_development_artifact": "save_comment",
            },
        }
    if provider == "azure_devops":
        return {
            "adapter": "azure_devops",
            "scope": scope,
            "connection": {
                "command": "npx",
                "args": [
                    "-y",
                    "@azure-devops/mcp",
                    _azure_org_arg(project_dest),
                    "-d",
                    "core",
                    "work-items",
                    "repositories",
                ],
            },
            "project": _azure_remote(project_dest)[1] if project_dest else "",
            "mappings": presets,
            "bindings": {
                "get_work_item": "wit_work_item",
                "search_work_items": "wit_query",
                "create_work_item": "wit_work_item_write",
                "list_children": "wit_query",
                "transition_work_item": "wit_work_item_write",
                "publish_artifact": "wit_work_item_comment_write",
                "list_artifacts": "wit_work_item",
                "link_development_artifact": "wit_work_item_link_write",
            },
        }
    if provider == "local_tracker":
        return {
            "adapter": "local_tracker",
            "root": ".local-tracker",
            "storagePolicy": "committed",
            "connection": _local_tracker_connection(
                project_dest or Path.cwd(), runtime_dir, ".local-tracker"
            ),
            "mappings": presets,
            "bindings": _local_tracker_bindings(),
        }
    raise ValueError(f"unsupported tracker: {provider}")


def _with_local_tracker_transport(
    payload: dict, *, project_dest: Path, runtime_dir: Path | None = None
) -> dict:
    tracker = payload.get("tracker")
    if not isinstance(tracker, dict) or tracker.get("adapter") != "local_tracker":
        return payload
    tracker = dict(tracker)
    root = str(tracker.get("root") or ".local-tracker")
    tracker.setdefault(
        "connection", _local_tracker_connection(project_dest, runtime_dir, root)
    )
    tracker["bindings"] = {
        **_local_tracker_bindings(),
        **(tracker.get("bindings") or {}),
    }
    result = dict(payload)
    result["tracker"] = tracker
    return result


def _local_tracker_connection(
    project_dest: Path, runtime_dir: Path | None, root: str
) -> dict:
    runtime = (runtime_dir or default_install_dir(project_dest)).resolve()
    return {
        "command": "python3",
        "args": [
            str(runtime / "scripts" / "integrations" / "run_local_tracker.py"),
            "--project-root",
            str(project_dest.resolve()),
            "--root",
            root,
        ],
    }


def _local_tracker_bindings() -> dict[str, str]:
    from scripts.integrations.local_tracker import LOCAL_TRACKER_BINDINGS

    return dict(LOCAL_TRACKER_BINDINGS)


def _initialize_local_tracker(project_dest: Path, tracker: dict) -> None:
    root = project_dest / str(tracker.get("root") or ".local-tracker")
    root.mkdir(parents=True, exist_ok=True)
    for state in ("backlog", "ready", "in_progress", "done", "canceled", "artifacts"):
        (root / state).mkdir(exist_ok=True)
    _set_local_tracker_ignore(
        project_dest, str(tracker.get("storagePolicy") or "committed") == "ignored"
    )


def _set_local_tracker_ignore(project_dest: Path, ignored: bool) -> None:
    path = project_dest / ".gitignore"
    start = "# codex-workflows-plugin local tracker (managed)"
    entry = ".local-tracker/"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = existing.splitlines()
    filtered: list[str] = []
    skip_next = False
    for line in lines:
        if line == start:
            skip_next = True
            continue
        if skip_next and line == entry:
            skip_next = False
            continue
        skip_next = False
        filtered.append(line)
    if ignored:
        if filtered and filtered[-1]:
            filtered.append("")
        filtered.extend((start, entry))
    content = "\n".join(filtered).rstrip() + "\n" if filtered else ""
    if content or path.exists():
        path.write_text(content, encoding="utf-8")


def _default_scm_config(provider: str, project_dest: Path) -> dict:
    if provider == "github":
        owner, repo = _github_remote(project_dest)
        return {
            "adapter": "github",
            "owner": owner,
            "repo": repo,
            "connection": {"command": "gh", "args": []},
            "bindings": {},
        }
    if provider == "azure_repos":
        org, project, repo = _azure_remote(project_dest)
        return {
            "adapter": "azure_repos",
            "organization": org,
            "project": project,
            "repository": repo,
            "connection": {
                "command": "npx",
                "args": [
                    "-y",
                    "@azure-devops/mcp",
                    _azure_org_arg(project_dest, fallback=org),
                    "-d",
                    "core",
                    "repositories",
                    "work-items",
                ],
            },
            "bindings": {
                "get_pull_request": "repo_pull_request",
                "create_pull_request": "repo_pull_request_write",
                "list_review_threads": "repo_pull_request_thread",
                "reply_to_thread": "repo_pull_request_thread_write",
                "link_work_item": "wit_work_item_link_write",
            },
        }
    raise ValueError(f"unsupported SCM: {provider}")


def _azure_org_arg(project_dest: Path | None = None, *, fallback: str = "") -> str:
    """Resolve Azure org for MCP argv; expandvars still applies at client spawn."""
    env_org = os.environ.get("AZURE_DEVOPS_ORG", "").strip()
    if env_org:
        return env_org
    if fallback.strip():
        return fallback.strip()
    if project_dest is not None:
        org, _, _ = _azure_remote(project_dest)
        if org:
            return org
    return "${AZURE_DEVOPS_ORG}"


def _github_remote(project_dest: Path) -> tuple[str, str]:
    try:
        remote = subprocess.run(
            ["git", "-C", str(project_dest), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "", ""
    value = remote.removesuffix(".git")
    if "github.com" not in value:
        return "", value.rsplit("/", 1)[-1]
    tail = value.split("github.com", 1)[-1].lstrip(":/")
    parts = tail.split("/")
    return (
        (parts[-2], parts[-1]) if len(parts) >= 2 else ("", parts[-1] if parts else "")
    )


def _azure_remote(project_dest: Path) -> tuple[str, str, str]:
    try:
        remote = subprocess.run(
            ["git", "-C", str(project_dest), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "", "", ""
    value = remote.removesuffix(".git")
    if "dev.azure.com" in value:
        # https://[user@]dev.azure.com/<org>/<project>/_git/<repo>
        # git@ssh.dev.azure.com:v3/<org>/<project>/<repo>
        tail = value.split("dev.azure.com", 1)[-1].lstrip(":/")
        parts = [part for part in tail.split("/") if part and part != "_git"]
        if value.split("dev.azure.com", 1)[0].endswith("ssh.") and parts[:1] == ["v3"]:
            parts = parts[1:]
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
    if "visualstudio.com" in value:
        host = value.split("://", 1)[-1]
        org = host.split(".visualstudio.com", 1)[0]
        tail = value.split(".visualstudio.com", 1)[-1].lstrip(":/")
        parts = [part for part in tail.split("/") if part and part != "_git"]
        if len(parts) >= 2:
            return org, parts[0], parts[1]
    return "", "", value.rsplit("/", 1)[-1]
