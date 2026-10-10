#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
INSTALLER="${REPO_ROOT}/install.sh"
PLUGIN_ROOT="${REPO_ROOT}/plugins/monolithic-dev-harness"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEMP_ROOT"' EXIT

PY_BIN="python3"
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY_BIN="${REPO_ROOT}/.venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PY_BIN="$(command -v python3.12)"
fi

mkdir -p "${TEMP_ROOT}/bin" "${TEMP_ROOT}/harness" "${TEMP_ROOT}/kimi" "${TEMP_ROOT}/agents/skills"
cat > "${TEMP_ROOT}/bin/kimi" <<'EOF'
#!/usr/bin/env sh
exit 0
EOF
chmod +x "${TEMP_ROOT}/bin/kimi"
# A foreign skill that must survive install and uninstall untouched.
printf 'foreign\n' > "${TEMP_ROOT}/agents/skills/bootstrap"

INSTALL_ENV=(
  "HARNESS_HOME=${TEMP_ROOT}/harness"
  "HARNESS_BIN_DIR=${TEMP_ROOT}/bin"
  "KIMI_CONFIG_DIR=${TEMP_ROOT}/kimi"
  "AGENTS_SHARED_DIR=${TEMP_ROOT}/agents"
  "HARNESS_PYTHON=${PY_BIN}"
  "PATH=${TEMP_ROOT}/bin:/usr/bin:/bin"
)

env "${INSTALL_ENV[@]}" bash "$INSTALLER" --source "$REPO_ROOT" --host kimi --yes >"${TEMP_ROOT}/install.log" 2>&1

# Hooks: three managed entries, valid TOML, existing content preserved.
grep -q -- '--host kimi --event pre-tool' "${TEMP_ROOT}/kimi/config.toml"
grep -q -- '--host kimi --event prompt' "${TEMP_ROOT}/kimi/config.toml"
grep -q -- '--host kimi --event stop' "${TEMP_ROOT}/kimi/config.toml"
[[ "$(grep -c '>>> monolithic-dev-harness hooks' "${TEMP_ROOT}/kimi/config.toml")" -eq 1 ]]
"$PY_BIN" -c "import sys, tomllib; d = tomllib.loads(open(sys.argv[1]).read()); assert len(d['hooks']) == 3" "${TEMP_ROOT}/kimi/config.toml"

# Reinstall stays idempotent (single managed block).
env "${INSTALL_ENV[@]}" bash "$INSTALLER" --source "$REPO_ROOT" --host kimi --yes >"${TEMP_ROOT}/reinstall.log" 2>&1
[[ "$(grep -c '>>> monolithic-dev-harness hooks' "${TEMP_ROOT}/kimi/config.toml")" -eq 1 ]]

# Shared skills/agents: harness entries linked, foreign bootstrap not clobbered.
[[ -L "${TEMP_ROOT}/agents/skills/run-test-project" ]]
[[ "$(find "${TEMP_ROOT}/agents/skills" -type l | wc -l)" -ge 70 ]]
[[ "$(cat "${TEMP_ROOT}/agents/skills/bootstrap")" = "foreign" ]]
[[ -e "${TEMP_ROOT}/agents/agents/thermo-nuclear-review-subagent.md" ]]

env "${INSTALL_ENV[@]}" bash "$INSTALLER" --uninstall --yes >"${TEMP_ROOT}/uninstall.log" 2>&1

# Uninstall: hooks removed, shared links removed, foreign skill kept.
[[ ! -e "${TEMP_ROOT}/kimi/config.toml.pre-harness" || ! -s "${TEMP_ROOT}/kimi/config.toml" ]] \
  || ! grep -q "monolithic-dev-harness" "${TEMP_ROOT}/kimi/config.toml"
[[ "$(find "${TEMP_ROOT}/agents/skills" -type l | wc -l)" -eq 0 ]]
[[ "$(cat "${TEMP_ROOT}/agents/skills/bootstrap")" = "foreign" ]]
[[ ! -e "${TEMP_ROOT}/agents/agents/thermo-nuclear-review-subagent.md" ]]

printf 'installer kimi checks passed\n'
