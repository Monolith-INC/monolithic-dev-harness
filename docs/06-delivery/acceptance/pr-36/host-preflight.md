---
title: PR 36 interactive acceptance preflight
status: awaiting-host-restart
last_reviewed: 2026-10-07
---

# Host preflight

Source under test: `3d723e3dda51097ff66723aba4631e34a4411d75`, branch
`feat/less-friction`, PR 36. Working tree was clean before evidence preparation.

Disposable fixture prepared through `scripts/acceptance_trial.py prepare --profile local-planning`:
`/tmp/monolithic-dev-harness-trial-hfex7n7v/project`. The canonical template was not edited.
The fixture remains available; no project workflow or test agent has started.

## Observed mismatch before installation

`codex plugin list --json` reports `monolithic-dev-harness@monolithic-dev-harness` installed,
enabled, version 0.6.2, from the user-local marketplace. The version label also appears in source,
so it cannot establish revision identity.

SHA-256 of `hooks/codex.hooks.json`:

- Current PR source: `0da4e714f97d590c0e15abe541c68cf7e348f936373a83c28391f4c446884731`.
- Installed cache: `e3fcd81107ba5ad5669cd686b97db49a077cf364e905c94343555974239d2469`.
- PATH marketplace copy: `e3fcd81107ba5ad5669cd686b97db49a077cf364e905c94343555974239d2469`.

The installed cache lacks `scripts/host_adapters/startup_context.py`. Running this desktop host
would exercise older integration, not the PR's new startup completion protocol.

## Authorized installation and verification

The human selected option 1: update the shared Codex installation. Executed the supported installer
from the reviewed checkout with `--host codex --source /home/monolith/projects/monolithic-dev-harness
--yes`. It exited successfully. The version label remains 0.6.2; this is a development build of
commit `3d723e3`, not a newly published release.

The previous installation, plugin cache, CLI link, config and managed review-agent files were
archived in the private directory `/tmp/harness-pr36-install-backup-O6UC1b`. Do not commit that
archive. Installer output is retained there as `install.log`.

Compared all 366 source files under `scripts`, `skills`, `references`, `hooks` and `config` against
the installed Codex cache: zero mismatches. The startup adapter and Codex hook hashes now match
source. The user config is byte-for-byte unchanged from the backup.

`harness doctor --repo /tmp/monolithic-dev-harness-trial-hfex7n7v/project` exited successfully:
Python 3.12, Git, npx, Codex registration, BMAD configuration, repository settings and local tracker
all passed. Doctor explicitly does not check live question capture. Other host registrations were
reported but their live operation was not tested.

## Pending host restart

The installer requires restarting the host so hooks and MCP servers load, and trusting plugin
hooks when prompted. No hot-reload capability was available in this chat. The desktop has not been
restarted automatically, and no trial agent has been launched against potentially stale hooks.
After restart, resume this chat and launch the prepared interactive fixture through its briefing.
No merge, deployment, or acceptance verdict is claimed. The fixture remains available.
