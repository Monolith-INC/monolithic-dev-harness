---
name: generate-breakdown-work-items
description: From a Story, Feature, or Epic, save an acceptance-criteria-linked Implementation Plan and atomic child Tasks, then publish reviewed Tasks through the selected tracker. Use for Story breakdown before start-ticket.
license: MIT
---

# Generate Breakdown Work Items

Read `../../references/workflow-storyboard.md` and the selected
[tracker contract](../../references/tracker-contract.md). Use the configured artifacts path and the
user's effective harness language. The active tracker defines where Tasks live. The local
Implementation Plan is always saved, and approved, before Tasks are proposed.

References in this skill: `references/plan-generation.md`, `references/atomic-tasks.md`, and
`references/fan-out.md`. Use `../../references/azure-mechanics.md` only for an Azure-backed Story.

## 1. Resolve and inspect

Accept a Story id, URL, or local path; ask only when none was supplied. Call `tracker_describe` to
identify the selected tracker. Read the Story and its parent Feature where present, then capture
acceptance criteria verbatim. Do not invent missing criteria. For a Feature or Epic, enumerate all
child Stories first, then process the chosen set without re-asking destination or language per Story.

## 2. Save the plan and have it approved

Save the Story's Implementation Plan where `harness document path --type implementation-plan --item
<story key>` says (its folder in the artifacts path), re-read it, and verify that every
acceptance criterion maps to a delivery step. When it is complete (still `status: draft`), show it with `harness workflow show --artifact <plan>` and put that output in your
reply, then ask `harness decision present --gate implementation-confirm --artifact <plan>`. This
approval is required and comes before any Task is proposed. The harness reads the Story from the
plan's `story` field and refuses the question unless the note is an implementation plan in the artifacts path
naming exactly one Story, that Story exists in the tracker, and the plan was shown as it reads now
(on Claude, in your own reply); approving pins the plan, then set its `status` to `active`. On Revise, change the plan and ask again;
editing an approved plan needs a new approval.

## 3. Propose, approve and create the Tasks

From the approved plan, list the atomic Tasks in order, followed by Staging, Review, and Breakdown.
Breakdown is last and completed. Derive hours with the `estimate-breakdown` command when the
selected tracker supplies the needed planning replies, and explain any capacity block before
anything is written.

Use the selected tracker for IDs, parent relationships, states, and field names. For Linear, Task
issues are child issues labelled `Task`; for Azure DevOps, Task work items under the User Story. If
a provider cannot represent Tasks, explain that they would remain local and obtain that choice
before any creation.

Present the Task batch, with each Task's hours and where it will appear, through the host's best
available review surface; a path or short summary alone is insufficient. Run `harness tracker
preflight` immediately before writing. For Linear, missing `Story`/`Task` labels or team readiness
block the first issue creation; include needed label creation in the reviewed batch. Ask the
`publish-items` approval gate with the Task drafts as `--artifact`s (see the harness skill's
approval protocol). Create each Task with `tracker_create_work_item`, then set its hours, assignee
and sprint with `tracker_update_work_item`, and read it back.

The publication review includes one `planning_completion` receipt on the Breakdown task and its
Done transition after verification. The receipt has JSON content:
`{"purpose":"breakdown","item_id":"<Breakdown id>","parent_id":"<Story id>","children":["<each other published child id>"]}`.
Show this intended bookkeeping in the batch review; it authorizes no implementation. After readback,
publish the receipt with `tracker_publish_artifact` (one stable title and a positive integer
revision, starting at `1` and increasing for corrections), then transition
only the Breakdown task to Done. The policy verifies its Task kind, Breakdown title, Story parent
and complete child set. It needs no checkout branch/session or implementation artifacts.
Ordinary Task and Story completion keeps its implementation evidence requirements.

Publish through the active tracker adapter and read back each Task to verify its Story parent,
state, and estimate fields where supported. After an uncertain response, search for the intended
item before retrying so a timeout does not create a duplicate. Report the plan location, Task ids
and destinations, and any local-only consequence. The Story remains in Backlog until this required
breakdown is complete; only then may `start-ticket` move it into progress.

Use `generate-plain-language-documentation` as an inline prose pass for the plan, Task descriptions,
choice labels, and user summaries. Keep internal ids in the audit record while speaking plainly in
the conversation.
