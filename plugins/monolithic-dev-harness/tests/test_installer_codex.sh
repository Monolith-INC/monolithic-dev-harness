#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEMP_ROOT"' EXIT
mkdir -p "$TEMP_ROOT/bin" "$TEMP_ROOT/codex"
cat > "$TEMP_ROOT/bin/codex" <<'CLI'
#!/usr/bin/env sh
case "$*" in
  'plugin list --json') printf '[{"id":"monolithic-dev-harness@monolithic-dev-harness"}]\n' ;;
  features*) printf 'installer must not change native question feature flags\n' >&2; exit 1 ;;
  *) exit 0 ;;
esac
CLI
chmod +x "$TEMP_ROOT/bin/codex"
printf '# user setting\n[features]\ndefault_mode_request_user_input = false\n' > "$TEMP_ROOT/codex/config.toml"
cp "$TEMP_ROOT/codex/config.toml" "$TEMP_ROOT/original.toml"
env CODEX_HOME="$TEMP_ROOT/codex" HARNESS_HOME="$TEMP_ROOT/harness" \
  HARNESS_BIN_DIR="$TEMP_ROOT/bin" HARNESS_PYTHON="${PYTHON:-python3.12}" \
  PATH="$TEMP_ROOT/bin:$PATH" bash "$REPO_ROOT/install.sh" \
  --host codex --source "$REPO_ROOT" --yes > "$TEMP_ROOT/install.log" 2>&1 || { cat "$TEMP_ROOT/install.log"; exit 1; }
cmp "$TEMP_ROOT/original.toml" "$TEMP_ROOT/codex/config.toml"
test -f "$TEMP_ROOT/codex/agents/mdh_thermo_review.toml"
test -f "$TEMP_ROOT/harness/marketplace/codex-marketplace/plugins/monolithic-dev-harness/scripts/host_adapters/codex_runtime.py"
test -f "$TEMP_ROOT/harness/marketplace/codex-marketplace/plugins/monolithic-dev-harness/scripts/host_adapters/codex_bindings.py"
printf 'Codex installer preserves native question configuration and packages runtime modules\n'
