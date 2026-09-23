#!/usr/bin/env bash
# One-shot installer for monolithic-dev-harness (Claude Code and Cursor).
#
#   curl -fsSL https://github.com/Monolith-INC/monolithic-dev-harness/releases/latest/download/install.sh | bash
#
# While the repository is private, fetch it with the GitHub CLI instead (same script, same flags):
#
#   gh release download --repo Monolith-INC/monolithic-dev-harness --pattern install.sh --output - | bash
#
# Flags (after `bash -s --` when piping):
#   --host auto|claude|cursor|all   hosts to install into (default: auto = every host found)
#   --org <name>                    Azure DevOps organization (default: $AZURE_DEVOPS_ORG, else asked)
#   --version <x.y.z>               release to install (default: latest)
#   --source <dir|archive.tar.gz>   install from a local build instead of downloading
#   --uninstall                     remove the harness from every host and delete its files
#   --yes                           never prompt
#
# Environment: HARNESS_HOME (default ~/.local/share/monolithic-dev-harness), HARNESS_BIN_DIR
# (default ~/.local/bin), CURSOR_PLUGIN_DIR (default ~/.cursor/plugins/local/monolithic-dev-harness),
# GH_TOKEN / GITHUB_TOKEN (private downloads without the GitHub CLI), CLAUDE_CONFIG_DIR (respected).
#
# Nothing is cloned: the installer downloads the release archive, verifies its SHA-256, and
# registers it with each host.
set -euo pipefail

readonly REPO="Monolith-INC/monolithic-dev-harness"
readonly PLUGIN="monolithic-dev-harness"
readonly PLUGIN_ID="${PLUGIN}@${PLUGIN}"
readonly HARNESS_HOME="${HARNESS_HOME:-${HOME}/.local/share/${PLUGIN}}"
readonly MARKETPLACE_DIR="${HARNESS_HOME}/marketplace"
readonly BIN_DIR="${HARNESS_BIN_DIR:-${HOME}/.local/bin}"
readonly CURSOR_DIR="${CURSOR_PLUGIN_DIR:-${HOME}/.cursor/plugins/local/${PLUGIN}}"
readonly CLAUDE_SETTINGS="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}/settings.json"

HOSTS="auto"
ORG="${AZURE_DEVOPS_ORG:-}"
VERSION="${HARNESS_VERSION:-}"
SOURCE=""
UNINSTALL=0
ASSUME_YES=0
TMP=""

say() { printf '\033[1m→\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
cleanup() { [[ -n "$TMP" ]] && rm -rf "$TMP"; return 0; }
trap cleanup EXIT

usage() {
  cat <<'EOF'
monolithic-dev-harness installer

  --host auto|claude|cursor|all   hosts to install into (default: every host found)
  --org <name>                    Azure DevOps organization (default: $AZURE_DEVOPS_ORG, else asked)
  --version <x.y.z>               release to install (default: latest)
  --source <dir|archive.tar.gz>   install from a local build instead of downloading
  --uninstall                     remove the harness from every host and delete its files
  --yes                           never prompt
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host) HOSTS="${2:?--host needs a value}"; shift 2 ;;
      --org) ORG="${2:?--org needs a value}"; shift 2 ;;
      --version) VERSION="${2:?--version needs a value}"; shift 2 ;;
      --source) SOURCE="${2:?--source needs a value}"; shift 2 ;;
      --uninstall) UNINSTALL=1; shift ;;
      --yes|-y) ASSUME_YES=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1 (see --help)" ;;
    esac
  done
  VERSION="${VERSION#v}"
  case "$HOSTS" in auto|claude|cursor|all) ;; *) die "--host must be auto, claude, cursor, or all" ;; esac
}

# --- preflight ---------------------------------------------------------------------------------

python_ok() {
  have python3 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
}

preflight() {
  have tar || die "tar is required"
  python_ok || die "python3 3.10 or newer is required (the harness hooks and orchestrators are Python)"
  have git || die "git is required (the hooks read git state)"
  have npx || warn "npx not found: install Node.js so the Azure DevOps MCP server can start"
  if [[ -z "$SOURCE" ]]; then
    have gh || have curl || die "curl or the GitHub CLI (gh) is required to download the release"
  fi
}

