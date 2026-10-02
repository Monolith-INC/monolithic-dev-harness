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

Run only `harness bootstrap --inspect` first. Its output includes the saved language, setup status,
available trackers and their required values, current choices, and safe Git inferences. Do not run
`harness preference show`, search the plugin source, or explore the repository to rediscover this
information. If the command is unavailable, use the bundled `bin/harness` described in the parent
`harness` skill.

If status is ready, do not ask setup questions; continue the user's original request. Otherwise, use
the inspection output as the full setup checklist. Never choose a tracker from an example or accept
placeholder values. If the language is unset, offer **English** and **Português (Brasil)** as
clickable choices. Offer the tracker choices the same way. Resolve required tracker values and
missing project paths from repository inspection or available provider choices; do not ask the user
to type them. If a required value cannot be inferred or presented as a selectable option, stop and
report which value is unavailable instead of opening a text prompt. Do not ask for values already
present or safely inferred.
No hosted code service is required: use the inferred GitHub or Azure Repos choice when present, and
otherwise use `local` without asking another question. Explain where tracker work will appear and
where the artifacts will be saved.

## 2. Prepare one reviewable proposal

Make one `harness bootstrap --propose` call with all chosen values. Example:

```bash
harness bootstrap --propose --tracker linear --tracker-value team=ENG \
  --scm local \
  --artifacts-path docs/backlog --base-branch main
```

The command prints the complete candidate, a `digest`, and a `source_digest`. Existing unrelated
settings are preserved. If proposal validation fails, use its error to correct the missing value;
do not inspect implementation files to second-guess the command. Show the candidate and artifact
destination briefly, then offer **Apply setup** or **Change choices** as clickable choices. Do not
provide a typed reply as a fallback. If the controls are unavailable or fail, leave
the proposal unapplied and report that approval is waiting for an interactive host. A selection to
apply authorizes only this exact local proposal; it does not authorize tracker or source-control
writes.

After the user chooses Apply, repeat the proposal arguments with `--apply-digest <digest>
--source-digest <source_digest>`. A change to the candidate or existing settings makes application
fail and requires a new review. The controlled command adds the local Git ignore, writes settings
atomically, preserves an explicit disabled Codex picker, and initializes knowledge. Never tell the
user to paste or modify JSON manually.

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

Repository settings are human-owned. Existing custom checks, paths, and host configuration survive
setup. The user-level language preference and clone-local workflow checkpoints are separate from
shared repository settings.
