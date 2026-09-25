---
name: onboard-tracker
description: Stage and validate a custom tracker adapter manifest for explicit human approval.
---

# Onboard tracker

Use this only when a repository needs a tracker that is not shipped with the harness.

1. Put `tracker.json`, adapter code, and provider references in one folder.
2. Run `python3 "<plugin root>/scripts/trackers/onboarding.py"` through its `stage` API to copy it into `.harness/trackers/<name>/`.
3. Inspect the complete staged folder and its declared `writes`, `ids`, `mentions_link`, and sources with the user. Do not select it yet.
4. After the user explicitly approves it, call `approve`; the next approval event pins its checksum. Any later edit invalidates that pin.
5. Set `.harness/integrations.json` tracker selection to `{ "name": "<name>", "source": "onboarded" }` only after it is approved and pinned.

The registry rejects invalid schemas, cyclic artifact hierarchies, and unpinned or modified onboarded folders.
