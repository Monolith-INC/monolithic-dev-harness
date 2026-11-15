---
date: 2026-09-23
type: ticket
work_item_type: Bug
provider: local
story_points: 2
language: en
tags: [ticket, bug, hooks, generated-files]
---

# The generated-files rule blocks the generator it asks you to run

## 🎯 What

The `generated-files` rule denies a shell command that runs the code generator when the command
line names a generated file, for example as a build filter. Its own message for hand edits says to
"re-run the generator", so the agent is told to do the one thing it was just blocked from doing.

## 💡 Why

Scoping a generator to one output is the normal, safest way to regenerate after a model change.
Blocking it pushes the agent toward broader regeneration, which in this case was worse: running the
generator for a whole folder deleted every generated file outside the filter (a build_runner
behavior with `--delete-conflicting-outputs`), and those files had to be restored from git.

## 📋 Expected Behavior

```text
fvm dart run build_runner build --build-filter="lib/.../student_data.model.g.dart"
  -> allowed: the generator writes the file, not the agent
sed -i ... lib/.../student_data.model.g.dart
  -> denied, as today
```

## Observed

- Command: `fvm dart run build_runner build --delete-conflicting-outputs
  --build-filter="lib/modules/student/infrastructure/student_data.model.g.dart"`.
- Denial: "`…student_data.model.g.dart` is generated; this command would edit it by hand."

## 🔧 Technical Notes

- `scripts/harness/rules.py` → `rule_generated_files` → `shell_writes_matching` treats every path
  `shellscan.scan` cannot rule out (`writes.unresolved`) as a write. A path passed as an argument to
  a generator is listed that way.
- Add a policy list of generator commands (for example `generators: ["build_runner",
  "flutter gen-l10n", "npm run auto-generate"]`), or recognize well-known generators, and allow
  them to name generated paths. Keep denying redirections, `sed -i`, `tee`, `cp` and similar
  writes to those paths.
- Mention the allowed generator commands in the denial message.

## ✅ Acceptance Criteria

- [ ] A configured generator command that names a generated file is allowed.
- [ ] Hand writes to generated files through the shell are still denied.
- [ ] The denial message names the generator commands the policy allows.
- [ ] Tests cover a generator invocation with a generated path as an argument.

## 📊 Complexity

**2 points** — Largest driver: Scope=2, Uncertainty=2, Integrations=1, Data=1, QA=2, Rollout=1 → 2 points

## 📄 Original Description

Found while regenerating a JSON serializer after adding a model field: the hook blocked the
generator because the command named the output file.
