# Third-party notices

`monolithic-dev-harness` is assembled from the sources below. Each was copied from a committed
revision (not a working tree) and adapted in place. License texts are in
`plugins/monolithic-dev-harness/licenses/`.

| Component in the harness | Source | Revision | License |
| --- | --- | --- | --- |
| Backlog skills, `common/`, `references/`, `runtime/orchestrator_core/`, `tests/backlog/` | agile-backlog-toolkit | `e7ae82c` | MIT (`agile-backlog-toolkit.LICENSE`) |
| Delivery skills, `scripts/` (policy, Claude and Cursor host adapters, orchestrator), `tests/delivery/` | codex-workflows-plugin (Monolith-INC) | `75c22f0` | no license file in the source repository; internal |
| `review-story-preflight`, `review-setup`, `review-typescript`, `review-maintainability`, `triage-pr-comments`, `respond-pr-comments` | monolithic-code-review-toolkit (Monolith-INC) | `9f3c6a4` | MIT (`monolithic-code-review-toolkit.LICENSE`) |
| `thermos`, `thermo-nuclear-review`, `thermo-nuclear-code-quality-review`, `agents/thermo-*` | thermos-claude (Claude adaptation of cursor/plugins `thermos`) | HEAD at copy time | MIT (`thermos.LICENSE`) |
| `deslop`, `verify-this`; adapted: `check`, `branch-and-pr` | cursor/plugins `cursor-team-kit` | `46756f8` | MIT (`cursor-team-kit.LICENSE`) |
| `prove-it-works`, `sequence-verifiable-units`, `architect/references/*`; adapted: `architect`, `tdd` | cursor/plugins `pstack` (Lauren Tan) | `46756f8` | MIT (`pstack.LICENSE`) |
| `plan-initiative`, `brainstorm-ideas`, `forge-idea`, `research-decision`, `product-brief`, `product-requirements`, `experience-design`, `architecture-spine`, `product-spec`; `references/planning-artifacts.md` | BMad Method (BMad Code, LLC) | `1cbcfa2` | MIT (`bmad-method.LICENSE`) |
| `azure-devops` skill | workstation `azure-devops-mcp` skill (Claude and Codex ports) | 2026-08-27 | internal |

Written for the harness: `harness`, `implement-story`, `review`, `bootstrap` (rewritten),
`onboard-tracker`, `start-ticket` (rewritten), `scripts/harness/` (the harness rules, hook entry
point, settings, sessions, checks, verdicts, bootstrap), `scripts/core/`, `scripts/integrations/`
(rewritten in 0.2.0: tracker contract, registry, trust, gateway, transport, SCM adapters),
`trackers/` (the Azure DevOps, Linear, and local adapters, rewritten in 0.2.0), `tests/harness/`,
`tests/core/`, `tests/integrations/`, the manifests, and the hook and MCP configuration.