select_hosts() {
  local want_claude=0 want_cursor=0
  case "$HOSTS" in
    claude) want_claude=1 ;;
    cursor) want_cursor=1 ;;
    all) want_claude=1; want_cursor=1 ;;
    auto)
      have claude && want_claude=1
      { [[ -d "${HOME}/.cursor" ]] || have cursor; } && want_cursor=1
      ;;
  esac
  if [[ $want_claude -eq 1 ]] && ! have claude; then
    die "Claude Code (the \`claude\` CLI) is not on PATH; install it or use --host cursor"
  fi
  [[ $want_claude -eq 1 || $want_cursor -eq 1 ]] || die "neither Claude Code nor Cursor was found; pass --host claude|cursor|all"
  INSTALL_CLAUDE=$want_claude
  INSTALL_CURSOR=$want_cursor
}

# --- download ----------------------------------------------------------------------------------

gh_ready() { have gh && gh auth status >/dev/null 2>&1; }
token() { printf '%s' "${GH_TOKEN:-${GITHUB_TOKEN:-}}"; }

api_get() {  # api_get <path under the repository> [<accept header>]
  local path="$1" accept="${2:-application/vnd.github+json}"
  if gh_ready; then
    gh api -H "Accept: ${accept}" "repos/${REPO}${path}"
  elif [[ -n "$(token)" ]]; then
    curl -fsSL -H "Authorization: Bearer $(token)" -H "Accept: ${accept}" \
      "https://api.github.com/repos/${REPO}${path}"
  else
    curl -fsSL -H "Accept: ${accept}" "https://api.github.com/repos/${REPO}${path}"
  fi
}

json_field() {  # json_field <python expression over `d`>; reads JSON on stdin
  python3 -c "import json,sys; d=json.load(sys.stdin); print($1)" 2>/dev/null
}

resolve_version() {
  [[ -n "$VERSION" ]] && return 0
  VERSION="$(api_get /releases/latest | json_field 'd["tag_name"]' || true)"
  [[ -n "$VERSION" ]] || die "could not find the latest release. Private repository? Run \`gh auth login\` or set GH_TOKEN, or pass --version"
  VERSION="${VERSION#v}"
}

release_id() {
  # The release is looked up by tag only for its id. GitHub's by-tag view has been seen to list
  # no files for a release that has them, so the files are listed by id instead.
  [[ -n "${RELEASE_ID:-}" ]] && return 0
  RELEASE_ID="$(api_get "/releases/tags/v${VERSION}" | json_field 'd["id"]' || true)"
  [[ -n "$RELEASE_ID" ]] || die "could not find release v${VERSION}. Private repository? Run \`gh auth login\` or set GH_TOKEN"
}

fetch_asset() {  # fetch_asset <asset name> <destination dir>
  local asset="$1" dest="$2" id
  release_id
  id="$(api_get "/releases/${RELEASE_ID}/assets?per_page=100" \
    | json_field "next(a['id'] for a in d if a['name'] == '${asset}')" || true)"
  [[ -n "$id" ]] || die "release v${VERSION} has no ${asset}"
  api_get "/releases/assets/${id}" "application/octet-stream" > "${dest}/${asset}" \
    || die "could not download ${asset} for v${VERSION}. Private repository? Run \`gh auth login\` or set GH_TOKEN"
}

verify_checksum() {  # verify_checksum <dir> <file>
  local dir="$1" file="$2" expected actual
  expected="$(awk -v f="$file" '$2==f {print $1}' "${dir}/SHA256SUMS")"
  [[ -n "$expected" ]] || die "SHA256SUMS has no entry for ${file}"
  if have sha256sum; then actual="$(sha256sum "${dir}/${file}" | awk '{print $1}')"
  else actual="$(shasum -a 256 "${dir}/${file}" | awk '{print $1}')"; fi
  [[ "$expected" == "$actual" ]] || die "checksum mismatch for ${file}: refusing to install"
}

