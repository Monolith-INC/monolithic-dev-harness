# Six-stage onboarding contract

This contract supersedes the old Discover → Backlog → Tech Plan preparation sequence.
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
`validate-artifact`; Tasks are a Story's breakdown into steps, not part of refinement:

1. Carry approach changes into items that already exist first: `enrich-work-item` for one item,
   `amend-workitems` for an Epic or Feature tree. The original text stays in Original Description.
2. Check items already in their type's template with `validate-artifact`; enrich only what fails.
   Write new items with `generate-work-item`, then `enrich-work-item`.
3. Split an Epic or Feature with `decompose-backlog`: approve the split (`refinement-split`), then
   the item bodies (`publish-items`); the items are created, read back and audited for coverage.
   Split an oversized Story with `split-story`.
4. For each Story, `generate-breakdown-work-items` saves its implementation plan with
   `status: approved`. Show it with `harness workflow show --artifact <plan>` and put the output in
   your reply, then ask `harness decision present --gate implementation-confirm --value
   story=<key> --artifact <plan>`. The harness refuses the question unless the note is that Story's
   plan, the Story exists in the tracker, and the plan was shown as it reads now (on Claude, in your
   own reply). Approving it pins the plan. Then propose the Story's Tasks, with Staging, Review and
   Breakdown, and create them after their own `publish-items` approval.

Every tracker write goes through the harness gateway and is read back. Nothing is approved in bulk:
each item, plan and document is shown and approved when it is created.

## Preparation

Write the risk and verification documents with `generate-plain-language-documentation`; show each
and approve it with `approve-document` before it is saved. Build the reading manifest over the
approved plans and documents so later stages load only what they need. Keep source decisions in the
memlog.

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
