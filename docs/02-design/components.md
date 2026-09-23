---
title: Components
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Components

## Context

Each component has one job. Skills are procedures the agent follows; everything else is code the
agent calls or cannot bypass.

## Authority Boundaries

Skills may call orchestrators, the gateway, and the Azure DevOps server; every such call passes
the hook runtime first. Reviewer agents have no file-edit tools (`tools:` in their frontmatter), and their Bash calls pass the hooks like any other.

## Components

### Skills by stage

| Stage | Skills |
| --- | --- |
| Conductors | `harness` (whole flow), `implement-story` (build stage), `review` (verify stage) |
| Setup | `bootstrap`, `azure-devops`, `review-setup`, `tracking-status`, `skip-tracker`, `resume-tracker` |
| 1 · Backlog | `generate-work-item`, `enrich-work-item`, `decompose-backlog`, `split-story`, `generate-breakdown-work-items`, `validate-artifact`, `auto-fix-artifact`, `amend-workitems`, `generate-plain-language-documentation` |
| 2 · Plan | `start-ticket`, `write-spec`, `feature-implementation` |
| 3 · Build | `architect`, `tdd`, `check`, `deslop`, `prove-it-works`, `verify-this`, `sequence-verifiable-units`, `commit-prep`, `automated-tests`, `repository-sync` |
| 4 · Verify | `review-story-preflight`, `review-typescript`, `review-maintainability`, `thermos`, `thermo-nuclear-review`, `thermo-nuclear-code-quality-review`, `branch-and-pr`, `review-pr`, `triage-pr-comments`, `respond-pr-comments`, `resolve-ticket` |
| Stacked Features | `reconcile-feature-stack`, `merge-story-stack-into-feature`, `finish-feature-development` |

Skills with a `manifest.json` are also served as MCP tools by an orchestrator, with their input and
output schemas enforced.

### Runtime components

| Component | Code | Role |
| --- | --- | --- |
| Hook entry point | `scripts/harness/hook.py` | normalizes both hosts' payloads; runs rules; delegates to the workflow policy |
| Rules | `scripts/harness/rules.py` | the seven named rules |
| Evidence store | `scripts/harness/state.py` | approvals, manual checks, check results, verdicts |
| Git queries | `scripts/harness/gitstate.py` | trees, staged paths, branch diffs (bounded by timeouts) |
| Workflow policy | `scripts/hook_runtime.py`, `scripts/policy/` | branch key, state, spec, evidence, protected branches, stack merges |
| Workflow orchestrator | `scripts/orchestrator/` | delivery skills as MCP tools; Actor-Critic loop |
| Integrations gateway | `scripts/integrations/` | tracker and SCM adapters |
| Backlog orchestrator | `runtime/orchestrator_core/` | backlog skills as MCP tools; validation, estimation, capacity; CLI |
| Setup | `scripts/harness/bootstrap.py`, `scripts/harness/integrations_setup.py` | opt a repository in |
| CLI | `bin/harness`, `scripts/harness/cli.py` | version, doctor, bootstrap |
| Installer | `install.sh` (repository root) | install, upgrade, uninstall |

## Runtime State Machine

See [../01-architecture/architecture.md](../01-architecture/architecture.md#runtime-state-machine).

## Durable State

See [../01-architecture/data-model.md](../01-architecture/data-model.md).

## Contracts / Schemas

See [api.md](api.md).

## Host Differences

Both hosts load the same skills, agents, and runtime. Hook wiring and MCP configuration differ per
host (`hooks/hooks.json` vs `hooks/cursor.hooks.json`, `.mcp.json` vs `cursor.mcp.json`).

## Failure Modes

See [../01-architecture/architecture.md](../01-architecture/architecture.md#failure-modes).

## Security Invariants

See [../05-security/security.md](../05-security/security.md).

## Validation Gates

Each runtime component is covered by `tests/`; see
[../03-engineering/testing.md](../03-engineering/testing.md).
