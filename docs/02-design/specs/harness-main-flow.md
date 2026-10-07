---
title: Harness Main Flow
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-06
---

# Harness main flow: stages, gates, interaction contract

Source evidence: DAY-003 shared-lists run (test-project-template), upstream `BMAD-METHOD/skills`.

## 1. What went wrong in DAY-003, and why

| Complaint | Root cause in the harness |
|---|---|
| Inconsistent UI (buttons vs text) | Three transports (blocking tool → async buttons → chat) chosen at runtime. Any time the agent explained something or the user asked a question, the next prompt fell back to chat. |
| "Reply with the exact option wording" | Every question, even routing and product choices, goes through the decision ledger and the hook must string-match the reply. "feature", "the first", "1" failed. |
| Deeper review not offered formally | Elicitation lives in a prose note before the G1 menu (copied from BMAD), not as a menu option. |
| Felt shallow | Our vendored `bmad-build` removed what gives BMAD its depth: subagent investigation ("investigate in the current session"), `review-prompts/` (edge-case-hunter, verification-gap), `references/` (claims/deletion checks), steps 3–5. The scope gate never fired, although the plan was clearly multi-goal (auth + invitations + Android + native Linux sync engine). |
| Had to ask "what's next" | A turn could end with neither a menu nor continued work. Conflict policy was answered in conversation, never captured, and the flow stalled. |
| Not cohesive | ~8 product questions asked one at a time with a button round-trip each, plus ~3000 lines of hook/adapter code for question capture. The storyboard describes transports, not the user's journey. |

## 2. How BMAD handles UI

BMAD has **no UI tool layer**. The chat itself is the interface:

- Every pause is written as **"HALT and give the user a choice:"**, followed by bold-named options with their consequences, and then the turn ends.
- Replies are interpreted by the model: *"Accept a number, menu `code`, or fuzzy description match."* Free text counts as direction, not an error.
- Open questions are **batched**: step-02 investigates first without asking anything, writes every gap as an Open Question with options, then presents all of them in one message.
- There are only a few gates: scope split, open questions, Checkpoint 1, and review findings. Step-02 also says: *"No intermediate approvals."*
- Product shaping uses a coach stance (`bmad-architecture`): explain the alternatives and recommend one. A crisp either/or is reserved for genuinely binary forks.

## 3. Decisions: one gate model, buttons first, graceful fallback

Decided 2026-10-06: keep native buttons and make them reliable. Record every approval once, never ask for it again, and close each series of decisions with a single final acknowledgement.

1. **One gate model, several renderings.** `harness gate render <id>` produces the gate content once (question, options, consequences, recommendation). Each transport renders that same content:
   1. a blocking native control;
   2. an asynchronous native control;
   3. a chat menu block.

   When one transport fails, the harness moves to the next one silently and re-asks the same gate. The user never sees transport errors and is never asked to diagnose them.
2. **The chat menu block** is the last fallback, and it is also what every host shows when the agent is mid-conversation:

   ```markdown
   **G1 · Plan ready — how do you want to proceed?**

   1. **Approve & continue** — plan locks; I draft work items next.
   2. **Deepen** — adversarial review, elicitation, or party mode before approving. *(recommended for multi-platform work)*
   3. **Revise** — tell me what to change.
   4. **Approve & stop** — plan locks; pause here.

   Reply with a number, a name, or your own direction.
   ```

3. **Replies are matched loosely on every transport.** A reply resolves the open gate when it is:
   - a button click;
   - a number;
   - an option name (case-insensitive);
   - a unique prefix or an unambiguous paraphrase ("the first", "feature").

   An ambiguous reply records nothing, and the agent re-asks the same gate once. Any other free text is direction, not an error.
4. **Every approval is recorded once and never repeated.** The ledger keys each approval by gate and artifact digest. An approval stays valid until the approved content materially changes, and a later stage reuses it instead of asking again.
5. **Final acknowledgement at the end of a series.** Individual product choices inside a Q-batch are answers, not approvals. When the series ends, a **recap gate** lists every choice made, with the option to change any of them, and the user acknowledges once. G1 is that recap for discovery; G2–G4 are recaps for publishing, the spec and delivery.
6. **No-stall rule:** every turn ends with either a gate block or ongoing work. A status beat ends with `Next: <action>` and continues without waiting.

## 4. Main flow

Yellow = gate (turn ends; answers go into the plan). Red 🔒 = recap/approval gate (recorded once, reused until the content changes). G1 is also a recorded recap.

![Harness main flow](../../assets/diagrams/harness-main-flow.svg)

