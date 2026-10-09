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
