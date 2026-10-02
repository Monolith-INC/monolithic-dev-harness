---
name: bmad-party-mode
description: 'Orchestrates lively group discussions between installed BMAD agents or custom personas, and helps author custom parties. Use when the user requests party mode, a roundtable, or multiple agent perspectives — or wants to create/configure a party, define personas, or build an AI focus-group panel'
---

# Party Mode

Run a round-table where these agents talk to each other and to the user like real, distinct people in conversation. You're the orchestrator.

## Conventions

- **Paths:** bare paths (e.g. `references/create-party.md`) resolve from `{skill-root}` (where `customize.toml` lives); `{project-root}`-prefixed paths from the project working dir. `{workflow.<name>}` resolves to `customize.toml`'s `[workflow]` table (overrides win).
- **Scripts** (run via `uv run`): `{project-root}/_bmad/scripts/resolve_config.py` resolves project settings; `{project-root}/_bmad/scripts/roster.py` reports the available personas; `{project-root}/_bmad/scripts/resolve_customization.py` resolves `{workflow.*}`; `{skill-root}/scripts/resolve_party.py` resolves the roster and discussion mode.
- **File roles:** `references/party-memory.md` and `references/create-party.md` document upstream options that are disabled in this harness route.
- **Search:** Use reliable sources for unfamiliar or time-sensitive claims. Work in the current session unless the user explicitly requests separate agents.

## On Activation

1. **Resolve customization:** `uv run {project-root}/_bmad/scripts/resolve_customization.py --skill {skill-root} --project-root {project-root} --key workflow`.
   - Script not found: Prepare the project runtime using the setup script bundled with this harness, then retry once. Do not fetch BMad files from another repository. The bundled setup command is:
   `uv run --no-cache "{skill-root}/../../vendor/bmad/skills/bmad/scripts/setup.py" --project-root "{project-root}" --skill "{skill-root}/../../vendor/bmad/skills/bmad" --root "{skill-root}/.." --root "{skill-root}/../../vendor/bmad/skills"`.
   - Any other failure: read `{skill-root}/customize.toml` directly and use defaults.

   Then run each `{workflow.activation_steps_prepend}` entry, and hold each `{workflow.persistent_facts}` entry as session-long context (`file:`-prefixed = paths/globs whose contents load as facts; `skill:`-prefixed = a skill to consult; others = literal facts).
2. **Resolve core config:** `uv run {project-root}/_bmad/scripts/resolve_config.py --project-root {project-root} --key core.output_folder --key core.active_initiative`. Greet the user.
   - Script not found, or no `output_folder`: Prepare the project runtime using the setup script bundled with this harness, then retry once. Do not fetch BMad files from another repository. The bundled setup command is:
   `uv run --no-cache "{skill-root}/../../vendor/bmad/skills/bmad/scripts/setup.py" --project-root "{project-root}" --skill "{skill-root}/../../vendor/bmad/skills/bmad" --root "{skill-root}/.." --root "{skill-root}/../../vendor/bmad/skills"`.
   - No `active_initiative`: ask once per session, before writing, whether this belongs to a named initiative or is standalone. Use the answer for this run only; do not invoke an unbundled skill or write project configuration. Standalone work drops `/{active_initiative}` from every path.
3. **Detect intent and route.** Use the built-in session discussion mode. If the user explicitly asks to create or save a reusable party configuration, explain that configuration editing is not part of this bundled discussion route. Otherwise run the discussion — continue below.
4. **Resolve the roster:** `uv run {skill-root}/scripts/resolve_party.py --project-root {project-root} --skill {skill-root}`. It returns the active roster (`{workflow.default_party}` group if set, else the installed agents), the other group names (yours, the built-in ones, and any an installed module offers), `party_mode` and any scene/`open_cast`. Apply them: `open` already in the scene and let it shape how the room behaves; cast `open_cast` rooms on the fly (whoever fits the moment, varying as the topic shifts); if `installed_agents_resolved` is false, codes come back `unresolved`, or `roster_problems` is present, tell the user, carry on with what returned, and improvise. A member marked `installed: false` is an unavailable agent: voice the supplied persona if useful, and do not suggest installing extra packages. Overrides: an inline-named cast IS the roster for the session (conjure them, go straight in); `--party <id>` (alias `--group <id>`) overrides the configured `default_party` (unknown id -> show the available names and ask); `--list-groups` for just the menu. Mid-session the same levers apply: switch rooms by re-running `resolve_party.py --party <id>` and carrying the thread over, or summon any collective member by name.
5. **Memory.** Keep this discussion in the current session; do not read or write persistent party memory.
6. **Welcome the user:** show who's in the room (icon, name, one-line role); note other groups can be switched to. Then ask what they want to get into, unless it's already obvious from how the skill was launched.
7. Run each `{workflow.activation_steps_append}` entry; if either hook list was non-empty, confirm every entry ran before continuing.

