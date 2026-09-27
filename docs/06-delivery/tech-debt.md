---
title: Tech debt
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-27
---

# Tech debt

Known gaps we chose to leave for now. Each entry says what the gap is, why it is open, the options
to close it, and when to revisit. Fix one on a `techdebt/…` branch and remove its entry.

## TD-1: A tracker can change between the walkthrough and the Trust question

- **Where:** onboarded trackers, trust by click (ADR-0009, decision 6).
- **What happens:** the harness pins the tracker folder's exact version when the **Trust** question
  is shown, not when the agent walks the user through the tracker. The folder under
  `.harness/trackers/` can be written by the agent, so the agent could change `adapter.py` or the
  staged values after the walkthrough and before asking. The user would then trust a version they
  were not shown.
- **Why it is open:** the user only ever sees what the agent relays, so no pin taken by the harness
  can prove what the user read. The earlier typed-digest line had the same limit. Closing the gap
  fully would stop the agent from staging trackers for the user.
- **Options:**
  - Make `.harness/trackers/` human-owned, so only a person can put a tracker there. Strongest, but
    the user copies the folder in by hand.
  - Record the version each time `harness tracker show` or `stage` prints the summary, and refuse
    a Trust question when the folder changed since that print. Catches edits after the summary, but
    not a summary printed again after an edit.
  - Show the file list and a short version code in the Trust question itself, so a change is visible
    to the user at the moment they click.
- **Risk today:** needs an agent working against the user; every other rule still applies to the
  trusted tracker's writes (approval windows, protected items).
- **Revisit:** before onboarded trackers are used outside the maintainers' own repositories.
