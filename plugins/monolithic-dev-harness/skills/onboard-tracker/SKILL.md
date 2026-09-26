---
name: onboard-tracker
description: Stage and validate a custom tracker manifest for explicit human approval.
---

# Onboard tracker

Use this only when a repository needs a tracker that is not shipped with the harness.

A tracker folder is data: `tracker.json`, the MCP server settings (`mcp.json`), and provider
references. It tells the harness the tracker's artifacts, states, id forms, and which of its MCP
tools write, so those writes need approval and protected items stay protected. It holds no adapter
code: the gateway's tracker operations cover the shipped trackers only, so an onboarded tracker is
used through its own MCP tools.

1. Put `tracker.json`, `mcp.json`, and provider references in one folder.
2. Stage it: `PYTHONPATH="<plugin root>/scripts" python3 -m trackers.onboarding stage <folder>`.
   It lands in `.harness/trackers/<name>/` as a draft.
3. Walk the user through the complete staged folder: its declared `writes`, `ids`, and sources.
   Do not select it yet.
4. Once the user agrees, mark it approved with
   `PYTHONPATH="<plugin root>/scripts" python3 -m trackers.onboarding approve <name>`, then ask one
   approval question that names it, for example "Approve the <name> tracker as staged?". Only an
   approval that says "tracker" and names it pins the folder's checksum; any other approval leaves
   it unpinned. Any later edit to the folder needs a new approval that names it again.
5. Set the `.harness/integrations.json` tracker selection to
   `{ "name": "<name>", "source": "onboarded" }` only after it is pinned. A selection the harness
   cannot load blocks every MCP call until it is fixed.

The registry rejects invalid schemas, cyclic artifact hierarchies, id patterns that do not compile
or that capture, and unpinned or modified onboarded folders. A broken onboarded folder hides only
itself.
