# Bundled BMad source

## Provenance

- Upstream project: <https://github.com/bmad-code-org/BMAD-METHOD>
- Source revision: `1cbcfa272fe65787c06a1fa164a901f46117cca7`
- License: MIT; see [LICENSE](LICENSE), [CONTRIBUTORS.md](CONTRIBUTORS.md), and
  [TRADEMARK.md](TRADEMARK.md).

## Files in this repository

The source copies are kept under `upstream/skills/`. One excess blank line at end of the PRD template was removed to satisfy the repository whitespace check; all other source content is preserved. Runtime manifests replace upstream update links with `plugin:monolithic-dev-harness`, so setup recognizes these skills as plugin-managed and never offers a network download:

- `upstream/skills/bmad-build/` — full BMad Build workflow, its review prompts, and templates.
- `upstream/skills/bmad-spec/` — optional BMad spec skill.
- `upstream/skills/bmad-architecture/` — optional BMad architecture skill.
- `upstream/skills/bmad-prd/` — detailed product-requirements skill.
- `upstream/skills/bmad-party-mode/` — group discussion skill.
- `upstream/skills/bmad-advanced-elicitation/` — structured review and refinement methods.
- `upstream/skills/bmad-review/` — review lenses used by BMad PRD, discovery Deepen, and Verify.
- `upstream/skills/bmad-correct-course/` — change-of-direction impact analysis.
- `upstream/skills/bmad-project-context/` — repository agent-instruction setup and audit.
- `upstream/skills/bmad-deep-recon/` — verified research and reconnaissance.
- `upstream/skills/bmad-qa-generate-e2e-tests/` — API and end-to-end test generation.

Runtime support copied from the same source revision is under `skills/`. Its package manifests are adapted to describe only the bundled skills; upstream links are removed from runtime metadata so setup cannot offer a download path:

- `skills/bmad/` — setup, renderer, configuration, and shared runtime scripts.
- `skills/bmad-ticket/` — BMad's local ticket-store support; kept internal to the bundle.
- `skills/bmod-method/` — local package manifest listing only the bundled runtime skills; it ships in the plugin's `skills/` folder, beside the skills it describes, because BMad looks for it there.

Harness-exposed copies are under `../skills/`:

- `../skills/bmad-build/` — adapted for technical discovery only. It uses bundled setup,
  accepts tracker data through the harness read-only interface, stops after plan approval, and
  hands the approved plan to the harness backlog stage.
- `../skills/bmad-spec/`, `../skills/bmad-architecture/`, `../skills/bmad-prd/`,
  `../skills/bmad-party-mode/`, `../skills/bmad-advanced-elicitation/`, `../skills/bmad-review/`,
  `../skills/bmad-correct-course/`, `../skills/bmad-project-context/`, `../skills/bmad-deep-recon/`,
  and `../skills/bmad-qa-generate-e2e-tests/` — source-backed skills whose setup instructions point
  to the bundled runtime and run scripts with the bundled Python. Subagent use, memlogs, and party
  memory are kept as upstream ships them. Harness adaptations: bundled setup instead of
  downloads; `bmad-correct-course` also accepts a discovery plan and routes work-item changes to
  harness backlog skills; `bmad-qa-generate-e2e-tests` defers code review to `review`/`thermos`
  and installs no extra modules; party mode defaults to `auto` and does not author saved parties.
  None starts implementation or writes tracker items.

## Runtime boundary

The harness plugin contains all source needed for this route. The pristine upstream manifests remain under `upstream/`; runtime manifests identify a local package made from the selected files. The local package lists thirteen bundled skills and has no remote update source. Runtime setup reads these bundled
files and may copy runtime configuration and scripts into the governed project. It must not read a
separate BMad checkout, install BMad from a package registry, or download BMad files. The harness
continues to own tracker writes, implementation, and verification.

Python 3.11 or later, `uv`, and the renderer's declared Jinja dependency are required to run the
BMad-backed route. These are local workflow requirements; they do not raise the harness-wide
Python minimum.
