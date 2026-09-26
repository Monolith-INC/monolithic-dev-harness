---
name: onboard-tracker
description: Bring in a tracker the harness does not ship (its tracker.json and adapter.py) so the user can review it, trust it by typing a line, and select it. Use when a repository needs a tracker other than Azure DevOps, Linear, or the local tracker.
---

# Onboard tracker

A tracker is one folder: `tracker.json`, checked against `config/tracker.schema.json`, and
`adapter.py`, which exports `adapter(context) -> TrackerOps` (see
`scripts/integrations/contracts.py`). Start from the closest shipped folder under
`<plugin root>/trackers/` and follow [the tracker contract](../../references/tracker-contract.md).

1. Build the folder outside `.harness/`, with real files only (no links). Give it a name no shipped
   tracker has. Cite the provider's documentation in `docs`.
2. Stage it: `harness tracker stage <folder>`. The command checks the folder against the contract,
   copies it to `.harness/trackers/<name>/`, and prints what it writes, how its ids link, what it
   runs, its files, and its digest. Fix anything it reports and stage again.
3. Walk the user through that output and `adapter.py` in full: the adapter runs inside the
   harness. Do not trust it yourself; you cannot.
4. If the user agrees, they type the line the command printed, themselves:
   `harness trust-tracker <name> <digest>`. The hook records trust for the folder exactly as it
   reads now. Any later edit to any file in it makes the tracker unusable until they trust it again;
   `harness untrust-tracker <name>` withdraws trust.
5. A person then selects it in `.harness/settings.json`:
   `"tracker": {"name": "<name>", "source": "onboarded", "values": {...}}`. The file is theirs;
   you cannot edit it.
6. Check with `harness doctor` (add `--tools` to confirm the provider offers every tool the
   manifest names).
