# Step 2: Plan

## RULES

- No intermediate approvals.
- **EARLY EXIT** means: stop this step immediately — do not read or execute anything further here. Read and fully follow the target file instead. Return here ONLY if a later step explicitly says to loop back.

## INSTRUCTIONS

1. Draft resume check. If `{plan_file}` exists with `status: draft`, read it and capture the verbatim `<frozen-after-approval>...</frozen-after-approval>` block as `preserved_intent`. Otherwise `preserved_intent` is empty.
2. Investigate the codebase. When you can, send deep searches to subagents and wait for them in this turn. Tell them to return short summaries only, so this session does not fill up with their notes. Keep only what the work needs: the specific files, symbols or lines, what to reuse, and what not to change. Write that into the Code Map. Do not retell the investigation when implementation starts — the plan already has it.

   When the code or domain is unfamiliar enough that a few searches will not settle it, use the bundled `bmad-deep-recon` skill for a focused reconnaissance pass and fold its findings into the Code Map. Compare the project's agent instructions (the managed block in `AGENTS.md`, when present) and current-state documents against what the code actually does; record any contradiction in the plan as a finding, and recommend `bmad-project-context` (intent `refresh` or `record`) during preparation.

   Do not ask the human during investigation. When something is unclear, look in the repository, planning artifacts first. Keep looking until you know, or until those sources have nothing more to say. Leave any remaining choice for the next step.

### Planning depth — after discovery, before drafting

Persist the discovery digest and Code Map first. Reuse a depth already selected for this work;
otherwise present `harness decision present --gate planning-depth`. This is a working preference,
not approval to implement. Explain the recommendation using the discovered risks and ticket.

- **Light:** draft from discovery, self-review, and focused checks for consequential gaps.
- **Standard:** contextual methods plus implementation risks, edge cases, dependency choices,
  codebase conflicts and known pitfalls; reconcile requirements before finalizing.
- **Hardcore:** Standard plus adversarial reviewers, assumption and security audits where relevant,
  source-preservation and verification-gap checks; interview only for unresolved consequential gaps.

For Standard or Hardcore present `harness decision present --gate planning-methods`:
contextual shortlist, full catalog, or agent recommendations. Use `bmad-advanced-elicitation`:
select categories from discovery and hand-pick five complementary methods with reasons. Follow its
paginated decision protocol: no more than three options per native decision, preserve ordered
multi-selection, and retain Reshuffle, full-catalog browsing, recommendation review, and Proceed.
Never replace these controls with a prose menu. Agent recommendations present a proposed selection
for the user to choose or revise; never silently run every method. Run chosen methods on the
discovered approach before writing the plan. Save accepted decisions incrementally and return here
when complete.
Native controls come first; delivery/capture failure uses the same decision's supported fallback,
then a faithful chat menu. Neither failed delivery nor dismissal is an answer. Suspension does
not remove the preference for native controls. Never require a session to communicate.
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
4. Read `{{ rendered("plan-template.md") }}` fully and create a **planning approach draft**, not the final implementation plan. Save it as `approach-<slug>.md` beside `{plan_file}`, with `type: planning-approach` and `status: draft`. Include the Code Map, proposed approach, scope, constraints, provisional tasks and unresolved choices. If `preserved_intent` is non-empty, retain its frozen intent. Do not mark it approved or present it as the execution contract.
5. Self-review the approach against READY FOR DEVELOPMENT. For anything important that's missing: if the repository can tell you, go look and fix the approach; if a human has to decide, add an `## Open Questions` entry. Do not invent the answer.
6. Resolve the gates before the checkpoint, combining the following in one message when both apply. **Plan length** (see SCOPE STANDARD) is advisory: measure once after drafting, and again only after a material plan edit. Edit repetition and irrelevant detail while preserving requirements and evidence. Length alone never creates a decision gate or justifies splitting a cohesive goal.

   **Open Questions:** show a concise overview of consequential unresolved choices, then stage one focused decision at a time using `harness decision present` with its question, options, explanations and recommendation. Attempt native controls and preserve the same choice through supported fallback. Accept an option name, number or understood paraphrase; ask again only when the answer genuinely cannot be placed. Independent work continues while a consequential choice is pending. Record genuine answers in the frozen intent and memlog, remove resolved entries, and revisit only new material gaps. Never replace staged controls with an unstaged prose menu.

   **Scope after answers:** answers can turn one goal into several (for example, a new platform target or an independent subsystem). Once Open Questions is empty, run the SCOPE STANDARD multi-goal check again against the decided plan. Offer **Split** or **Keep full plan** only when investigation identifies independently shippable goals; name each goal, explain the boundary, recommend which to build first and record deferred work. Do not offer an option that would merely discard acceptance checks. Log the outcome to the memlog either way.

### Hardening and preparation handoff

Once consequential Open Questions are settled, run the hardening selected by planning depth.
Light runs readiness self-review and focused edge checks. Standard adds contextual risk and
edge-case reviewers, input reconciliation and technical-choice checks. Hardcore adds adversarial,
assumption/security (when relevant), source-preservation and verification-gap reviews. Use the
bundled bmad-review and advanced elicitation methods; preserve reviewer findings and triage them.
The user decides substantive alternatives. Do not ask for implementation approval here.

If the user wants further exploration, use the same paginated native decision protocol for
contextual methods, Reshuffle, full-catalog browsing, agent recommendations and Proceed. Do not
reopen completed choices. Otherwise continue automatically to preparation; an optional extra
review is never required to finish. Record accepted changes once and reuse them.

Follow [the six-stage contract](../../references/six-stage-onboarding.md). In Preparation, in order:
(a) assemble requirements, specification, risk findings, architecture/UX companions and verification;
(b) refine/decompose and locally draft the full tracker hierarchy and required child Tasks, then
validate the batch against tracker capabilities; (c) create a manifest draft covering all companions
and tracker drafts; (d) write `{plan_file}` as the final implementation plan, resolving it only after
the tracker breakdown is known; (e) update the manifest with the final plan digest. The final plan
references the manifest path and all load-bearing companion/tracker artifacts. Do not start-ticket,
inspect Git, or create a branch during preparation. If an existing plan is missing, recover it from
real evidence or ask only for missing consequential input; never synthesize approval.

Present the complete bundle and all recorded decisions once. Use `harness decision present
--gate implementation-confirm --artifact <implementation-plan> --artifact <manifest>` and include
all reviewed companion and tracker-draft files. Explain concrete tracker writes and execution
scope. Native controls first, then supported async/chat fallback on delivery failure.

On Approve, re-read reviewed artifacts and validate digests; changed circumstances require
consultation. Treat this as the one durable approval for the unchanged bundle and its named local
execution actions. Record approval in workflow state; do not edit plan/manifest/decision artifacts,
change their status, add tracker records, or ask the same confirmation again after approval. If the
human requests a substantive revision or an external action was not included, consult only about
that changed scope. The approval detail must name the actual next action and honor any user-set boundary
(for example, an acceptance run that stops at execution entry). Close onboarding and hand the
unchanged approved bundle to harness execution only when that is within the approved scope.
On Revise, revisit only the affected stage. On Stop, preserve progress and pause immediately.
No separate discovery, outline, body or spec reapproval is required for this same bundle.
Merging and unrelated external actions remain independently context-bound.

## NEXT

The harness owns execution after the final bundle confirmation. Do not follow upstream Build's
implementation steps from this preparation workflow.
{% endif %}
