---
name: codex_workflows
description: "Provider-neutral workflow orchestration, integration contracts, and enforced hook policies."
---

# Workflow orchestration

The orchestrator discovers and invokes skills, validates their input/output contracts, retries transient failures, and runs Actor-Critic reflection. It returns instructions and plans; it is not an MCP client or provider proxy.

The separate `workflow-integrations` MCP gateway owns provider transport. Tracker adapters implement work-item retrieval, creation, hierarchy, state transitions, and durable artifact publication. SCM adapters implement pull requests and review threads. Core workflows depend only on those generic contracts.

Bootstrap selects a tracker (Linear, Azure DevOps Boards, or local tracker), an SCM (GitHub or Azure Repos), provider mappings, and a branch template with `{key}`. Hooks enforce the selected branch convention, one mapped work item per worktree, `in_progress` state before writes, artifact prerequisites, and completion evidence. Provider failures fail closed. `/skip-tracker` pauses only tracker-backed enforcement; SCM workflows and protected-branch Git safety remain active until `/resume-tracker` restores tracking.
