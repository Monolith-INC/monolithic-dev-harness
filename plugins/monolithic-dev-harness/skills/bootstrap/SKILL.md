---
name: bootstrap
description: Use on first harness activation or when repository setup is absent, incomplete, or being changed. Guide the user through language, tracker, and missing project choices; propose and apply reviewed settings without manual JSON editing.
---

# Guided bootstrap

The harness is opt-in per repository. Before any planning or backlog stage, inspect setup. Preserve
the user's original request and return to it as soon as setup is usable. Drive every decision and
approval through clickable choices in the host's question controls. In Codex, call
`request_user_input_async` with selectable options and wait for a click selection. Never ask the
user to type an option, command, or free-text answer. If a required value cannot be discovered or
offered as a clickable choice, stop before asking or applying changes and report that setup is waiting
for an interactive control. The user never needs to edit settings JSON by hand.

## 1. Inspect once

Run only `harness bootstrap --inspect` first. Its output includes the saved language, whether this
project has confirmed it, setup status, available trackers and their required values, and current
choices. It also reports the current commit state, saved workflow, and local tracker folders. Treat
these live fields as authoritative; a saved checkpoint may describe an older state. Do not run
`harness preference show`, search the plugin source, or explore the repository to rediscover this
information. If the command is unavailable, use the bundled `bin/harness` described in the parent
`harness` skill.

If the selected tracker is `local` and `tracker_storage.ready` is false, run
`harness bootstrap --prepare-local-tracker` immediately and inspect again. This creates the bundled
tracker's state, artifact, and capacity folders. It is routine local setup, needs no user choice,
and preserves existing records. The local tracker is shipped with the plugin; `harness tracker stage`
is for adding a new tracker provider and must never be used to initialize it. If preparation fails,
report the concrete file access problem; do not ask the user to diagnose tracker internals.

If `language_confirmed` is false, always ask which language this project should use, even when a
different project previously saved a user-level preference. Offer **English** and **Português
(Brasil)** as clickable choices, then save the click with `harness preference language <en|pt-br>
--repo .`. Never infer a user's preferred language from their operating system or an older project.

If setup is ready, continue the original request. Otherwise, use the inspection output as the full
setup checklist. A missing `tracker.storage` is repaired above, not presented as a choice. Never
choose a tracker from an example or accept placeholder values. Offer tracker
choices as clickable choices. Resolve required tracker values and missing project paths from
repository inspection or available provider choices; do not ask the user to type them. If a required
value cannot be inferred or presented as a selectable option, stop and report which value is
unavailable instead of opening a text prompt. Do not ask for values already present or safely
inferred. Use `local` for source control by default. Do not inspect or present hosted code services
as a setup choice; the user can configure one later if they request pull-request features. Explain
where tracker work will appear and where plans will be saved. For the local tracker, work-item
records live in `.harness/tracker/` in this project; `artifacts_path` is the folder for planning
drafts. Never claim those two folders are the same.

## 2. Prepare one reviewable proposal

Make one `harness bootstrap --propose` call with all chosen values. Example:

```bash
harness bootstrap --propose --tracker linear --tracker-value team=ENG \
  --artifacts-path docs/backlog
```

The command prints the complete candidate, a `digest`, and a `source_digest`. Existing unrelated
settings are preserved. If proposal validation fails, use its error to correct the missing value;
do not inspect implementation files to second-guess the command. Summarize only user-facing choices:
the selected work-item tracker and artifact destination. Do not show raw settings, inferred remote,
branch, or source-control fields. Then offer **Apply setup** or **Change choices** as clickable
choices. Do not provide a typed reply as a fallback. If the controls are unavailable or fail, leave
the proposal unapplied and report that approval is waiting for an interactive host. A selection to
apply authorizes only this exact local proposal; it does not authorize tracker or source-control
writes.

After the user chooses Apply, repeat the proposal arguments with `--apply-digest <digest>
--source-digest <source_digest>`. A change to the candidate or existing settings makes application
fail and requires a new review. The controlled command adds the local Git ignore, writes settings
atomically, prepares every local-tracker folder when selected, preserves an explicit disabled Codex
picker, and initializes knowledge. It works in a
folder without Git; it never asks for a branch or initial commit. Never tell the user to paste or
modify JSON manually.

The older `--settings-from <file>` import remains for a user who supplies an already reviewed file.
Bare `harness bootstrap` now inspects the repository; it never writes the Azure example.

## 3. Verify once and return

Run `harness doctor` once. Do not run `--tools`, `review-setup`, knowledge discovery, or knowledge
building as part of basic setup. Do those only when the user's next task needs them. Report a missing
optional tool without searching for or installing replacements. Tell the user only about a sign-in,
project trust, or restart that is actually required.

After setup is ready, ask what to do next through `request_user_input_async`. Offer up to three
clickable choices based on the current request: continue the named task, prepare work items, or
explore an idea. When no task was supplied, use **Start feature work** as the first choice. Do not
add a literal **Other** option: the question UI supplies its default **Other** text field. Route the
clicked choice or the text entered through **Other** and continue in this same run; do not ask the
user to invoke the harness again.

The next route starts product or engineering work. A named project file can be read directly; it is
not required to be a tracker-issued item before discovery. Do not ask for a commit, branch, session,
or local-tracker initialization while planning. At every later decision, including permission to
create a branch or commit, use a clickable question control. Never replace a failed control with a
plain-text question.

Repository settings are human-owned. Existing custom checks, paths, and host configuration survive
setup. The user-level language preference and clone-local workflow checkpoints are separate from
shared repository settings.
