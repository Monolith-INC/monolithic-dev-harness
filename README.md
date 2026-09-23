# monolithic-dev-harness

[![CI](https://github.com/Monolith-INC/monolithic-dev-harness/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Monolith-INC/monolithic-dev-harness/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.1.3-brightgreen.svg)](https://github.com/Monolith-INC/monolithic-dev-harness/releases)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-blueviolet.svg)](https://docs.anthropic.com/en/docs/claude-code)
[![Cursor](https://img.shields.io/badge/Cursor-supported-black.svg)](https://cursor.com)
[![Documentation](https://img.shields.io/badge/docs-project_documentation-informational.svg)](./docs/README.md)

An AI delivery harness for teams on Azure DevOps: one plugin for Claude Code and Cursor that takes
an idea from the backlog to a reviewed draft pull request, with people deciding at four gates and
hooks enforcing every rule that must not depend on the model remembering it.

> **Core principle:** skills tell the agent what to do; deterministic hooks decide what it may do.

## Why this exists

AI agents can refine a backlog, write a spec, implement, and review, but a delivery process built
only from prompts is advice, not a process. The agent can skip the approval, write to the wrong
work item, commit without tests, or open a pull request nobody reviewed, and nothing stops it.

The harness splits the work in two. Model-driven skills do the thinking. A deterministic runtime,
fed by evidence tied to git ids, sits in front of every tool call and refuses the ones the team's
rules forbid.

```text
            Idea / work item
                   |
                   v
   +-------------------------------+        +---------------------------+
   | Skills (model-driven)         |        | Hooks (deterministic)     |
   | backlog -> spec -> build ->   | -----> | every Bash / edit / MCP   |
   | review                        |  tool  | call checked against the  |
   +-------------------------------+  call  | repo policy + evidence    |
                   ^                        +-------------+-------------+
                   |                                      |
            people decide at                     allow  or  deny with
            G1 G2 G3 G4                          the rule and the fix
```

## Documentation

The complete project documentation is available under [`docs/`](./docs/README.md).

| Area         | Documentation                                                                                                 |
| ------------ | ------------------------------------------------------------------------------------------------------------- |
| Product      | [`docs/00-product/`](./docs/00-product/) — vision, requirements, glossary                                     |
| Architecture | [`docs/01-architecture/`](./docs/01-architecture/) — system context, architecture, data model, ADRs           |
| Design       | [`docs/02-design/`](./docs/02-design/) — command and policy contracts, components, workflows                  |
| Engineering  | [`docs/03-engineering/`](./docs/03-engineering/) — development, testing, standards, dependencies              |
| Operations   | [`docs/04-operations/`](./docs/04-operations/) — installation, environments, observability, runbook           |
| Security     | [`docs/05-security/`](./docs/05-security/) — security model, threat model, data privacy                       |
| Delivery     | [`docs/06-delivery/`](./docs/06-delivery/) — roadmap, release process, changelog                              |
| Guides       | [`docs/07-guides/`](./docs/07-guides/) — onboarding, user guide, troubleshooting                              |

## Architecture at a glance

The plugin ships skills (what the agent follows), reviewer subagents, four MCP servers, and one
hook runtime shared by both hosts. The two orchestrator servers validate skill inputs and outputs
and run bounded Actor-Critic loops; they never call a provider. Every provider call goes through
the integrations gateway or the Azure DevOps server, where the hook runtime sees it first.

```text
  Claude Code / Cursor
  +----------------------------------------------------------------+
  |  agent session --follows--> 46 skills --delegates--> thermos   |
  |       |                                              reviewers |
  |       | every governed tool call                               |
  |       v                                                        |
  |  hook runtime (scripts/harness/hook.py)                        |
  |       reads .harness/policy.json and .harness/state/ evidence  |
  +-------|--------------------------------------------------------+
          | allowed calls
          v
  MCP servers:  backlog-orchestrator    workflow-orchestrator
                workflow-integrations --+
                azure-devops -----------+--> Azure Boards + Azure Repos
```

See [`docs/01-architecture/architecture.md`](./docs/01-architecture/architecture.md).

## Features / capabilities

- **Linear backlog:** Epic → Features → Stories (with Story Points in the Azure field) → Tasks, in
  one run with two approval gates, audited for coverage against the source text.
- **Spec-driven delivery:** a technical spec per Story, then one test-first, checked, cleaned-up
  commit per Task; stacked branches for multi-Story Features.
- **Requirements-first review:** coverage of the Story's acceptance criteria before a deep
  correctness and maintainability audit, ending in a recorded verdict and a **draft** pull request.
- **Deterministic enforcement:** seven named rules (for example `approval-required`,
  `tests-with-code`, `draft-reviewed-prs`) plus the workflow policy, evaluated before every
  governed tool call, failing closed for writes.
- **Human approvals that the agent cannot forge:** writes to Azure DevOps open only after you reply
  `approve HB-…`.
- **One-shot install** for Claude Code and Cursor, with a `harness` command for bootstrap and
  health checks.

## Requirements

| Requirement               | Version / Notes                                                        |
| ------------------------- | ---------------------------------------------------------------------- |
| Claude Code and/or Cursor | current releases                                                       |
| Python                    | 3.10 or newer (hooks, orchestrators, CLI)                              |
| git                       | any recent version (the hooks read git state)                          |
| Node.js                   | provides `npx`, which starts the Azure DevOps MCP server               |
| Azure DevOps              | an organization; sign-in is interactive OAuth in your browser          |
| GitHub CLI (`gh`)         | only while the repository is private, to download releases             |

## Installation

```bash
curl -fsSL https://github.com/Monolith-INC/monolithic-dev-harness/releases/latest/download/install.sh | bash
```

While the repository is private, fetch the same installer with the GitHub CLI:

```bash
gh release download --repo Monolith-INC/monolithic-dev-harness --pattern install.sh --output - | bash
```

The installer finds your hosts, downloads the release archive (no cloning), verifies its SHA-256,
installs the plugin into each host, records `AZURE_DEVOPS_ORG`, and links `harness` into
`~/.local/bin`. Options go after `bash -s --`: `--host claude|cursor|all`, `--org <name>`,
`--version <x.y.z>`, `--uninstall`. See
[`docs/04-operations/deployment.md`](./docs/04-operations/deployment.md).

## Quick start

```bash
cd your-repository
harness bootstrap      # writes .harness/policy.json from the example policy
harness doctor         # checks tools, hosts, configuration, and this repository
```

Restart Claude Code (or reload Cursor), then ask the agent:

```text
Take "students can add a profile photo" through the harness, starting with the backlog.
```

The agent drafts the Epic, proposes Features and Stories, and stops at gate G1 for your approval.
Nothing reaches Azure DevOps until you reply `approve HB-…` for the batch it shows you.

## How it works

```text
 1 BACKLOG   generate-work-item -> enrich-work-item -> decompose-backlog -> breakdown
             Epic -> Features -> Stories (points) -> Tasks
                 |
                 +-- G1  Feature Owner / PO approve the split and the bodies
                 v
 2 PLAN      start-ticket -> write-spec (Actor-Critic)
                 |
                 +-- G2  Tech Lead approves the spec
                 v
 3 BUILD     implement-story, per Task:
             architect -> failing test -> implement -> check -> deslop -> commit
                 v
 4 VERIFY    review-story-preflight -> thermos -> fixes -> verdict -> draft PR
                 |
                 +-- G3  staging validation
                 +-- G4  a person publishes and approves the pull request
```

See [`docs/02-design/workflows.md`](./docs/02-design/workflows.md).

## Repository layout

| Path                                                                                                   | Purpose                                                      |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| [`docs/`](./docs/)                                                                                     | Project documentation                                        |
| [`install.sh`](./install.sh)                                                                           | One-shot installer (also attached to every release)          |
| [`.claude-plugin/`](./.claude-plugin/), [`.cursor-plugin/`](./.cursor-plugin/)                         | Marketplace catalogs for each host                           |
| [`plugins/monolithic-dev-harness/`](./plugins/monolithic-dev-harness/)                                 | The plugin: skills, agents, hooks, MCP config, runtime       |
| [`plugins/monolithic-dev-harness/scripts/harness/`](./plugins/monolithic-dev-harness/scripts/harness/) | Rules, hook entry point, evidence scripts, bootstrap, CLI    |
| [`plugins/monolithic-dev-harness/tests/`](./plugins/monolithic-dev-harness/tests/)                     | Automated tests                                              |
| [`scripts/`](./scripts/)                                                                               | Release build and version checks                             |

## Configuration

A repository opts in with `.harness/policy.json` (written by `harness bootstrap`; schema in
[`config/policy.schema.json`](./plugins/monolithic-dev-harness/config/policy.schema.json), example in
[`examples/policy.example.json`](./plugins/monolithic-dev-harness/examples/policy.example.json)).

| Variable / Setting                                                      | Required | Purpose                                                          |
| ----------------------------------------------------------------------- | -------- | ---------------------------------------------------------------- |
| `AZURE_DEVOPS_ORG`                                                      | yes      | Azure DevOps organization for the MCP server and bootstrap       |
| `.harness/policy.json` → `azure`                                        | yes      | project, team, repository, protected work items                  |
| `.harness/policy.json` → `checks`                                       | no       | commands that produce check evidence                             |
| `.harness/policy.json` → `tests_required`, `generated`, `guarded_paths` | no       | inputs to `tests-with-code`, `generated-files`, `guarded-paths`  |

See [`docs/04-operations/environments.md`](./docs/04-operations/environments.md).

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff==0.16.4 jsonschema
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

See [`docs/03-engineering/development.md`](./docs/03-engineering/development.md).

## Testing

```bash
PYTHON=.venv/bin/python plugins/monolithic-dev-harness/tests/run.sh
```

The suites prove the backlog orchestrator's validation, estimation, and capacity logic, the
workflow policy runtime, and every harness rule (a deny case and an allow case, through the real
hook entry point, for both hosts). CI also installs the built release into a sandboxed Claude Code
profile. They do not prove behavior inside a live host session or against a live Azure DevOps
organization: those are the release gates in
[`docs/06-delivery/release-process.md`](./docs/06-delivery/release-process.md).

See [`docs/03-engineering/testing.md`](./docs/03-engineering/testing.md).

## Deployment

Releases are cut by pushing a `vX.Y.Z` tag: CI builds the archive and checksums and publishes the
GitHub release that the installer downloads. Users upgrade by re-running the installer.

See [`docs/04-operations/deployment.md`](./docs/04-operations/deployment.md).

## Security

The agent works with your Azure DevOps identity, so the harness assumes the model can be wrong or
misled. Every tracker and SCM write needs an approval window that only your own prompt can open;
protected work items can never be touched; approval and manual-check records are human-owned; and
the runtime fails closed for writes. Report vulnerabilities privately to the maintainers.

See [`docs/05-security/security.md`](./docs/05-security/security.md).

## Project status

`0.1.3`. The rules, installer, and test suites are verified in CI. Loading in
Cursor and a full end-to-end run against a live Azure DevOps project are pending observation.

See [`docs/06-delivery/roadmap.md`](./docs/06-delivery/roadmap.md).

## Contributing

Edit the sources under `plugins/monolithic-dev-harness/`, never an installed copy. Every rule
change ships with a deny test and an allow test; `ruff check`, `ruff format --check`, and the test
suites must pass; the four version sources must agree before a release.

See [`docs/07-guides/onboarding.md`](./docs/07-guides/onboarding.md).

---

For the complete project model, start with **[`docs/README.md`](./docs/README.md)**.
