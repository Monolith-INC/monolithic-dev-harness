# Plain-Language Principles

Human-facing documentation standard. Derived from the artifacts path feature spec
`Features/generate-plain-language-documentation.md`.

## Mission

Turn technical content into prose a feature owner, tech lead, or developer can read once and reason
about without cross-referencing. The reader understands rationale, problem origin, and required
changes.

## Hard rules (non-negotiable)

1. **Explain every term inline at first use.** Pattern: *"**fingerprints** — stored snapshots used
   to detect whether something changed"*. If you cannot explain a term in one clause, replace it
   with what it does.
2. **Ban internal codenames.** Defect ids, backlog row ids, stage letters, and project shorthand
   never reach the reader. Fold content into named narratives.
3. **Prose carries explanation and rationale.** Lists enumerate evidence, steps, reasons, or
   sequences — never present an argument as a list of fragments.
4. **Simple, descriptive, brief, objective language.** Complete sentences. Brevity comes from
   cutting topics, not compressing sentences.
5. **No presumed knowledge.** When a mechanism must be mentioned, give a one-line explanation; add
   a diagram for workflow parts.
6. **References: source code and official documentation only.** Cite code as repository paths (with
   line numbers when they matter). Cite external claims as subject + source + URL. Never reference
   tickets, PRs, work items, or internal session notes.
7. **Minimum sufficient content.** Preserve decisions, evidence, and open questions; drop
   traceability tables and methodology narration.
8. **Diagrams where they cut cognitive load.** Narrow, vertical, top-down; two or three per document
   is the usual ceiling.
9. **Language policy.** English unless the user requires pt-BR. For pt-BR, run glossary verification
   (`./glossary-usage.md`).

## Completeness contract

Before drafting, inventory:

- Every decision that must survive
- Every problem and its evidence
- Every open question

After drafting, verify each item is present. Nothing outside the contract may be added.

## Default structure (adapt, don't worship)

1. **What this document is** — purpose, audience, how it will be used.
2. **Background** — system or workflow from zero, with a diagram when helpful.
3. **Problems and where they come from** — named subsection per problem; prose then evidence bullets.
4. **The core idea** — organizing principle, with before/after diagram when useful.
5. **The changes** — stage by stage or component by component.
6. **Out of scope** — explicit non-goals.
7. **Delivery plan** — ordered, reviewable steps; effort estimate when known.
8. **Decisions that must be recorded** — reversals and deferrals, stated generically.
9. **Open questions, with recommendations** — never a bare question.

For `work-item-prose`, use the caller skill's section contract instead of this structure.

## Self-review sweeps

1. **Jargon sweep** — scan for unexplained acronyms, stack terms, abbreviations.
2. **Reference sweep** — confirm every reference is a code path or official URL.
3. **Completeness check** — contract items present; no scope creep.

## Quality gate (all must pass)

- [ ] A reader outside the team could explain each problem and each change after one read.
- [ ] Zero unexplained acronyms, codenames, or stack-specific terms.
- [ ] Rationale is in prose; lists only enumerate.
- [ ] Every reference is a repository path or an official-documentation URL.
- [ ] No mention of tickets, PRs, work items, user stories, or internal notes (unless sub-skill
      mode preserves work-item section labels required by a sibling skill).
- [ ] Diagrams are narrow, vertical, and only where they reduce effort.
- [ ] Completeness contract satisfied.
- [ ] Language matches request; pt-BR is glossary-checked and calque-free.
