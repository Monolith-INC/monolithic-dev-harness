# Onboarding contract

Discovery and communication require neither Git nor an implementation session. Free mode allows
direct skill use. The user can pause, resume, restart, reset or drop preparation at any time;
archive prior progress before replacing it, preserve decisions and external-write receipts,
and never replay completed tracker writes. Suspension disables all harness vetoes.

## Discovery

Read the request, ticket, relevant project documents and code. Use subagent investigations and
focused deep reconnaissance when useful. Record the Code Map, constraints and unresolved choices.
Investigate before asking. Do not inspect branches, commits or repository readiness here.

## Planning

After discovery and before drafting, present the bilingual planning-depth gate. Light means
focused self-review; Standard means contextual methods, technical choices, risks and edge cases;
Hardcore adds adversarial and preservation/verification reviewers. Present the planning-methods
gate for contextual shortlist, full catalog or agent recommendations. The shortlist is selected
from the discovered work, not random. Retain BMAD's Reshuffle, List all and Proceed controls.
All method choices use native-first decisions with no more than three options at a time. Page the
shortlist and full catalog; retain selected methods and their order between decisions. On transport
failure, use the same decision's supported fallback and say that the surface changed.
Save decisions and findings as they occur. A recorded choice is not asked again unless reopened
by the user or materially changed circumstances.

## Hardening

Review the drafted approach using the selected rigor. Reconcile original requirements and accepted
decisions. Triage findings into fixes, consequential choices and deferred improvements with owner
and revisit trigger. Resolve only choices that objectively block dependent work; continue independent
work. Additional elicitation remains available but is not an endless default loop.

## Refinement

Right after Hardening, refine the backlog in the selected tracker with the agile-backlog-toolkit
skills, run as their workflow is written. An item is refined when its text is in its type's template
(`enrich-work-item` writes it, keeping the draft as Original Description) and it passes
`validate-artifact`; Tasks are a Story's breakdown into steps, not part of refinement.

The work session tracks the item the user started from: once that Epic, Feature or Story exists in
the tracker, run `harness work-session track --work-item <key>`. Later, each Story is linked in turn
with `harness work-session link`, which refuses a Story outside that item's tree. The steps:

1. Carry approach changes into items that already exist first: `enrich-work-item` for one item,
   `amend-workitems` for an Epic or Feature tree. The original text stays in Original Description.
2. Check items already in their type's template with `validate-artifact`; enrich only what fails.
   Write new items with `generate-work-item`, then `enrich-work-item`. When the work started from a
   project file, that file's text is the draft and becomes the Original Description.
3. Split an Epic or Feature with `decompose-backlog`: approve the split (`refinement-split`), then
   the item bodies (`publish-items`); the items are created, read back and audited for coverage.
   Split an oversized Story with `split-story`.
4. For each Story, `generate-breakdown-work-items` saves its implementation plan and has it shown
   and approved with `implementation-confirm`, as that skill's section 2 describes; approving it
   pins the plan. The Story must pass `validate-artifact` first: the plan is written from its
   refined acceptance criteria. Then propose the Story's Tasks, with Staging, Review and Breakdown,
   and create them after their own `publish-items` approval.

Every item is written first as a draft ticket in `Tickets/Ready/` (the toolkit's ticket format;
no `provider_id`). Show the drafts with `harness workflow show --artifact <draft>`, then ask
`publish-items` with the same `--artifact` files. The gateway writes an item's description only
when it is an approved draft's body, word for word; with the local tracker, creating the item turns
its draft into the tracked ticket. Every tracker write is read back. Nothing is approved in bulk:
each item, plan and document is shown and approved when it is created.

Planning files are not code. When the project sets no source globs, every file counts as code except
documents and data in the planning folder (`.md`, `.json`, `.jsonl`, `.yaml`, `.yml`, `.csv`,
`.txt`), so refinement can write outlines and hour sheets before any Story is linked; a script there
still counts as code. A project that keeps files its application reads in the planning folder should
set source globs, which then decide what is code.

## Preparation

Write the risk and verification documents with `generate-plain-language-documentation`, as notes in
the artifacts path that name their Story (`story: <key>`). For each one, when it is complete: set
`status: approved`, show it with `harness workflow show --artifact <document>` and put the output
in your reply, then ask `harness decision present --gate approve-document --artifact <document>`. Approving pins its exact content; editing it afterwards needs a new approval. With a
remote tracker, then publish it to its Story with `tracker_publish_artifact` so the team sees it
where the work item lives. Build the reading manifest over the approved plans and documents so later
stages load only what they need; the manifest is harness state, not a document to approve. Keep
source decisions in the memlog.

## Execution

Close onboarding and begin work from the approved plan. Detect versioning automatically now; its
presence or absence never blocks local implementation. Branches, commits, pushes, and pull requests
are optional delivery choices; never create or require them as a prerequisite to edit and verify
locally. Code changes start when `harness workflow requirements` reports `ready` for the work
session: it is linked to the Story or Bug (`harness work-session link --work-item <key>`), the
tracker holds that item in progress with its Tasks parented to it, and its implementation plan was
approved and has not changed since. The requirements come from `config/prepared-workflows.json`; a missing one
names the stage and skill that produce it. Preserve pre-existing files, isolate effects and
verify the edge-case matrix against tests actually run. Use Thermos for code review and BMAD
verification/claims checks where relevant. External delivery and merging remain separate,
context-bound actions.

## Interaction and recovery

Stage choices through the decision catalog and attempt native controls first. Preserve the same
question, artifact bindings and choices on failure: blocking native → async native → chat menu.
Do not invent an answer or demand exact wording for an understood preference. A failed transport
does not stop unrelated work. Progress saving remains available while paused. Active-mode stop
enforcement rejects unstaged prose menus once, directing presentation through the supported path;
it never runs while suspended. Suspended capture is observation only and cannot veto a tool.
Lifecycle controls use `harness decision present --gate harness-controls` independently of a
pending work decision. Show them from the project's own workspace so a reply cannot affect a
different project. Repeat this gate with async or chat capability flags on delivery failure;
do not fall back to an unrelated pending work question. Paused onboarding permits ending a turn.

Evidence of a run belongs in the project's reviewable result and artifacts: record actual decisions,
saved decision IDs/status, relevant command outcomes, artifact paths and digests, and limitations as
they occur. The host's complete conversation transcript is not a required project artifact. Leave
it in the host's original store; do not copy it wholesale into a repository or another workspace.
If transcript access or archival is unavailable or rejected, record that limitation in the result
and continue or pause according to the user's workflow choice. An archival failure alone must never
block progress, invalidate a captured decision, or trigger bypassing host security review. If the
project-local evidence write itself is unavailable, retain concise factual notes in the conversation
and report the evidence limitation; do not claim the record was saved.
