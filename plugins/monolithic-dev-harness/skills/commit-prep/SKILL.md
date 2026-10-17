---
name: commit-prep
description: Prepare atomic commits for the current work.
---

# Commit prep

Group completed work into small, verifiable commits with a clear message and scope.

## In the harness

Commits are made only with Git-based delivery. For a changed path configured with
`manual:<name>` evidence, show the exact change and ask one question with **Approve change** and
**Not now** choices. The harness pins the code as it is before showing the question and records the
manual check only when the user clicks **Approve change** while that code is unchanged. If the host
cannot show clickable choices, stop without recording approval or committing. Never alter working
files or the index merely to get a commit hook through.
