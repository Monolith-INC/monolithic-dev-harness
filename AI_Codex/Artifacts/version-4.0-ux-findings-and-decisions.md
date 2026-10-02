# Harness v4.0 real test: UX findings and proposed decisions

Status: Revised after user critique and the agreed "Workflow Command Design" choices; proposed implementation scope, not authorization to change harness code.

Sources: `version-4.0-real-test.md` (route guard test transcript); current harness `harness`, `bootstrap`, `plan-initiative`, `planning-artifacts`, `write-spec`, and `generate-plain-language-documentation` instructions; and BMAD Method's `bmad`, `bmad-walkthrough`, brainstorming, forge, brief, PRD, architecture, UX, and spec skills. The transcript ends during Task 2. It does not record every native UI control or final delivery.

## Assessment

The largest defect is first contact. The harness can bootstrap a repository, but this test did not turn an unready repository into a guided setup flow. It assumed Azure DevOps, let planning proceed with placeholder tracker settings, then asked the user to edit configuration manually after they chose Linear. The remaining flow protected consequential writes but overused confirmation, presented approvals inconsistently, and did not reliably show full artifacts before asking the user to decide.

The transcript contains 30 user follow-up messages after the initial request: eight `proceed` replies, five approval-code replies, and one failed plain `approve` reply. These counts describe this test, not a target for every harness run.

## Prioritized findings and proposed decisions

### P0 — Guided first-run bootstrap before workflow routing

**Finding.** The test agent read `.harness/settings.json` early, but did not ask which tracker to use until the Azure placeholders blocked publication. After the user chose Linear, it gave them JSON to edit manually and waited for `ready` (`version-4.0-real-test.md`, lines 408–472). The current harness entrypoint says to run bootstrap if settings are missing, and the bootstrap skill can create a settings file, but that is not a complete first-activation dialogue. Its CLI will not replace an existing settings file. Thus the product has bootstrap machinery but lacks a reliable assisted path for both an absent configuration and an existing placeholder or incomplete one.

**Decision.** On first invocation, run a setup preflight before Stage 0 or backlog work. Distinguish: ready repository; no opt-in/configuration; and existing but incomplete or conflicting configuration. If the user has no harness language preference, offer **English** and **Português (Brasil)** and save the choice in user-level state outside the repository. Then ask which tracker to use rather than assuming Azure. Derive safe repository facts automatically; ask only for missing tracker, SCM, artifact, and host options that cannot be inferred. Show the resulting configuration and its destination for review, apply it through a defined idempotent bootstrap/update path that preserves unrelated user-owned settings, verify with doctor and a narrow tracker capability check, then resume the original request. If a host trust or authentication step genuinely requires the human, explain that one step and resume automatically afterward. A project or workflow language override can be designed later as an explicit exception.

### P0 — One interaction contract across choices, approvals, and fallbacks

**Finding.** The Linear publication prompt displayed **Approve** and **Not now**, but a plain `approve` reply did not open the write window; the agent then requested `approve HB-LIN7Q2` (`version-4.0-real-test.md`, lines 503–527). The user had to discover the real input after failure. Later writes used other approval codes (lines 688–692, 915–925, 1278–1282, 1475–1485).

**Decision.** Define the choice once, then render it through a host capability ladder: native structured option or boolean controls when available; otherwise a clearly numbered text choice with the same labels, order, default, and consequences. Approval controls must open the approval window they claim to open. If a typed token is the only supported approval path, display its exact syntax in the first prompt and do not advertise nonfunctional buttons. Apply the same contract to bootstrap, planning route, artifact review, and write approval. A fallback changes presentation, never the decision's meaning.

### P0 — Plain language is part of the interaction contract

**Finding.** Routine messages in the test used process terms and untranslated language shifts, even when the user needed a simple description of what would happen next (for example, lines 325–327, 1029–1040, 1203, 1275). The `generate-plain-language-documentation` skill provides a completeness check, a jargon pass, and glossary-backed English/pt-BR wording for human-facing prose.