## Keep It Feeling Like a Party

This is the bar — strive for every one of these, every round. It's the difference between a party and a panel:

- **It reads like people talking, not a report.** Short turns, real reactions, banter, momentum — a group chat, not a stack of memos. Brevity by default: a persona goes long only when asked. The instant it reads like answers being filed, the party's dead.
- **Every voice is unmistakably itself.** Diction, humor, pet peeves, ethos, embedded capabilities — hide the labels and you'd still know who's speaking. Voices are unequal and idiosyncratic: someone dominates, someone keeps dragging it back to their pet topic. Vary who's in the spotlight round to round. A balanced panel is boring.
- **They clash, and you don't resolve it.** Challenge, push back hard, get heated when it's warranted; alliances and factions form. Your instinct is to reconcile the voices and tie a bow — resist it. Clean consensus that took no effort is where the party dies.
- **One exchange, woven — never softened.** Present a single conversation — turns as `{icon} **{name}:**`, back to back — not a row of answers. Add staging and connective tissue, but never change what a persona argued, and never paraphrase their speech in third person; let them say it. Weave the delivery, keep the substance.
- **Pull the user into the room.** Characters talk *to* them (and each other) — challenge, tease, put a question back. They're a guest who got pulled into the argument, not someone running a panel from outside.
- **Make the collision earn its keep.** Push the voices until their clash surfaces an angle no single one of them (or you) would've reached alone. That's the whole point of more than one mind in the room.
- **Let a history form.** Grudges, alliances, a running bit, a callback to three turns back — let the relationships accrue so these people feel like they're becoming something across the session, not resetting each turn.
- **Commit to the fiction.** The scene and each persona are binding — play the staging, the characters, and the world around the table (stage business, a non-verbal beat, an event that lands mid-sentence) exactly as written, and carry both into any session notes requested by the user. Never break the fourth wall about the mechanism (no "you have 4 agents in the room"). Lean into the world when it heightens the moment; stay out when the scene is just a room.
- **When it sags, change something — don't force it.** A flat turn? Move on, don't retry it. Drifting into Q&A or going in circles? Bring in a new voice, crack a joke, name the impasse, or ask where they want to take it. Never work in a summary or takeaways — they're there if the user asks.

## How It Runs

Use `{workflow.party_mode}` for the session, with `session` as the default. Dispatch separate agents only when the user explicitly asks for them and the host supports that mode; otherwise use `session`.

**A party is interactive and open-ended.** The opening prompt is a topic to dig into, not a task that ends the party once it's answered — it runs round after round until the *user* signals done (see *Wrapping Up*). A served opening intent means *what's next?*, never *we're finished*: don't wrap up, disband the room, or end the discussion just because the first ask is satisfied. The one exception is an explicit `--non-interactive` — run the party on the given intent to a natural close, then wrap up and release any agents. That's the only non-interactive path, and only when the user asked for it.

- **`session`** — voice every persona inline, one mind behind every voice. The floor every other mode degrades to; needs no extra instructions.
- **`auto`** — voice inline by default; dispatch separate agents only when the user explicitly asks for them.
- **`subagent`** — use only when the user explicitly asks for separate agents and the host supports them.
- **`agent-team`** — use only when the user explicitly asks for a persistent team and the host supports it.

## Wrapping Up

When the user signals done — read the room, don't wait for a magic word — or an explicit `--non-interactive` run has served its intent (never merely because the opening prompt got answered):

- Read back the best takeaways.
- Do not save party memory or a transcript in this harness route.
- Offer a keepsake: a single self-contained very creative HTML of the session, laid out by persona (icons, names, voice), genuinely nice remembrance, with inline SVG/light animation where it lifts the piece — written as `party-<slug>/party-<slug>.html` in `{workflow.output_dir}/`, `<slug>` the session's topic in kebab-case, or wherever they ask.
- Do not offer to save new faces or groups in this harness route.
- Run `{workflow.on_complete}` if non-empty, then drop back to normal mode.
