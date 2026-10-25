#!/usr/bin/env bash
# One-shot installer for monolithic-dev-harness (Claude Code, Cursor, Codex, Kimi Code CLI, and Zed).
#
#   curl -fsSL https://github.com/Monolith-INC/monolithic-dev-harness/releases/latest/download/install.sh | bash
#
# While the repository is private, fetch it with the GitHub CLI instead (same script, same flags):
#
#   gh release download --repo Monolith-INC/monolithic-dev-harness --pattern install.sh --output - | bash
#
# Flags (after `bash -s --` when piping):
#   --host auto|claude|cursor|codex|kimi|zed|all   hosts to install into (default: every host found)
#   --version <x.y.z>               release to install (default: latest)
#   --source <dir|archive.tar.gz>   install from a local build instead of downloading
#   --scope user|local|all          installation scope (required; all is removal-only)
#   --project <dir>                 local project (repeatable; defaults to the current directory)
#   --purge                         remove local .harness data as well as installed assets
#   --uninstall                     remove the harness from the selected scope
#   --yes                           skip the install or uninstall confirmation prompt
#
# Environment: HARNESS_HOME (default ~/.local/share/monolithic-dev-harness), HARNESS_BIN_DIR
# (default ~/.local/bin), CURSOR_PLUGIN_DIR (default ~/.cursor/plugins/local/monolithic-dev-harness),
# ZED_CONFIG_DIR (default ~/.config/zed), KIMI_CONFIG_DIR (default ~/.kimi-code), AGENTS_SHARED_DIR (default ~/.agents),
# GH_TOKEN / GITHUB_TOKEN (private downloads without the
# GitHub CLI), CLAUDE_CONFIG_DIR (respected).
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
readonly ZED_DIR="${ZED_CONFIG_DIR:-${HOME}/.config/zed}"
readonly ZED_SETTINGS="${ZED_DIR}/settings.json"
readonly KIMI_DIR="${KIMI_CONFIG_DIR:-${KIMI_CODE_HOME:-${HOME}/.kimi-code}}"
readonly KIMI_CONFIG="${KIMI_DIR}/config.toml"
readonly AGENTS_SHARED_DIR="${AGENTS_SHARED_DIR:-${HOME}/.agents}"
readonly CODEX_MARKETPLACE="${MARKETPLACE_DIR}/codex-marketplace"
readonly CODEX_AGENTS_DIR="${CODEX_HOME:-${HOME}/.codex}/agents"

HOSTS="auto"
VERSION="${HARNESS_VERSION:-}"
SOURCE=""
UNINSTALL=0
ASSUME_YES=0
SCOPE=""
PROJECTS=()
PURGE=0
TMP=""
PY=""
MODULE_ROOT=""

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

  --host auto|claude|cursor|codex|kimi|zed|all   hosts to install into (default: every host found)
  --scope user|local|all          installation scope (required; all is removal-only)
  --project <dir>                 local project (repeatable; defaults to the current directory)
  --purge                         remove local .harness data as well as installed assets
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
      --scope) SCOPE="${2:?--scope needs a value}"; shift 2 ;;
      --project) PROJECTS+=("${2:?--project needs a value}"); shift 2 ;;
      --purge) PURGE=1; shift ;;
      --version) VERSION="${2:?--version needs a value}"; shift 2 ;;
      --source) SOURCE="${2:?--source needs a value}"; shift 2 ;;
      --uninstall) UNINSTALL=1; shift ;;
      --yes|-y) ASSUME_YES=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1 (see --help)" ;;
    esac
  done
  VERSION="${VERSION#v}"
  case "$HOSTS" in auto|claude|cursor|codex|kimi|zed|all) ;; *) die "--host must be auto, claude, cursor, codex, kimi, zed, or all" ;; esac
  case "$SCOPE" in "") ;; user|local|all) ;; *) die "--scope must be user, local, or all" ;; esac
}

