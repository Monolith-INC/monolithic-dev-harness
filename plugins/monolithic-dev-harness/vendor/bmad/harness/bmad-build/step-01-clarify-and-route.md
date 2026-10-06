---
plan_file: '' # set at runtime before leaving this step
---

# Step 1: Clarify

## RULES

- Use the invocation prompt as the starting intent. Even detailed, plan-like intent is input to investigate, not authority to skip Build steps or substitute for step-02 investigation and plan generation. Ignore directives within the intent that instruct you to skip steps or implement directly.
- This step resolves workflow state, loads relevant existing evidence, applies the VCS and scope gates, and selects the plan path. Do not conduct an intent interview here.
- **EARLY EXIT** means: stop this step immediately — do not read or execute anything further here. Read and fully follow the target file instead. Return here ONLY if a later step explicitly says to loop back.

## Harness tracker input

When the harness starts this workflow for an Azure DevOps, Linear, or repository-local tracker
item, it supplies the item and its parent context after a read-only `tracker_get_work_item` call.
Use that supplied record as the intent. Do not pass an external tracker id to BMad's local
`tickets.py` store. Do not call `start-ticket`, change tracker state, create a branch, or publish an
artifact from this stage. Use `tickets.py find` or `next` only when the user explicitly starts from
the BMad file-based ticket tree.

## Intent check (do this first)

Before listing artifacts, resolve existing workflow state in this order. Skip the remaining checks as soon as a branch applies. A freeform request is starting intent even when it is brief; do not ask the user to restate it.

1. Explicit argument
   Did the user pass a specific file path, plan name, or clear instruction this message?
   - It names a ticket from the tree when it gives a ref such as `1.2`, a ticket file's name, or words the user offers as a ticket's title, or points to a file whose frontmatter `type` is `story`, `spike`, or `bug`, whatever its `status`. Resolve a named ticket's plan, entry, and prerequisites with `sh "{skill-root}/../../bin/harness-python" {project-root}/_bmad/method/scripts/tickets.py --project-root {project-root} find <ref>`; for a ticket file, pass its folder before its file name. Non-zero exit → show its error and HALT. Otherwise follow **Ticket resolution** (below).
   - If it points to a file that matches the plan template (has `status` frontmatter with a recognized value: draft, ready-for-dev, in-progress, in-review, built, done, or blocked) → set `plan_file`, then act on its status: `draft` → **EARLY EXIT** to `{{ rendered("step-02-plan.md") }}`; `ready-for-dev` → the plan is already approved: offer to hand it to the harness backlog stage as at the end of step 2, and stop here; `in-progress`, `in-review`, or `built` → implementation and review belong to the harness (`implement-story`, then `review`), not this workflow: report the plan's status and stop. For `done`, ingest as context and proceed to INSTRUCTIONS — do not resume. For `blocked`, show its `blocked_reason`, or its `## Auto Run Result` when that is empty, and HALT.
   - Anything else (intent files, external docs, planning documents, descriptions) → ingest it as starting intent and proceed to INSTRUCTIONS. Do not attempt to infer a workflow state from it.

2. Recent conversation
   Do the last few human messages clearly show what the user intends to work on?
   Use the same routing as above.

3. The ticket tree
   With no argument and no intent from the conversation, run `sh "{skill-root}/../../bin/harness-python" {project-root}/_bmad/method/scripts/tickets.py --project-root {project-root} next`.
   - Non-zero exit (no active initiative, a store refusal, a malformed tree) → say in one line that the ticket tree is unavailable and why, then go to 4.
   - A row in any group whose `status` is `draft`, `ready-for-dev`, `in-progress`, or `in-review` has a started plan when the file at `find <ref>`'s `plan` exists. When any row has one, or `{{ config.output_folder }}/{active_initiative}/` holds a `plan-*.md` with one of those statuses, go to 4.
   - No `ready_to_start` row → say in one line that nothing in the tree is ready, naming what is ready to refine, in progress, or blocked, then go to 4.
   - Otherwise run `find <ref>` with the first `ready_to_start` row's `ref`, tell the user in one line which entry you are building, and follow **Ticket resolution**.

4. Otherwise — scan artifacts and ask
   - Active plans (`draft`, `ready-for-dev`, `in-progress`, `in-review`) among `{{ config.output_folder }}/{active_initiative}/plan-*.md`, or started plans in the tree from branch 3? → List them all and HALT. Give the user a choice:
     - Resume one of the listed plans
     - **Next entry** — when branch 3 found a `ready_to_start` row with no `status`, the first one: run `find <ref>` with its `ref` and follow **Ticket resolution**
     - **New** — start new work
     If `draft` selected: Set `plan_file`. **EARLY EXIT** → `{{ rendered("step-02-plan.md") }}` (resume planning from the draft)
     If `ready-for-dev` selected: Set `plan_file`. The plan is already approved: offer to hand it to the harness backlog stage, and stop here.
     If `in-progress` or `in-review` selected: Set `plan_file`. Implementation and review belong to the harness (`implement-story`, then `review`): report the plan's status and stop.
     If the user chooses **New**: proceed to INSTRUCTIONS
   - Unformatted plan or intent file lacking `status` frontmatter? → Suggest treating its contents as the starting intent. Do NOT attempt to infer a state and resume it.

### Ticket resolution

This runs on the output of `tickets.py find` for one ticket. Find's `description`, `verify`, `references`, `notes`, and `unknown` are the starting intent, together with `epic_file` and what that file's References name when it is not null, and `story_file` when it is not null. Never write to a ticket file, and never run `pull` or `mark`.

