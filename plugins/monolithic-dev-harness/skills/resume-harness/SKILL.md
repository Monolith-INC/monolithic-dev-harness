---
name: resume-harness
description: Turn the harness checks back on in this repository after suspend-harness. Use when the user asks to resume, re-enable, or restore the harness (/resume-harness).
---

# Resume harness

Run `harness policies resume --repo <project>` (or the sibling `bin/harness` from this plugin), then
confirm with `harness policies status --repo <project>` that it reports `"mode": "active"`.

From then on every harness check applies again. Resuming opens no approval window and does not
accept work done while suspended as reviewed: work started outside the harness needs a session
(`start-ticket`) or `adopt-existing-implementation` before it continues under the workflow. Run
`harness doctor` if the settings or tracker changed while the checks were off.
