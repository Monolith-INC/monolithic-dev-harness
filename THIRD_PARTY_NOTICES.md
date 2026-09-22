# Third-party notices

`monolithic-dev-harness` is assembled from the sources below. Each was copied from a committed
revision (not a working tree) and adapted in place. License texts are in
`plugins/monolithic-dev-harness/licenses/`.

| Component in the harness | Source | Revision | License |
| --- | --- | --- | --- |
| Backlog skills, `common/`, `references/`, `runtime/orchestrator_core/`, `tests/backlog/` | agile-backlog-toolkit | `e7ae82c` | MIT (`agile-backlog-toolkit.LICENSE`) |
| Delivery skills, `scripts/` (policy, integrations, Claude and Cursor host adapters, orchestrator), `scripts/harness/integrations_setup.py` (extracted from its installer), `tests/delivery/` | codex-workflows-plugin (Monolith-INC) | `75c22f0` | no license file in the source repository; internal |
| `review-story-preflight`, `review-setup`, `review-typescript`, `review-maintainability`, `triage-pr-comments`, `respond-pr-comments` | monolithic-code-review-toolkit (Monolith-INC) | `9f3c6a4` | MIT (`monolithic-code-review-toolkit.LICENSE`) |
| `thermos`, `thermo-nuclear-review`, `thermo-nuclear-code-quality-review`, `agents/thermo-*` | thermos-claude (Claude adaptation of cursor/plugins `thermos`) | HEAD at copy time | MIT (`thermos.LICENSE`) |
| `deslop`, `verify-this`; adapted: `check`, `branch-and-pr` | cursor/plugins `cursor-team-kit` | `46756f8` | MIT (`cursor-team-kit.LICENSE`) |
| `prove-it-works`, `sequence-verifiable-units`, `architect/references/*`; adapted: `architect`, `tdd` | cursor/plugins `pstack` (Lauren Tan) | `46756f8` | MIT (`pstack.LICENSE`) |
| `azure-devops` skill | workstation `azure-devops-mcp` skill (Claude and Codex ports) | 2026-08-27 | internal |

Written for the harness: `harness`, `implement-story`, `review`, `bootstrap` (rewritten),
`scripts/harness/` (the harness rules, hook entry point, checks, verdicts, bootstrap), `tests/harness/`,
the manifests, and the hook and MCP configuration.
