---
type: implementation-plan
status: in-progress
created: 2026-10-02
spec: [[2026-10-02-technical-first-stage-zero]]
source_revision: 1cbcfa272fe65787c06a1fa164a901f46117cca7
---

# Assimilate BMad's ticket-to-build planning into Stage 0

## Intent

Move technical discovery for an assigned, incomplete request ahead of backlog creation. Use BMad's
existing clarify, investigate, plan, and review method, then hand the accepted strategy to the
harness's existing backlog and delivery stages. Product ideation stays available as an optional
route.

This plan describes source assimilation and harness integration. It does not authorize starting
the paused live trial.

## Source inventory

The inspected BMad source checkout is at revision
`1cbcfa272fe65787c06a1fa164a901f46117cca7` (`feat(bmad): setup cleans up renamed and removed
skills; help loads only for help requests (#2981) (#2983)`). Its working tree was clean.

| Source component | What it provides | Planned treatment |
| --- | --- | --- |
| `skills/bmad-build/` | Complete five-step build workflow, clarify-and-route, codebase investigation and plan, plan template, review prompts, and package configuration | Preserve the full source tree under `vendor/bmad/upstream/` and maintain the adapted host integration under `skills/`. Stage 0 uses its intake, planning, and review steps before backlog. Later build steps must hand off to existing harness delivery rather than bypassing its gates. |
| `skills/bmad/` | Renderer, configuration and customization tools, setup checks, project config template, and setup guidance | Copy the required source files into this repository and use the bundled setup script to materialize project runtime files. Remove instructions that install or fetch BMad from GitHub at runtime. |
| `skills/bmad-ticket/` | Ticket-tree scripts, schemas/templates, store instructions, and breakdown references | Bring the source files needed by BMad Build's ticket-tree lookup. Use the harness's existing tracker read path for Azure DevOps, Linear, and other external tickets; do not call ticket mutation commands during Stage 0. |
| `skills/bmad-spec/`, `skills/bmad-architecture/`, `skills/bmad-prd/`, `skills/bmad-party-mode/`, `skills/bmad-advanced-elicitation/`, and `skills/bmad-review/` | Optional requirements, architecture, group discussion, and structured review workflows, with their templates, references, and scripts | Preserve each pristine package under `vendor/bmad/upstream/`; bundle adapted copies under `plugins/monolithic-dev-harness/skills/`. BMad Build uses PRD only for unclear user behavior and the other two as optional review support. |
| `skills/bmod-method/bmod.toml` | Method module metadata for BMad package discovery | Preserve the pristine manifest under `vendor/bmad/upstream/`; use an adapted local manifest that lists only the nine bundled skills and contains no upstream source links. |
| `LICENSE` | MIT terms, BMad Code, LLC copyright, and trademark notice | Keep `plugins/monolithic-dev-harness/licenses/bmad-method.LICENSE` aligned with the source and retain attribution in the imported-package documentation. |

The BMad Build skill invokes `uv` to run its renderer. The renderer requires Python 3.11 or newer
and `jinja2>=3.1`; its other runtime scripts use Python 3.11 standard-library `tomllib`. BMad Build
expects project files under `_bmad/` for the shared renderer/config scripts and method ticket script,
with plan output under the configured output folder. The harness currently supports Python 3.10+,
so installation and runtime behavior on Python 3.10 must be addressed explicitly rather than
silently raising the harness-wide minimum.

## Delivery order

1. **Pin and stage the source package.** Copy source files from the recorded BMad revision, keep
   upstream paths, manifests, templates, references, review prompts, and scripts intact, and retain
   license and attribution. Add a small source map listing each copied file, upstream path, revision,
   and any harness overlay. Keep every required BMad source file inside this repository and the
   shipped harness package. Do not include unrelated BMad modules.
2. **Provide the required BMad runtime.** Use BMad's own setup/materialization behavior to make the
   renderer, config, and ticket-tree scripts available inside a governed project from the bundled
   source. Runtime must not read or download from the BMad checkout. Preserve team and user
   configuration boundaries and existing project files. Keep the imported source scripts
   identifiable and avoid a second hand-written config or template engine. Resolve how `uv` and
   Python 3.11 are supplied without changing the harness's global Python minimum.
3. **Connect request intake safely.** Route an assigned ticket through the existing tracker adapter
   in read-only mode and give the source workflow its request, parent context, and revision. Retain
   BMad's local ticket-tree route where that store is selected. Verify that intake performs no
   tracker writes, branch creation, or implementation start.
