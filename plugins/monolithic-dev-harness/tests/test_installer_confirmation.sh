#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
INSTALLER="${REPO_ROOT}/install.sh"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEMP_ROOT"' EXIT

mkdir -p "${TEMP_ROOT}/bin" "${TEMP_ROOT}/harness" "${TEMP_ROOT}/cursor"
cat > "${TEMP_ROOT}/bin/claude" <<'EOF'
#!/usr/bin/env sh
case "$*" in
  *"plugin list"*) printf '[]\n' ;;
  *"marketplace list"*) printf '[]\n' ;;
  *) exit 0 ;;
esac
EOF
cat > "${TEMP_ROOT}/bin/codex" <<'EOF'
#!/usr/bin/env sh
case "$*" in
  *"plugin list"*) printf '{"installed":[],"available":[]}\n' ;;
  *"marketplace list"*) printf '{"marketplaces":[]}\n' ;;
  *) exit 0 ;;
esac
EOF
chmod +x "${TEMP_ROOT}/bin/claude" "${TEMP_ROOT}/bin/codex"

INSTALL_ENV=(
  "HARNESS_HOME=${TEMP_ROOT}/harness"
  "HARNESS_BIN_DIR=${TEMP_ROOT}/bin"
  "CURSOR_PLUGIN_DIR=${TEMP_ROOT}/cursor"
  "CODEX_HOME=${TEMP_ROOT}/codex"
  "ZED_CONFIG_DIR=${TEMP_ROOT}/zed"
  "KIMI_CONFIG_DIR=${TEMP_ROOT}/kimi"
  "AGENTS_SHARED_DIR=${TEMP_ROOT}/agents"
  "HOME=${TEMP_ROOT}/home"
  "CLAUDE_CONFIG_DIR=${TEMP_ROOT}/claude-config"
  "HARNESS_PYTHON=$(command -v python3.12)"
  "PATH=${TEMP_ROOT}/bin:/usr/bin:/bin"
)

if env "${INSTALL_ENV[@]}" bash "$INSTALLER" --uninstall --scope user --source "$REPO_ROOT" >"${TEMP_ROOT}/refused.log" 2>&1; then
  printf 'uninstall unexpectedly continued without confirmation\n' >&2
  exit 1
fi
grep -q 'rerun with --yes' "${TEMP_ROOT}/refused.log"
test -d "${TEMP_ROOT}/harness"
test -d "${TEMP_ROOT}/cursor"

env "${INSTALL_ENV[@]}" bash "$INSTALLER" --uninstall --scope user --source "$REPO_ROOT" --yes
test -d "${TEMP_ROOT}/harness"
test -d "${TEMP_ROOT}/cursor"
printf 'installer confirmation checks passed\n'