**Decision.** Apply that skill's writing rules to every user-facing question, choice label, status summary, and artifact review. Explain the consequence of a choice in the selected language, and keep internal names in the audit record. Build this as a reusable prose pass inside the workflow; do not run the skill's full standalone intake and approval gate for every message, because that would create the interruptions this redesign is intended to remove. Use its pt-BR glossary check when Portuguese is selected.

### P0 — Back navigation and durable workflow pause/resume

**Finding.** The user could ask to revisit one earlier stream question (lines 92–101), but the test offered no consistent Back control across the multi-step flow. Existing `harness session pause/resume` changes the state of an implementation session tied to a checkout; it does not save the first-run, discovery, artifact-review, or backlog position or list earlier review points.

**Decision.** `back`, `pause`, `resume`, and `cancel` are the canonical workflow actions. Show native controls where available and use textual commands as fallback. Expose them through a separate `harness workflow` CLI namespace, so the user can act from chat or a terminal without confusing them with implementation-session or tracker-enforcement commands. Pause saves the current stage, accepted decisions, artifact revisions, unresolved questions, completed external writes, and the next safe action. Resume defaults to the latest saved review point and can also show a short list of earlier saved points for the user to choose. Back shows which later drafts or approvals become stale and re-derives only affected work. Cancel ends the active workflow without implying automatic continuation; completed work and the audit record remain intact. Resume rechecks repository and tracker state and never blindly repeats an external write.

The first-activation checkpoint needs a durable location before `.harness/settings.json` exists. Its exact storage path is an implementation decision; it must be private to the user, recoverable after a restart, and absent from commits by default.

### P0 — A predetermined storyboard with meaningful breakpoints and visible artifacts

**Finding.** The test used repeated `proceed` requests for local drafting and revisions (lines 138–143, 230–232, 302–304, 348–350, 404–406). The technical specification gate showed only a link and short summary before approval (lines 1260–1282); the transcript does not show the complete spec, a faithful section preview, or an open document pane. Current `write-spec` instructions require a complete presentation. The user may have independently opened the linked file, which this record cannot establish.

**Decision.** Give the agent a defined stage storyboard, entry/exit checks, artifact owners, scripts for deterministic checks, and a small set of pause reasons. Within a stage, continue through reversible drafting and validation without asking for a new `proceed` each time. Pause for unresolved product choices, an actual policy-required write, or a final review of a material contract. Before a review gate, present the exact artifact and revision through the best surface the host supports: interactive canvas/document/editor, native rendered preview, opened file with structured summary, or faithful inline review. A bare path or summary is insufficient. The user's approval should pin what was visibly reviewed. The harness defines review intent; host adapters choose presentation.

### P0 — Rebuild Stage 0 around substantive BMAD-style discovery

**Finding.** Stage 0 in this test quickly narrowed the idea to a series of small binary behavior questions, produced a spec, and moved on (lines 60–173). It did clarify important stream behavior, but it did not show a broader product or architecture inquiry, alternatives, assumptions, failure modes, or a deliberate planning-depth choice. The current `plan-initiative` skill lists useful routes, but this run mostly took the shortest path without showing why that depth was enough.

**Decision.** Read the user's description and brownfield repository first, then establish the goal, stakes, and unknowns. Offer a coaching path for exploration and a fast path that marks assumptions for review. Route by the actual gap: brainstorming to widen options, forging to challenge a held idea, research when current evidence matters, brief/PRD for product intent, UX for interaction contracts, and architecture for shared technical invariants. Do not run every skill as a waterfall. In the coaching path, ask open questions that expose load-bearing assumptions rather than a long quiz of obvious binaries. Before the final Stage 0 decision, run an adversarial critique of the user's idea: name the strongest counterargument, hidden assumptions, likely failure cases, and a simpler alternative; allow the user to defend, revise, or abandon the idea. Record the result and remaining uncertainty. The critique should challenge the idea rather than add a ceremonial approval. End Stage 0 only when the product contract and any needed UX/architecture companions make the backlog scope defensible; show the contract and critique together at one clear review point.