4. **Place Stage 0 before backlog.** Update the harness route so assigned or draft feature requests
   enter the assimilated BMad investigation and strategy review. Keep `plan-initiative` and its
   discovery skills available when the user chooses ideation. After strategy approval, hand off to
   existing backlog creation. Keep existing technical planning, implementation, and verification
   gates in force; prevent BMad Build's later steps from bypassing them.
5. **Connect artifacts and pause/resume.** Preserve the source plan format and state needed to resume
   BMad's steps. Record the accepted strategy and its reference in the harness checkpoint and
   subsequent backlog inputs. Select the project artifact location and tracker-link behavior before
   wiring publication; do not make an external write during Stage 0.
6. **Verify source fidelity and harness behavior.** Retain or adapt upstream runtime tests for copied
   scripts. Add harness tests for runtime setup, source-version/license presence, safe read-only
   intake, optional ideation routing, strategy approval before backlog writes, resume behavior, and
   handoff into the existing workflow. Check that all three host packages contain the imported
   source and overlays.

## Acceptance checks

- An assigned, incomplete request reaches BMad's technical investigation by default; ideation is
  chosen only when requested or when the intended outcome is not yet identifiable.
- The imported BMad Build folder and required supporting files are traceable to the pinned source
  revision, with required license and attribution preserved.
- A clean project can render and run the imported workflow using the documented runtime without a
  separate, user-managed BMad installation.
- Python 3.10 users receive a clear, bounded runtime result; no silent harness-wide version change
  occurs.
- Ticket intake reads through the configured source and does not alter tracker state or start
  implementation.
- The strategy includes a code map, recommendation and alternatives, assumptions, risks, open
  product decisions, implementation slices, and checks, proportionate to scope.
- Backlog writes remain blocked until the complete strategy is reviewed and approved.
- Approved strategy is carried forward without repeating investigation or changing decisions.
- BMad implementation steps cannot bypass the harness's existing session, testing, review, and
  approval gates.
- Existing product-ideation behavior remains available as an explicit optional route.

## Decisions settled by the user

- Vendor the needed BMad source files inside the Monolithic Dev Harness repository and ship them
  with the harness. Runtime must not depend on the BMad source checkout or fetch BMad files from it.
- Set up the project runtime through the harness using the bundled BMad setup behavior. The source
  setup may materialize its runtime files into a governed project, but those files must come from
  the harness's own bundle.
- Preserve BMad's own planning method, then hand the reviewed plan to the harness backlog flow.

## Decisions resolved during implementation

- **Python and `uv`:** Keep these requirements local to the BMad-backed route. The harness-wide
  Python minimum stays unchanged. If `uv` or Python 3.11 is unavailable, the route must stop with a
  clear setup message rather than fetch BMad source or silently run an alternate renderer.
- **Strategy storage:** Keep BMad's native `_bmad-output` location for fidelity to its workflow. The
  harness checkpoint records the approved plan path and digest; tracker references are read-only
  input and are not written by Stage 0.
- **Source workflow boundary:** Stage 0 ends after review and approval of BMad's plan. It checkpoints
  and hands the plan to harness backlog drafting. Later BMad implementation/review/present steps
  remain bundled reference material and cannot bypass harness delivery controls.
- **Conditional skills:** Bundle spec, architecture, PRD, party discussion, and advanced elicitation.
  The build workflow may use PRD for focused requirements clarification and the review, elicitation,
  and party skills as optional support. Keep setup and ticket-store packages internal to the plugin.

## Implementation decisions

- Keep the original BMad Build package under `vendor/bmad/upstream/skills/bmad-build/`; expose its
  harness-integrated copy under `skills/bmad-build/`. The source map will record every adapted
  file. Keep the BMad core and ticket-management packages under `vendor/` so the harness can use
  their runtime scripts without exposing BMad's independent setup or tracker-write flows as
  competing host skills.
- Keep the selected BMad source files and license in this repository. At run time, invoke the
  bundled BMad setup script with the bundled skill roots; it may materialize scripts/config in the
  governed project, but it must not access the original checkout or fetch BMad from GitHub.
- Record source revision, pristine source paths, adapted skill paths, runtime boundaries, and license
  documents in `plugins/monolithic-dev-harness/vendor/bmad/SOURCE-MANIFEST.md`.
- Stage 0 ends after BMad's investigation plan is reviewed. On approval, pass that plan into the
  harness backlog flow. BMad's remaining build steps stay bundled as source reference but cannot
  bypass harness implementation and verification gates.

