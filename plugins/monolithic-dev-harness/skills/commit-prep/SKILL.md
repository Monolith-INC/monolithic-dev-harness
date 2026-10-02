---
name: commit-prep
description: Prepare atomic commits for the current work.
---

# Commit prep

Group completed work into small, verifiable commits with a clear message and scope.

For a staged path configured with `manual:<name>` evidence, show the exact staged diff and ask one
question UI with **Approve change** and **Not now** choices. The harness pins the staged tree before
showing the question and records the manual check only when the user clicks **Approve change** while
that tree is unchanged. If the host cannot show clickable choices, stop without recording approval
or committing. Never replace the choice with a typed phrase, or alter working files or the index
merely to get a commit hook through.