<details><summary>Mermaid source (regenerate the SVG with <code>npx @mermaid-js/mermaid-cli -i flow.mmd -o docs/assets/diagrams/harness-main-flow.svg</code>, <code>htmlLabels: false</code>)</summary>

```mermaid
flowchart TD
    REQ([Request: ticket / idea / file]) --> SETUP{{"G0 Setup<br/>only if config missing<br/>(one batched menu)"}}
    SETUP --> ROUTE["Route<br/>infer from request; ask only if ambiguous"]
    ROUTE -->|idea| IDEATE["Ideate<br/>plan-initiative: brief → PRD → UX → arch<br/>coach, don't quiz"]
    ROUTE -->|ticket / feature| INV

    subgraph DISCOVER["Discover (bmad-build steps 1–2)"]
      INV["Investigate silently<br/>subagent fan-out → Code Map"] --> SCOPE{{"Scope gate<br/>multi-goal or >1600 tokens?<br/>Split / Keep"}}
      SCOPE --> DRAFT["Draft plan + Open Questions<br/>each with options + recommendation"]
      DRAFT --> OQ{{"Q-batch<br/>all open questions in ONE message"}}
      OQ -->|answers expose new gaps| DRAFT
    end

    IDEATE --> G1
    OQ -->|none left| G1{{"G1 Plan gate<br/>1 Approve & continue<br/>2 Deepen<br/>3 Revise<br/>4 Approve & stop"}}
    G1 -->|2 Deepen| DEEP["Deepen loop<br/>adversarial review (subagents) ·<br/>elicitation methods · party mode<br/>→ Apply / Reject per proposal"]
    DEEP --> G1
    G1 -->|3 Revise| DRAFT
    G1 -->|4| STOP1([Paused: plan ready-for-dev])
    G1 -->|1| BACKLOG["Backlog<br/>draft Feature / Stories / Tasks locally"]

    BACKLOG --> G2{{"G2 Publish gate 🔒<br/>exact batch + destination<br/>Approve / Revise / Stop"}}
    G2 -->|approve| SPEC["Story spec<br/>per ready story"]
    SPEC --> G3{{"G3 Spec gate 🔒<br/>Approve & build / Deepen / Revise"}}
    G3 --> BUILD["Build<br/>tasks + checks, no routine stops"]
    BUILD -.->|material decision only| QB{{"Q-batch"}}
    QB -.-> BUILD
    BUILD --> VERIFY["Verify<br/>thermos ∥ bmad-review: edge cases ·<br/>claims · verification gap (subagents)"]
    VERIFY --> G4{{"G4 Delivery gate 🔒<br/>findings: Apply all / Walk through / Defer<br/>then open draft PR?"}}
    G4 --> DONE([Draft PR + evidence])

    classDef gate fill:#fff3cd,stroke:#b58900,color:#000
    classDef lock fill:#f8d7da,stroke:#a33,color:#000
    class SETUP,SCOPE,OQ,G1,QB gate
    class G2,G3,G4 lock
```

</details>

### Interaction types (the only four)

| Type | When | Ends turn? | Recorded |
|---|---|---|---|
| **Gate** | G0, scope | yes | plan frontmatter / checkpoint |
| **Q-batch** | Open Questions after investigation, or a material build decision | yes | answers → frozen block |
| **Recap / approval gate** 🔒 | G1, G2, G3, G4 | yes | decision ledger (gate + digest), never re-asked |
| **Status beat** | progress between gates | **no**, ends with `Next: …` | checkpoint |

### DAY-003 replayed under this flow

Silent investigation, then a scope gate (split the native Linux sync engine into its own goal?), then **one** Q-batch with 6 questions and a recommendation for each, then G1 with **Deepen** as option 2. Deepen loops (First principles → Assumption audit → Security personas) return to G1 automatically. That is about 4 user turns before approval, compared with roughly 20 in the original run.

## 5. Direction (priority order)

### P1: Restore BMAD depth (top priority) — implemented on `feat/bmad-depth`, awaiting P4 replay

Our vendored skills consistently turned off the three things that make BMAD deep: subagents, the memlog, and the reviewers.

