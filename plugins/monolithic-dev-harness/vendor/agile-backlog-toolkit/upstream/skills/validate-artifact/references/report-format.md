# Report Format

## Terminal output template

```
Validating <type> — "<title>" [<source: artifacts path|azure>]
============================================================

STRUCTURAL
  [PASS]  frontmatter-type-present
  [FAIL]  frontmatter-status-absent — `status: active` found in frontmatter
  [SKIP]  filename-regex — source is Azure, not a local draft

HIERARCHY
  [PASS]  hierarchy-story-parent-is-feature — parent #6868 is Feature "Payment Flow"
  [WARN]  hierarchy-skipped-no-azure-id — no provider_id in frontmatter, hierarchy checks skipped

CONTENT
  [PASS]  content-complexidade-breakdown
  [FAIL]  content-story-points-set — story_points not set in frontmatter
  [PASS]  content-descricao-original-present
  [WARN]  content-no-machine-paths — found: /home/user/projects/repo

DoR
  [PASS]  dor-title-clear
  [PASS]  dor-description-present
  [FAIL]  dor-story-points-set — story points not set
  [FAIL]  dor-linked-to-feature — hierarchy-story-parent-is-feature failed

------------------------------------------------------------
Summary: 5 passed · 4 failed · 2 warnings
Outcome: FAIL
```

Rules:
- Every check that ran appears as one line: `  [PASS|FAIL|WARN|SKIP]  <check-name>  —  <detail>`
- SKIP: check was intentionally not run (wrong artifact type, missing provider_id). Include reason.
- Detail field: omit for PASS unless the detail adds value (e.g., confirming a parent id).
- Separator line: 60 `=` characters (header) and 60 `-` characters (before summary).

## Report frontmatter

```yaml
---
date: <YYYY-MM-DD>
type: report
artifact: <azure-id or artifacts path-filename>
artifact_type: <Epic|Feature|User Story>
source: <artifacts path|azure>
outcome: <pass|fail>
---
```

Do NOT include `status:` — the draft contract forbids it in report frontmatter.

## Report body

Reproduce the terminal output from the Report phase verbatim as a fenced code block:

```
(terminal output here)
```

No reformatting. What was printed is what is stored.