resolve_scope() {
  if [[ -z "$SCOPE" ]]; then
    if ! IFS= read -r -p "Install scope (user/local/all) [user] " SCOPE </dev/tty; then
      die "--scope is required in non-interactive mode; rerun with --scope user, --scope local, or --scope all"
    fi
    SCOPE="${SCOPE:-user}"
    case "$SCOPE" in user|local|all) ;; *) die "scope must be user, local, or all" ;; esac
  fi
  if [[ "$SCOPE" == local && ${#PROJECTS[@]} -eq 0 ]]; then PROJECTS+=("$PWD"); fi
  [[ "$SCOPE" != local || ${#PROJECTS[@]} -eq 1 ]] || die "--scope local requires exactly one --project"
  if [[ "$SCOPE" == all && $UNINSTALL -ne 1 ]]; then
    die "--scope all is removal-only; use --uninstall"
  fi
}

configure_paths() {
  local project
  if [[ "$SCOPE" == local ]]; then
    project="$(cd "${PROJECTS[0]}" 2>/dev/null && pwd -P)" || die "local project does not exist: ${PROJECTS[0]}"
    [[ "$project" != "$HOME" && "$project" != / ]] || die "refusing to use home or root as a local project"
    PROJECTS=("$project")
  fi
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
  local want_claude=0 want_cursor=0 want_codex=0 want_kimi=0 want_zed=0
  case "$HOSTS" in
    claude) want_claude=1 ;;
    cursor) want_cursor=1 ;;
    codex) want_codex=1 ;;
    kimi) want_kimi=1 ;;
    zed) want_zed=1 ;;
    all) want_claude=1; want_cursor=1; want_codex=1; want_kimi=1; want_zed=1 ;;
    auto)
      have claude && want_claude=1
      { [[ -d "${HOME}/.cursor" ]] || have cursor; } && want_cursor=1
      have codex && want_codex=1
      { [[ -f "$KIMI_CONFIG" ]] || have kimi; } && want_kimi=1
      { [[ -f "$ZED_SETTINGS" ]] || have zed; } && want_zed=1
      ;;
  esac
  if [[ "$SCOPE" != local && $want_claude -eq 1 ]] && ! have claude; then
    die "Claude Code (the \`claude\` CLI) is not on PATH; install it or use --host cursor"
  fi
  if [[ "$SCOPE" != local && $want_codex -eq 1 ]] && ! have codex; then
    die "Codex (the \`codex\` CLI) is not on PATH; install it or select another host"
  fi
  # Zed and Kimi are config-file hosts with no CLI gate: their installers create the
  # config location when absent, so unlike claude/codex there is no hard "not found"
  # error. Auto-detect only opts in when a config or binary is present; an explicit
  # --host zed / --host kimi / --host all always installs.
  INSTALL_CLAUDE=$want_claude
  INSTALL_CURSOR=$want_cursor
  INSTALL_CODEX=$want_codex
  INSTALL_KIMI=$want_kimi
  INSTALL_ZED=$want_zed
  if [[ $INSTALL_KIMI -eq 1 ]] && ! have kimi; then
    warn "Kimi Code CLI (the \`kimi\` command) is not on PATH; hooks are registered in ${KIMI_CONFIG} but cannot fire until it is installed"
  fi
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
  # Keep required rendering dependencies in the owned copy; stop before package publication on failure.
  if ! "$PY" -m pip install --disable-pip-version-check --no-cache-dir --no-compile \
    --target "${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/runtime/python" \
    -r "${MARKETPLACE_DIR}.new/plugins/${PLUGIN}/requirements-runtime.txt"; then
    die "runtime dependencies could not be installed for ${PY}; package publication stopped. Install pip for that Python and retry"
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
  # Claude caches the plugin by version, so `plugin update` keeps stale code when a source install
  # reuses the version. Reinstalling replaces the cache; --keep-data preserves the plugin's data.
  if claude plugin list --json 2>/dev/null | grep -q "\"${PLUGIN_ID}\""; then
    claude plugin uninstall --keep-data "$PLUGIN_ID" >/dev/null
  fi
  claude plugin install "$PLUGIN_ID" >/dev/null
  claude plugin list --json 2>/dev/null | grep -q "\"${PLUGIN_ID}\"" || die "Claude Code did not report the plugin as installed"
  verify_claude_cache
  local details
  details="$(claude plugin details "$PLUGIN_ID" 2>/dev/null || true)"
  if grep -q "Hooks (0)" <<<"$details" || grep -q "MCP servers (0)" <<<"$details"; then
    die "Claude Code loaded the plugin without its hooks or MCP servers; the release is incomplete"
  fi
}

