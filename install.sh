#!/usr/bin/env bash
# One-shot installer for monolithic-dev-harness (Claude Code, Cursor, and Codex).
#
#   curl -fsSL https://github.com/Monolith-INC/monolithic-dev-harness/releases/latest/download/install.sh | bash
#
# While the repository is private, fetch it with the GitHub CLI instead (same script, same flags):
#
#   gh release download --repo Monolith-INC/monolithic-dev-harness --pattern install.sh --output - | bash
#
# Flags (after `bash -s --` when piping):
#   --host auto|claude|cursor|codex|all   hosts to install into (default: every host found)
#   --version <x.y.z>               release to install (default: latest)
#   --source <dir|archive.tar.gz>   install from a local build instead of downloading
#   --uninstall                     remove the harness from every host and delete its files
#   --yes                           skip the install or uninstall confirmation prompt
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
readonly CODEX_MARKETPLACE="${MARKETPLACE_DIR}/codex-marketplace"
readonly CODEX_AGENTS_DIR="${CODEX_HOME:-${HOME}/.codex}/agents"
readonly CODEX_CONFIG="${CODEX_HOME:-${HOME}/.codex}/config.toml"
readonly CODEX_CHOICES_MARKER="${HARNESS_HOME}/codex-choices-enabled-by-harness"

HOSTS="auto"
VERSION="${HARNESS_VERSION:-}"
SOURCE=""
UNINSTALL=0
ASSUME_YES=0
TMP=""
PY=""

say() { printf '\033[1m→\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
cleanup() { [[ -n "$TMP" ]] && rm -rf "$TMP"; return 0; }
trap cleanup EXIT

confirm_action() {
  [[ $ASSUME_YES -eq 1 ]] && return 0
  local answer
  if ! IFS= read -r -p "$1 [y/N] " answer </dev/tty; then
    die "confirmation requires an interactive terminal; rerun with --yes"
  fi
  case "$answer" in
    y|Y|yes|YES|Yes) ;;
    *) die "cancelled" ;;
  esac
}

usage() {
  cat <<'EOF'
monolithic-dev-harness installer

  --host auto|claude|cursor|codex|all   hosts to install into (default: every host found)
  --version <x.y.z>               release to install (default: latest)
  --source <dir|archive.tar.gz>   install from a local build instead of downloading
  --uninstall                     remove the harness from every host and delete its files
  --yes                           skip the install or uninstall confirmation prompt
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host) HOSTS="${2:?--host needs a value}"; shift 2 ;;
      --version) VERSION="${2:?--version needs a value}"; shift 2 ;;
      --source) SOURCE="${2:?--source needs a value}"; shift 2 ;;
      --uninstall) UNINSTALL=1; shift ;;
      --yes|-y) ASSUME_YES=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1 (see --help)" ;;
    esac
  done
  VERSION="${VERSION#v}"
  case "$HOSTS" in auto|claude|cursor|codex|all) ;; *) die "--host must be auto, claude, cursor, codex, or all" ;; esac
}

# --- preflight ---------------------------------------------------------------------------------

