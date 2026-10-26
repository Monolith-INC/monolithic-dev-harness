#!/bin/bash
# Per-run wrapper for acceptance_trial.py run: install the current source into the isolated
# environment, record what was installed, then run the project agent on the briefing (stdin).
set -eu
evidence='/home/monolith/projects/monolithic-dev-harness/AI_Codex/Artifacts/live-trials/20261015-day001-planning-gate-01'
checkout='/home/monolith/projects/monolithic-dev-harness'
trial_root="$(dirname "$PWD")"
export HARNESS_HOME="$trial_root/harness-install"
export HARNESS_BIN_DIR="$trial_root/bin"
export HARNESS_PYTHON='/home/monolith/.local/bin/python3.14'
export PATH="$HARNESS_BIN_DIR:$PATH"
printf '%s\n' "$PWD" > "$evidence/project-path.txt"
bash "$checkout/install.sh" --host codex --source "$checkout" --yes > "$evidence/installer.log" 2>&1
codex plugin list --json > "$evidence/plugin-list.json"
# Keep the project's end state, whatever happens to the agent run.
trap 'git status --porcelain > "$evidence/project-status.txt"; harness workflow requirements --repo "$PWD" > "$evidence/requirements-at-exit.json" 2>&1 || true; tar --exclude=.git -czf "$evidence/project-artifacts.tar.gz" -C "$PWD" .' EXIT
# The isolated trial config keeps the installed plugin registered; --ignore-user-config would hide it.
codex exec --sandbox workspace-write --model gpt-6-luna -c 'model_reasoning_effort="low"' --json --output-last-message "$evidence/result.md" -