verify_claude_cache() {
  local cached
  cached="$(claude plugin list --json 2>/dev/null | "$PY" -c '
import json, sys
plugins = json.load(sys.stdin)
print(next((p.get("installPath", "") for p in plugins if p.get("id") == sys.argv[1]), ""))
' "$PLUGIN_ID")" || cached=""
  [[ -n "$cached" && -d "$cached" ]] || die "Claude Code did not report where it keeps the plugin"
  diff -rq "${MARKETPLACE_DIR}/plugins/${PLUGIN}" "$cached" >/dev/null \
    || die "Claude Code is still loading an older copy of the plugin from ${cached}; run \`claude plugin uninstall ${PLUGIN_ID}\` and install again"
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

configure_codex_choices() {
  say "Codex: preserving question feature preferences; native tools are discovered at runtime"
}

# Zed keeps its settings in JSON-with-comments; parse leniently, edit, and write pure JSON.
# Zed reads plain JSON fine and rewrites this file itself, so dropping comments is acceptable.
# A one-time .pre-harness backup is made before the first harness edit and restored on uninstall.
zed_settings_edit() {  # zed_settings_edit <python-script> [args...]
  "$PY" - "$ZED_SETTINGS" "$@"
}

install_zed() {
  say "Zed: registering MCP context servers in ${ZED_SETTINGS}"
  mkdir -p "$ZED_DIR"
  [[ -f "$ZED_SETTINGS" ]] || printf '{}\n' > "$ZED_SETTINGS"
  local plugin_root="${MARKETPLACE_DIR}/plugins/${PLUGIN}"
  zed_settings_edit "$plugin_root" "$HARNESS_HOME" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
plugin_root = Path(sys.argv[2]).resolve()

SERVERS = ("backlog-orchestrator", "workflow-orchestrator", "workflow-integrations")

def strip_jsonc(text: str) -> str:
    out, i, n = [], 0, len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
        elif ch == '"':
            in_str = True
            out.append(ch)
            i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] not in "\r\n":
                i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)

raw = settings_path.read_text(encoding="utf-8") if settings_path.is_file() else "{}"
try:
    data = json.loads(strip_jsonc(raw) or "{}")
except json.JSONDecodeError as exc:
    print(f"zed settings are not valid JSON even after removing comments: {exc}", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(data, dict):
    print("zed settings root must be a JSON object", file=sys.stderr)
    raise SystemExit(1)

context_servers = data.get("context_servers")
if context_servers is None:
    context_servers = {}
    data["context_servers"] = context_servers
if not isinstance(context_servers, dict):
    print("zed settings context_servers must be a JSON object", file=sys.stderr)
    raise SystemExit(1)

backup = settings_path.with_suffix(".json.pre-harness")
if not backup.exists():
    backup.write_text(raw, encoding="utf-8")

zed_mcp = json.loads((plugin_root / "zed.mcp.json").read_text(encoding="utf-8"))
for name in SERVERS:
    entry = zed_mcp[name]
    context_servers[name] = {
        "command": entry["command"],
        "args": [a.replace("${PLUGIN_ROOT}", str(plugin_root)) for a in entry["args"]],
        "env": {k: v.replace("${PLUGIN_ROOT}", str(plugin_root)) for k, v in entry["env"].items()},
    }

settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"wrote {len(SERVERS)} context servers to {settings_path}")
PY
  [[ -f "$ZED_SETTINGS" ]] || die "Zed settings were not written"
}

