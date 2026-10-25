#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALLER="${ROOT}/install.sh"

assert_fails_with() {
  local expected="$1"
  shift
  local output
  if output="$("$@" 2>&1)"; then
    printf 'expected command to fail: %s\n' "$*" >&2
    return 1
  fi
  grep -Fq -- "$expected" <<<"$output"
}

grep -Fq -- '--scope user|local|all' "$INSTALLER"
grep -Fq -- '--project <dir>' "$INSTALLER"
grep -Fq -- '--purge' "$INSTALLER"
assert_fails_with '--scope is required in non-interactive mode' bash "$INSTALLER" --yes </dev/null
assert_fails_with '--scope all is removal-only' bash "$INSTALLER" --scope all --yes
assert_fails_with 'unknown option: --not-an-option' bash "$INSTALLER" --not-an-option

printf 'install scope parsing checks passed\n'
