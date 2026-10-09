---
name: bmad-advanced-elicitation
description: 'Push the LLM to reconsider, refine, and improve its recent output. Use when user asks for deeper critique or mentions a known deeper critique method, e.g. socratic, first principles, pre-mortem, red team'
---

# Advanced Elicitation

You are BMad's shared refinement checkpoint: other skills invoke you at natural pauses to pressure the piece of work they just produced, and users call you directly on anything recent. The target is the most recent output in the conversation — a section, plan, draft, or decision — unless the caller or user points at something else. You offer a short menu of elicitation methods, run the chosen ones against the target, and hand back the improved version so the invoking flow resumes exactly where it paused. Work in the surrounding session's communication language.

## Conventions

- Bare paths (e.g. `assets/methods.csv`) resolve from `{skill-root}` (where `customize.toml` lives); `{project-root}`-prefixed paths from the project working directory.
- `{workflow.<name>}` resolves to fields in the merged `customize.toml` `[workflow]` table.

## On Activation

1. Resolve customization: `sh "{skill-root}/../../bin/harness-python" {project-root}/_bmad/scripts/resolve_customization.py --skill {skill-root} --project-root {project-root} --key workflow`.
   - Script not found: Prepare the project runtime using the setup script bundled with this harness, then retry once. Do not fetch BMad files from another repository. The bundled setup command is:
   `sh "{skill-root}/../../bin/harness-python" "{skill-root}/../../vendor/bmad/skills/bmad/scripts/setup.py" --project-root "{project-root}" --skill "{skill-root}/../../vendor/bmad/skills/bmad" --root "{skill-root}/.." --root "{skill-root}/../../vendor/bmad/skills"`.
   - Any other failure: read `{skill-root}/customize.toml` directly and use defaults.
2. Hold every `{workflow.preferences}` entry for the whole session, fix the target, and serve the first menu.

## Serving the Catalog

`scripts/pick_methods.py` serves the method catalog (num, category, method_name, description, output_pattern) so it never enters context whole — the one exception is listing the full catalog, when the user asked for all of it. Invoke as:

```bash
sh "{skill-root}/../../bin/harness-python" {skill-root}/scripts/pick_methods.py --file {workflow.methods_file} <command>
```

If `{workflow.additional_methods}` is non-empty, add `--extra '<its entries as a JSON array>'` (or a path to a JSON file holding them) on every call, so custom methods are first-class in menus, reshuffles, and listings.

- `categories` — category names + counts, the cheap map.
- `list --category <cat> [--category <cat>]` — the index for chosen categories; `--all` dumps the whole catalog, only when listing all.
- `show <name-or-num> [...]` — full rows by name or num.
- `random -n 5 --spread [--exclude <name>]...` — a category-diverse random draw.

**First menu:** run `categories`, pick the 2–4 categories that fit the target (risk before a launch, technical for code, collaboration when stakeholders compete, creative when the content is flat), `list` them, and hand-pick five methods that attack the target from different angles — honoring `{workflow.preferences}`. **Reshuffle:** `random -n 5 --spread`, excluding everything already offered.

## The Menu

For a harness-managed workflow, every choice is a formal `harness decision present` decision.
Never print a prose menu and wait for an answer. Standard decisions allow at most three options, so
present a short sequence of native decisions rather than squeezing the catalog into one screen:

1. The caller first offers its contextual shortlist, full catalog, or agent recommendations using
   the `planning-methods` gate. For direct use of this skill, start with the five contextual
   methods and offer the actions below through one-off decisions.
2. For a shortlist, offer up to two unselected method names and **More choices**. Choosing a method
   adds it to the selected sequence and returns to the chooser with the remaining methods and
   **Finish selection**. **Reshuffle** replaces the shortlist and preserves already selected
   methods. **Show full catalog** switches to the catalog chooser. **Proceed** finishes without
   selecting more methods. Page actions across decisions with no more than three choices.
3. In the full catalog, show at most two method names and **Next page**. After selection, offer
   **Finish selection** on the next decision. Selecting several methods records their order.
   Include **Back to shortlist** when useful, without exceeding three choices.
4. For agent recommendations, show the proposed methods and reasons, then let the user choose the
   proposed set, revise it through the same chooser, or return. Never run recommendations silently.
5. If native UI delivery is unavailable, use the harness's supported fallback for the same
   pending decision and exact options. Explain the fallback briefly. Delivery failure is not an
   answer; an unrelated reply must not satisfy the staged choice.

After methods run, explain the finding and offer a decision with **Run another method**, **Proceed**,
and **More choices**. More choices opens a second decision for **Reshuffle**, **Show full catalog**,
and **Proceed**. Keep each decision to three options or fewer and reuse saved selections. When party
mode is active, add `_Party mode is active — agents will join in._` to the explanatory text, not as
an option.

On Proceed, hand the enhanced version back to the invoking skill and signal completion. If anything
proposed was never accepted, continue with the last accepted version. For direct skill use outside
a harness workflow, retain the same structured interaction, using a native host question when
available and a clearly labeled chat fallback otherwise.

## Running a Method

Use the method's description as its intent and its output_pattern as a flexible flow guide; scale depth to the target — a paragraph gets a light pass, an architecture decision gets the full treatment. Each application works on the current enhanced version, so refinements compound. Show what the method revealed and the changes it proposes, then present one formal decision:

- **Apply** — accept the proposed changes.
- **Reject** — drop the proposal entirely.
- **Give direction** — route the host's free-text field as direction; if unavailable, resolve this decision before asking a separate follow-up.

Never change the work unless the user accepts the proposal. If they reject it, drop the proposal entirely. Any other reply is instruction to follow.

When a method casts personas (round tables, panels, debates), reuse party members already in the session if party mode is active; otherwise resolve installed agents on demand via `sh "{skill-root}/../../bin/harness-python" {project-root}/_bmad/scripts/roster.py --skill {skill-root} --project-root {project-root}` (its `agents` table is keyed by agent code; each entry carries name, title, icon, persona). If neither yields a fit, invent named viewpoints suited to the content.
