# Session entry legacy-route candidate trial

This trial used the candidate checkout at `/tmp/monolithic-dev-harness-trial-locw4ixf/project`, the bundled candidate command `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness`, and the candidate skill at `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/skills/harness/SKILL.md`.

The exact request routed was: `Continue DAY-001 task counts — investigate the existing request and prepare its plan`.

## Commands and exact outputs

Command:

```text
/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness bootstrap --inspect --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project
```

Output:

```json
{
  "current_scm": {"name": "local", "values": {}},
  "current_tracker": {"name": "local", "values": {}},
  "handoff": {
    "command": "/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness",
    "environment": {"HARNESS_USER_STATE_DIR": "/home/monolith/.config/monolithic-dev-harness"},
    "instruction": "Use this project and environment for every operation. Preserve the saved original request and current checkpoint. Do not repeat confirmed setup choices, restart an existing run, or advance while a question is unanswered. Report invalid saved state instead of replacing it. Suspended policies do not authorize automatically resuming the run.",
    "next_action": "Draft, enrich, decompose, and break down local work items for human batch review; do not publish.",
    "original_request": "Bootstrap the harness and continue the existing request backlog/DAY-001-task-counts.md through planning and artifacts, stopping before implementation.",
    "paths": {
      "artifacts": "/tmp/monolithic-dev-harness-trial-locw4ixf/project/docs/planning",
      "preferences": "/home/monolith/.config/monolithic-dev-harness/preferences.json",
      "settings": "/tmp/monolithic-dev-harness-trial-locw4ixf/project/.harness/settings.json",
      "workflow": "/tmp/monolithic-dev-harness-trial-locw4ixf/project/.harness/state/workflow.json"
    },
    "pending_question": null,
    "policies_suspended": true,
    "project_root": "/tmp/monolithic-dev-harness-trial-locw4ixf/project",
    "waiting_for_answer": false,
    "workflow_status": "active",
    "working_directory": "/tmp/monolithic-dev-harness-trial-locw4ixf/project"
  },
  "language": "en",
  "language_confirmed": true,
  "missing": [],
  "repository": {
    "branch": "master",
    "git_present": true,
    "has_committed_head": true,
    "head": "a2549ed11e043ba65c6a380f43c3bbe1a2d22c30"
  },
  "status": "ready",
  "tracker_storage": {
    "folders": ["backlog", "ready", "in_progress", "done", "canceled", "artifacts", "capacity"],
    "path": "/tmp/monolithic-dev-harness-trial-locw4ixf/project/.harness/tracker",
    "ready": true,
    "work_item_count": 0
  },
  "trackers": [
    {"label": "Azure DevOps Boards", "name": "azure-devops", "required_values": ["organization", "project"]},
    {"label": "Linear", "name": "linear", "required_values": ["team"]},
    {"label": "Local tracker", "name": "local", "required_values": []}
  ],
  "workflow": {
    "artifacts": [{"digest": "3b43bca461415807f77239587c2947b2cda1b2ce4ce2ab93ed869c92a238227c", "path": "/tmp/monolithic-dev-harness-trial-locw4ixf/project/docs/planning/DAY-001-task-counts-plan.md"}],
    "label": "Approved DAY-001 discovery plan",
    "next_action": "Draft, enrich, decompose, and break down local work items for human batch review; do not publish.",
    "pending": "",
    "point": 4,
    "request": "Bootstrap the harness and continue the existing request backlog/DAY-001-task-counts.md through planning and artifacts, stopping before implementation.",
    "stage": "backlog",
    "stale_artifacts": [],
    "status": "active"
  }
}
```

Command:

```text
/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness work-session route --request "Continue DAY-001 task counts — investigate the existing request and prepare its plan" --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project
```

Output:

```json
{
  "request": "Continue DAY-001 task counts — investigate the existing request and prepare its plan",
  "action": "review_legacy",
  "session_id": null,
  "matches": [],
  "candidates": [
    {
      "version": 1,
      "id": "WS-22ebb757709f",
      "project_root": "/tmp/monolithic-dev-harness-trial-locw4ixf/project",
      "request": "Investigate DAY-001 task counts and prepare its plan.",
      "status": "stopped",
      "created_at": "2026-10-05T07:31:12.615382+00:00",
      "updated_at": "2026-10-05T07:48:10.710334+00:00",
      "events": [
        {"type": "started", "at": "2026-10-05T07:31:12.615382+00:00"},
        {"type": "paused", "at": "2026-10-05T07:31:13.197202+00:00"},
        {"type": "resumed", "at": "2026-10-05T07:31:13.490597+00:00"},
        {"type": "stopped", "at": "2026-10-05T07:31:13.636935+00:00"},
        {"type": "resumed", "at": "2026-10-05T07:48:09.965610+00:00"},
        {"type": "stopped", "at": "2026-10-05T07:48:10.710334+00:00"}
      ]
    },
    {
      "version": 1,
      "id": "WS-66b279ef2af9",
      "project_root": "/tmp/monolithic-dev-harness-trial-locw4ixf/project",
      "request": "Investigate a separate task-count issue, DAY-002.",
      "status": "stopped",
      "created_at": "2026-10-05T07:31:12.836432+00:00",
      "updated_at": "2026-10-05T07:48:11.458273+00:00",
      "events": [
        {"type": "started", "at": "2026-10-05T07:31:12.836432+00:00"},
        {"type": "stopped", "at": "2026-10-05T07:31:13.344521+00:00"},
        {"type": "resumed", "at": "2026-10-05T07:48:10.855630+00:00"},
        {"type": "stopped", "at": "2026-10-05T07:48:11.458273+00:00"}
      ]
    }
  ],
  "legacy_workflow": {
    "status": "active",
    "request": "Bootstrap the harness and continue the existing request backlog/DAY-001-task-counts.md through planning and artifacts, stopping before implementation.",
    "point": {
      "id": 4,
      "label": "Approved DAY-001 discovery plan",
      "stage": "backlog",
      "next_action": "Draft, enrich, decompose, and break down local work items for human batch review; do not publish."
    }
  }
}
```

## Result and limits

The route preserved the exact request, returned two stopped candidates (`WS-22ebb757709f` and `WS-66b279ef2af9`), selected `review_legacy`, and reported the active legacy workflow's saved request, stage (`backlog`), and next action. This is the required review gate. No question was asked and no session, workflow, tracker, or project state was changed.

Direct file-content reads: 1, the candidate skill file. No candidate project file contents were directly read; the two command outputs above are the inspection and route commands' structured results. No repository discovery, ticket file, saved workflow file, or planning artifact was opened directly.

Model/reasoning: The trial worker was launched as GPT-6 Luna at medium reasoning. Its own runtime did not expose model metadata inside the trial, so this level is verified from the coordinator's launch configuration.

This trial verifies candidate-local command behavior only. It does not verify an installed skill, host-provided skill behavior, or native user-interface controls.
