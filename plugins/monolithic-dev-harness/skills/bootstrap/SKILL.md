---
name: bootstrap
description: Use on first harness activation or when repository setup is absent, incomplete, or being changed. Guide the user through language, tracker, and missing project choices; propose and apply reviewed settings without manual JSON editing.
---

# Guided bootstrap

The harness is opt-in per repository. Before any planning or backlog stage, inspect setup. Preserve
the user's original request and return to it as soon as setup is usable. Use the host's structured
question UI when available; use numbered choices with the same meaning otherwise. The user never
needs to edit settings JSON by hand.

## 1. Inspect the user and repository

Run `harness preference show` and `harness bootstrap --inspect`. The latter reports whether the
repository is missing settings, incomplete, or ready; it lists shipped trackers, required values,
and safe Git inferences. An absent preference is a first activation: ask **English** or
**Português (Brasil)** as one two-option choice, then set it with `harness preference language en`
or `harness preference language pt-br`. This preference lives outside the repository and applies to
future harness requests by this user. Do not ask again when it is already set.

When settings are ready, check the selected tracker and proceed with the original request. When
missing or incomplete, ask which listed tracker to use. Do not select Azure from the bundled example
or assume the tracker from a placeholder setting. The shipped choices include Azure DevOps, Linear,
and the local tracker; explain where work will appear. Ask for the tracker's required values one at
a time, then ask only for source-control values, base branch, and artifact destination that cannot be
inferred. Explain any host trust or sign-in action the user actually must take.

## 2. Prepare one reviewable proposal

Use `harness bootstrap --propose` with the chosen values. Example:

```bash
harness bootstrap --propose --tracker linear --tracker-value team=ENG \
  --scm github --scm-value owner=team --scm-value repo=project \
  --artifacts-path docs/backlog --base-branch main
```

The command prints the complete candidate, a `digest`, and a `source_digest`. Existing unrelated
settings are preserved. Show the proposed changes and destination in the selected language. Ask a
single choice, **Apply setup** or **Change choices**, through the available host UI. For a text-only
host, show those same options as numbered choices. A reply to apply authorizes only this exact
local setup proposal; it does not authorize tracker or source-control writes.

After the user chooses Apply, repeat the proposal arguments with `--apply-digest <digest>
--source-digest <source_digest>`. A change to the candidate or existing settings makes application
fail and requires a new review. The controlled command adds the local Git ignore, writes settings
atomically, preserves an explicit disabled Codex picker, and initializes knowledge. Never tell the
user to paste or modify JSON manually.

The older `--settings-from <file>` import remains for a user who supplies an already reviewed file.
Bare `harness bootstrap` now inspects the repository; it never writes the Azure example.

## 3. Verify and return

Run `harness doctor`; use `--tools` for the selected tracker when authentication/tool readiness
needs checking. Run `review-setup` if its sources are missing. Tell the user precisely about any
sign-in, project trust, or session restart the host requires. Save a workflow checkpoint before a
required interruption and resume the original request after it. Do not ask the user to start the
harness again.

Repository settings are human-owned. Existing custom checks, paths, and host configuration survive
setup. The user-level language preference and clone-local workflow checkpoints are separate from
shared repository settings.
