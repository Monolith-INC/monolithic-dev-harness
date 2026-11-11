---
name: discovery
description: Take a raw product idea to an approved Vision Doc and PRD, published as revisions on a discovery Epic. Use when someone brings an idea, wants to explore or shape one, starts a "new project", or asks for "discovery", and when called by name. A general question about product documents is answered directly, without this skill.
---

# Discovery

Discovery is a harness mode: a bundle with its own procedure, rules, hooks that act only while it
runs, and a work session the user is never asked about. It turns an idea into a Vision Doc (the
problem, users, outcome and limits) and a PRD (the product requirements), each published as
revisions on a discovery Epic, called ROOT, and each approved by the user. Where the work stands is
read from ROOT, so leaving and coming back resumes at the right step.

## Start

1. Check the tracker first: `tracker_preflight` (reports whether the tracker is ready). If it does
   not pass, report the result and stop. Do not enter the mode.
2. Know the project name, and the user's name for the change history. Ask once, in one message, for
   whichever is missing.
3. Run `harness modes enter discovery`, which starts the mode. Add `--root <Epic key>` when the
   user named the discovery Epic. It prints the mode and its Epic. If it says a mode is already
   active, tell the user which and ask whether to continue it or end it with `harness modes leave`.
   If it says the harness does not govern the project, tell the user to set the project up first.
4. Read the procedure ([`workflow.md`](../../modes/discovery/workflow.md)), the rules
   ([`rules.md`](../../modes/discovery/rules.md)) and the document catalog
   ([`documents.toml`](../../config/documents.toml): each document's title, headings in order and
   interview areas).
5. Run `harness modes step`. It reads ROOT's documents and prints where the work stands: the
   `step` and what holds. Follow that step. Run it again after every publish and whenever the user
   comes back; each prompt also repeats it as the current step.
6. When the knowledge store may hold facts about the project, run the `knowledge-acquire` skill
   once, before step 1. An empty, stale or missing store is never a reason to wait.

While the mode runs, only the gateway tools the mode lists are allowed, and every tracker write
still needs the user's approval. Answer a general question directly and stay in the mode.

## Writing a document (Step 1, Step 2)

- The document follows the catalog: `# <title>` with the project name, a `Status: Draft` line, then
  each `##` heading in order, the last being `Change history` with a `Date | Change | By` table.
  Every section has real content or `TBD — <reason> (owner: <name>)`.
- Interview the user in one message, with an "I'm already assuming: …" list, and wait. Use the
  `bmad-advanced-elicitation` skill only to deepen a thin answer, at most once per section.
- Write the draft where `harness document path --type <kind> --item <ROOT key>` says, with `<kind>`
  `vision-doc` or `prd`. Before ROOT exists, use `--new epic --title "<project name>"` instead; if
  the tracker assigns ids only when an item is created, create ROOT first. If the draft file
  already exists, resume from it.
- Revisions are `r1`, `r2`, …: the next one is one above the highest revision of that kind that
  `tracker_list_artifacts` shows. Publish with `tracker_publish_artifact` (kind, the catalog title,
  the content, the revision), then list again to confirm the new revision is there under that
  title. If it is not, report it and stop.
- Create ROOT, when it is absent, with `tracker_create_work_item` (kind epic, title the project
  name, no description). Then run `harness modes leave` and `harness modes enter discovery --root
  <the new key>`, so the mode knows its Epic; nothing is lost, because the step comes from ROOT.
  If ROOT may already exist, look for an Epic with the project's name first
  (`tracker_search_work_items`), and use it after the user confirms.
- Step 2 starts only from an approved Vision Doc. Read it with `tracker_list_artifacts` (kind
  `vision-doc`, highest revision), map its sections with the catalog's `upstream` entry, show
  "Already have: …", and interview only the gaps.

## Gates (G1, G2): show it, approve it, then save it

The harness will not save a document nobody approved, so ask the gate before the publish the
workflow lists, and publish once, as the approved revision:

1. Show the draft: run `harness workflow show --artifact <draft>`, put its output in your reply, run
   `harness decision status`, then ask `harness decision present --gate approve-document --artifact
   <draft>`. Read [human decisions](../../references/human-decisions.md) when asking. Never pass a
   session id, and never approve for the user.
2. When the user approves, publish the draft's text with two changes made in the publish call, not
   in the file (editing the file voids the approval): the `Status` line reads `Approved`, and
   `Change history` gains a row `<today> | Approved by <user> | <user>`.
3. If the user answers "Not now", keep the draft, ask what to change, and publish nothing.
4. A new Vision Doc revision means re-checking the PRD: fill or flag only its gaps.

## Exit

When `harness modes step` reports the exit, tell the user the Vision Doc and PRD are approved on
ROOT and that the next discovery steps come in a later slice, then run `harness modes leave`, which
ends the mode. Run it too when the user moves on to other work.
