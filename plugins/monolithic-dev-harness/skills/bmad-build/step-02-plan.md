# Step 2: Plan

## RULES

- No intermediate approvals.
- **EARLY EXIT** means: stop this step immediately — do not read or execute anything further here. Read and fully follow the target file instead. Return here ONLY if a later step explicitly says to loop back.

## INSTRUCTIONS

1. Draft resume check. If `{plan_file}` exists with `status: draft`, read it and capture the verbatim `<frozen-after-approval>...</frozen-after-approval>` block as `preserved_intent`. Otherwise `preserved_intent` is empty.
2. Investigate the codebase. When you can, send deep searches to subagents and wait for them in this turn. Tell them to return short summaries only, so this session does not fill up with their notes. Keep only what the work needs: the specific files, symbols or lines, what to reuse, and what not to change. Write that into the Code Map. Do not retell the investigation when implementation starts — the plan already has it.

   When the code or domain is unfamiliar enough that a few searches will not settle it, use the bundled `bmad-deep-recon` skill for a focused reconnaissance pass and fold its findings into the Code Map. Compare the project's agent instructions (the managed block in `AGENTS.md`, when present) and current-state documents against what the code actually does; record any contradiction in the plan as a finding, and recommend `bmad-project-context` (intent `refresh` or `record`) at Checkpoint 1.

   Do not ask the human during investigation. When something is unclear, look in the repository, planning artifacts, or history first. Keep looking until you know, or until those sources have nothing more to say. Leave any remaining choice for the next step.
{% if workflow.route == "oneshot" %}
3. Read `{{ rendered("plan-template.md") }}` fully and write `{plan_file}`.
   Set `route: 'oneshot'`, `route_source: 'pinned'`, and `status: 'in-progress'`, resolving `date` to the current system date.
   If `preserved_intent` is non-empty, use it as the frozen block.
   **EARLY EXIT** → `{{ rendered("step-oneshot.md") }}`.
{% elif workflow.route == "full" %}
3. Set `route: 'full'` and `route_source: 'pinned'`, then continue.
{% else %}
3. {{ workflow.route_selection }}

   For oneshot: read `{{ rendered("plan-template.md") }}` fully and write `{plan_file}`.
   Set `route: 'oneshot'`, `route_source: 'auto'`, and `status: 'in-progress'`, resolving `date` to the current system date.
   If `preserved_intent` is non-empty, use it as the frozen block.
   **EARLY EXIT** → `{{ rendered("step-oneshot.md") }}`.

   For full, set `route: 'full'` and `route_source: 'auto'`, then continue.
{% endif %}
{% if workflow.route != "oneshot" %}
4. Read `{{ rendered("plan-template.md") }}` fully. Fill it out from the intent and investigation, resolving the template's `date` field to the current system date. Put the investigation into `## Code Map`: paths, symbols or lines, what to reuse, and what not to change. Implementation should work from the plan without being told the investigation again. If there are intent gaps, add a `## Open Questions` section with one entry per gap: the choice, the options, and what each option means. Never write an intent gap into the frozen block as an assumption. If `preserved_intent` is non-empty, replace the `<frozen-after-approval>` block with it before writing. Write the result to `{plan_file}`.
5. Self-review against READY FOR DEVELOPMENT standard. For anything important that's missing: if the repository can tell you, go look and fix the plan; if a human has to decide, add an `## Open Questions` entry. Do not invent the answer.
6. Resolve the gates before the checkpoint. Two things must be settled, in whatever order the conversation makes natural; combine them in one message when both apply.
   - **Plan length** (see SCOPE STANDARD). Measure and report length as advisory. Edit repetition and irrelevant detail while preserving requirements and evidence. Length alone never creates a decision gate and never justifies splitting a cohesive goal.
   - **Open Questions.** Present every entry together in one message, as a numbered question with its options, what each option means in practice (the trade-off, not just the label), and your recommendation with a one-line reason. Never ask them one at a time. HALT for the human's answers. Accept answers in any form — `1b`, an option name, a paraphrase, or "your recommendations" for all of them — and ask again only about an answer you genuinely cannot place. Write each answer into the `<frozen-after-approval>` block as a decision, log it to the memlog, and delete the entry. An answer may expose a new intent gap — add it and ask again, batched the same way. When the last entry is gone, delete the section.
   - **Scope after answers.** Answers can turn one goal into several (for example, a new platform target or an independent subsystem). Once Open Questions is empty, run the SCOPE STANDARD multi-goal check again against the decided plan and measure its token count honestly. Length is advisory. Offer **Split** or **Keep full plan** only when investigation identifies independently shippable goals; name each goal, explain the boundary, recommend which to build first and record deferred work. Do not offer an option that would merely discard acceptance checks. Log the outcome to the memlog either way.