# Kimi Code CLI discovers skills and agents at user level in the shared
# ~/.agents/skills and ~/.agents/agents directories (its docs: "the generic
# ~/.agents/ ... directory stays under the real OS home so it can be shared
# across tools"), so one symlink set also serves other hosts reading them.
# Existing entries that are not harness-managed are never touched.
link_kimi_shared_files() {
  local plugin_root="${MARKETPLACE_DIR}/plugins/${PLUGIN}"
  local scope dest name target
  for scope in skills agents; do
    [[ -d "${plugin_root}/${scope}" ]] || continue
    dest="${AGENTS_SHARED_DIR}/${scope}"
    mkdir -p "$dest"
    for target in "${plugin_root}/${scope}"/*; do
      [[ -e "$target" ]] || continue
      name="$(basename "$target")"
      if [[ -L "${dest}/${name}" ]]; then
        [[ "$(readlink "${dest}/${name}")" == "$target" ]] && continue
        warn "shared ${scope}/${name} is a symlink to elsewhere; leaving it in place"
        continue
      fi
      if [[ -e "${dest}/${name}" ]]; then
        warn "shared ${scope}/${name} already exists and is not harness-managed; leaving it in place"
        continue
      fi
      ln -s "$target" "${dest}/${name}"
    done
  done
  say "Kimi Code CLI: harness skills and agents linked into ${AGENTS_SHARED_DIR} (user level)"
}

install_kimi() {
  say "Kimi Code CLI: registering PreToolUse hooks in ${KIMI_CONFIG}"
  mkdir -p "$KIMI_DIR"
  [[ -f "$KIMI_CONFIG" ]] || printf '\n' > "$KIMI_CONFIG"
  local plugin_root="${MARKETPLACE_DIR}/plugins/${PLUGIN}"
  local backup="${KIMI_CONFIG}.pre-harness"
  [[ -f "$backup" ]] || cp "$KIMI_CONFIG" "$backup"
  "$PY" - "$KIMI_CONFIG" "$plugin_root" <<'PY'
import json
import re
import sys
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1])
plugin_root = Path(sys.argv[2]).resolve()

# Only tool names documented in the Kimi Code CLI hooks docs are matched
# (Shell, WriteFile, StrReplaceFile), plus the mcp__* tool glob the agent
# docs describe. Confirm against a live runtime before widening this.
HOOKS = (
    {
        "event": "PreToolUse",
        "matcher": "Shell|WriteFile|StrReplaceFile|mcp__.*",
        "command": f'sh "{plugin_root}/bin/harness-python" "{plugin_root}/scripts/harness/hook.py" --host kimi --event pre-tool',
        "timeout": 15,
    },
    {
        "event": "UserPromptSubmit",
        "matcher": "",
        "command": f'sh "{plugin_root}/bin/harness-python" "{plugin_root}/scripts/harness/hook.py" --host kimi --event prompt',
        "timeout": 10,
    },
    {
        "event": "Stop",
        "matcher": "",
        "command": f'sh "{plugin_root}/bin/harness-python" "{plugin_root}/scripts/harness/hook.py" --host kimi --event stop',
        "timeout": 10,
    },
)

BEGIN = "# >>> monolithic-dev-harness hooks (managed: install.sh --host kimi) >>>"
END = "# <<< monolithic-dev-harness hooks <<<"

raw = config_path.read_text(encoding="utf-8")
# Drop a previously managed block so reinstalls stay idempotent.
raw = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "", raw, flags=re.DOTALL)

lines = ["", BEGIN]
for hook in HOOKS:
    lines.append("[[hooks]]")
    lines.append(f'event = "{hook["event"]}"')
    if hook["matcher"]:
        lines.append(f'matcher = "{hook["matcher"]}"')
    # json.dumps escaping is valid for TOML basic strings.
    lines.append(f'command = {json.dumps(hook["command"])}')
    lines.append(f'timeout = {hook["timeout"]}')
    lines.append("")
lines.append(END)
block = "\n".join(lines) + "\n"

updated = raw.rstrip("\n") + "\n" + block
# Fail closed on our own edit: if we cannot parse it, Kimi must not either.
tomllib.loads(updated)
config_path.write_text(updated, encoding="utf-8")
print(f"wrote {len(HOOKS)} harness hooks to {config_path}")
PY
  link_kimi_shared_files
}

install_cli() {
  mkdir -p "$BIN_DIR"
  ln -sfn "${MARKETPLACE_DIR}/plugins/${PLUGIN}/bin/harness" "${BIN_DIR}/harness"
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *) warn "${BIN_DIR} is not on your PATH; add it to use the \`harness\` command" ;;
  esac
}

selected_host_names() {
  printf '%s' "$( [[ $INSTALL_CLAUDE -eq 1 ]] && printf 'claude,' )$( [[ $INSTALL_CURSOR -eq 1 ]] && printf 'cursor,' )$( [[ $INSTALL_CODEX -eq 1 ]] && printf 'codex,' )$( [[ $INSTALL_KIMI -eq 1 ]] && printf 'kimi,' )$( [[ $INSTALL_ZED -eq 1 ]] && printf 'zed,' )" | sed 's/,$//'
}

installation_module_root() {
  if [[ -n "$SOURCE" ]]; then
    stage_payload
    MODULE_ROOT="${PAYLOAD}/plugins/${PLUGIN}"
  elif [[ -f "${MARKETPLACE_DIR}/plugins/${PLUGIN}/scripts/harness/installation_lifecycle.py" ]]; then
    MODULE_ROOT="${MARKETPLACE_DIR}/plugins/${PLUGIN}"
  else
    stage_payload
    MODULE_ROOT="${PAYLOAD}/plugins/${PLUGIN}"
  fi
}

run_installation_module() {
  local module_root="$1"
  shift
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${module_root}/scripts${PYTHONPATH:+:${PYTHONPATH}}" "$PY" -m harness.installation_lifecycle "$@"
}

record_installation() {
  local module_root="$1" hosts
  hosts="$(selected_host_names)"
  run_installation_module "$module_root" record --scope user --plugin "${MARKETPLACE_DIR}/plugins/${PLUGIN}" --host "$hosts"
}

uninstall() {
  say "Removing ${PLUGIN}"
  local module_root project args=()
  installation_module_root
  module_root="$MODULE_ROOT"
  args=(uninstall --scope "$SCOPE")
  for project in "${PROJECTS[@]}"; do args+=(--project "$project"); done
  [[ $PURGE -eq 1 ]] && args+=(--purge)
  run_installation_module "$module_root" "${args[@]}"
  say "Done. Repositories keep their .harness/ folders (settings and records); delete them if you no longer want them."
}

main() {
  parse_args "$@"
  resolve_scope
  configure_paths
  if [[ $UNINSTALL -eq 1 ]]; then
    PY="$(find_python)" || die "Python 3.12 or newer is required for ownership-safe removal; set HARNESS_PYTHON"
    confirm_action "Remove ${PLUGIN} from this computer?"
    uninstall
    return 0
  fi
  preflight
  select_hosts
  if [[ "$SCOPE" == local && $INSTALL_CLAUDE -eq 0 && $INSTALL_CURSOR -eq 0 && $INSTALL_CODEX -eq 0 && $INSTALL_KIMI -eq 0 && $INSTALL_ZED -eq 0 ]]; then
    die "local installation selected no hosts; pass --host explicitly or install a supported host"
  fi
  stage_payload
  local targets=()
  [[ $INSTALL_CLAUDE -eq 1 ]] && targets+=("Claude Code")
  [[ $INSTALL_CURSOR -eq 1 ]] && targets+=("Cursor")
  [[ $INSTALL_CODEX -eq 1 ]] && targets+=("Codex")
  [[ $INSTALL_KIMI -eq 1 ]] && targets+=("Kimi Code CLI")
  [[ $INSTALL_ZED -eq 1 ]] && targets+=("Zed")
  confirm_action "Install ${PLUGIN} v${VERSION} for ${targets[*]}?"
  if [[ "$SCOPE" == local ]]; then
    local module_root project
    module_root="${PAYLOAD}/plugins/${PLUGIN}"
    for project in "${PROJECTS[@]}"; do
      if [[ $PURGE -eq 1 ]]; then
        run_installation_module "$module_root" uninstall --scope local --project "$project" --purge
      fi
    done
    run_installation_module "$module_root" check --scope local --project "${PROJECTS[0]}" --plugin "${PAYLOAD}/plugins/${PLUGIN}" --destination "${MARKETPLACE_DIR}/plugins/${PLUGIN}" --host "$(selected_host_names)"
    install_marketplace_copy
    install_cli
    module_root="${MARKETPLACE_DIR}/plugins/${PLUGIN}"
    for project in "${PROJECTS[@]}"; do
      run_installation_module "$module_root" install --scope local --project "$project" --plugin "${MARKETPLACE_DIR}/plugins/${PLUGIN}" --host "$(selected_host_names)"
    done
    return 0
  fi
  if [[ "$SCOPE" == user && $PURGE -eq 1 ]]; then
    run_installation_module "${PAYLOAD}/plugins/${PLUGIN}" uninstall --scope user --purge
  fi
  run_installation_module "${PAYLOAD}/plugins/${PLUGIN}" begin --scope user --host "$(selected_host_names)"
  install_marketplace_copy
  if [[ $INSTALL_CLAUDE -eq 1 ]]; then install_claude; fi
  if [[ $INSTALL_CURSOR -eq 1 ]]; then install_cursor; fi
  if [[ $INSTALL_CODEX -eq 1 ]]; then install_codex; fi
  if [[ $INSTALL_KIMI -eq 1 ]]; then install_kimi; fi
  if [[ $INSTALL_ZED -eq 1 ]]; then install_zed; fi
  install_cli
  record_installation "${MARKETPLACE_DIR}/plugins/${PLUGIN}"

  cat <<EOF

✓ ${PLUGIN} ${VERSION} installed ($( [[ $INSTALL_CLAUDE -eq 1 ]] && printf 'Claude Code ' )$( [[ $INSTALL_CURSOR -eq 1 ]] && printf 'Cursor ' )$( [[ $INSTALL_CODEX -eq 1 ]] && printf 'Codex ' )$( [[ $INSTALL_KIMI -eq 1 ]] && printf 'Kimi Code CLI ' )$( [[ $INSTALL_ZED -eq 1 ]] && printf 'Zed' ))

Next:
  1. Restart your host so the hooks and MCP servers load; trust plugin hooks when prompted.
  2. In a repository you want governed:   harness bootstrap
  3. Check everything:                    harness doctor
EOF
}

main "$@"
