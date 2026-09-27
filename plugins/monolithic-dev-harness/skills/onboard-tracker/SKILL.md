---
name: onboard-tracker
description: Bring in a tracker the harness does not ship (its tracker.json and adapter.py) so the user can review it, then trust and select it with two clicks. Use when a repository needs a tracker other than Azure DevOps, Linear, or the local tracker.
---

# Onboard tracker

A tracker is one folder: `tracker.json`, checked against `config/tracker.schema.json`, and
`adapter.py`, which exports `adapter(context) -> TrackerOps` (see
`scripts/integrations/contracts.py`). Start from the closest shipped folder under
`<plugin root>/trackers/` and follow [the tracker contract](../../references/tracker-contract.md).

1. Build the folder outside `.harness/`, with real files only (no links). Give it a name no shipped
   tracker has. Cite the provider's documentation in `docs`.
2. Ask the user, in plain words, for any value the tracker's settings need (organization,
   project, ...). Then stage it: `harness tracker stage <folder> --value KEY=VALUE ...`. The command
   checks the folder against the contract, copies it to `.harness/trackers/<name>/` with the values,
   and prints what it writes, how its ids link, what it runs, its files and values. Fix anything it
   reports and stage again.
3. Walk the user through that output and `adapter.py` in full: the adapter runs inside the
   harness.
4. Ask one question that names the tracker, with the options **Trust** and **Not now**, for example
   "Trust the Acme Boards tracker as I just described it?". The harness pins the folder's version
   when the question is shown and trusts exactly that version when the user clicks. If the folder
   changed in between, nothing is trusted: explain what changed and ask again. You cannot trust a
   tracker yourself.
5. If they trusted it, ask a second question with the options **Use it** and
   **Keep the current one**, for example "Use Acme Boards as this project's tracker now?". On
   **Use it**, the harness writes the tracker and its staged values into the settings file. You
   cannot edit that file yourself.
6. In Cursor, which has no buttons, show the short id the summary printed and ask the user to reply
   `approve HT-XXXXXX` to trust it, then `use HT-XXXXXX` to use it. Each reply counts only as the
   whole message.
7. To withdraw trust, ask a question naming it with the options **Stop trusting** and **Keep it**
   (in Cursor, the user replies `stop trusting the <name> tracker`). Any edit to the folder also
   drops trust until the user trusts it again.

Every tracker question must say "tracker" and name the tracker by its label, or the harness does
not treat it as one. Staging refuses a tracker that is missing a required value.
8. Check with `harness doctor` (add `--tools` to confirm the provider offers every tool the
   manifest names).