stage_payload() {  # leaves the marketplace root in $PAYLOAD
  TMP="$(mktemp -d)"
  if [[ -n "$SOURCE" && -d "$SOURCE" ]]; then
    PAYLOAD="$(cd "$SOURCE" && pwd)"
  else
    local archive
    if [[ -n "$SOURCE" ]]; then
      archive="$SOURCE"
    else
      resolve_version
      say "Downloading ${PLUGIN} v${VERSION}"
      fetch_asset "${PLUGIN}-${VERSION}.tar.gz" "$TMP"
      fetch_asset "SHA256SUMS" "$TMP"
      verify_checksum "$TMP" "${PLUGIN}-${VERSION}.tar.gz"
      archive="${TMP}/${PLUGIN}-${VERSION}.tar.gz"
    fi
    mkdir -p "${TMP}/extract"
    tar -xzf "$archive" -C "${TMP}/extract"
    PAYLOAD="$(find "${TMP}/extract" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  fi
  [[ -f "${PAYLOAD}/.claude-plugin/marketplace.json" && -f "${PAYLOAD}/plugins/${PLUGIN}/.claude-plugin/plugin.json" ]] \
    || die "${SOURCE:-the release archive} does not look like a ${PLUGIN} build"
  VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "${PAYLOAD}/plugins/${PLUGIN}/.claude-plugin/plugin.json")"
}

# --- configuration -----------------------------------------------------------------------------

ask_org() {
  [[ -n "$ORG" ]] && return 0
  if [[ $ASSUME_YES -eq 0 && -r /dev/tty ]]; then
    printf 'Azure DevOps organization (as in dev.azure.com/<org>): ' > /dev/tty
    IFS= read -r ORG < /dev/tty || true
  fi
  [[ -n "$ORG" ]] || warn "no Azure DevOps organization given: set AZURE_DEVOPS_ORG later, or re-run with --org"
}

claude_settings_env() {  # claude_settings_env set <org> | unset
  python3 - "$CLAUDE_SETTINGS" "$1" "${2:-}" <<'PY'
import json, sys
from pathlib import Path
path, action, org = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
data = json.loads(path.read_text()) if path.is_file() and path.read_text().strip() else {}
env = data.setdefault("env", {})
if action == "set":
    env["AZURE_DEVOPS_ORG"] = org
else:
    env.pop("AZURE_DEVOPS_ORG", None)
    if not env:
        data.pop("env")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, indent=2) + "\n")
PY
}

# --- hosts -------------------------------------------------------------------------------------

install_marketplace_copy() {
  # Copy only what the hosts load, so a --source checkout never drags .git or scratch along.
  mkdir -p "$HARNESS_HOME"
  rm -rf "${MARKETPLACE_DIR}.new"
  mkdir -p "${MARKETPLACE_DIR}.new/plugins"
  cp -R "${PAYLOAD}/.claude-plugin" "${PAYLOAD}/.cursor-plugin" "${MARKETPLACE_DIR}.new/"
  cp -R "${PAYLOAD}/plugins/${PLUGIN}" "${MARKETPLACE_DIR}.new/plugins/"
  rm -rf "${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/tests"
  find "${MARKETPLACE_DIR}.new" -name __pycache__ -type d -prune -exec rm -rf {} +
  for doc in README.md CHANGELOG.md THIRD_PARTY_NOTICES.md; do
    if [[ -f "${PAYLOAD}/${doc}" ]]; then cp "${PAYLOAD}/${doc}" "${MARKETPLACE_DIR}.new/"; fi
  done
  rm -rf "$MARKETPLACE_DIR"
  mv "${MARKETPLACE_DIR}.new" "$MARKETPLACE_DIR"
}

