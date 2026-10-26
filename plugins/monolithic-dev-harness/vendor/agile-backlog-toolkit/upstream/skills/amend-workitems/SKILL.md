---
name: amend-workitems
description: >
  Analyze user instructions and safely amend an entire Azure DevOps or local artifacts work-item tree. Use when a user supplies corrections or adjustments for an Epic or Feature and expects the Epic, Features, User Stories, and child Tasks to be scanned, placed, reviewed, and updated consistently. This skill gathers and presents a change set before any write, creates a recoverable tree backup, and never changes work items without explicit approval.
license: MIT
---

# Amend Work Items

Safely incorporate approved corrections across a complete Epic or Feature tree. The skill is
content-only by default: hierarchy, state, assignee, area, iteration, tags, and unrelated text
remain unchanged. Read the references below before making placement or persistence decisions.

References:

- `./references/placement.md` — keyword ranking and type/section placement.
- `./references/backup-and-artifacts path.md` — backup, revision, Obsidian, and recovery rules.
- `./references/approval-and-persistence.md` — change-set approval and delegated writers.
- `../../references/ticket-structure.md` — artifacts path structure and section order.
- `../../references/azure-mechanics.md` — Azure reads, links, updates, and read-back.
- `../enrich-work-item/references/` — canonical sections and examples for Epic, Feature, and Story.
- `../generate-breakdown-work-items/references/` — Implementation Plans and Task child rules.

## Workflow

### 1. Intake through UI

Ask one question at a time through the host UI:

1. Collect the amendment instructions verbatim. Do not paraphrase away corrections.
2. Collect the reference Epic or Feature (Azure id/URL, Artifacts path, or filesystem path).
3. Confirm scope as the complete descendant tree and the non-destructive, content-only policy.

Do not read or write the tree before the reference is supplied. If the reference is ambiguous,
stop and ask for a resolvable id, URL, or path.

### 2. Resolve, snapshot, and scan

Read `backup-and-artifacts path.md` before resolving the source. Create a backup of the entire tree before
semantic analysis. The snapshot must include every Epic, Feature, Story, and Task body; ids,
revisions, parent links, child links, attachments, and related `Implementation_Plans/` notes. Verify
that the backup is readable and complete. A failed or partial backup is a hard stop.

Resolve the reference and enumerate descendants from Epic → Feature → User Story → Task before
proposing changes. Read each node and retain its original revision. When a local Artifacts exists,
use `obsidian search`/CLI first for title, id, and extracted keywords; use `rg` as the fallback or
secondary index. Search exact phrases, identifiers, normalized tokens, and stemmed terms from the
instructions. Keep unmatched instructions visible instead of silently dropping them.

### 3. Analyze and offer placement

Split the instructions into atomic amendments. For each amendment, score candidate nodes and
canonical sections using exact identifiers, title matches, phrase matches, and type/section
compatibility. Read `placement.md` and the relevant canonical/example reference before deciding.

Present a single-select UI list for each amendment. Put the recommended placement first, include
the reason and affected node/section, and make the final option exactly `Other` so the user can
describe an alternative. Do not apply a placement until the user selects it. If a placement would
require a new work item, structural relink, deletion, or state transition, flag it as out of scope
and request explicit direction.

### 4. Build and approve one change set

Produce a consolidated preview containing, for every selected placement:

- work-item id/path, type, and section;
- before/after content or an exact insertion/replacement description;
- linked Task and Implementation Plan consequences;
- preserved fields and unresolved items;
- backup location and source revisions.

Re-read current revisions immediately before the approval prompt. If any revision changed since
the scan, refresh that node and rebuild the affected proposal. Request explicit approval through
the UI. Cancellation or rejection ends the run without writes.

### 5. Apply using existing Agile Backlog Toolkit skills

After approval, delegate type-specific content work to the existing skills rather than inventing a
parallel format:

- Epic, Feature, or User Story prose/section changes → `$enrich-work-item` with its canonical
  references and approval gate.
- Human-facing wording → `$generate-plain-language-documentation`.
- An existing Story's plan-backed Task changes → `$generate-breakdown-work-items` rules; update
  the saved Implementation Plan before reconciling its Tasks.
- A missing required Task explicitly approved by the user → `$generate-work-item` and then link it
  as a child of the Story.

Apply approved content top-down. Never mutate hierarchy, state, ownership, area, iteration, tags,
or unrelated sections. Reconcile the Task child list without deleting existing Tasks: update only
affected Task content, add approved missing Tasks, and report stale/unmatched Tasks for review.

**Any change to a Story's Task list invalidates its hour estimates.** Whenever Tasks are added,
removed, retitled, or rescoped, recompute the whole Story's split, write the new figures, and
report every one that moved (old → new). Nothing asked for approval, so nothing may move silently.
Re-check the total against the assignee's remaining capacity in the active sprint; if it no longer
fits, STOP and ask before writing. Full rules in
`../generate-breakdown-work-items/references/atomic-tasks.md`.
Update related Artifacts Implementation Plans when the amendment changes scope, acceptance coverage,
or task sequencing. Read back every changed Azure item and Artifacts file, verify parent links and
revisions, and run the applicable `validate-artifact` checks. Stop on the first failed write or
read-back; leave the backup intact and report the exact recovery target.

### 6. Report

Report backup location, scanned tree counts, approved placements, changed nodes, recomputed
Task hours (old → new), Task-list and
Implementation-Plan updates, validation results, and unresolved instructions. State explicitly
that no state or hierarchy changes were made when that is true.

## Safety invariants

- Never write before backup, placement selection, consolidated preview, and explicit approval.
- Never overwrite a newer revision; refresh and re-propose instead.
- Never delete, relink, or change state without a separate explicit approval.
- Preserve original instruction text and all unmatched items in the report.
- If Azure and Artifacts disagree, stop and present the conflict; do not guess which copy wins.