# The first Python 3.12 or newer, found the way the plugin's bin/harness-python finds it.
find_python() {
  local candidate
  for candidate in "${HARNESS_PYTHON:-}" python3.15 python3.14 python3.13 python3.12 python3; do
    [[ -n "$candidate" ]] || continue
    if have "$candidate" && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

preflight() {
  have tar || die "tar is required"
  PY="$(find_python)" || die "Python 3.12 or newer is required (the harness hooks and orchestrators are Python); install it or set HARNESS_PYTHON"
  have git || warn "git not found: versioned delivery features will be unavailable"
  have npx || warn "npx not found: install Node.js so the Azure DevOps MCP server can start"
  if [[ -z "$SOURCE" ]]; then
    have gh || have curl || die "curl or the GitHub CLI (gh) is required to download the release"
  fi
}

select_hosts() {
  local want_claude=0 want_cursor=0 want_codex=0
  case "$HOSTS" in
    claude) want_claude=1 ;;
    cursor) want_cursor=1 ;;
    codex) want_codex=1 ;;
    all) want_claude=1; want_cursor=1; want_codex=1 ;;
    auto)
      have claude && want_claude=1
      { [[ -d "${HOME}/.cursor" ]] || have cursor; } && want_cursor=1
      have codex && want_codex=1
      ;;
  esac
  if [[ $want_claude -eq 1 ]] && ! have claude; then
    die "Claude Code (the \`claude\` CLI) is not on PATH; install it or use --host cursor"
  fi
  if [[ $want_codex -eq 1 ]] && ! have codex; then
    die "Codex (the \`codex\` CLI) is not on PATH; install it or select another host"
  fi
  [[ $want_claude -eq 1 || $want_cursor -eq 1 || $want_codex -eq 1 ]] || die "no supported host was found; pass --host claude|cursor|codex|all"
  INSTALL_CLAUDE=$want_claude
  INSTALL_CURSOR=$want_cursor
  INSTALL_CODEX=$want_codex
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
  "$PY" -c "import json,sys; d=json.load(sys.stdin); print($1)" 2>/dev/null
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
  VERSION="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "${PAYLOAD}/plugins/${PLUGIN}/.claude-plugin/plugin.json")"
}

# --- configuration -----------------------------------------------------------------------------

# --- hosts -------------------------------------------------------------------------------------

install_marketplace_copy() {
  # Copy only what the hosts load, so a --source checkout never drags .git or scratch along.
  mkdir -p "$HARNESS_HOME"
  rm -rf "${MARKETPLACE_DIR}.new"
  mkdir -p "${MARKETPLACE_DIR}.new/plugins"
  cp -R "${PAYLOAD}/.claude-plugin" "${PAYLOAD}/.cursor-plugin" "${MARKETPLACE_DIR}.new/"
  cp -R "${PAYLOAD}/plugins/${PLUGIN}" "${MARKETPLACE_DIR}.new/plugins/"
  # Hosts started from the desktop may not see this terminal's PATH: remember the Python found
  # here, which bin/harness-python tries first.
  printf '%s\n' "$PY" >"${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/runtime/python-path"
  # Keep rendering dependencies in the owned plugin copy, never user-global Python. Only planning
  # discovery needs them, so a failure here is a warning, not a failed install.
  if ! "$PY" -m pip install --disable-pip-version-check --no-cache-dir --no-compile \
    --target "${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/runtime/python" \
    -r "${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/requirements-runtime.txt"; then
    warn "could not install Jinja2 for ${PY}; \`harness workflow render\` needs it. Install pip for that Python and run the installer again"
  fi
  cp -R "${PAYLOAD}/codex-marketplace" "${MARKETPLACE_DIR}.new/"
  mkdir -p "${MARKETPLACE_DIR}.new/codex-marketplace/.agents/plugins"
  cp "${PAYLOAD}/codex-marketplace/marketplace.json" \
    "${MARKETPLACE_DIR}.new/codex-marketplace/.agents/plugins/marketplace.json"
  mkdir -p "${MARKETPLACE_DIR}.new/codex-marketplace/plugins"
  cp -R "${PAYLOAD}/plugins/${PLUGIN}" "${MARKETPLACE_DIR}.new/codex-marketplace/plugins/"
  mkdir -p "${MARKETPLACE_DIR}.new/codex-marketplace/plugins/${PLUGIN}/runtime"
  cp "${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/runtime/python-path" \
    "${MARKETPLACE_DIR}.new/codex-marketplace/plugins/${PLUGIN}/runtime/"
  if [[ -d "${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/runtime/python" ]]; then
    cp -R "${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/runtime/python" \
      "${MARKETPLACE_DIR}.new/codex-marketplace/plugins/${PLUGIN}/runtime/"
  fi
  rm -rf "${MARKETPLACE_DIR}.new/codex-marketplace/plugins/${PLUGIN}/tests"
  cp "${PAYLOAD}/plugins/${PLUGIN}/codex.mcp.json" \
    "${MARKETPLACE_DIR}.new/codex-marketplace/plugins/${PLUGIN}/.mcp.json"
  "$PY" - "${MARKETPLACE_DIR}.new/codex-marketplace/plugins/${PLUGIN}/.mcp.json" \
    "${MARKETPLACE_DIR}/codex-marketplace/plugins/${PLUGIN}" <<'PY'
import json, sys
from pathlib import Path
path, root = Path(sys.argv[1]), sys.argv[2]
data = json.loads(path.read_text())
path.write_text(
    json.dumps(data).replace("${PLUGIN_ROOT}", json.dumps(root)[1:-1]) + "\n"
)
PY
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
}

