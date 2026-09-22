# Monolithic Dev Harness

An AI delivery process for teams on Azure DevOps, packaged as one plugin for **Claude Code** and
**Cursor**. It takes an idea from the backlog to a draft pull request in four stages. People decide
at four gates, and hooks enforce the rules that must not depend on the model remembering them.

```
 idea / work item
      │
 1 BACKLOG   Epic draft → enrich → Features → Stories (with points) → Tasks
      ├── G1  Feature Owner / PO approve the split and the bodies before anything is written to Azure
 2 PLAN      start the Story → technical spec (drafted, then critiqued)
      ├── G2  Tech Lead approves the spec
 3 BUILD     per Task: architect → failing test → implement → checks → deslop → commit
 4 VERIFY    requirements coverage → deep audit (thermos) → fixes → verdict → draft pull request
      ├── G3  Feature Owner validates in staging
      └── G4  a person publishes and approves the pull request
```

## Install

Requirements: Python 3.10+, `git`, Node.js with `npx` (for the Azure DevOps MCP server), and a
browser signed in to Azure DevOps (the server uses interactive OAuth).

**Claude Code**

```bash
claude plugin marketplace add <path-or-git-url-of-this-repo>
claude plugin install monolithic-dev-harness@monolithic-dev-harness
```

Set `AZURE_DEVOPS_ORG` to your Azure DevOps organization before starting the host. It is required;
the plugin has no default organization.

**Cursor**: add this repository as a local plugin marketplace (it ships
`.cursor-plugin/marketplace.json`), or copy `plugins/monolithic-dev-harness` into Cursor's local
plugins directory, then reload the window and enable **Monolithic Dev Harness** under *Customize*.
Cursor reads the same `AZURE_DEVOPS_ORG` environment variable (`cursor.mcp.json`).

## Opt a repository in

Installing the plugin changes nothing on its own. A repository is governed only once it has
`.harness/policy.json`:

```bash
AZURE_DEVOPS_ORG=<your-org> python3 <plugin>/scripts/harness/bootstrap.py --repo <repo> --policy-from <plugin>/examples/policy.example.json
```

When the policy leaves `azure.organization` empty (as the example does), bootstrap records the value
of `AZURE_DEVOPS_ORG` in the repository's policy.

Then run the `review-setup` skill once and restart the session. The `bootstrap` skill walks you
through it and explains every policy field (schema: `config/policy.schema.json`).

## What is enforced (hooks)

One policy runtime runs on every relevant tool call in both hosts (Claude `PreToolUse` /
`UserPromptSubmit`; Cursor `preToolUse`, `beforeShellExecution`, `beforeMCPExecution`,
`beforeSubmitPrompt`).

| Rule | Blocks |
| --- | --- |
| `human-owned` | the agent writing `.harness/policy.json`, approval records, or manual-check records |
| `approval-required` | any Azure DevOps write (work items, links, comments, pull requests, threads, branches) and `git push`, unless the user opened an approval window by replying `approve HB-…` |
| `protected-items` | writes, links, or children on protected work items, even with approval |
| `tests-with-code` | commits that change source files with no test change in the commit or on the branch |
| `generated-files` | hand edits to generated files |
| `guarded-paths` | commits to guarded paths (e.g. database migrations, security rules, infrastructure) without check or manual evidence for the exact staged tree |
| `draft-reviewed-prs` | non-draft pull requests, pull requests without a `ready` review verdict and passing checks for HEAD, and the agent publishing drafts or voting |
| workflow | branch naming with exactly one work-item key, in-progress state, spec before code, completion evidence, protected branches, stack merge order (from codex-workflows) |

Evidence is keyed to git tree and commit ids, so any change after a check or a review makes it
stale. The runtime fails closed for write-class calls: if the rules cannot run, writes are blocked
and reads still work. Some things stay review-only because no deterministic check exists, for
example PII masking in the UI.

## Design decisions

- **The board stays the source of truth.** Work-item state lives in Azure Boards, and the harness
  adds no columns: its stages map onto the usual Story tasks (Kickoff, Breakdown, Staging, Review).
  Specs, plans, and reports live in the repository's artifacts folder and are linked from the work
  items. Every write passes the approval gate.
- **It extends the tools it is built from.** The backlog skills gain a linear Epic → Feature →
  Story pass and mandatory Story Points in the Azure field; delivery keeps codex-workflows'
  Feature Owner flow with stacked branches; review puts requirements coverage before the deep
  audit. A repository's older code-review or workflow skills are best retired when it opts in, so
  one enforcer and one review path run per repository.
- **People decide at four gates.** G1 backlog approval, G2 spec approval, G3 staging validation, G4
  pull-request approval. Each is either an approval batch the hooks require or an action the hooks
  reserve for people.
- **Models and cost.** Opus-class for backlog, spec, and review synthesis; Opus-class at medium
  effort or Sonnet-class for implementation (measure both on real Stories); the thermos reviewers
  are pinned to `opus`. Interactive use is covered by host seats; automation (pipelines, triggers)
  is billed per token, so record usage per stage on real runs rather than estimating it.

## Layout

```
plugins/monolithic-dev-harness/
  skills/        46 skills (backlog, delivery, execution, review, harness conductor, azure-devops)
  agents/        thermos reviewer subagents
  hooks/         hooks.json (Claude), cursor.hooks.json (Cursor)
  scripts/       harness rules + workflow policy runtime, integrations gateway, orchestrator
  runtime/       backlog orchestrator (MCP server + CLI via bin/agile-backlog-toolkit)
  config/        policy schema     examples/  example policy
  tests/         backlog, delivery, harness suites (tests/run.sh)
```

Third-party sources and licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
