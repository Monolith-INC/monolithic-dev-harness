#!/bin/bash
# One round of the resumable DAY-001 trial.
#   round.sh 1                 install the current source (first round only) and start the agent
#   round.sh <n> <answer>      resume the same Codex session with the human's exact answer
# Each round writes round-<n>.jsonl, round-<n>-stderr.log, round-<n>-result.md and
# round-<n>-requirements.json to the evidence folder.
set -eu
evidence='/home/monolith/projects/monolithic-dev-harness/AI_Codex/Artifacts/live-trials/20261015-day001-planning-gate-02'
checkout='/home/monolith/projects/monolithic-dev-harness'
project='/tmp/monolithic-dev-harness-trial-ed0k7v76/project'
trial_root="$(dirname "$project")"
round="$1"
export CODEX_HOME="$trial_root/codex-home"
export HARNESS_USER_STATE_DIR="$trial_root/preferences"
export TMPDIR="$trial_root/runner-tmp"
export HARNESS_HOME="$trial_root/harness-install"
export HARNESS_BIN_DIR="$trial_root/bin"
export HARNESS_PYTHON='/home/monolith/.local/bin/python3.14'
export PATH="$HARNESS_BIN_DIR:$PATH"
# Host context from the parent session must not leak into the trial (the runner's own list,
# plus the parent Claude session's).
unset CODEX_THREAD_ID CODEX_SESSION_ID CODEX_INTERNAL_ORIGINATOR_OVERRIDE CODEX_APP_TOOLS_PIPE_PATH \
  CODEX_TASK_WORKSPACE_VERIFYING_IDENTITY CODEX_SAGE_BACKFILL_TRACKER_TAB_REUSE CODEX_SHELL \
  CLAUDE_PROJECT_DIR CLAUDECODE CLAUDE_CODE_ENTRYPOINT CURSOR_PROJECT_DIR 2>/dev/null || true
cd "$project"
out="$evidence/round-$round"
model=(--model gpt-6-luna -c 'model_reasoning_effort="low"')
if [ "$round" = 1 ]; then
  bash "$checkout/install.sh" --host codex --source "$checkout" --yes > "$evidence/installer.log" 2>&1
  codex plugin list --json > "$evidence/plugin-list.json"
  codex exec --sandbox workspace-write "${model[@]}" --json --output-last-message "$out-result.md" - \
    < "$evidence/briefing.md" > "$out.jsonl" 2> "$out-stderr.log" || echo $? > "$out-exit.txt"
else
  session="$(cat "$evidence/codex-session-id.txt")"
  printf '%s\n' "$2" > "$out-answer.txt"
  codex exec resume "$session" "${model[@]}" -c 'sandbox_mode="workspace-write"' --json --output-last-message "$out-result.md" "$2" \
    > "$out.jsonl" 2> "$out-stderr.log" || echo $? > "$out-exit.txt"
fi
git status --porcelain > "$out-project-status.txt"
harness workflow requirements --repo "$project" > "$out-requirements.json" 2>&1 || true
if [ "$round" = 1 ]; then
  grep -o '"thread_id":"[^"]*"' "$out.jsonl" | head -1 | cut -d'"' -f4 > "$evidence/codex-session-id.txt"
fi