install_cursor() {
  say "Cursor: installing to ${CURSOR_DIR}"
  mkdir -p "$(dirname "$CURSOR_DIR")"
  rm -rf "${CURSOR_DIR}.new"
  cp -R "${MARKETPLACE_DIR}/plugins/${PLUGIN}" "${CURSOR_DIR}.new"
  rm -rf "$CURSOR_DIR"
  mv "${CURSOR_DIR}.new" "$CURSOR_DIR"
  [[ -f "${CURSOR_DIR}/.cursor-plugin/plugin.json" ]] || die "Cursor plugin manifest missing after install"
}

install_codex() {
  say "Codex: registering the plugin marketplace"
  for agent in mdh_thermo_review mdh_thermo_quality; do
    if [[ -e "${CODEX_AGENTS_DIR}/${agent}.toml" ]] \
      && ! grep -qx '# managed by monolithic-dev-harness' "${CODEX_AGENTS_DIR}/${agent}.toml"; then
      die "${CODEX_AGENTS_DIR}/${agent}.toml already exists and is not harness-managed"
    fi
  done
  # Codex refuses to run when CODEX_HOME names a directory that does not exist yet.
  mkdir -p "$CODEX_AGENTS_DIR"
  configure_codex_choices
  codex plugin remove "$PLUGIN_ID" >/dev/null 2>&1 || true
  codex plugin marketplace remove "$PLUGIN" >/dev/null 2>&1 || true
  codex plugin marketplace add "$CODEX_MARKETPLACE" >/dev/null
  codex plugin add "$PLUGIN_ID" >/dev/null
  codex plugin list --json | grep -q "\"${PLUGIN_ID}\"" \
    || die "Codex did not report the plugin as installed"
  for agent in mdh_thermo_review mdh_thermo_quality; do
    cp "${CODEX_MARKETPLACE}/agents/${agent}.toml" "${CODEX_AGENTS_DIR}/${agent}.toml"
  done
}

codex_choice_setting() {
  "$PY" - "$CODEX_CONFIG" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
section = ""
for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else ():
    match = re.match(r"\s*\[([^]]+)\]\s*(?:#.*)?$", line)
    if match:
        section = match.group(1)
    elif section == "features":
        value = re.match(r"\s*default_mode_request_user_input\s*=\s*(true|false)\b", line)
        if value:
            print(value.group(1))
            raise SystemExit(0)
print("unset")
PY
}

configure_codex_choices() {
  case "$(codex_choice_setting)" in
    true) return 0 ;;
    false) die "Codex explicitly disables clickable questions in ${CODEX_CONFIG}; the harness cannot offer its required choices" ;;
    unset)
      codex features enable default_mode_request_user_input >/dev/null \
        || die "Codex could not enable clickable questions; the harness cannot run its choice-driven workflow"
      [[ "$(codex_choice_setting)" == true ]] \
        || die "Codex did not save the clickable-question setting"
      mkdir -p "$HARNESS_HOME"
      : > "$CODEX_CHOICES_MARKER"
      ;;
  esac
}

