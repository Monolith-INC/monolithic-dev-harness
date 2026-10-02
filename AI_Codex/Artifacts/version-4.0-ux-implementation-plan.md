# Harness UX implementation plan

Status: Approved for implementation by the user. The three interaction design choices are resolved from the user's agreement in "Workflow Command Design". Implementation changes remain uncommitted and do not include tracker or release changes.

This plan turns the findings in `version-4.0-ux-findings-and-decisions.md` into small changes that can be checked separately. The goal is a usable first encounter with the harness, followed by a clear path from idea to delivery with few interruptions and reviewable decisions.

Here, a **tracker** is the service that holds work items, such as Azure DevOps or Linear. An **artifact** is a document or work-item draft the user must review.

## Intended user experience

1. The first harness request checks whether the user has a language preference and whether the repository is ready. If the language is unset, it offers **English** and **Português (Brasil)** and saves the choice for that user across repositories. If repository setup is missing or incomplete, it asks which tracker to use and only the other choices it cannot discover. It shows the proposed settings before writing them, verifies the setup, and returns to the user's original request. The user does not edit JSON by hand.
2. Every choice has the same meaning across hosts. Native buttons are preferred; a numbered text choice preserves the options where buttons are unavailable. Approval text names the action that actually authorizes the write.
3. The user can go Back in a multi-step flow, Pause at any point, Resume from the latest saved review point or choose an earlier one, and Cancel the workflow. Resuming checks current repository and tracker state and does not repeat a completed external write. These are workflow actions presented as native controls where possible; text commands are the fallback.
4. Planning reads the existing project, explores the idea to the depth it warrants, and challenges its assumptions before the user approves a product contract. A short, clear idea can take a fast path; a consequential or unclear idea gets deeper coaching.
5. The agent drafts and checks reversible work without repeated `proceed` prompts. At a real decision point, it presents the exact artifact through the best available review surface: an interactive canvas/document/editor, a native rendered preview, an opened file with a structured summary, or a faithful inline review. A file link or summary alone does not count as presentation. The approval is bound to the revision the user saw.
6. A Linear-backed project publishes its work in a coherent Linear hierarchy, or tells the user plainly before creation that some Tasks will remain local.

## Constraints to preserve

- Repository settings and approval records remain human-owned. A reviewed setup operation may change only the fields the user chose and must preserve unrelated settings. Existing explicit host settings, including a disabled Codex picker, are not silently overridden.
- Tracker and source-control writes still require a clearly scoped user approval. Local drafts and routine checks do not create new approval gates.
- The harness remains self-contained. BMAD Method is a design reference, not a runtime dependency.
- The current `harness session pause/resume` controls an implementation checkout. Workflow pause/resume must have a separate state and command so neither action silently changes the other.
- Preferred language belongs to the user-level harness installation outside the repository. The workflow records the effective language for recovery; an explicit project or workflow override can be designed later.
- Checkpoint files contain no credentials. Existing approval windows are not reused after a workflow resumes or an approved artifact changes.

## Build order

Each unit ends with a passing check before the next begins. The files below identify likely ownership; the implementation can use the existing module boundaries where inspection shows a better fit.

### 1. Define the workflow contract and acceptance fixtures

Write one source-of-truth storyboard under `plugins/monolithic-dev-harness/references/`, then update `skills/harness/SKILL.md` to follow it. Define the stages, required inputs, artifact owners, review points, conditions for stopping, and which external writes need approval. Define `back`, `pause`, `resume`, and `cancel` as canonical workflow actions, with their state effects and host controls. Use the real route-guard transcript as a regression fixture without making it a runtime dependency.

**Check:** A reviewer can trace a fresh repository from first request to verified setup and return to the original task; no stage begins before its inputs exist. Skill and manifest/link checks pass.

### 2. Add durable workflow state and navigation

Add a versioned workflow record under the existing ignored `.harness/state/` area. Reuse the atomic state writer in `scripts/harness/state.py`; add a focused module for pure state transitions rather than putting planning state into implementation sessions. Record the current stage, a short list of saved review points, effective language, decisions, artifact paths and digests, pending questions, completed external-write identities, and the next safe action. Ensure `.harness/state/` is excluded from Git before writing a first-run record, even when settings do not yet exist. Store the user language preference separately in user-scoped harness state outside the checkout.

Expose the four actions through `scripts/harness/cli.py` under a distinct `harness workflow` namespace, while native host controls invoke the same transitions. Resume defaults to the latest point and can list earlier points. Back shows the effect of revising a choice, marks dependent drafts and approvals stale, and rebuilds only the affected work. Cancel ends the active workflow without promising automatic continuation; keep its audit record and completed work intact. A saved record is data, not permission to perform an external write.

**Check:** Unit tests cover pause before bootstrap, restart and resume, selection of an earlier point, Back invalidation, Cancel, changed files, expired approvals, stale artifact digests, malformed state, and no duplicate tracker write after an interrupted response. A preference set in one repository is available in another without writing either repository's settings.

### 3. Build one host-aware choice and approval layer

Extend the existing `scripts/harness/questions.py` and hook integration rather than adding a second approval system. Define each choice once with stable option IDs, labels, consequences, effective language, and whether it authorizes a write. The harness owns interaction intent; a host adapter renders it for Claude's question UI, Codex's structured picker when exposed and trusted, or the best supported text fallback. Offer Back, Pause, Resume, and Cancel controls where each action applies; keep write approval distinct from ordinary routing choices.

Use `generate-plain-language-documentation` as an embedded prose check for labels, prompts, status updates, and artifact summaries. It must not run its standalone intake or persistence gate for each message. Apply the bundled glossary to Portuguese text. Typed approvals remain available only when needed and must show the exact accepted syntax before the user responds.