install_claude() {
  say "Claude Code: registering the plugin"
  if claude plugin marketplace list --json 2>/dev/null | grep -q "\"${PLUGIN}\""; then
    claude plugin marketplace update "$PLUGIN" >/dev/null
  else
    claude plugin marketplace add "$MARKETPLACE_DIR" >/dev/null
  fi
  if claude plugin list --json 2>/dev/null | grep -q "\"${PLUGIN_ID}\""; then
    claude plugin update "$PLUGIN_ID" >/dev/null
  else
    claude plugin install "$PLUGIN_ID" >/dev/null
  fi
  claude plugin list --json 2>/dev/null | grep -q "\"${PLUGIN_ID}\"" || die "Claude Code did not report the plugin as installed"
  local details
  details="$(claude plugin details "$PLUGIN_ID" 2>/dev/null || true)"
  if grep -q "Hooks (0)" <<<"$details" || grep -q "MCP servers (0)" <<<"$details"; then
    die "Claude Code loaded the plugin without its hooks or MCP servers; the release is incomplete"
  fi
  if [[ -n "$ORG" ]]; then
    claude_settings_env set "$ORG"
    say "Claude Code: AZURE_DEVOPS_ORG=${ORG} recorded in ${CLAUDE_SETTINGS}"
  fi
}

install_cursor() {
  say "Cursor: installing to ${CURSOR_DIR}"
  mkdir -p "$(dirname "$CURSOR_DIR")"
  rm -rf "${CURSOR_DIR}.new"
  cp -R "${MARKETPLACE_DIR}/plugins/${PLUGIN}" "${CURSOR_DIR}.new"
  if [[ -n "$ORG" ]]; then
    # Cursor is usually started from the desktop, without the shell's environment: pin the org.
    python3 - "${CURSOR_DIR}.new/cursor.mcp.json" "$ORG" <<'PY'
import sys
from pathlib import Path
path, org = Path(sys.argv[1]), sys.argv[2]
path.write_text(path.read_text().replace("${env:AZURE_DEVOPS_ORG}", org))
PY
  fi
  rm -rf "$CURSOR_DIR"
  mv "${CURSOR_DIR}.new" "$CURSOR_DIR"
  [[ -f "${CURSOR_DIR}/.cursor-plugin/plugin.json" ]] || die "Cursor plugin manifest missing after install"
}

install_cli() {
  mkdir -p "$BIN_DIR"
  ln -sfn "${MARKETPLACE_DIR}/plugins/${PLUGIN}/bin/harness" "${BIN_DIR}/harness"
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *) warn "${BIN_DIR} is not on your PATH; add it to use the \`harness\` command" ;;
  esac
}

uninstall() {
  say "Removing ${PLUGIN}"
  if have claude; then
    claude plugin uninstall "$PLUGIN_ID" >/dev/null 2>&1 || true
    claude plugin marketplace remove "$PLUGIN" >/dev/null 2>&1 || true
    if [[ -f "$CLAUDE_SETTINGS" ]]; then claude_settings_env unset; fi
  fi
  rm -rf "$CURSOR_DIR" "$HARNESS_HOME"
  if [[ -L "${BIN_DIR}/harness" ]]; then rm -f "${BIN_DIR}/harness"; fi
  say "Done. Repositories keep their .harness/ policy files; delete them if you no longer want them."
}

main() {
  parse_args "$@"
  if [[ $UNINSTALL -eq 1 ]]; then uninstall; return 0; fi
  preflight
  select_hosts
  stage_payload
  ask_org
  install_marketplace_copy
  if [[ $INSTALL_CLAUDE -eq 1 ]]; then install_claude; fi
  if [[ $INSTALL_CURSOR -eq 1 ]]; then install_cursor; fi
  install_cli

  cat <<EOF

✓ ${PLUGIN} ${VERSION} installed ($( [[ $INSTALL_CLAUDE -eq 1 ]] && printf 'Claude Code ' )$( [[ $INSTALL_CURSOR -eq 1 ]] && printf 'Cursor' ))

Next:
  1. Restart Claude Code / reload Cursor so the hooks and MCP servers load.
  2. In a repository you want governed:   harness bootstrap
  3. Check everything:                    harness doctor
EOF
}

main "$@"