### CHECKPOINT 1

Only when Open Questions is empty.

Present summary. Display the plan file path in whatever form is clickable where you are presenting it (e.g. code citation in chat, CWD-relative path with no leading `/` in terminal). If unsure, use CWD-relative path.

Report the advisory length once; do not ask the user to approve a token estimate.

The summary closes the series of decisions: list every decision recorded in this run (from the memlog), so the user can change any of them here instead of re-approving each one. Never re-ask a decision that is already recorded unless the user reopens it.

HALT and give the user a choice: the `plan-checkpoint` gate, `harness decision present --gate plan-checkpoint --artifact {plan_file}`, adding `--recommended deepen` when the plan spans several platforms or subsystems, carries security or data-loss risk, or the user kept the full plan past the scope check. Its options, worded in the project's language by the harness, mean:

1. **Approve and continue** — approve the plan, leave it `ready-for-dev`, and hand it to the harness backlog stage for work-item drafting. This approval does not publish tracker items or authorize implementation.
2. **Deepen** — challenge the plan before approving it.
3. **Approve and stop** — approve the plan, leave it `ready-for-dev`, and stop before backlog drafting.

Any other reply is a revision: apply what the user asked for, then return to this checkpoint. When the command returns `already_answered`, the plan has not changed since the user chose; act on that choice.

**Deepen** runs, in order, returning to this checkpoint when done:

1. **Adversarial review.** Invoke the bundled `bmad-review` skill on `{plan_file}` with lenses `adversarial` and `edge-case-hunter` (as `skill:bmad-review lenses=adversarial,edge-case-hunter`), passing the memlog as `also_consider`. Its lenses run as parallel subagents when available. Present the triaged findings and the plan changes they imply, then HALT for **Apply**, **Reject**, or other direction per finding group. Change the plan only for what the user accepts, and log each outcome to the memlog.
2. **Elicitation.** Invoke the bundled `bmad-advanced-elicitation` skill on the revised plan. Its own menu lets the user run methods or **Proceed**.
3. **Party mode** (offered, not automatic). When decisions remain contested, offer the bundled `bmad-party-mode` skill for a round-table on them.

After Deepen, present the checkpoint again with an updated summary of what changed.

Before acting on approval, re-read `{plan_file}` from disk. If it is missing, HALT without recreating it, changing status, or proceeding. If it changed, acknowledge the external edits and continue with the updated version. Set status `ready-for-dev`; everything inside `<frozen-after-approval>` is then locked and only the human can change it. Log the approval to the memlog. For **Approve and continue**, record this plan as the accepted discovery artifact in the harness workflow checkpoint, then hand it to the harness backlog stage. Do not follow BMad Step 3 or start implementation.

## NEXT

For this harness Stage 0 integration, the workflow ends here. If the user chose **Approve and
continue**, continue with the harness backlog stage using `{plan_file}` as an input. Do not read or
follow BMad's implementation, review, or presentation steps; the harness owns those later stages.
{% endif %}
