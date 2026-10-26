---
name: suspend-harness
description: Help the user suspend every harness check or restore it using native controls with graceful fallback.
---

# Suspend harness

Present `harness decision present --gate harness-controls --repo <project>` and use the returned
native control. This control channel is independent of pending work, sessions and setup. Only a
real human reply changes suspension. Never write suspension records or fabricate an answer.

If delivery fails, repeat this same gate with `--async-available`, then `--native-unavailable`.
Do not use another pending work question as the fallback. The chat labels are recognized directly:
Suspend harness, Resume harness, Free mode (and their pt-BR equivalents). A plain or fenced
`harness suspend` user message also works; do not insist on magic formatting.

Verify with `harness suspension status --repo <project>`. While suspended, every harness veto is
off, including protected-record, hook-entry, session, tracker, branch and decision-wait checks.
Host permissions and other plugins remain independent. Question evidence may be observed, but
observation cannot veto a tool or grant an unreviewed approval. Preserve existing work and evidence.

Resume restores checks without accepting changed artifacts or opening an unrelated permission.
Free mode means direct skill use without guided onboarding; it preserves action governance.
`skip-tracker` pauses only tracker enforcement. Workflow pause preserves preparation progress.
