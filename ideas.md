# Harness test project: Daybook

## Purpose

Use a small but working app to see whether the harness can understand an existing project, investigate
a product-owner request, explain its options, and prepare a grounded plan before changing code. The
fixture should contain enough real behavior to inspect without turning the first trial into a large
build.

The existing Flutter Daybook app is the starting point. Extend it in place; do not replace it with a
new sample app.

## Fixture shape

The project should grow in small rounds. The current round provides:

- local demo sign-in, clearly distinguished from real account security;
- a working task list with create, read, edit, completion, and delete actions;
- one useful task search and status-filter feature;
- `fpdart` for typed success and failure results, plus Riverpod for app state;
- short product and engineering notes that describe the code as it exists;
- a small local backlog with requests of different sizes, one bug report to verify, and an optional
  idea-discovery prompt.

Keep the first version local and easy to run. Add routing, streaming, remote accounts, and TypeScript
server functions in later rounds when they support a specific test. The longer-term fixture may use
`go_router` or `auto_route`, `rxdart`, and TypeScript functions with callable, request, and event
handlers.

## First harness trial

Use the short, ready backlog request in `test-project-template/backlog/`. Start from a fresh disposable
copy and follow the harness's normal first-run path with the relevant skill. Run one child agent using
the least costly suitable model and medium reasoning when the host allows those choices. Give it the
actual skill and only the project, the selected request, and the basic safety boundary: work only in
the disposable copy, make no remote writes, and stop at a human approval point or when blocked. Do
not coach the agent through the technical answer or add special workflow steps.

The supervising agent should observe without steering. Record the step, what happened, the evidence,
and any recovery in `AI_Codex/Artifacts/live-trials/`. If the agent asks for a product decision,
answer only when the trial brief already contains the answer; otherwise record the pause as expected
behavior. Do not resume the older idea brainstorming run.

## Observable outcomes

**Pass** when the harness starts the technical investigation from the assigned request, uses the
actual code and project notes, identifies relevant behavior and unknowns, compares reasonable
approaches, prepares a reviewable proposal, and waits for approval before backlog or code changes.
Record the produced artifact and the observed workflow steps.

**Fail** when the harness skips investigation, invents repository facts, silently changes the
request, publishes work or edits code before approval, or bypasses an expected workflow gate.

**Inconclusive** when the run cannot start or finish because of an environment problem, the observer
has to intervene, or a missing product decision prevents a fair assessment. Keep these separate from
harness defects.

Do not claim the harness passed merely because an agent produced a plausible plan. The observer
must be able to point to the actual project evidence, the review artifact, and the approval boundary.
