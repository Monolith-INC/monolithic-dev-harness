# Step 2: Plan

## RULES

- No intermediate approvals.
- **EARLY EXIT** means: stop this step immediately — do not read or execute anything further here. Read and fully follow the target file instead. Return here ONLY if a later step explicitly says to loop back.

## INSTRUCTIONS

1. Draft resume check. If `{plan_file}` exists with `status: draft`, read it and capture the verbatim `<frozen-after-approval>...</frozen-after-approval>` block as `preserved_intent`. Otherwise `preserved_intent` is empty.
2. Investigate the codebase in the current session. Search the repository and read only the relevant files. Keep the Code Map focused on the paths and symbols involved, what to reuse, and what not to change. Do not retell the investigation when implementation starts — the plan already has it.

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
   - **Token count** (see SCOPE STANDARD). If the plan exceeds 1600 tokens, show the count and give the user a choice:
     - **Split** — carve off secondary goals. Propose the split — name each secondary goal. For each deferred goal, append one new entry to `{{ config.output_folder }}/{active_initiative}/deferred-work.md` using the format below. Do not modify existing entries or look for duplicates. Rewrite the current plan to cover only the main goal — do not surgically carve sections out; regenerate the plan for the narrowed scope.
     - **Keep full plan** — accept the risks.
     ```markdown
     - source_plan: `{plan_file}`
       summary: <one sentence naming the deferred goal>
       evidence: <why this was split from the current plan>
     ```
   - **Open Questions.** Present every entry as a numbered question with its options and what each option means, and HALT for the human's answers. Write each answer into the `<frozen-after-approval>` block as a decision and delete the entry. An answer may expose a new intent gap — add it and ask again. When the last entry is gone, delete the section.

### CHECKPOINT 1

Only when Open Questions is empty.

Present summary. Display the plan file path in whatever form is clickable where you are presenting it (e.g. code citation in chat, CWD-relative path with no leading `/` in terminal). If unsure, use CWD-relative path.

If token count exceeded 1600 and the user chose to keep the full plan, include the token count and explain why it may be a problem.

After presenting the summary, display this note:

---

Before approving, you can open the plan file in an editor or ask me questions and tell me what to change. For deeper challenge, use the bundled `bmad-advanced-elicitation` skill. When the user asks for several perspectives, use the bundled `bmad-party-mode` skill. Both are part of this harness package.

---

HALT and give the user a choice:

- **Approve and continue** — approve the plan, leave it `ready-for-dev`, and hand it to the harness backlog stage for work-item drafting. This approval does not publish tracker items or authorize implementation.
- **Approve and stop** — approve the plan, leave it `ready-for-dev`, and stop before backlog drafting.
- **Review plan** — review the plan against its requirements and code evidence, discuss any findings or revisions with the user until it is ready to approve, then either stop or continue.

Before acting on approval, re-read `{plan_file}` from disk. If it is missing, HALT without recreating it, changing status, or proceeding. If it changed, acknowledge the external edits and continue with the updated version. Set status `ready-for-dev`; everything inside `<frozen-after-approval>` is then locked and only the human can change it. For **Approve and continue**, record this plan as the accepted discovery artifact in the harness workflow checkpoint, then hand it to the harness backlog stage. Do not follow BMad Step 3 or start implementation.

## NEXT

For this harness Stage 0 integration, the workflow ends here. If the user chose **Approve and
continue**, continue with the harness backlog stage using `{plan_file}` as an input. Do not read or
follow BMad's implementation, review, or presentation steps; the harness owns those later stages.
{% endif %}
