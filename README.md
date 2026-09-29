# monolithic-dev-harness

[![CI](https://github.com/Monolith-INC/monolithic-dev-harness/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Monolith-INC/monolithic-dev-harness/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.2.0-brightgreen.svg)](https://github.com/Monolith-INC/monolithic-dev-harness/releases)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-blueviolet.svg)](https://docs.anthropic.com/en/docs/claude-code)
[![Cursor](https://img.shields.io/badge/Cursor-supported-black.svg)](https://cursor.com)
[![Documentation](https://img.shields.io/badge/docs-project_documentation-informational.svg)](./docs/README.md)

An AI delivery harness for teams on Azure DevOps, Linear, a repository-local tracker, or a tracker
they onboard: one plugin for Claude Code and Cursor that takes an idea from the backlog to a
reviewed draft pull request, with people deciding at four gates and
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
   +-------------------------------+  call  | repo settings + evidence  |
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
| Design       | [`docs/02-design/`](./docs/02-design/) — command, settings, and tracker contracts, components, workflows      |
| Engineering  | [`docs/03-engineering/`](./docs/03-engineering/) — development, testing, standards, dependencies              |
| Operations   | [`docs/04-operations/`](./docs/04-operations/) — installation, environments, observability, runbook           |
| Security     | [`docs/05-security/`](./docs/05-security/) — security model, threat model, data privacy                       |
| Delivery     | [`docs/06-delivery/`](./docs/06-delivery/) — roadmap, release process, changelog                              |
| Guides       | [`docs/07-guides/`](./docs/07-guides/) — onboarding, user guide, troubleshooting                              |

## Architecture at a glance

The plugin ships skills (what the agent follows), reviewer subagents, four MCP servers, and one
hook runtime shared by both hosts. The two orchestrator servers validate skill inputs and outputs
and run bounded Actor-Critic loops; they never call a provider. Every provider call goes through
the integrations gateway or a tracker's own server, where the hook runtime sees it first. Each
tracker is one folder (`trackers/<name>/`: a checked `tracker.json` and an `adapter.py`).

```text
  Claude Code / Cursor
  +----------------------------------------------------------------+
  |  agent session --follows--> 45 skills --delegates--> thermos   |
  |       |                                              reviewers |
  |       | every governed tool call                               |
  |       v                                                        |
  |  hook runtime (scripts/harness/hook.py)                        |
  |       reads .harness/settings.json, tracker folders, evidence  |
  +-------|--------------------------------------------------------+
          | allowed calls
          v
  MCP servers:  backlog-orchestrator    workflow-orchestrator
                workflow-integrations --> selected tracker's adapter
                                          (Azure DevOps, Linear, local, onboarded)
                                          + SCM (Azure Repos, GitHub)
                azure-devops -----------> Azure Boards + Azure Repos
```

See [`docs/01-architecture/architecture.md`](./docs/01-architecture/architecture.md).

## Features / capabilities

- **Linear backlog:** Epic → Features → Stories (with Story Points) → Tasks, in one run with two
  approval gates, audited for coverage against the source text.
- **Trackers are adapters:** Azure DevOps, Linear, and a repository-local tracker ship; any other
  can be onboarded as a folder, and counts only once a person trusts it as it reads.
- **Sessions:** a work item is bound to one checkout; code changes need an active session, and the
  workflow checks that item.
- **Spec-driven delivery:** a technical spec per Story, then one test-first, checked, cleaned-up
  commit per Task; stacked branches for multi-Story Features.
- **Requirements-first review:** coverage of the Story's acceptance criteria before a deep
  correctness and maintainability audit, ending in a recorded verdict and a **draft** pull request.
- **Deterministic enforcement:** nine named rules (for example `approval-required`,
  `tests-with-code`, `draft-reviewed-prs`) plus the workflow policy, evaluated before every
  governed tool call, failing closed for writes.
- **Human approvals that the agent cannot forge:** tracker and SCM writes open only after you click
  **Approve** on the agent's question (or, in Cursor, reply `approve HB-…`).
- **Plain questions:** a hook sends back any question to you that is long, asks several things, or
  uses file names, code, or internal names.
- **One settings file** per repository, `.harness/settings.json`, written by people and only read
  by the harness.
- **One-shot install** for Claude Code and Cursor, with a `harness` command for bootstrap, health
  checks, sessions, and trackers.

## Requirements

| Requirement               | Version / Notes                                                        |
| ------------------------- | ---------------------------------------------------------------------- |
| Claude Code and/or Cursor | current releases                                                       |
| Python                    | 3.10 or newer (hooks, orchestrators, CLI)                              |
| git                       | any recent version (the hooks read git state)                          |
| Node.js                   | provides `npx`, which starts the Azure DevOps and Linear MCP servers   |
| A tracker                 | Azure DevOps or Linear (sign-in is OAuth in your browser), or none for the local tracker |
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
installs the plugin into each host, records `AZURE_DEVOPS_ORG` for the host's Azure DevOps server,
and links `harness` into
`~/.local/bin`. Options go after `bash -s --`: `--host claude|cursor|all`, `--org <name>`,
`--version <x.y.z>`, `--uninstall`. See
[`docs/04-operations/deployment.md`](./docs/04-operations/deployment.md).

## Quick start

```bash
cd your-repository
harness bootstrap --settings-from my-settings.json   # checks it, then writes .harness/settings.json
harness doctor                                       # tools, hosts, settings, tracker, session
```

Restart Claude Code (or reload Cursor), then ask the agent:

```text
Take "students can add a profile photo" through the harness, starting with the backlog.
```

The agent drafts the Epic, proposes Features and Stories, and stops at gate G1 for your approval.
Nothing reaches the tracker until you click **Approve** on the batch it shows you. Start from
[`examples/settings.example.json`](./plugins/monolithic-dev-harness/examples/settings.example.json).

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

### The implementation workflow

Stage 3 starts once a Story has an approved technical spec. Its job is to turn each of the
Story's Tasks into one tested, checked commit.

**What it starts from.** The Story and its acceptance criteria (backlog stage), the ordered list of
Tasks (breakdown), and the spec approved at gate G2. It doesn't re-decide any of these. If there is
no approved spec, it stops and asks for one.

#### Start of the Story

1. Move the Story to in progress in the tracker. That's a board write, so a person approves it.
2. Create the branch, for example `userstory/1234-short-title`, and bind the Story to this checkout
   with `harness session start 1234`.
3. Read the repository's `AGENTS.md` once and note the rules that apply: tests for new code,
   generated files, guarded paths.

#### Each Task, in order, finished before the next one starts

1. **Design first**, only if the Task changes an interface: sketch the types and signatures.
2. **Write a failing test** for the Task's acceptance criterion.
3. **Write the smallest code** that makes it pass.
4. **Run the repository's checks:** lint and tests, plus the check a guarded path needs if one
   changed. Fix until green.
5. **Clean up** leftover AI clutter in the diff.
6. **Commit**, one commit per Task, naming the Task id.
7. **Mark the Task done** in the tracker. That's a board write, so a person approves it; several
   finished Tasks can share one approval.

#### What the hooks block while it works

- committing code without tests (`tests-with-code`)
- editing generated files (`generated-files`)
- committing a guarded path before its check passes, or before a person has checked it by hand
  (`guarded-paths`)
- writing to the board or pushing without approval (`approval-required`)

#### End of the Story

1. Run the checks once more on the final code, and record the result.
2. Run the real thing (app, emulator, endpoint) and write down what actually happened.
3. Hand over to stage 4 (review). The pull request is opened there, not here.

**What you get back:** per Task, the commit, the test that failed and then passed, and the checks
run. Per Story, the evidence and the observed behavior.

### Implementing a Feature

A Feature with several Stories runs the Story workflow once per Story, on branches stacked under
one Feature branch:

```text
develop
  +-- feature/1200-short-title          <- Feature branch
        +-- userstory/1201-...          <- Story 1, branched from the Feature
        +-- userstory/1202-...          <- Story 2
        +-- userstory/1203-...          <- Story 3
```

1. **Plan** (`feature-implementation`): read the Feature and its Stories from the tracker, confirm
   their states and acceptance criteria, create the Feature branch, and publish an implementation
   plan on the Feature.
2. **Each Story, in stack order:** start the Story (approved), write the spec (gate G2), implement
   it on a Story branch cut from the Feature branch, then review it. Review ends in a draft pull
   request from the Story branch **into the Feature branch**, not into `develop`.
3. **Reconcile** (`reconcile-feature-stack`): when an earlier Story changes after later ones were
   branched from it, carry that change forward into the later branches in order, then re-run the
   checks.
4. **Land the stack** (`merge-story-stack-into-feature`): merge the Story pull requests into the
   Feature branch oldest to newest, with merge commits only. While this runs, a hook blocks rebase,
   squash, and force-push.
5. **Finish** (`finish-feature-development`): once every Story has landed, open the Feature →
   `develop` pull request, link it to the Feature, post a closing summary, and move the Feature to
   done.

Every board write, push, and pull request along the way needs a person's approval, the same as for
a single Story.

### Common questions

#### How does code review fit into the workflow?

Code review is stage 4: after implementation, before any pull request. The harness first checks the
whole Story branch against the Story's requirements and definition of done. Two reviewers then
audit the diff in parallel, one for correctness and security, one for maintainability. Verified
findings of high severity or above are fixed as new commits, and a verdict is recorded for the
exact commit reviewed. The hooks refuse to open a pull request without a `ready` verdict and
passing checks for that commit, so the order is enforced, not advised.

#### How does the harness choose an implementation flow?

By what it is given. A single Story runs the Story workflow above; a Feature with several Stories
runs the Feature workflow, with stacked branches. The conductor skill (`harness`) describes that
choice; nothing in code makes it. Inside either flow, the work follows what was agreed: the
Story's acceptance criteria, its ordered Tasks, and its approved spec. The harness does not
redefine scope during implementation.

#### Is there a pull request review flow?

Yes, in two parts.

- **Before the pull request:** the review above. When the verdict is ready and the checks pass,
  the harness pushes and opens a **draft** pull request linked to the Story, after a person
  approves that push and pull request as one batch. In stacked work the Story's pull request
  targets the Feature branch; otherwise the repository's base branch.
- **After it:** a person publishes and approves the pull request; the hooks block the agent from
  doing either. When reviewers leave comments, `triage-pr-comments` lists them with their file and
  line and fact-checks each one, and `respond-pr-comments` replies or makes the requested changes.
  Both run only when you ask, and every reply posted needs approval.

#### What if implementation is already in progress?

Not supported yet. There is no workflow that takes over a branch someone already started, maps its
commits to the Story's Tasks, and continues from there. The workflow hooks also refuse writes on a
branch whose name doesn't follow the configured convention (for example `develop`). The review
stage can run on an existing branch; implementation cannot resume mid-way.

#### What happens when an Epic, Feature, or Story changes during stacked development?

Changes to the work items go through `amend-workitems`. It backs up the whole tree, shows the
complete proposed change set, and waits for approval before writing anything. When the change
touches a Story's Tasks, it updates the Story's implementation plan and recomputes the Tasks' hour
estimates, reporting every figure that moved. When an earlier Story's branch changes, the harness
carries that change forward through the later Story branches with merges and runs the checks
again.

#### Are the related records updated when a Task is complete?

Yes. After a Task is committed and checked, the harness moves it to done in the tracker once a
person approves (several finished Tasks can share one approval). Technical specifications are kept
as artifacts on the work item. The harness does not change unrelated records, ownership, state, or
hierarchy without separate approval.

#### When does the harness use test-first development?

By default, for every Task that has a practical automated test: the test is written first, seen to
fail for the intended reason, then made to pass. When a useful automated test isn't practical, the
harness says so and uses the closest reliable check instead (a targeted script, an emulator
scenario, or a manual check).

Known conflict: the `tests-with-code` hook refuses any commit that changes source files with no
test changes in the commit or earlier on the branch. So a Task with no practical automated test
can only be committed once the branch already has test changes; as the first Task on a branch,
it is blocked.

#### What if the team has only an idea and no backlog records?

The harness can start from the idea. It drafts a work item from it (any level: an Epic, a Feature,
or a Story, and neither of the last two needs a parent), structures the description, breaks it into
Features and Stories, and creates Tasks for the Stories that will be built next. Nothing is written
to the tracker before a person approves the proposed backlog.

#### Is there a planning or brainstorming workflow?

Planning, yes; brainstorming, no. Planning starts once the team knows what to build: the backlog
stage, then a technical spec per Story (see below). There is no step for exploring a problem,
comparing options, or deciding whether something is worth building.

#### Is there a worker-agent workflow?

No. Implementation is one agent working one Task at a time. The only subagents are the two review
agents (thermos) and the architect's design candidates. Nothing dispatches Tasks or Stories to
agents working in parallel.

### Planning and delivery

The harness plans delivery after a team has chosen what to build. It starts with an idea or an
existing backlog item, drafts and approves the backlog, then creates a technical specification for
each selected Story. The specification describes the system design, affected parts of the repository,
test approach, user-interface notes, and risks. A technical lead must approve it before
implementation begins.

```text
Idea or existing backlog item
  |
  v
Backlog draft and approval
  |
  v
Technical planning for a selected Story
  |
  v
Approved specification
  |
  v
Implementation
```

## Repository layout

| Path                                                                                                   | Purpose                                                      |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| [`docs/`](./docs/)                                                                                     | Project documentation                                        |
| [`install.sh`](./install.sh)                                                                           | One-shot installer (also attached to every release)          |
| [`.claude-plugin/`](./.claude-plugin/), [`.cursor-plugin/`](./.cursor-plugin/)                         | Marketplace catalogs for each host                           |
| [`plugins/monolithic-dev-harness/`](./plugins/monolithic-dev-harness/)                                 | The plugin: skills, agents, hooks, MCP config, runtime       |
| [`plugins/monolithic-dev-harness/scripts/harness/`](./plugins/monolithic-dev-harness/scripts/harness/) | Rules, hook entry point, settings, sessions, bootstrap, CLI  |
| [`plugins/monolithic-dev-harness/scripts/integrations/`](./plugins/monolithic-dev-harness/scripts/integrations/) | Tracker contract, registry, trust, gateway, SCM adapters |
| [`plugins/monolithic-dev-harness/trackers/`](./plugins/monolithic-dev-harness/trackers/)               | Shipped trackers: one `tracker.json` and `adapter.py` each   |
| [`plugins/monolithic-dev-harness/config/`](./plugins/monolithic-dev-harness/config/)                   | Settings and tracker schemas                                 |
| [`plugins/monolithic-dev-harness/tests/`](./plugins/monolithic-dev-harness/tests/)                     | Automated tests                                              |
| [`scripts/`](./scripts/)                                                                               | Release build and version checks                             |

## Configuration

A repository opts in with `.harness/settings.json`, its only settings file (people write it; the
harness only reads it). Schema:
[`config/settings.schema.json`](./plugins/monolithic-dev-harness/config/settings.schema.json);
example:
[`examples/settings.example.json`](./plugins/monolithic-dev-harness/examples/settings.example.json).

| Setting                                          | Required | Purpose                                                         |
| ------------------------------------------------ | -------- | --------------------------------------------------------------- |
| `tracker` (`name`, `source`, `values`)           | yes      | which tracker, and the values its `tracker.json` asks for       |
| `scm` (`name`, `values`)                         | yes      | GitHub or Azure Repos                                           |
| `branch_template`                                | yes      | ticket branch names; contains `{key}`                           |
| `protected_work_items`                           | no       | ids never written, linked, parented, or mentioned               |
| `artifacts_path`                                 | no       | where plans, specs, and backlog drafts live                     |
| `checks`, `tests_required`, `generated`, `guarded_paths`, `pull_requests` | no | inputs to the commit and pull request rules |
| `AZURE_DEVOPS_ORG` (environment)                 | Azure    | the organization for the host-registered Azure DevOps server    |

Adding a tracker: [`skills/onboard-tracker`](./plugins/monolithic-dev-harness/skills/onboard-tracker/SKILL.md).
See [`docs/04-operations/environments.md`](./docs/04-operations/environments.md) and
[`docs/02-design/api.md`](./docs/02-design/api.md).

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff==0.16.4
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

See [`docs/03-engineering/development.md`](./docs/03-engineering/development.md).

## Testing

```bash
PYTHON=.venv/bin/python plugins/monolithic-dev-harness/tests/run.sh
```

The suites prove the backlog orchestrator's validation, estimation, and capacity logic, the tracker
contract and each shipped adapter against its provider's reply shapes, sessions, the workflow
policy runtime, and every harness rule (a deny case and an allow case, through the real
hook entry point, for both hosts). CI also installs the built release into a sandboxed Claude Code
profile. They do not prove behavior inside a live host session or against live Azure DevOps or
Linear projects: those are the release gates in
[`docs/06-delivery/release-process.md`](./docs/06-delivery/release-process.md).

See [`docs/03-engineering/testing.md`](./docs/03-engineering/testing.md).

## Deployment

Releases are cut by pushing a `vX.Y.Z` tag: CI builds the archive and checksums and publishes the
GitHub release that the installer downloads. Users upgrade by re-running the installer.

See [`docs/04-operations/deployment.md`](./docs/04-operations/deployment.md).

## Security

The agent works with your tracker and repository identity, so the harness assumes the model can be
wrong or misled. Every tracker and SCM write needs an approval window that only your own prompt can
open; protected work items can never be touched; the settings, approval, manual-check, session, and
tracker-trust records are human-owned; an onboarded tracker counts only as you trusted it; and the
runtime fails closed for writes. Report vulnerabilities privately to the maintainers.

See [`docs/05-security/security.md`](./docs/05-security/security.md).

## Project status

`0.2.0`. The rules, adapters, installer, and test suites are verified in CI. Loading in Cursor, a
full end-to-end run against a live Azure DevOps project, and a live check of the Linear adapter are
pending observation.

See [`docs/06-delivery/roadmap.md`](./docs/06-delivery/roadmap.md).

## Contributing

Edit the sources under `plugins/monolithic-dev-harness/`, never an installed copy. Every rule
change ships with a deny test and an allow test; `ruff check`, `ruff format --check`, and the test
suites must pass; the four version sources must agree before a release.

See [`docs/07-guides/onboarding.md`](./docs/07-guides/onboarding.md).

---

For the complete project model, start with **[`docs/README.md`](./docs/README.md)**.
