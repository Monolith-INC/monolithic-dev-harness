# Installed desktop question dismissal investigation

Date: 2026-10-05. Read-only inspection; no installed app changes.

## Evidence and conclusion

Installed archive: `/usr/lib/chatgpt/resources/app.asar`.
Package: `openai-codex-electron`, version `26.928.40906`, read from the archive package.json.
Inspected application code is copied under `/tmp/codex-question-source`.

In `app-initial-e01dcc01f03e.js`, function `tPt` initializes an asynchronous question deadline
at the supplied current time plus 30,000 milliseconds. Interaction handlers `nPt`, `rPt`, and
`iPt` clear that deadline when selecting/editing the question. Function `sPt` clears the selected
question panel without recording a human answer.

In `app-primary-e604abe154dc.js`, question panel `zqe` schedules `qde` with dismissal reason
`timeout` for the saved deadline. It returns no visible panel unless the turn status is
`inProgress`. The import/export aliases map `qde` to `e1s` in the initial bundle. That function
calls `sPt` and records a dismissal reason.

In the initial bundle, function `a1s` subscribes to the `turn/completed` event. When the selected
question belongs to that turn, it calls `e1s` with reason `turn_completed`. Thus the installed
app explicitly dismisses an unanswered asynchronous question when its turn finishes, independently
of the 30-second timer. No button click or later assistant message is required.

This explains the failure of the proposed immediate-end-turn button workflow on this app version.
The static code proves both dismissal conditions exist; without a correlated UI event trace it
does not prove which condition fired for each reported disappearance. The actual live reports
include disappearance with and without an assistant message, and the human confirmed no click.

## Documentation cross-check

Context7 `/openai/codex` surfaced a similar 30-second timer in the terminal interface. That alone
was not desktop proof; the installed desktop bundle provides separate direct evidence above.
Official OpenAI documentation describes cleanup on turn completion for the separate blocking
`tool/requestUserInput` protocol, and permits an optional auto-resolution timeout:
https://learn.chatgpt.com/docs/app-server
The Responses API asynchronous-tool guide describes application-owned lifecycle behavior, not
the desktop implementation inspected here:
https://developers.openai.com/api/docs/guides/async-tool-calling

## Implication for the harness

Keep pending human decisions independent of UI visibility. Never interpret dismissal, timeout,
or turn completion as consent. The candidate instruction to end the turn immediately preserves
workflow waiting but cannot preserve these native buttons. The host adapter must mark persistent
native buttons unsupported on this version, or provide a supported blocking interaction that
retains the UI while awaiting the real reply. Do not try to disable this app timer using an
invented tool argument; the exposed asynchronous tool has no timer parameter. No new live test
was launched; accumulate timer expiry, turn completion, unrelated-message, restoration, and
actual-answer cases for the next focused test batch, using the same prepared project.

## Bundle hashes
- `app-initial-e01dcc01f03e.js`: SHA-256 `2e3f80785abb47819d9958c96d6c7e233259d187e7b39cdf644daab473119a4d`
- `app-primary-e604abe154dc.js`: SHA-256 `1d3cc9de7029e9c83c01cece0640fc7836094099e70434c45ec2f6b9e21a3797`
