#!/usr/bin/env bash
# Build the release archive that install.sh downloads.
#
#   scripts/build_release.sh [<version>]     # default: the version in the plugin manifest
#
# Output (dist/):
#   monolithic-dev-harness-<version>.tar.gz   marketplace root: .claude-plugin/, .cursor-plugin/, plugins/, docs
#   install.sh                                the one-shot installer, attached next to the archive
#   SHA256SUMS                                checksums for both
#
# The archive is built from committed files only (git archive), so local scratch never ships.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VERSION="${1:-$(python3 -c 'import json;print(json.load(open("plugins/monolithic-dev-harness/.claude-plugin/plugin.json"))["version"])')}"
VERSION="${VERSION#v}"
NAME="monolithic-dev-harness-${VERSION}"
DIST="${ROOT}/dist"

python3 scripts/check_versions.py --tag "v${VERSION}"

rm -rf "$DIST"
mkdir -p "$DIST"
# Ship what the hosts load; leave the test suites and repository tooling out of the archive.
git archive --format=tar --prefix="${NAME}/" HEAD \
  .claude-plugin .cursor-plugin plugins README.md CHANGELOG.md THIRD_PARTY_NOTICES.md \
  ':(exclude)plugins/monolithic-dev-harness/tests' \
  | gzip -9 > "${DIST}/${NAME}.tar.gz"
cp install.sh "${DIST}/install.sh"

cd "$DIST"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${NAME}.tar.gz" install.sh > SHA256SUMS
else
  shasum -a 256 "${NAME}.tar.gz" install.sh > SHA256SUMS
fi
echo "built ${DIST}/${NAME}.tar.gz"
cat SHA256SUMS
