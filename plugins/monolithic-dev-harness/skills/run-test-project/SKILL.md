---
name: run-test-project
description: "Run an end-to-end test of a harness release candidate on a fresh copy of the test project, headless or interactive. Use to test harness behavior, rather than run a normal project's unit tests."
---

# Run test project

The harness needs a project to act on. `test-project-template/`, in the harness folder, is a small
app at an early stage with a `backlog/` of tickets that grow in difficulty. A test copies it, installs
a release candidate into the copy as a user would, and goes through the workflow as that user.

Run this only when a human asks for it. Work from the harness folder.

## 1. Cut a release candidate

The candidate must contain the changes under test. Follow
[`docs/06-delivery/release-process.md`](../../../../docs/06-delivery/release-process.md).

## 2. Prepare a copy

```sh
plugins/monolithic-dev-harness/bin/harness-python tools/project_fixture.py
```

It copies the template to the next unused `temp/test-NNN/`, then downloads the newest candidate's
`install.sh` from GitHub and runs it for that copy only (`--scope local`). It also stops Claude
Code in the copy from loading the harness folder's own `AGENTS.md` and `CLAUDE.md`, so the test agent
sees only what a user's project has. It prints the copy's path.
Pass `--version X.Y.Z-rc.N` to install a given release, and `--host` (repeatable) to choose hosts;
the default is Claude Code and Codex. If the lookup fails, it says so; pass `--version`, or install
by hand with the README's instructions.

Never edit or run in `test-project-template/` itself. Clear old copies from `temp/` by hand.

## 3. Run the test

Pick a ticket from the copy's `backlog/`. `DAY-001-task-counts.md` is the usual simple test; the
later tickets are for broader ones. Give the test agent the copy's path and this request: bootstrap
the harness, then start the main workflow with the chosen ticket.

- **Headless**, when the interactions do not need testing. Run the agent in the copy, for example
  `claude -p "<request>"` or `codex exec --sandbox workspace-write "<request>"`.
- **Interactive**, when they do. Start a subagent in the copy and relay its questions to the human
  and their answers back. An approval relayed this way does not count: the human gives it in the
  test agent's own conversation.

The test agent behaves as a user would. Check that the harness does what the change was meant to do,
and report what happened, including failures.
