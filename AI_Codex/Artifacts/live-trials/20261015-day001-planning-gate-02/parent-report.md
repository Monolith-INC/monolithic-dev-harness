# DAY-001 planning-gate trial 02 — parent report

- **Harness:** source `addd129`, installed as plugin 0.6.2 in the fixture's isolated Codex home.
- **Host / model / effort:** Codex CLI, `codex exec` then `codex exec resume` per answer;
  `gpt-6-luna`, low; workspace-write sandbox. Codex session `01a13f63-28e9-7783-9846-d8d3e12ae642`.
- **Rounds:** 10. Answers: rounds 2–4 by the human; rounds 5–10 by the parent on the human's
  delegation (`delegated-answers.md`).
- **Stopped by the human** after round 10, at decision "Should I request an exception to publish the
  local Story before the full bundle review?" (unanswered). Fixture discarded after export.
- **Evidence:** per-round `round-N*` files, `transcript.jsonl` (all rounds), `summary.json`,
  `codex-session-rollout.jsonl` (Codex's own record), `planning-artifacts/`,
  `work-sessions-state/`, `project-artifacts.tar.gz`, `hook-trust.md`.

## Reached

Discovery through planning: `harness begin`, BMad Build steps 1–2, planning-depth (Standard),
methods (contextual shortlist; boundary & edge-case sweep, critique and refine, both applied), an
approach draft (`approach-show-both-task-counts.md`), then preparation drafts (a Story ticket draft,
a spec draft, a dated plan). No tracker item, link, Task, `implementation-confirm`, or code edit.
Project source and tests unchanged throughout.

## Findings

1. **Harness hooks did not run until a person trusted them (host setup, affects every headless
   trial).** Codex runs plugin hooks only with persisted trust (`[hooks.state] … trusted_hash`);
   `codex exec` shows no trust prompt. Rounds 1–2 ran hook-less: the relayed answer was not captured
   and no host-session record existed. After the human trusted the 6 hooks interactively, answers
   were captured by the prompt hook (round 3 on), and a hook refused an attempt to replace a pending
   decision (round 4). Earlier headless trials were most likely hook-less too.
2. **Codex approval policy `never` blocked the harness's MCP tools (host setup).** `tracker_describe`,
   `generate-work-item`, and `generate-breakdown-work-items` failed with "MCP tool call requires
   approval, but approval policy is never" (round 10). Preparation could not use the normal tools.
3. **The agent misattributed the block (agent behavior).** It reported that "the harness pre-tool
   hook blocked" Task-draft writes; the transcript holds no such refusal and no attempted write. It
   inferred it from `harness workflow requirements` (no linked work item) and then proposed an
   off-workflow exception (publish the Story before the bundle review).
4. **Real harness defect behind the agent's guess (confirmed by the parent).** With no source/test
   globs (this profile), `is_code` treats `docs/planning/tracker-drafts.json` as code: the planning
   folder exempts only Markdown. The six-stage bundle needs that file before approval and before any
   Story exists to link, so the code-change gate would refuse it: a deadlock. Fix: the planning
   folder's tracker drafts are planning, not code.
5. **Lower-tier variation:** trial 01 asked "standalone or initiative"; this run decided standalone
   itself (matching the human's answer).
6. **Decision handling worked once hooks ran:** native attempts recorded as dismissed in
   noninteractive mode, chat/async fallback captured each answer, and every answer was scoped to
   the work session.

## Outcome

**Fail** for completing the planning gate: preparation stalled on host approval policy (2) and the
harness drafts-file defect (4) would have blocked it next. **Pass** for decision handling and
answer capture with trusted hooks (1, 6). The code-change refusal itself was still not exercised
live, because no code edit was attempted.

## Follow-ups

- Fix 4 (planning-folder tracker drafts are not code) with a test.
- Trial preparation: record hook trust and MCP tool approval for the isolated Codex home through a
  supported, human-approved step, and say so in the evidence; never use the bypass flags silently.
