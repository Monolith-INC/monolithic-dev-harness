# Private runner isolation trial

Date: 2026-10-05. Model: GPT-6 Luna, medium reasoning. Sandbox: read-only. Profile: local planning.
Trial scope: read the test project's README and report its name; no edits were authorized or made.

The disposable runner created a project, private mode-0700 temporary and preference folders, and a
separate Codex home. It linked the existing sign-in file without copying its contents and ran Codex
with user configuration disabled. The parent command exited and removed the disposable project.

The CLI itself started, but its first shell command failed with:

> error building bubblewrap command: app-server socket directory must be a user-owned directory with mode 0700

No project files were read and no changes were made. The transcript records one shell command
attempt, zero explicit file-read events, and 34,346 input tokens. The JSONL transcript also includes
one non-JSON startup line; the transcript summarizer reports it separately.

The shared `/tmp/codex-daemon-1003` path remains a read-only mount with mode `000`. The private
`TMPDIR` did not redirect the socket directory used by the nested Codex shell executor, so the
socket blocker is unresolved. The CLI tried to write its normal shared-home log database during an
earlier retry; the private Codex home avoided that write, but did not repair shell startup.

This trial tested the new test-runner setup, not the candidate harness hooks or plugin installation.
No further lower-tier run should be spent until the socket directory can be controlled or the host
runner provides a supported override. See [problem log](../Artifacts/2026-10-05-live-trial-problems.md).

## Retry with detached desktop context

A second trial used GPT-6 Luna at low reasoning and also removed inherited desktop thread and tool
pipe identifiers from the child environment. It again failed before reading the README with the
same socket-directory error. The transcript records one shell attempt, zero explicit file reads,
and 34,316 input tokens. The disposable project was removed. This rejects the theory that inherited
desktop session identifiers alone caused the failure; it does not identify a supported socket
override.

Retry evidence: [JSONL transcript](2026-10-05-runner-socket-isolation-retry.jsonl).

## Successful run outside the enclosing sandbox

The same disposable run succeeded when the launcher itself ran outside the enclosing Codex shell
sandbox, while the child Codex session retained its own read-only sandbox. GPT-6 Luna at low
reasoning ran one shell command, read `README.md`, reported “Daybook,” and made no changes. The
helper removed the project and its isolated environment at process exit.

The saved transcript reports one shell command and one recognized simple shell read path (`README.md`),
zero explicit file-read events, and 34,587 input tokens. This confirms the failure was specific to
nesting the Codex runner inside the outer sandbox. It does not verify the harness plugin or hooks.
Transcript: [runner success](2026-10-05-runner-escalated-success.jsonl).
