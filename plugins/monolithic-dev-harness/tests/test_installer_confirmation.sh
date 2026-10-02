#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
INSTALLER="${REPO_ROOT}/install.sh"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEMP_ROOT"' EXIT

mkdir -p "${TEMP_ROOT}/bin" "${TEMP_ROOT}/harness" "${TEMP_ROOT}/cursor"
cat > "${TEMP_ROOT}/bin/claude" <<'EOF'
#!/usr/bin/env sh
exit 0
EOF
cat > "${TEMP_ROOT}/bin/codex" <<'EOF'
#!/usr/bin/env sh
exit 0
EOF
chmod +x "${TEMP_ROOT}/bin/claude" "${TEMP_ROOT}/bin/codex"

INSTALL_ENV=(
  "HARNESS_HOME=${TEMP_ROOT}/harness"
  "HARNESS_BIN_DIR=${TEMP_ROOT}/bin"
  "CURSOR_PLUGIN_DIR=${TEMP_ROOT}/cursor"
  "CODEX_HOME=${TEMP_ROOT}/codex"
  "PATH=${TEMP_ROOT}/bin:/usr/bin:/bin"
)

if env "${INSTALL_ENV[@]}" bash "$INSTALLER" --uninstall >"${TEMP_ROOT}/refused.log" 2>&1; then
  printf 'uninstall unexpectedly continued without confirmation\n' >&2
  exit 1
fi
grep -q 'rerun with --yes' "${TEMP_ROOT}/refused.log"
test -d "${TEMP_ROOT}/harness"
test -d "${TEMP_ROOT}/cursor"

env "${INSTALL_ENV[@]}" bash "$INSTALLER" --uninstall --yes
test ! -e "${TEMP_ROOT}/harness"
test ! -e "${TEMP_ROOT}/cursor"
printf 'installer confirmation checks passed\n'