### P1 — Finish backlog prerequisites before starting a Story

**Finding.** The agent moved `AGE-58` to In Progress, created its branch, and opened its session before discovering that the Implementation Plan and Tasks were still needed (lines 915–1027). It then paused technical specification work to run a second intake and breakdown sequence (lines 1029–1230). The current harness flow places breakdown before `start-ticket`.

**Decision.** Complete the Story breakdown and its meaningful review gates before changing tracker state or opening the implementation session. Present one clear transition from approved backlog to technical plan.

### P1 — Keep Linear work visible in Linear, or explain a local-only boundary

**Finding.** After the user chose Linear, the breakdown intake set `destination: filesystem` (lines 1029–1040). Six Tasks were then saved locally, while the Story lived in Linear; the agent said no hours were sent to the tracker (lines 1203–1230). The user was not told in plain language that these Tasks would be absent from the Linear Story.

**Decision.** At breakdown, state explicitly where Tasks will appear and how progress will be tracked. The preferred end state is one coherent Linear hierarchy for a Linear-backed Story. If local-only Tasks are required, present that consequence as a choice before creation. Prepare the Linear adapter for its actual issue kinds and labels before the Story starts.

### P1 — Check tracker readiness before opening a publication batch

**Finding.** Placeholder Azure DevOps settings surfaced only after local backlog approval (lines 408–421), prompting a tracker switch. In Linear, the Feature was created before the first Story failed because the required `Story` label was missing (lines 620–692). The timeout recovery did correctly search before retrying and avoided an observed duplicate (lines 550–600).

**Decision.** Make tracker readiness part of bootstrap and recheck immediately before publication: selected provider, authentication, team/project, issue kinds and labels, parent-child mapping, and write permissions where these can be checked safely. Preserve the existing lookup-before-retry behavior for uncertain writes. Resolve missing prerequisites before creating any item in the batch where possible.

### P2 — Keep the conversation about the user's work

**Finding.** The user approved successive local artifacts and revisions with repeated `proceed` messages (lines 138–143, 230–232, 302–304, 348–350, 404–406). Routine updates used terms such as `provider_id`, Gate 1/2, normalized intake, `seed-default`, and Actor-Critic (for example, lines 325–327, 1029–1040, 1203, 1275). The initial request was in English; most responses were in Portuguese.

**Decision.** Keep gates that protect consequential writes or material decisions. Apply the selected language and the plain-language writing pass to the message before showing it. Keep technical IDs and detailed logs in artifacts for audit, with only actionable status in chat.

## Proposed end-to-end storyboard

1. **First activation:** inspect user language preference and repository state; ask English or Português (Brasil) only when the preference is unset, then the tracker and other missing setup choices; run assisted bootstrap only for missing or incomplete settings; verify readiness; resume the original request.
2. **Discovery:** read existing inputs and code; calibrate stakes; choose coaching or fast path; use the smallest BMAD-inspired set of discovery tools that resolves real uncertainty; challenge the resulting idea before closure.
3. **Product decision:** display the complete product contract, critique, and any load-bearing UX/architecture companions. Ask for one informed decision to begin backlog work.
4. **Backlog:** draft, enrich, validate, and break down locally; display the final Feature/Story/Task batch; preflight the selected tracker; obtain one clearly scoped publication approval; publish and verify.
5. **Story start and technical plan:** start a ready Story; draft and validate the technical spec; display its exact revision in a review surface; obtain Gate 2 approval.
6. **Build and verify:** implement in atomic Tasks, report test evidence, and pause only at consequential write/review points required by policy. Keep the user oriented to the current outcome rather than internal machinery.

At every stage, preserve a resumable review point. Offer Back where earlier choices can be revised, Pause and Resume for continuation, and Cancel to end the active workflow. The agent should work between these points without repeatedly asking for trivial confirmation.

