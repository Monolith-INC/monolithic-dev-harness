# Bundled agile-backlog-toolkit source

## Provenance

- Upstream project: `agile-backlog-toolkit` (local source `/home/monolith/projects/agile-backlog-toolkit`)
- Version 0.12.1, source revision `e7ae82c31771a0ccda22c21858eee066168de1f2`, clean tree, copied 2026-10-16
- License: MIT; see [LICENSE](LICENSE).

## Files in this repository

`upstream/` holds the source exactly as it is: the nine backlog skills under `upstream/skills/`,
and the shared `upstream/references/` and `upstream/common/` they read.

The harness runs the copies under `../../skills/<name>/`. Each was copied over from `upstream/`
and then aligned only where the source conflicts with the harness contract
([`CONSTITUTION.md`](../../../../CONSTITUTION.md)). Every phase, rule and approval step not listed
below runs as the source wrote it.

| Seam | Source | Harness copy |
| --- | --- | --- |
| Tracker reads and writes | Azure DevOps MCP tools (`wit_*`), Azure field names, Linear branches | the gateway's `tracker_*` tools and harness kinds (Article 7); per-tracker notes live in `trackers/<name>/notes/` |
| Destination | asked (`filesystem` / `azure` / `both`) | always the selected tracker; never asked |
| Paths | `bin/agile-backlog-toolkit config --show`, `<artifacts>/Implementation_Plans/YYYY-MM-DD-…`, `<artifacts>/Tickets/Ready/…`, `.agile-backlog-toolkit/reports/` | `harness document path` (Article 8a), `Tickets/Ready/` at the project root, `.harness/backlog/reports/` |
| Confirmations | WAIT points and selection lists | harness gates: `refinement-split`, `publish-items`, `implementation-confirm` (required, before Tasks), `approve-document` (Article 6) |
| Breakdown Task | assignee and Done set by Azure field writes | sprint and assignee copied by the gateway; Done through `tracker_transition_work_item` |
| A Story without a parent | breakdown stops | valid; planned from the Story alone |
| Renaming after creation | drafts renamed to `<id>-<slug>.md` | names given by `harness document path` are kept |

Fixed source slips: relative paths to `../../references/` from inside `references/`, the
`backup-and-ledger.md` and canonical-template links, and the auto-fix body sections, which now
follow the canonical templates (Article 3).

To sync a new version: copy `upstream/` again, copy each skill over `../../skills/<name>/`, and
re-apply the seams above; `tests/harness/test_tracker_neutral.py`,
`tests/harness/test_no_stale_rules.py` and `tests/delivery/contract/` flag what was missed.