restore_codex_choices() {
  [[ -f "$CODEX_CHOICES_MARKER" ]] || return 0
  "$PY" - "$CODEX_CONFIG" <<'PY'
import os
import re
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(0)
section = ""
kept = []
for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
    match = re.match(r"\s*\[([^]]+)\]\s*(?:#.*)?$", line)
    if match:
        section = match.group(1)
    if section == "features" and re.match(
        r"\s*default_mode_request_user_input\s*=\s*true\b", line
    ):
        continue
    kept.append(line)
replacement = path.with_suffix(".toml.harness-tmp")
replacement.write_text("".join(kept), encoding="utf-8")
os.chmod(replacement, stat.S_IMODE(path.stat().st_mode))
replacement.replace(path)
PY
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
  restore_codex_choices
  if have codex; then
    codex plugin remove "$PLUGIN_ID" >/dev/null 2>&1 || true
    codex plugin marketplace remove "$PLUGIN" >/dev/null 2>&1 || true
  fi
  for agent in mdh_thermo_review mdh_thermo_quality; do
    if [[ -f "${CODEX_AGENTS_DIR}/${agent}.toml" ]] \
      && grep -qx '# managed by monolithic-dev-harness' "${CODEX_AGENTS_DIR}/${agent}.toml"; then
      rm -f "${CODEX_AGENTS_DIR}/${agent}.toml"
    fi
  done
  if have claude; then
    claude plugin uninstall "$PLUGIN_ID" >/dev/null 2>&1 || true
    claude plugin marketplace remove "$PLUGIN" >/dev/null 2>&1 || true
  fi
  rm -rf "$CURSOR_DIR" "$HARNESS_HOME"
  if [[ -L "${BIN_DIR}/harness" ]]; then rm -f "${BIN_DIR}/harness"; fi
  say "Done. Repositories keep their .harness/ folders (settings and records); delete them if you no longer want them."
}

main() {
  parse_args "$@"
  if [[ $UNINSTALL -eq 1 ]]; then
    # Removing the harness only edits JSON, so any Python 3 will do.
    PY="$(find_python)" || PY="python3"
    confirm_action "Remove ${PLUGIN} from this computer?"
    uninstall
    return 0
  fi
  preflight
  select_hosts
  if [[ $INSTALL_CODEX -eq 1 && "$(codex_choice_setting)" == false ]]; then
    die "Codex explicitly disables clickable questions in ${CODEX_CONFIG}; the harness cannot offer its required choices"
  fi
  stage_payload
  local targets=()
  [[ $INSTALL_CLAUDE -eq 1 ]] && targets+=("Claude Code")
  [[ $INSTALL_CURSOR -eq 1 ]] && targets+=("Cursor")
  [[ $INSTALL_CODEX -eq 1 ]] && targets+=("Codex")
  confirm_action "Install ${PLUGIN} v${VERSION} for ${targets[*]}?"
  install_marketplace_copy
  if [[ $INSTALL_CLAUDE -eq 1 ]]; then install_claude; fi
  if [[ $INSTALL_CURSOR -eq 1 ]]; then install_cursor; fi
  if [[ $INSTALL_CODEX -eq 1 ]]; then install_codex; fi
  install_cli

  cat <<EOF

✓ ${PLUGIN} ${VERSION} installed ($( [[ $INSTALL_CLAUDE -eq 1 ]] && printf 'Claude Code ' )$( [[ $INSTALL_CURSOR -eq 1 ]] && printf 'Cursor ' )$( [[ $INSTALL_CODEX -eq 1 ]] && printf 'Codex' ))

Next:
  1. Restart your host so the hooks and MCP servers load; trust Codex plugin hooks when prompted.
  2. In a repository you want governed:   harness bootstrap
  3. Check everything:                    harness doctor
EOF
}

main "$@"
