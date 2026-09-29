---
name: commit-prep
description: Prepare atomic commits for the current work.
---

# Commit prep

Group completed work into small, verifiable commits with a clear message and scope.

For a staged path configured with `manual:<name>` evidence, show the exact staged diff and ask one
chat question with **Approve change** and **Not now** buttons. The harness pins the staged tree before
showing the question and records the manual check only when the user clicks **Approve change** while
that tree is unchanged. Cursor has no supported button flow, so use the typed phrase reported by the
guarded-path error there. Never alter working files or the index merely to get a commit hook through.
