# Transcript repair acceptance

This checklist records the bounded offline acceptance for the 2026-10-26 harness repairs. It does
not qualify a live host installation or Azure OAuth session.

- [ ] Existing gateway owner serves local CLI and hook reads over a same-user private socket.
- [ ] A second owner fails closed; clients do not spawn provider processes.
- [ ] Provider exit, EOF, timeout and read failure remain distinct; terminal failures do not relaunch
      OAuth, and owner death terminates its owned process group.
- [ ] Async human replies correlate to the staged lifecycle question and exact conversation; model
      hook payloads do not count as answers.
- [ ] Planning choices survive interruption; finish, reopen, catalog paging and accepted method
      outcomes require captured human replies.
- [ ] Current-round gates require depth, selected-method outcomes and review artifacts matching the
      approach being approved.
- [ ] Plan approval is tied to the current tracked Story digest; successful writes require readback,
      and published-item progress matches the approved `key:`/`title:` identity list/count and the
      current digest of every item in that batch, including provider-assigned keys for new items.
- [ ] Task completion requires per-Task verification evidence; audit is read-only.
- [ ] Selected local provider-conflict repair backs up original configuration and leaves unrelated
      registrations unchanged; future-control language preference does not alter artifact language.
- [ ] Release archive contains every new runtime module.

Record the exact targeted test command and output below before treating offline acceptance as
complete. Live OAuth, installed-host reload, cross-process owner recovery in a real host, and Azure
readback remain unverified until separately performed against that installation.
