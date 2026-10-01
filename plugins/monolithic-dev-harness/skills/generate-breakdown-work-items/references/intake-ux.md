# Breakdown intake

Capture the Story, Feature, or Epic reference from the user's request. Ask for it only when absent.
Resolve IDs and URLs through the selected tracker adapter; accept a local artifact path when the
source is a file. Use the user-level harness language unless the user explicitly changes it.

The default destination is the active tracker for Tasks and the configured artifacts path for the
Implementation Plan. Do not silently select a local-only Task destination for a tracker-backed
Story. Ask a destination question only when the user requests a different destination or the
selected tracker cannot represent Tasks. Explain exactly which Tasks would be absent from the
tracker before that choice.

Ask each missing choice through native host controls when available, or show numbered options with
the same labels and consequences. Back revises an earlier reversible choice; Pause saves progress.
Do not add a confirmation gate for the normalized intake. Continue to reading the work items once
the required reference and destination are known.
