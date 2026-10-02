---
type: implementation-plan
feature: "pending:draft-make-trackers-pluggable-adapters"
story: "pending:draft-define-the-tracker-manifest-and-registry"
skill: generate-breakdown-work-items
language: en
destination: filesystem
status: draft
created: 2026-09-24
area: trackers
stack: [python, json, markdown]
tags: [implementation-plan, trackers, adapters]
---

# Trackers are adapters — implementation plan

Design: `AI_Codex/Specs/2026-09-24-trackers-are-adapters-design.md` (draft, awaiting G2).
Backlog: `AI_Codex/Tickets/Ready/draft-make-trackers-pluggable-adapters.md` and its seven Story drafts (local only;
no Azure items for this Feature).

## Delivery order

One Story, one branch, one pull request. Stacked on a Feature branch `feature/trackers-are-adapters`.

| # | Story | Points | Depends on | Branch |
| --- | --- | --- | --- | --- |
| 1 | Define the tracker manifest and registry | 5 | — | `userstory/trackers-1-manifest-registry` |
| 2 | Move Azure DevOps into its own tracker folder | 8 | 1 | `userstory/trackers-2-azure-folder` |
| 3 | Package Linear and the local tracker as trackers | 5 | 1 | `userstory/trackers-3-linear-local` |
| 4 | Gate writes and protect items through the active tracker | 5 | 1 (fixtures), then 2–3 | `userstory/trackers-4-hooks` |
| 5 | Backlog skills read the tracker's shape | 8 | 2, 3 | `userstory/trackers-5-backlog-skills` |
| 6 | Bootstrap asks which tracker to use | 5 | 2, 3, 4 | `userstory/trackers-6-bootstrap` |
| 7 | Onboard a new tracker from its documentation | 8 | 1, 4, 6 | `userstory/trackers-7-onboarding` |

Release after Story 4 as a minor version (the hooks change is the security-relevant part), and again after
Story 7. Every Story keeps a 0.1.x Azure repository working without re-running bootstrap.

## Story 1 — Define the tracker manifest and registry (next to build)

### Scope

New, with no change in behavior for existing repositories: nothing reads the registry until Story 2.

```text
config/tracker.schema.json            manifest schema, versioned
scripts/trackers/__init__.py
scripts/trackers/registry.py          discover, validate, cache, active tracker, describe()
scripts/trackers/pinning.py           folder digest for onboarded trackers
scripts/harness/state.py              pin_tracker / pinned_trackers (approval records)
scripts/harness/hook.py               an approval also pins onboarded trackers marked approved
tests/trackers/fixtures/{azure-like,linear-like,local-like}/tracker.json
tests/trackers/test_schema.py, test_registry.py, test_pinning.py
docs/01-architecture/decisions/ADR-0009-trackers-are-adapters.md
```

### Architecture sketch (2026-09-25)

`Tracker` is an immutable record containing a validated manifest, its folder, and whether it is
shipped or onboarded. `registry.available(repo)` discovers both roots, validates manifests with
the versioned JSON Schema plus the hierarchy and role invariants, and exposes only approved,
approval-pinned onboarded folders. `registry.active(repo)` reads the selected tracker from the
integration configuration and fails closed when it cannot resolve a valid selection. Parsing is
cached by manifest path and modification time; the approval hook records the sorted content digest
of each approved onboarded folder, so an edit invalidates that selection without mutable registry
state.

### Tasks

Each Task is one verified commit (architect → failing test → implement → check → deslop → commit).

1. **Architect the manifest and registry API.** Sketch the schema fields, the `Tracker` dataclass, and
   `registry.active(repo) -> Tracker`, `registry.available(repo) -> list[Tracker]`,
   `registry.describe(repo) -> dict`. Record the sketch in this plan before code.
   *Done when:* the sketch names every field the design's manifest example uses, and the three roles.
2. **Manifest schema with validation errors that name the field.** `config/tracker.schema.json`
   (identity, access, settings, artifacts with children and estimate, roles, states for the five logical states,
   ids with pattern / branch_key / mention, mentions_link, attachments, text_format, writes, sources, status).
   Validation checks the schema plus rules JSON Schema cannot: every role and child names a declared artifact;
   the hierarchy has no cycle; the delivery unit is below every container.
   *Done when:* three fixture manifests validate; each broken fixture fails with the field named.
