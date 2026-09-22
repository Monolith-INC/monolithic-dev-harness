# Placement and search

Treat each instruction as an atomic amendment. Preserve its original wording and derive a small
search set: exact phrases, identifiers, title words, normalized tokens, and simple stems. Search
the Artifacts with Obsidian CLI/search when available, then use `rg -n -i` over the artifacts path and plugin
references. Rank a candidate by:

1. exact work-item id or URL;
2. exact phrase in title/body;
3. title-token overlap;
4. body-token overlap;
5. parent-chain and child-task context;
6. compatibility with the canonical type and section.

Use the examples and canonical references under `../enrich-work-item/references/` as the contract.
Do not put a requirement in a convenient section merely because it matches a keyword.

| Work-item type | Preferred canonical placement |
| --- | --- |
| Epic | strategic vision, business problem, strategic objectives, success metrics, strategic scope, areas/projects, dependencies/risks |
| Feature | objective, scope, success criteria, areas/modules |
| User Story | what, why, expected behavior, acceptance criteria, complexity |
| Task | implementation-plan step, test/review/staging detail, or task-specific acceptance evidence |

Choose the narrowest compatible existing section. If one amendment affects multiple levels, show
one placement option per affected node and explain the propagation. If no candidate reaches high
confidence, recommend `Other` and ask the user to identify the node/section.
