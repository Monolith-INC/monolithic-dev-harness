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

## Preparation

Assemble only relevant requirements, specification, risk analysis, architecture/UX companions and
verification requirements. Create a manifest with each document's relative path, purpose, read
trigger, owning skill and current digest. Keep source decisions in the memlog. Readers use the
manifest to load relevant evidence rather than ingest everything. Draft tracker artifacts locally;
publish only under an existing authorization for that exact bundle, otherwise include publication
in the final confirmation. Persist the implementation plan locally unless the tracker explicitly
supports storing it. It references the manifest and every load-bearing companion.

## Confirmation

Show the complete implementation plan or faithful preview, artifact links, recorded decisions,
remaining limitations, and concrete tracker writes to be performed. Present the implementation-confirm
gate with all reviewed artifacts. One confirmation accepts this bundle and begins its specified
execution. This replaces separate preparation approvals; it does not authorize a future merge or
unrelated external writes. Revision returns to the affected stage; stopping preserves the bundle.
Recheck artifact digests before acting; a substantive change requires consultation.
Record this gate as the `confirmation` workflow stage before execution begins.
The user must be able to inspect the actual reviewed files through the best available host surface
before the gate. Tool success or an artifact link alone does not establish that the content was
visible. For an acceptance run that stops at execution entry, say explicitly that the recorded
approval ends at that boundary and does not authorize execution or tracker publication.

## Execution

Close onboarding and begin work from the approved plan. Detect versioning automatically now;
support projects without it. Preserve pre-existing files, isolate effects and verify the edge-case
matrix against tests actually run. Use Thermos for code review and BMAD verification/claims checks
where relevant. External delivery and merging remain separate, context-bound actions.

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
