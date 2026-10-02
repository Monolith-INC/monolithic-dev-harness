---
title: Development
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Development

## Purpose

How to change the harness safely: where the sources are, how to run it from a checkout, and what
must pass before a change is done.

## Prerequisites

- Python 3.10+ (CI tests 3.10 and 3.12), `git`, Node.js.
- Claude Code for local install checks; Cursor optional.

```bash
python3 -m venv .venv
.venv/bin/pip install pytest ruff==0.16.4 shellcheck-py
```

## Authoritative Source Files

| What | Where |
| --- | --- |
| Skills | `plugins/monolithic-dev-harness/skills/*/SKILL.md` (+ `manifest.json` for orchestrated skills) |
| Rules and hook entry point | `plugins/monolithic-dev-harness/scripts/harness/` |
| Workflow policy, orchestrator, gateway, registry | `plugins/monolithic-dev-harness/scripts/` |
| Tracker folders (manifests and adapters) | `plugins/monolithic-dev-harness/trackers/` |
| Settings and tracker schemas | `plugins/monolithic-dev-harness/config/` |
| Backlog orchestrator | `plugins/monolithic-dev-harness/runtime/orchestrator_core/` |
| Hook wiring | `plugins/monolithic-dev-harness/hooks/hooks.json`, `hooks/cursor.hooks.json` |
| MCP wiring | `plugins/monolithic-dev-harness/.mcp.json`, `cursor.mcp.json` |
| Manifests | `plugins/monolithic-dev-harness/.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, root `.claude-plugin/` and `.cursor-plugin/` marketplaces |
| Policy schema and example | `plugins/monolithic-dev-harness/config/`, `examples/` |
| Installer and release tooling | `install.sh`, `scripts/` |

## Generated Files

Never edit these by hand; rebuild or reinstall instead:

- `dist/` (release archive, `install.sh` copy, `SHA256SUMS`): `scripts/build_release.sh`.
- Installed copies: the Claude plugin cache, `~/.cursor/plugins/local/monolithic-dev-harness`,
  `~/.local/share/monolithic-dev-harness`.

## Development Workflow

1. Branch from `main` (`feature/…`, `bugfix/…`, `techdebt/…`).
2. Change the sources above; add or update tests with the change.
3. Run the full outcome gate below.
4. Try it in a host from your checkout, without touching your real install:

   ```bash
   S=$(mktemp -d)
   HOME=$S CLAUDE_CONFIG_DIR=$S/.claude bash install.sh --source . --yes
   HOME=$S CLAUDE_CONFIG_DIR=$S/.claude claude plugin list
   ```

5. Open a pull request; CI runs the same gate plus a sandboxed install of the built release.

## Tests

See [testing.md](testing.md).

## Full Outcome Gate

```bash
.venv/bin/ruff check --no-cache . && .venv/bin/ruff format --no-cache --check .
.venv/bin/shellcheck install.sh scripts/build_release.sh plugins/monolithic-dev-harness/bin/* plugins/monolithic-dev-harness/tests/run.sh
PYTHON=.venv/bin/python plugins/monolithic-dev-harness/tests/run.sh
python3 scripts/check_versions.py
claude plugin validate plugins/monolithic-dev-harness && claude plugin validate .
```

## Definition of Done

- The outcome gate passes locally and in CI.
- A new or changed rule has a deny test and an allow test through `hook.py`.
- User-visible behavior is reflected in `docs/` and, for releases, `CHANGELOG.md`.
- No client- or organization-specific names, ids, or paths in the plugin; those belong in a
  repository's `.harness/settings.json`.

## Common Failure Modes

| Symptom | Cause |
| --- | --- |
| Tests fail with `No module named pytest` | run through the venv's Python (`PYTHON=.venv/bin/python`) |
| `claude plugin validate` passes but the plugin does not load | a skill's frontmatter `name` differs from its folder |
| A rule change passes unit tests but not in a host | the host's payload shape differs; add a case with that host's payload to `tests/harness/` |
