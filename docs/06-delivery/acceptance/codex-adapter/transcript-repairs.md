# Transcript repair acceptance

This checklist records the bounded offline acceptance for the 2026-10-26 harness repairs. It does
not qualify a live host installation or Azure OAuth session.

- [x] Existing gateway owner serves local CLI and hook reads over a same-user private socket.
- [x] A second owner fails closed; clients do not spawn provider processes.
- [x] Provider exit, EOF, timeout and read failure remain distinct; terminal failures do not relaunch
      OAuth, and owner death terminates its owned process group.
- [x] Async human replies correlate to the staged lifecycle question and exact conversation; model
      hook payloads do not count as answers.
- [x] Planning choices survive interruption; finish, reopen, catalog paging and accepted method
      outcomes require captured human replies.
- [x] Current-round gates require depth, selected-method outcomes and review artifacts matching the
      approach being approved.
- [x] Plan approval is tied to the current tracked Story digest; successful writes require readback,
      and published-item progress matches the approved `key:`/`title:` identity list/count and the
      current digest of every item in that batch, including provider-assigned keys for new items.
- [x] Task completion requires per-Task verification evidence; audit is read-only.
- [x] Selected local provider-conflict repair backs up original configuration and leaves unrelated
      registrations unchanged; future-control language preference does not alter artifact language.
- [x] Release archive contains every new runtime module; each required payload file matches the
      committed source SHA-256.

Offline verification completed on Python 3.12. The affected harness/integration suite passed
227 tests. The additional transport, delayed-answer, lifecycle, session, installation-scope and
delivery-hook contract suite passed 88 tests; these counts overlap and are not summed. The final
route/chooser change passed its 20-test subset. Ruff on all changed Python files, JSON/TOML parsing,
shell syntax and whitespace checks passed. `bash scripts/build_release.sh` built the local RC9
archive and verified required payload files against committed source digests. The archive is a
local verification artifact, not a published release.

The independent review found four Important issues in provider cleanup, publication source/draft
identity validation and durable-selection route integration. The fix pass added regressions for
SIGTERM-ignoring providers, stale batch members, new item title-to-key mapping and route selection;
the affected suites above passed afterward. No Critical or deferred Minor findings were reported.

Live OAuth, installed-host reload, cross-process owner recovery in a real host, and Azure readback
remain unverified until separately performed against a disposable installation. That acceptance
must exercise `next`, implementation-confirm preparation, tracking and linking through the shared
owner, followed by outage recovery and native lifecycle capture. A standalone gateway read does
not qualify those paths.
