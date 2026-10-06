---
name: resume-harness
description: Turn the harness checks back on in this repository after the user suspended them. Use when the user asks to resume, re-enable, or restore the harness (/resume-harness).
---

# Resume harness

Run `harness suspension resume --repo <project>` (or the sibling `bin/harness` from this plugin),
then confirm with `harness suspension status --repo <project>` that it reports `"mode": "active"`.
If the command is refused, for example because the settings are invalid, ask the user to send
`harness resume` as its own message.

From then on every harness check applies again. Resuming opens no approval window and does not
accept work done while suspended as reviewed: work started outside the harness needs a session
(`start-ticket`) or `adopt-existing-implementation` before it continues under the workflow. Run
`harness doctor` if the settings or tracker changed while the checks were off.