| Status | Gap | Fix |
|---|---|---|
| ✅ | Investigation ran in one session | `bmad-build` step-02 restores the upstream subagent fan-out; `workflow.md` asks once per run when the host needs permission. |
| ✅ | Missing upstream skills | `bmad-correct-course`, `bmad-project-context`, `bmad-deep-recon`, `bmad-qa-generate-e2e-tests` vendored (pristine copy under `vendor/bmad/upstream/`) and wired in. |
| ✅ | Scope gate never fired | Multi-goal and token checks run again on the decided plan; compressing the plan to fit is forbidden. |
| ✅ | Party mode was one voice | Upstream `auto`/`subagent`/`agent-team` modes restored, default `auto`; per-party memory restored. |
| ✅ | No durable decision memory | `plan-<slug>.memlog.md` beside the plan (new `memlog_command` in the render context); every answer, accepted proposal, scope choice and approval is logged; resume reads it first. |
| ✅ | Deepen not a formal option | Checkpoint 1 is now *Approve & continue / Deepen / Revise / Approve & stop*. Deepen = `bmad-review` (adversarial + edge-case lenses, parallel subagents) → elicitation → party mode offer. The recap lists every recorded decision instead of re-asking. |
| ✅ | Build and verify were thin | Verify runs `thermos` ∥ `bmad-review` edge-case (claims + deletion checks) and verification-gap lenses, then one triage menu. Build generates e2e tests at Story done. BMAD's code-diff `review-prompts/` stay unvendored: `bmad-review` ships the same lenses. |
| ✅ | Quiz instead of coaching | Open Questions go out in one message with trade-offs and a recommendation; answers accepted in any form. |
| ✅ | Subagents also disabled elsewhere | `bmad-prd` (research, extraction, review lenses, reconciliation) and `bmad-review` (parallel lenses) restored. |

### Standing duty: documentation

Every change in P1–P4 updates, in the same branch:

- [x] `docs/02-design/workflows.md` — discovery depth model, correct-course, Build/Verify changes (P1).
- [x] `vendor/bmad/SOURCE-MANIFEST.md` — bundled skills and each harness adaptation (P1).
- [x] `CHANGELOG.md` and `docs/06-delivery/changelog.md` (P1).
- [ ] `references/human-decisions.md` and `references/workflow-storyboard.md` — rewrite for the gate model (P2).
- [ ] `docs/03-engineering/discovery-rendering.md` — memlog command and gate rendering (P2).
- [ ] This spec — status per phase, and the diagram regenerated when the flow changes (`docs/assets/diagrams/harness-main-flow.svg`).
- [ ] User-facing guide (`docs/07-guides/`) — what each gate means and how to answer it (after P4).

### P2: Gate model and reliable buttons

1. Gate definitions as data (`config/gates.toml`: id, question, options, consequences, recommendation, recap flag). Add `harness gate render` for all three transports.
2. Loose reply matching in the hook for all transports (§3.3). Ledger keyed by gate + digest; reuse instead of re-asking (§3.4).
3. A transport ladder with silent fallback, plus a per-host reliability test: click, typed number, typed name and paraphrase must each resolve on Codex, Claude Code and Cursor.
4. Rewrite `references/human-decisions.md` and `workflow-storyboard.md` around §3–4. No compatibility path is needed (not in production).

### P3: Flow continuity

1. A no-stall `Stop` hook: if a workflow is active and the last message has neither a gate nor a `Next:` line, nudge the agent to continue.
2. Scope pending decisions to the work session (a known gap noted in the storyboard).

### P4: Acceptance

Replay DAY-003 on test-project-template in Codex and Claude Code, and keep the replay as a regression fixture. Pass criteria:

- the scope split is offered;
- one Q-batch with recommendations;
- Deepen is option 2 at G1 and runs reviewer subagents;
- the memlog holds every decision, and resume reads it;
- party mode spawns per-persona agents on a host that supports them;
- zero "reply with exact wording", zero "what's next", zero repeated approvals;
- buttons on both hosts, with chat fallback verified.

## 6. Decisions

- ✅ Keep native buttons; make them reliable; fall back silently to the next transport.
- ✅ Record every approval once; no repeated approvals; a final recap acknowledgement at the end of each decision series.
- ✅ BMAD depth is priority one.
- ✅ Add upstream skills, vendored with subagents and memlog intact:
  - `bmad-correct-course` — change of direction mid-feature; re-enters at the earliest affected gate.
  - `bmad-project-context` — persistent facts loaded at Discover. In DAY-003, `current-state.md` claimed a working sign-out that the code did not have; that kind of drift is what this skill catches.
  - `bmad-deep-recon` — available in Discover and Deepen for unfamiliar code or domains.
  - `bmad-qa-generate-e2e-tests` — runs in Build/Verify alongside `automated-tests`.
- ✅ Code review stays with `thermos`. Verify runs `thermos` plus `bmad-review`'s edge-case (claims + deletion) and verification-gap lenses. Of BMAD's step-04/05 we port only the findings-triage menu.
- ✅ Documentation is a standing duty of every phase (see §5).
