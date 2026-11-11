# Discovery: from an idea to an approved Vision Doc and PRD

## Given

- `tracker_preflight` passes.
- The project name is known. If it is not, ask for it once, before step 1.
- ROOT is the discovery Epic, titled with the project name. Every document is published on it.
- The knowledge store is optional and never a gate. If it is empty or stale, discovery continues
  without it.

| Document | `kind` | `title` |
|---|---|---|
| Vision Doc | `vision-doc` | `Vision Doc — [Project Name]` |
| PRD | `prd` | `PRD — [Project Name]` |

The headings of each document, in order, and its interview areas are in the document catalog
(`config/documents.toml`). A document's `Status` line sits under its title and reads `Draft` or
`Approved`. A section is complete when it has real content, or `TBD — [reason] (owner: [name])`; an
empty heading, or a bare `TBD`, is not.

A revision is `r1`, `r2`, and so on. A (title, revision) is published once, so every change is a
new revision. The latest revision of each kind is the document.

## Routing

The step is derived from ROOT's artifacts: the first row whose condition is true. Nothing about it
is stored. `harness modes step` prints it.

| Condition | Go to |
|---|---|
| No ROOT, or no `vision-doc` | Step 1 |
| `vision-doc` has incomplete sections | Step 1 (resume) |
| `vision-doc` is not approved | Gate G1 |
| No `prd`, or `prd` incomplete | Step 2 |
| `prd` is not approved | Gate G2 |
| `prd` approved | Exit: advise that the next discovery steps come in a later slice, then `harness modes leave` |

## Sequence

### Step 1: Vision Doc

1. Scan: ROOT, then the artifacts on it.
2. Interview the 7 areas in one message, with an "I'm already assuming…" list, then wait:
   Problem, Target users, Desired outcome, Business objectives, Success metrics (with baseline),
   Constraints, Out of scope.
3. Write the draft with the catalog's headings and show it. Nothing is saved yet.

### Gate G1

The harness `approve-document` question on the Vision Doc draft, asked before anything is saved.
When it is approved, create ROOT if it is absent (`tracker_create_work_item`, kind epic, title the
project name, no description), then publish `vision-doc` once, as the next revision
(`tracker_publish_artifact`), with Status `Approved` and a `Change history` row "Approved by
[user]". It is never published as a draft first.

### Step 2: PRD

1. Stop without an approved Vision Doc.
2. Map the Vision Doc's sections into the PRD with the catalog, and show "Already have: …".
3. Interview only the gaps, in one message: user journeys, functional requirements, NFRs,
   dependencies, risks, open questions.
4. Write the draft: functional requirements numbered `FR-01…`, written with "shall" and "should",
   and show it. Nothing is saved yet.

### Gate G2

As G1, on the PRD: when it is approved, publish `prd` once, with Status `Approved`.

## Loops

A new Vision Doc revision means re-checking the PRD: fill or flag only the gaps.

## Exit criteria

- ROOT holds a Vision Doc and a PRD whose latest revisions are approved.
- Every section of both is complete, and each ends with `Change history`.
- Every open question has an owner.

## Invariant

- Each kind has exactly one title on ROOT.
- Every revision keeps all the complete content of the one before it.
- Nothing is published before its upstream gate has passed.