3. **Registry discovery and the active tracker.** Shipped trackers from `<plugin>/trackers/*/tracker.json`, onboarded
   from `<repo>/.harness/trackers/*/tracker.json`. Active tracker from `.harness/integrations.json`: `tracker.name`,
   or the legacy `tracker.adapter` mapped (`azure_devops` → `azure-devops`, `local_tracker` → `local`) with a
   warning. Cache by manifest mtime. A missing or invalid active manifest raises `TrackerError`, which callers treat
   as fail-closed.
   *Done when:* tests cover shipped only, onboarded only, a name clash, legacy names, and a broken active manifest.
4. **Pin onboarded trackers by the user's approval.** Digest of an onboarded folder's files (sorted relative path +
   content). When an approval opens, the hook pins every onboarded folder whose manifest says
   `"status": "approved"` (same flow as approved spec notes). The registry lists an onboarded tracker only when its
   current digest is pinned by an approval that was not revoked.
   *Done when:* an unpinned, edited-after-approval, or revoked-approval folder is not listed; a pinned one is; the
   hook test clicks Approve and sees the pin.
5. **`describe()` for hooks, gateway, and backlog runtime.** One function returns the active manifest with settings
   resolved (environment first, then `integrations.json`). No caller outside `scripts/trackers/` reads a manifest
   file directly.
   *Done when:* a test resolves an env-provided setting over the file value.
6. **ADR-0009 and docs.** ADR (status Proposed until G2), the registry in `docs/02-design/components.md`, a
   CHANGELOG `Unreleased` entry.
   *Done when:* markdownlint and `scripts/check_repo.py` pass.
7. **Staging.** Build the release archive, install it into a sandboxed profile (the CI install job), run
   `harness doctor` on a 0.1.10 Azure repository and confirm nothing changed.
8. **Review.** `review` stage: requirements check against the Story's criteria, thermos, fixes, verdict, draft PR.
9. **Breakdown done.** Mark this breakdown complete once Tasks 1–8 are tracked.

### Test strategy

Unit tests only for Story 1 (schema, registry, pinning), plus one hook subprocess test for pinning on Approve,
following `tests/harness/test_questions.py`. Fixture manifests are reused by Story 4's table-driven hook tests.

## Stories 2–7 — approach

**2. Azure folder.** Create `trackers/azure-devops/` by moving, not rewriting: `scripts/integrations/azure.py` →
`adapter.py`; the backlog provider's field mapping merges into it; `skills/azure-devops/references/*`,
`references/azure-mechanics.md`, `enrich-work-item/references/azure-ingest.md` → `references/`;
`common/templates/canonical-*.md` → `templates/`; the health check script → `doctor.py`. The gateway starts the
server from `mcp.json`; drop `azure-devops` from the plugin `.mcp.json` last, after the gateway path is verified.
Existing tests move with the code and must pass unchanged.

**3. Linear and local.** Linear from `LinearTrackerAdapter` + `common/providers.md` rules (managed type labels,
`parentId`, Projects are not Epics). Local from `local_tracker.py` and its runner; records stay in
`.harness/tracker/`. Add a shared contract test module that every shipped tracker runs.

**4. Hooks.** Replace `is_azure_write` / `AZURE_EXTRA_WRITES` with "gateway write or listed in the active manifest's
`writes`". `protected-items` and `mentioned_ids` read `ids.pattern` / `ids.mention` and `mentions_link`.
`resolve_branch_key` uses `ids.branch_key`. `TrackerError` → deny with the reason. Table-driven tests per tracker.

**5. Backlog skills.** Add gateway operations `update_work_item`, `set_estimate`, `describe_tracker`. Rewrite skills
one at a time (validate → generate → enrich → split → decompose → breakdown → amend → auto-fix), each reading
`describe_tracker` for artifacts, hierarchy, and the template path, and writing through the gateway. Replace the
fixed enums in `common/artifact-schema.json` with a check against the active tracker.

**6. Bootstrap.** Question: which tracker (listed from the registry, plus "Onboard a new tracker"). Ask only the
manifest's `settings`. Write `tracker: {name, settings}` once; derive `backlog/config.json` and the review
tracker from it. Migrate the policy's `azure` block. `harness doctor` runs the active tracker's `doctor.py`.

**7. Onboarding.** New skill `onboard-tracker`: the interview and flow in the design; discovery proposes
bindings for MCP access; the result is written with `"status": "draft"`, validated, probed read-only, then set to
approved and pinned by the user's Approve click. Generated adapter code only for trackers without an MCP server.

## Gates

- **G1 (backlog split and bodies):** the user reviews the eight drafts in `AI_Codex/Tickets/Ready/`. No tracker
  write follows, since this Feature's backlog stays local.
- **G2 (design):** the user approves the design doc, including the five decisions listed in it.
- Build starts with Story 1 only after both.
