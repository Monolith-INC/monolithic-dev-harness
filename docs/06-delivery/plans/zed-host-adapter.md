---
title: Zed host adapter
status: complete
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-09
created: 2026-10-09
---

# Zed host adapter

## Goal

Run the harness six-stage flow inside the Zed editor agent panel (any model, including
Kimi-for-coding) as a first-class host alongside claude/cursor/codex. Decisions render through
the chat fallback; harness tools reach the agent through MCP context servers; policy
enforcement is delegated to Zed's tool-permission prompts because Zed has no hook lifecycle.

## Evidence

- Zed supports MCP Tools + Prompts via `context_servers` in `~/.config/zed/settings.json`
  (or project `.zed/settings.json`); per-tool permissions use `mcp:<server>:<tool>` keys.
- Zed does not implement MCP Elicitation and has no hook/PreToolUse lifecycle, so the
  harness cannot deny tool calls itself; `agent.tool_permissions` is the only gate.
- Zed exposes no thread/session env var to MCP servers, so session identity must be
  project-local (worktree path + harness-managed conversation pointer), like the cursor host.
- The existing chat fallback in `host_adapters/interactions.py` already renders the one
  canonical menu, so `zed` reuses it with a Zed-specific delivery instruction.

## Work

1. `hosts/zed.json`: capability file. Subagent ops unsupported (unsourced provenance, same as
   other hosts); notes record the no-hook and no-elicitation limitations.
2. `host_adapters/zed_adapter.py` + registration in `host_adapters/__init__.py`
   (`select_adapter`, `native_session_id`). `parse_zed_payload` reuses the generic policy
   event parser so future Zed hook support drops in without a rewrite.
3. `host_adapters/interactions.py`: `zed` host returns chat transport with a Zed-specific
   instruction (MCP tool results are data; end the turn and wait for the human reply).
4. `harness decision --host zed` in `scripts/harness/cli_workflow.py` (choices extended;
   default host detection extended for Zed worktree env).
5. MCP exposure: `zed.mcp.json` (same three servers as `codex.mcp.json`) and installer
   support: `--host zed` writes a `context_servers` block into `~/.config/zed/settings.json`
   idempotently (JSON-preserving edit, backup on first change), and uninstall removes it.
6. Project-root detection: accept `ZED_WORKTREE_ROOT` in `orchestrator_core/main.py` and
   `project_config.py` (mirrors `CURSOR_PROJECT_DIR` handling).
7. Trial runner: `acceptance_trial.py` gains a `zed` host profile writing
   `.zed/settings.json` inside the prepared project; runner env stays project-local.
8. Regression tests: adapter parse/format round-trip, chat-transport contract for `zed`,
   installer settings edit idempotence, trial `zed` profile shape, CLI `--host zed` dispatch.

## Acceptance

- `harness decision present --host zed` emits the canonical chat menu with Zed instruction.
- Installer `--host zed` registers three MCP servers in Zed settings; re-running changes
  nothing; `--uninstall` removes only the harness block.
- `harness doctor` lists Zed when configured.
- A trial prepared with the `zed` profile opens in Zed with harness tools available and the
  knowledge index consulted before broad reads; no Git imposition; one confirmation.

## Boundaries

No Zed extension (Rust/WASM) work; no attempt to emulate hooks; do not alter existing host
behavior; Zed settings edits must be strictly additive and reversible.
