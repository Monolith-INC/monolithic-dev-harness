# App-based lower-tier interactive trial

Date: 2026-10-05
Status: first route failed; later app-side run completed through local draft review

## Attempt and outcome

The first attempt launched a separate Codex command-line process with candidate
`monolithic-dev-harness` 0.5.3, GPT-6 Luna, and low reasoning. It read DAY-001 and prepared a complete
proposal, then called the blocking `request_user_input` control with Continue and Stop choices. The
control appeared only inside that separate process. It was not visible in the user's Codex app, and
the app showed no active subagent for it. The process was stopped without choosing an answer. Its
temporary project was removed.

The user clarified that the live test must run in the Codex app, not in a terminal. A real app
subagent was then started with GPT-6 Luna at low reasoning. Its app view reported no open app
windows or available app tabs, so it could not enter or verify an app session. It did not launch a
terminal or run the harness. No app-based live run has passed.

## Terminal trial evidence

- Installed candidate: `monolithic-dev-harness` 0.5.3 through the supported installer.
- Model and effort: GPT-6 Luna, low reasoning.
- Harness proposal gate: reached; the complete DAY-001 proposal was displayed and the blocking
  control offered Continue and Stop.
- User-visible result: failure. The child session's native control was isolated from the app thread.
- Human answer: none. The unanswered control was aborted when the hidden process was stopped.
- Changes to source, test project, tracker, or work items: none observed.
- Temporary project: removed after the process exited.
- Successful direct file displays: 15 over 15 unique paths, from seven completed shell commands.
  Two shell commands failed and are not counted as reads. The 15 paths include three harness
  references and twelve project files. File searches are not counted.
- Transcript: [interactive trial transcript](2026-10-05-interactive-lower-tier-question-visibility.jsonl).
- Model usage recorded by the child session: 221,420 input tokens (187,136 cached), 2,009 output
  tokens, and 414 reasoning tokens.

The transcript reader did not recognize the Codex app-session JSONL event format and reported zero
reads. The 15-read count above was recomputed from completed command events with successful direct
file-display operations. Add this transcript format to the reader before relying on automated read
counts for app-originated sessions.

## Next test requirement

Retry only through a user-visible Codex app session. Before starting discovery, verify that the
lower-tier agent and its active session appear in the app. At the review gate, surface the complete
proposal and choices in the user's current app conversation, then wait for the actual answer. If the
app session cannot be reached, record a blocker and do not substitute a hidden terminal process.

## Correction after the app-side trial

The prior “no app window” result was misread. It described the subagent's computer-use visibility,
not whether it could run as an app subagent or have the main session surface a question. The user
confirmed this is the intended design: subagents send their decision to the main session, which
shows the native question and waits for the real answer. The later main-session-bubbled run did this
for proposal review and revision requests. See
[the app-side run report](2026-10-05-main-session-bubbled-run.md).
