---
name: bmad-build
description: 'Harness adaptation of BMad Build for technical discovery of assigned or draft feature work. Investigates the repository and produces a reviewed implementation plan before backlog creation. It does not start implementation; the harness owns later stages.'
---

This copy is bundled with the Monolithic Dev Harness. Do not install or fetch BMad from another
repository. Before rendering the workflow, prepare its project runtime from the bundled source:

```bash
uv run --no-cache "{skill-root}/../../vendor/bmad/skills/bmad/scripts/setup.py" --project-root "{project-root}" --skill "{skill-root}/../../vendor/bmad/skills/bmad" --root "{skill-root}/.." --root "{skill-root}/../../vendor/bmad/skills"
```

- If this setup command fails, report its output and stop. Do not run `npx skills`, access the
  upstream checkout, or download BMad files.

Then run the bundled renderer exactly once without changing the current working directory. Replace
`{project-root}` with the absolute path to the project root and `{skill-root}` with the absolute path
to this skill's directory. This harness route always uses `full` so planning cannot take the
one-shot path into implementation:

```bash
uv run --no-cache "{project-root}/_bmad/scripts/render_skill.py" --project-root "{project-root}" --skill "{skill-root}" --set workflow.route=full
```

- On success, read and follow the one absolute `workflow.md` instruction printed to stdout.
- If the renderer is still missing after bundled setup, report that failure and stop.
- On any other failure, including missing `uv`, report the command output and stop. Do not run
  unrendered workflow source directly.

For this harness integration, follow BMad's clarify, investigate, plan, and human review steps. When
the reviewed plan is approved, stop and hand it to the harness backlog stage. Do not continue into
BMad's implementation steps; implementation and verification remain governed by the harness.

This bundle also includes BMad's PRD, party discussion, and advanced elicitation skills. Use
`bmad-prd` only when the intended user behavior cannot yet be stated clearly enough to investigate.
Use `bmad-advanced-elicitation` for an optional deeper challenge of the current plan, and
`bmad-party-mode` when the user requests several perspectives. These are supporting steps within
Stage 0; after using them, return to the technical investigation and plan review above.
