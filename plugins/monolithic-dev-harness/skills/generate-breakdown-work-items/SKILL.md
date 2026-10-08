---
name: generate-breakdown-work-items
description: From a Story, Feature, or Epic, save an acceptance-criteria-linked Implementation Plan and atomic child Tasks, then publish reviewed Tasks through the selected tracker. Use for Story breakdown before start-ticket.
license: MIT
---

# Generate Breakdown Work Items

Read `../../references/workflow-storyboard.md` and the selected
[tracker contract](../../references/tracker-contract.md). Use the configured artifacts path and the
user's effective harness language. The active tracker, not an Azure-specific intake choice, defines
where published Tasks live. The local Implementation Plan is always saved before Tasks are created.

References in this skill: `references/plan-generation.md`, `references/atomic-tasks.md`, and
`references/fan-out.md`. Use `../../references/azure-mechanics.md` only for an Azure-backed Story.

## 1. Resolve and inspect

Accept a Story id, URL, or local path; ask only when none was supplied. Call `tracker_describe` to
identify the selected tracker. Read the Story and its parent Feature where present, then capture
acceptance criteria verbatim. Do not invent missing criteria. For a Feature or Epic, enumerate all
child Stories first, then process the chosen set without re-asking destination or language per Story.

## 2. Draft and check locally

Save an Implementation Plan in the configured artifacts path, re-read it, and verify that every
acceptance criterion maps to a delivery step. Create an ordered list of atomic Tasks from the saved
plan, followed by Staging, Review, and Breakdown. Breakdown is last and completed. Derive estimates
with the existing `estimate-breakdown` command when the selected tracker supplies the needed
planning replies. Explain any capacity block before external writes. These reversible steps do not
need separate `proceed` confirmations.

Use the selected tracker and source-control provider for IDs, parent relationships, states, and
field names. For Linear, Task issues are child issues labelled `Task`; for Azure DevOps, use Task
work items under the User Story. If a provider cannot represent Tasks, explain that they would
remain local and obtain that choice before any creation.

## 3. Review once and publish safely

Present the complete saved plan and the proposed Task batch through the host's best available
artifact review surface. A path or short summary alone is insufficient. Show where every Task will
appear. Run `harness tracker preflight` immediately before publication. For Linear, missing
`Story`/`Task` labels or team readiness block the first issue creation; include needed label
creation in the reviewed batch and create labels before dependent issues. The provider must expose
the needed write operations. Seek one approval for the external writes:
the `publish-items` approval gate with the drafts as `--artifact`s (see the harness skill's approval protocol). Local drafts
and deterministic checks need no additional approval.

Publish through the active tracker adapter and read back each Task to verify its Story parent,
state, and estimate fields where supported. After an uncertain response, search for the intended
item before retrying so a timeout does not create a duplicate. Report the plan location, Task ids
and destinations, and any local-only consequence. The Story remains in Backlog until this required
breakdown is complete; only then may `start-ticket` move it into progress.

Use `generate-plain-language-documentation` as an inline prose pass for the plan, Task descriptions,
choice labels, and user summaries. Keep internal ids in the audit record while speaking plainly in
the conversation.