**Check:** Contract tests run the same choices through each host and fallback; option order, consequence, language, and answer meaning agree. A plain approval never appears to work when only a code works. Hook tests prove only a real user answer opens a write window, including Codex's ID-keyed answer shape.

### 4. Implement assisted first-run setup

Extend `scripts/harness/bootstrap.py`, `scripts/harness/settings.py`, and the bootstrap skill with inspect, propose, review, apply, and verify steps. The flow must work before `.harness/settings.json` and project hooks exist. Resolve the current mismatch between the bootstrap skill's implied default and the CLI's required `--settings-from` input; the assisted path must provide a candidate without assuming the Azure example. Ask for language only when the user-level preference is absent, save it outside the repository, then offer shipped trackers. Read each tracker's declared required values and ask only for missing ones; discover safe Git and source-control facts where possible. The agent prepares the candidate settings for review and applies them through the controlled bootstrap path, not by telling the user to edit JSON.

Handle three cases separately: no settings, valid existing settings, and existing settings with placeholders or missing values. Preserve all unrelated existing fields and an explicit `false` for the Codex picker. Do not use the bundled Azure example as an implicit selection. Run doctor and a narrow tracker check, explain any human authentication or trust action, then continue the original request.

**Check:** `tests/harness/test_bootstrap.py` and `test_settings.py` cover fresh Git repositories, Azure and Linear choices, existing placeholder settings, existing custom settings, repeated setup, explicit host conflicts, and safe failure without half-written settings. A scripted first-run test reaches the original task without a manual settings edit.

### 5. Strengthen Stage 0 and its final critique

Update `skills/plan-initiative`, `brainstorm-ideas`, `forge-idea`, `product-brief`, `product-requirements`, `experience-design`, `architecture-spine`, `product-spec`, and `references/planning-artifacts.md` as needed. Start from the user's goal and existing repository evidence. Offer coaching or fast drafting with assumptions marked. Route to the smallest set of planning skills that resolves actual uncertainty, preserving BMAD's depth without forcing every skill into every run.

Before the Stage 0 review, produce an adversarial critique tied to the idea: the strongest counterargument, unsupported assumptions, failure cases, and a simpler alternative. Let the user defend, revise, or abandon the idea; keep reversals and unresolved questions in the existing decision log. Display the product contract and critique together. Do not turn the critique into a generic extra confirmation.

**Check:** Scenario tests cover a small well-defined feature and an uncertain cross-team idea. The latter must show substantive challenge and a revised or explicitly retained contract; both must avoid a chain of trivial binary questions.

### 6. Make artifact review and gates reviewable

Update the harness stage instructions and `skills/write-spec/SKILL.md` to require a visible, exact revision before asking for approval. Implement a host review ladder: interactive artifact surface when available, native rendered preview, opened file with structured summary, then faithful inline review. The chosen surface must actually present the material needed for the decision; a path plus summary is insufficient if the file was not opened. Record the artifact digest and presentation evidence at the decision point. Combine reversible draft/enrich/validate actions within the stage; stop at a material product decision or a write that needs permission.

**Check:** A gate test fails when only a path or short summary is presented, or when the selected host surface did not actually open/render the artifact. A changed artifact invalidates the prior approval. The route-guard scenario reaches the final backlog and technical-spec decisions without repeated approval for each local draft.

### 7. Prepare selected trackers and keep Tasks visible

Add read-only readiness checks to the tracker integration before publication: selected provider, required values, authentication, team, supported hierarchy, needed Linear labels, and available write operations. Make missing setup visible before creating the first item. Where a required label needs creation, include it in the reviewed publication batch and create it before dependent items. Retain lookup-before-retry after an uncertain provider response.

Remove Azure-only destination assumptions from `skills/generate-breakdown-work-items` and its references. Use the active tracker contract for Task persistence and read-back checks. If a provider cannot represent the Tasks, show the local-only consequence and obtain that choice before creating them. Complete breakdown before `start-ticket` moves the Story into progress.

**Check:** Linear contract tests cover missing `Story` and `Task` labels, parent-child links, partial publication recovery, and Task visibility. A scenario with a missing label stops before Feature creation. The Story remains in Backlog until its required plan and Tasks are ready.

### 8. Run integrated host trials and release checks

Run focused tests after each unit, then the full repository suite, lint, format check, manifest/link checks, and version checks. Exercise fresh and partially configured repositories in Codex, Claude, and a host with only text choices. Repeat the route-guard scenario with both English and Portuguese, a mid-flow Pause/Resume, a Back revision, an interrupted Linear write, and artifact review in a real pane or full fallback view. Inspect the resulting state and tracker records rather than relying on agent narration.

**Check:** The first run finishes setup and returns to the original request; no unapproved write occurs; no external write is replayed; the selected language remains consistent; and every approval follows a visible decision. Record any host limitation with the fallback actually used.

## Delivery sequence and review points

Deliver the state and interaction foundation first, then assisted setup, Stage 0, review surfaces, and tracker flow. A reviewer should be able to inspect a working scenario after each unit rather than a single large final change. Do not publish a release until the integrated host trials pass. No tracker item, branch, commit, pull request, or release is part of preparing this plan.

## Resolved interaction decisions

- `back`, `pause`, `resume`, and `cancel` are canonical workflow actions. Host-native controls present them when available; textual commands are the fallback. CLI commands use the `harness workflow` namespace so they remain distinct from implementation-session and tracker-enforcement commands.
- Preferred language is user-scoped bootstrap state outside the repository, initially English or Português (Brasil). Future project or workflow overrides require an explicit design and do not change this default.
- Artifact review uses the best available host surface. A meaningful decision gate cannot ask for approval until that surface has actually presented the material needed for the decision. The harness defines the interaction and state transition; the host adapter determines its presentation.