## BMAD reference interpretation

- `bmad` provides a setup/check/fix/question model. Its structure supports assisted first-run initialization, but the harness must remain self-contained and own its own settings contract.
- `bmad-walkthrough` is specifically a human review of a commit, PR, file, or directory. Its reusable ideas are prewritten blocks, one concern at a time, a visible narrative, and an unobtrusive log. Its per-block human stop should not be copied into every harness step; it is not itself a full delivery storyboard.
- BMAD brainstorming, forge, brief, PRD, architecture, UX, and spec skills show how to scale discovery to uncertainty and stakes. Their coaching/fast-path distinction, brownfield source reading, assumption marking, and durable decision memory are the relevant Stage 0 patterns. The harness should adapt these patterns instead of relying on BMAD at runtime.
- BMAD Forge Idea's attack/defend moves are a direct reference for the adversarial critique at the end of discovery. The review must remain specific to the user's idea and evidence, with a path to revise or reject it.

The harness's [plain-language documentation skill](/home/bhave/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.4.0/skills/generate-plain-language-documentation/SKILL.md) is the reference for user-facing wording. Its glossary and completeness checks should run as an embedded quality pass, with no new user approval for routine prose.

Reference files consulted: [BMAD setup](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad/references/setup.md), [BMAD walkthrough](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-walkthrough/workflow.md), [BMAD brainstorming](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-brainstorming/SKILL.md), [BMAD forge](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-forge-idea/SKILL.md), [BMAD brief](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-product-brief/SKILL.md), [BMAD PRD](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-prd/SKILL.md), [BMAD architecture](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-architecture/SKILL.md), [BMAD UX](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-ux/SKILL.md), and [BMAD spec](/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-spec/SKILL.md).

## Review scenarios for the proposed UX

- Fresh repository: the first harness request enters guided setup, asks the tracker choice through the best available structured UI, writes a reviewed configuration, verifies it, and returns to the original request without manual JSON editing.
- Language choice: when user-level preference is unset, the first setup offers English and Português (Brasil); later questions, artifact summaries, and choice consequences follow that preference across repositories, and the choice can be changed.
- Existing incomplete settings: onboarding diagnoses only missing/conflicting values and preserves all unrelated human-owned configuration.
- Host without native buttons: numbered choices retain the same semantics; an approval never advertises a control that cannot authorize the write.
- Navigation: Back revises a prior choice and identifies affected later work; Pause records a safe review point; Resume offers the latest point or a list of saved points and does not repeat completed external writes; Cancel ends the active workflow without losing the audit record.
- Linear publication: missing labels or kind mapping are caught before the first item is created, and the final Story/Task location is explained.
- Stage 0: a nontrivial idea receives substantive exploration, a specific adversarial challenge, and a reviewable contract; a clear, small idea takes a shorter path with its assumptions visible.
- Review gate: the exact artifact is displayed before approval, and routine local drafting does not generate a chain of `proceed` prompts.

## What the test supports—and what it does not

- Supported: the agent clarified behavior, accepted a correction to an earlier question, handled a provider timeout cautiously, verified Linear parent-child links, and reported focused tests and analyzer results for Task 1 (lines 92–125, 550–600, 793–819, 1465–1470).
- Not established: visual quality of native picker controls, whether the user opened linked files, correctness of later Tasks, completion of `AGE-58` or `AGE-59`, or the quality of the final feature. The transcript stops during Task 2 (lines 1499–1508).

## Discussion status

This record includes the user's bootstrap, interaction, storyboard, Stage 0, language, navigation, and pause/resume criticism. The user agreed in the referenced "Workflow Command Design" conversation that workflow controls are `back`/`pause`/`resume`/`cancel`, language is a user-level harness preference, and artifact review uses the best available host surface before a meaningful approval gate. These choices are reflected in the implementation plan; no harness code has been changed for them.