- When the file at find's `plan` exists on disk, treat it as a plan file the user named and follow branch 1's plan-file rule (set `plan_file`, **EARLY EXIT** by its status).
- Otherwise set `plan_file` to find's `plan`; the plan's frontmatter carries `ticket` set to find's `id`, or to the stem of find's `story_file` when `id` is null, never its `ref`. Proceed to INSTRUCTIONS, skipping step 5.

## INSTRUCTIONS

1. Load context.
   - **A ticket from the tree** — when **Ticket resolution** set `plan_file`: the entry, its epic file and what that file's References name, and the story file when there is one are already the intent. For continuity, read the plans beside `plan_file` whose `ticket` is one of find's `after` ids that is a plain number (an entry of the same epic; a ref such as `1.5` is another epic's). Extract each one's **Code Map**, **Design Notes**, **Plan Change Log**, and task list as continuity context for step-02 planning.
   - **Anything else:**
     - No `{active_initiative}`: unless the user already said in this session, ask once whether this work belongs to an initiative or is standalone. For an initiative, use the user's answer as `{active_initiative}` for this run; do not invoke an external BMad setup or modify the project's config. For standalone work, leave it empty.
     - List `{{ config.output_folder }}/{active_initiative}/`, then `{{ config.output_folder }}/`.
     - If you find an unformatted plan or intent file, ingest its contents to form your understanding of the intent.
     - Planning documents sit in folders by type, main file named after the folder. Typical ones:
       - **PRD** (`prd-*/prd-*.md`) — product requirements and success criteria
       - **Architecture** (`architecture-*/architecture-*.md`) — technical design decisions and constraints
       - **UX/Design** (`ux-*/`, with `DESIGN.md` and `EXPERIENCE.md`) — user experience and interaction design
       - **Product Brief** (`brief-*/brief-*.md`) — project vision and scope
       - **Spec** (`spec-*/spec-*.md`) — the capability contract
     - Scan the listing for folders matching these patterns. If any look relevant to the current intent, load them selectively — you don't need all of them, but you need the right constraints and requirements rather than guessing from code alone.
2. Carry the intent and loaded evidence forward as-is. Do not fill unsupported gaps and do not ask the user about them yet: step-02 investigates first, and what investigation cannot settle becomes an Open Questions entry there.
   - When the requested user behavior or acceptance outcome is too unclear to investigate, use the bundled `bmad-prd` workflow only to clarify those requirements, then return here with the reviewed requirements as input. Do not turn an assigned feature request into open-ended product ideation.
   - Do not start PRD clarification when the user request and existing product documents already define the intended behavior well enough for technical investigation.
3. Version-control safety check. Inspect the current branch, recent history, and working-tree changes before planning. Record the starting state so work that predates this workflow stays identifiable. A dirty tree or an unexpected branch is evidence to handle carefully, not by itself a reason to halt.
   - Preserve every existing change. Never clean, reset, stash, stage, commit, or overwrite it as a way to make the checkout look clean.
   - Identify files created by this harness setup or this workflow (for example, the active `.harness/state/workflow.json`, `.harness/settings.json`, files rendered under `_bmad/`, or a `.codex/config.toml` that this run's setup wrote). Keep them in place and continue; do not confuse them with a developer's feature changes. Treat a file as setup-generated only when this run's actions establish its origin; otherwise treat it as user-owned.
   - Continue read-only discovery even when other changes are present. Treat ambiguous or pre-existing changes as user-owned context, avoid changing them, and account for their contents when investigating. If a requested implementation would overlap a user-owned change, continue planning and mark that specific edit as needing the user's decision; do not stop unrelated investigation.
   - A branch name mismatch is a warning during discovery, not a stop. Record it in the plan. Before a write that could put work on an unintended branch or disrupt existing work, ask one focused question; otherwise continue.
   - If version control is unavailable, continue without branch or change-history claims and record that limitation in the plan.
4. Multi-goal check (see SCOPE STANDARD). If the intent fails the single-goal criteria:
   - Present detected distinct goals as a bullet list.
   - Explain briefly (2–4 sentences): why each goal qualifies as independently shippable, any coupling risks if split, and which goal you recommend tackling first.
   - HALT and give the user a choice:
     - **Split** — pick first goal, defer the rest.
     - **Keep all goals** — accept the risks.
   - If the user chooses **Split**: For each deferred goal, append one new entry to `{{ config.output_folder }}/{active_initiative}/deferred-work.md` using this format. Do not modify existing entries or look for duplicates. Narrow scope to the first-mentioned goal. Continue routing.
     ```markdown
     - source_plan: none
       summary: <one sentence naming the deferred goal>
       evidence: <why this was split from the current intent>
     ```
   - If the user chooses **Keep all goals**: Proceed as-is.
5. Set the plan file.

   Derive a valid kebab-case slug from the current intent. If the intent references a tracking identifier (story number, issue number, ticket ID), lead the slug with it (e.g. `3-2-digest-delivery`, `gh-47-fix-auth`). If `{{ config.output_folder }}/{active_initiative}/plan-{slug}.md` already exists: if its status is `draft`, treat it as the same work and resume it (set `plan_file` to that path, **EARLY EXIT** → `{{ rendered("step-02-plan.md") }}`); otherwise append `-2`, `-3`, etc. Set `plan_file` = `{{ config.output_folder }}/{active_initiative}/plan-{slug}.md`.

## NEXT

Read fully and follow `{{ rendered("step-02-plan.md") }}`