## Risks

- BMad's source setup assumes its own `_bmad/` configuration and ticket tree. A partial runtime copy
  can fail only after a user starts the workflow unless clean-project setup is covered explicitly.
- BMad Build's intended code implementation and review steps overlap the harness's later workflow.
  An unclear handoff could duplicate planning or skip a harness gate.
- `uv` and Python 3.11 requirements may not be satisfied on every supported host. Report this as a
  workflow dependency, not as a reason to rewrite the source scripts.
- Upstream updates can change the renderer, manifests, or workflow. The source map and tests must
  make local overlays and version drift visible.

## Evidence consulted

- BMad source revision: `/mnt/DATA/Projects/Corporate/BMAD-METHOD` at
  `1cbcfa272fe65787c06a1fa164a901f46117cca7`.
- `skills/bmad-build/` including its source manifest, renderer call, five workflow steps, plan
  template, references, and review prompts.
- `skills/bmad/` setup instructions, setup script, runtime scripts, and config template.
- `skills/bmad-ticket/` manifest, ticket scripts, store references, and ticket templates.
- `skills/bmod-method/bmod.toml`, `skills/bmad-spec/`, `skills/bmad-architecture/`, `skills/bmad-prd/`,
  `skills/bmad-party-mode/`, `skills/bmad-advanced-elicitation/`, `skills/bmad-review/`, and upstream `LICENSE`.
- Harness Stage 0 and delivery routing in `plugins/monolithic-dev-harness/skills/harness/SKILL.md`,
  `plan-initiative/SKILL.md`, `start-ticket/SKILL.md`, `resolve-ticket/SKILL.md`, and
  `write-spec/SKILL.md`.
- Thermos assimilation files and `plugins/monolithic-dev-harness/licenses/bmad-method.LICENSE`.

## Issues during this review

| Workflow point | What went wrong | Effect | Recovery or current state |
| --- | --- | --- | --- |
| Pinning the BMad source | Git refused the first read-only revision lookup because the source checkout has a different owner. | The source revision was not identified by that command. | Re-ran the read-only Git commands with a one-command `safe.directory` setting; recorded the clean source revision above. No global Git setting was changed. |
| Checking the existing license copy | A byte comparison found the existing harness license file used adapted link text and a shortened trademark notice. | It was not an exact copy of the upstream license. | Replaced it with the upstream license text, changed only the two relative links to bundled upstream documents, and copied `CONTRIBUTORS.md` and `TRADEMARK.md` into the repository. |
| Adjusting the bundled license links | The first helper command assumed a `python` executable was available, but only `python3` is installed. | The two relative links were not updated by that attempt. | Repeated the local edit with `python3`; the file now points to the bundled attribution and trademark documents. |
| Updating workflow documentation | A patch did not match the current paragraph text. | The documentation edits were not applied by that attempt. | Re-read the current files and retry with smaller, exact-context changes. |
| Checking optional skill handoffs | A command string failed to parse before execution. | The search did not run and no files changed. | Reissued the check with a simpler command and recorded its results. |
| Copying the added BMad skills | The filesystem rejected source permission preservation during the first copy. | The upstream PRD folder may have been only partly copied; the active copies were not started. | Remove only the newly created partial destination folders and recopy file contents without preserving source permissions. |
| Adapting bundled agent instructions | A helper script had an unescaped quote in one replacement string and did not start. | None of its intended workflow edits were applied. | Re-run the edits with safely delimited strings; no files were changed by the failed script. |
| Adapting local reviewer and party instructions | A patch expected wording that differed from the copied source. | The patch made no changes. | Re-read the exact active skill wording and apply the change with direct string replacement. |
| Checking the local bundle manifests | The host's `python3` lacks the standard-library TOML reader required by the check. | The manifest parser check stopped before reading any files; subsequent text searches still ran. | Confirm manifest membership by direct inspection. The bundled BMad runtime itself explicitly requires Python 3.11 or newer. |
| Staging the approved changes | The workspace sandbox made the repository's Git index read-only. | Git could not create `.git/index.lock`, so no files were staged. | Retry staging with the authorized Git metadata access; keep the unrelated example-project edits excluded. |
| Checking the staged changes | Git reported extra blank lines at the ends of three bundled source files. | The staged whitespace check did not pass. | Remove only the extra end-of-file blank lines, record that source normalization, and rerun the check. |
