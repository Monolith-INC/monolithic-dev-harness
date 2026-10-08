---
name: bootstrap
description: Use on first harness activation or when repository setup is absent, incomplete, or being changed. Guide the user through language, tracker, and missing project choices; propose and apply reviewed settings without manual JSON editing.
---

# Guided bootstrap

This initial workflow is **onboarding**, and is optional. Honor skip or dismissal with
`harness onboarding skip` or `dismiss`; provide skills and guidance in free mode without a session.
`harness onboarding restart` restarts onboarding without resetting existing work or approvals.
Free mode never authorizes protected writes or disables governance.

Onboarding does not require a work session, workflow, or checkout-bound implementation session.
Do not start or resume one to configure the project. Complete and verify setup first; select a
project work session only when the user proceeds to actual product or engineering work.

The harness is opt-in per repository. Before any planning or backlog stage, inspect setup. Preserve
the user's original request and return to it as soon as setup is usable. Use the host adapter interaction contract in `references/human-decisions.md` for every decision. Prefer a supported blocking control; otherwise use adapter-supported buttons and follow its waiting instructions. Use chat and end the turn when no button tool is available. When the adapter uses asynchronous buttons, keep the turn open with interruptible waits until the actual answer. Accept a direct human reply when a blocking control is unavailable. The host adapter chooses a supported button tool; delivery must never advance setup. The user never needs to edit settings JSON by hand.

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

Once settings are configured, if `bmad_runtime.ready` is false, run
`harness bootstrap --prepare-runtime --repo <project>` and inspect again. This prepares or repairs
the bundled runtime locally without a session, installation, download, or extra human choice.
Preserve existing configuration. If preparation fails, report its actual output and stop.

Language confirmation is optional. Use the captured project choice, saved user preference, or
English by default. Ask the `language` preference gate only when the user wants to change it.
Missing capture, dismissal or skipping never prevents setup or work. A default is not a recorded
human answer; do not synthesize confirmation.

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
branch, or source-control fields. Show the selected language, work-item tracker, and planning
folder once, then ask the `setup-confirm` gate: `harness decision present --repo <project> --host
<host> --gate setup-confirm`, adding `--blocking-available` or `--async-available` according to the
tools actually available. Invoke the returned control, or show the returned `menu` in chat. This
works before settings exist. Do not ask another confirmation after Yes. No returns to changing the
selected choices while keeping their current values.

If delivery fails, quietly use `harness decision fallback` to re-ask the same confirmation by the
next method: blocking buttons, asynchronous buttons, then ordinary chat. Keep the run and proposal;
do not expose tool failures, demand a typed Apply command, or report onboarding blocked. Chat shows
the same menu and continues this run when the human replies. Silence,
dismissal, and elapsed time never count as Yes. Yes authorizes only this exact local proposal;
it does not authorize tracker or source-control writes.

After the user chooses Yes, repeat the proposal arguments with `--apply-digest <digest>
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
Doctor checks installation and repository configuration; it does not verify live answer capture.
A read-only Codex configuration path or unavailable picker uses the next question method and
does not require restarting setup. Do not describe optional host configuration as fully applied
when the command reports it was preserved or could not be written.

After setup is ready, when the request did not already name what to do, ask the `next-step` gate
(`harness decision present --gate next-step`). Route the chosen option or the typed request and
continue in this same run; do not ask the user to invoke the harness again. A typed request never
approves writes. Quietly fall back and re-ask if the control fails to
land. Never abandon the run for a question delivery or capture failure.

The next route starts product or engineering work. A named project file can be read directly; it is
not required to be a tracker-issued item before discovery. At this boundary, return to the harness
entry skill to select the project work session and start its workflow. Do not ask for a commit,
branch, checkout-bound implementation session, or local-tracker initialization while planning.
At every later decision, including permission to
create a branch or commit, use a menu ([human-decisions.md](../../references/human-decisions.md)).

Repository settings are human-owned. Existing custom checks, paths, and host configuration survive
setup. The user-level language preference and clone-local workflow checkpoints are separate from
shared repository settings.

## Hand the saved context back to the run

After setup, use `harness bootstrap --inspect --repo <project>` and preserve its `handoff`:
absolute project and artifact paths, bundled command, preferences environment, original request,
current workflow status, next action, and pending human question. Reuse this context across steps
and delegation. Do not bootstrap again or ask confirmed setup choices again within this project.
An invalid workflow is a recovery blocker, not permission to silently start over.
