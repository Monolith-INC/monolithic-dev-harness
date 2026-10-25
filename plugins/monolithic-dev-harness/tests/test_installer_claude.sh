#!/usr/bin/env bash
# A same-version reinstall must replace Claude Code's cached plugin, and the installer must refuse
# to report success while Claude would still load an older copy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
INSTALLER="${REPO_ROOT}/install.sh"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEMP_ROOT"' EXIT

PY_BIN="python3"
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY_BIN="${REPO_ROOT}/.venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PY_BIN="$(command -v python3.12)"
fi

mkdir -p "${TEMP_ROOT}/bin" "${TEMP_ROOT}/harness" "${TEMP_ROOT}/claude" "${TEMP_ROOT}/claude-config"
export HOME="${TEMP_ROOT}/home"
mkdir -p "$HOME"
# Stub `claude` that caches by version like the real CLI: `plugin update` keeps the cache, and
# only `plugin install` copies the marketplace plugin into it. STUB_KEEP_CACHE makes install
# keep a cache that already exists, to prove the installer notices.
cat > "${TEMP_ROOT}/bin/claude" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
state="${CLAUDE_STUB_STATE}"
cache="${state}/cache/0.6.2"
id="monolithic-dev-harness@monolithic-dev-harness"
case "$1 $2 ${3:-}" in
  "plugin marketplace list")
    if [[ -f "${state}/marketplace" ]]; then
      printf '[{"name":"monolithic-dev-harness","installLocation":"%s"}]\n' "$(cat "${state}/marketplace")"
    else echo '[]'; fi ;;
  "plugin marketplace add") printf '%s' "$4" > "${state}/marketplace" ;;
  "plugin marketplace update" | "plugin marketplace remove") ;;
  "plugin list --json")
    if [[ -f "${state}/installed" ]]; then
      printf '[{"id": "%s", "installPath": "%s"}]\n' "$id" "$cache"
    else
      echo '[]'
    fi ;;
  plugin\ install\ *)
    if [[ -z "${STUB_KEEP_CACHE:-}" || ! -d "$cache" ]]; then
      rm -rf "$cache"
      mkdir -p "${state}/cache"
      cp -R "$(cat "${state}/marketplace")/plugins/monolithic-dev-harness" "$cache"
    fi
    touch "${state}/installed" ;;
  plugin\ update\ *) ;;
  plugin\ uninstall\ *)
    rm -f "${state}/installed"
    [[ -n "${STUB_KEEP_CACHE:-}" ]] || rm -rf "$cache" ;;
  plugin\ details\ *) echo "Hooks (4)  MCP servers (3)" ;;
  *) echo "unexpected stub call: $*" >&2; exit 2 ;;
esac
EOF
chmod +x "${TEMP_ROOT}/bin/claude"

INSTALL_ENV=(
  "HARNESS_HOME=${TEMP_ROOT}/harness"
  "HARNESS_BIN_DIR=${TEMP_ROOT}/bin"
  "CLAUDE_STUB_STATE=${TEMP_ROOT}/claude"
  "HARNESS_PYTHON=${PY_BIN}"
  "CLAUDE_CONFIG_DIR=${TEMP_ROOT}/claude-config"
  "PATH=${TEMP_ROOT}/bin:/usr/bin:/bin"
)
STAGED="${TEMP_ROOT}/harness/marketplace/plugins/monolithic-dev-harness"
CACHED="${TEMP_ROOT}/claude/cache/0.6.2"
STALE_FILE="scripts/harness/decisions.py"

env "${INSTALL_ENV[@]}" bash "$INSTALLER" --source "$REPO_ROOT" --scope user --host claude --yes >"${TEMP_ROOT}/install.log" 2>&1
diff -rq "$STAGED" "$CACHED"

# An older build of the same version is cached; reinstalling must replace it.
printf '# stale build\n' >> "${CACHED}/${STALE_FILE}"
env "${INSTALL_ENV[@]}" bash "$INSTALLER" --source "$REPO_ROOT" --scope user --host claude --yes >"${TEMP_ROOT}/reinstall.log" 2>&1
diff -rq "$STAGED" "$CACHED"

# If Claude still keeps the stale copy, the installer fails and says so.
printf '# stale build\n' >> "${CACHED}/${STALE_FILE}"
if env "${INSTALL_ENV[@]}" STUB_KEEP_CACHE=1 bash "$INSTALLER" --source "$REPO_ROOT" --scope user --host claude --yes \
  >"${TEMP_ROOT}/stale.log" 2>&1; then
  printf 'installer reported success while Claude kept a stale plugin copy\n' >&2
  exit 1
fi
grep -q 'older copy of the plugin' "${TEMP_ROOT}/stale.log"

printf 'installer claude checks passed\n'
