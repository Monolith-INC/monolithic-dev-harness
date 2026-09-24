---
name: knowledge-acquire
description: Acquire bounded, source-backed knowledge from a harness-owned store before making a project-specific decision.
---

# Knowledge acquisition

Use the harness-owned store. Do not read arbitrary project knowledge folders, run a semantic search,
or guess a project convention.

```bash
harness knowledge catalog --store project
harness knowledge find <term> [<term> ...] --store project
harness knowledge resolve <logical-unit-id> --store project
harness knowledge fetch <logical-unit-id> --store project
```

The command returns JSON. `catalog` is routing metadata only. `find` returns at most twelve current
units. `resolve` names the current immutable revision; `fetch` returns its evidence and freshness.

When knowledge is missing or stale, state the gap and run the smallest available refresh:

```bash
harness knowledge refresh --store project
```

Knowledge is agent-owned and append-only. Never edit a revision, catalog, source index, or event
directly. Bootstrap initializes the `project` store from `.harness/policy.json`; refresh creates a
new revision only when its source evidence changed.

