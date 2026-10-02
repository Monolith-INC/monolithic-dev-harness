# Harness workflow storyboard

The harness owns the sequence and the meaning of each decision. Host adapters choose how to show a question or document. A first request resumes after setup instead of making the user repeat it.

| Stage | Entry | Work before stopping | Review point | Exit |
| --- | --- | --- | --- | --- |
| Setup | Any harness request | Check user language preference, repository settings, host controls, and selected tracker; ask only for missing values; prepare a candidate | Show the exact settings changes before writing; explain required trust or sign-in | Settings and tracker are usable, then return to the original request |
| Discover | Assigned ticket or draft feature request without a reviewed technical plan; optional product idea when explicitly requested | For feature work, read the request and repository, investigate fit and alternatives, and prepare a reviewed implementation plan. For optional product ideation, use the product-discovery route. | Show the full technical plan or product contract and its review notes | Accepted technical plan is checkpointed for backlog drafting, or accepted product contract enters backlog |
| Backlog | Accepted product contract or sufficiently defined work item | Draft, enrich, decompose, create Story Tasks, and validate locally; check tracker readiness before publication | Show the complete Feature, Story, and Task batch and its destination; seek one approval for the specified external writes | Publish and read back the approved batch |
| Technical plan | A ready Story and its Tasks | Start the Story, draft and validate its Story-local technical spec | Present the exact spec revision, then seek the technical decision | Approved spec is pinned to its revision |
| Build | Approved spec and active implementation session | Work through atomic Tasks and checks | Stop only for a material decision or protected write | Verified implementation and evidence |
| Verify | Checked implementation | Review requirements, quality, and delivery evidence | Present verdict and any required staging or pull-request decision | Draft pull request or a clearly blocked result, then mark the workflow complete |

An agent continues through reversible local work within a stage. It stops for missing information that cannot be inferred, a material product choice, a review of a complete contract, or a write that policy protects. A `proceed` prompt for routine drafting is not a gate. Story breakdown precedes changing the Story to In Progress.

## Workflow actions

- **Back:** return to the previous reversible decision or a chosen saved review point. Show which later drafts and approvals become stale; rebuild only those dependents. Never undo an external write silently.
- **Pause:** save the stage, review points, pending decision, artifact digests, completed external-write identities, and the next safe action. Stop work.
- **Resume:** offer the latest point or earlier saved points. Recheck files, repository state, tracker state, and approvals. A checkpoint is not permission to repeat a write.
- **Cancel:** end the active workflow without implying automatic continuation. Preserve completed work and the audit record. Starting a later workflow archives the cancelled record first.
- **Complete:** mark the requested outcome finished. Starting a later workflow archives the completed record first.

These are semantic actions. Prefer native host controls, then numbered text choices. Terminal commands use the separate `harness workflow` namespace; `harness session pause/resume` still controls only an implementation checkout.

`harness workflow list` shows saved review points and the current point. `harness workflow status` shows the full saved record. Resuming can choose any listed point.

## Review and approval

An artifact decision identifies the exact path and content digest. Present the material needed to decide through the best available host surface: interactive canvas/document/editor, native rendered preview, an actually opened file with a structured summary, then faithful inline review. A link or summary alone is insufficient. The user sees the material before the approval question. A changed digest invalidates the decision.

An external tracker or source-control write still needs the existing approval hook. State precisely what will be written. The host control must truly open the approval window; otherwise show the exact typed syntax at the outset. A routing choice, Back, Pause, Resume, Cancel, or Complete never opens a write window.

## Language and setup

Ask for English or Português (Brasil) only when the user-level harness preference is unset. Store that preference outside the repository; record the effective language in a workflow checkpoint for recovery. Repository settings hold tracker and project choices. Preserve unrelated user-owned settings and explicit host conflicts. Do not silently select the bundled Azure example. Check the selected tracker's required values and capabilities before any publication batch.
