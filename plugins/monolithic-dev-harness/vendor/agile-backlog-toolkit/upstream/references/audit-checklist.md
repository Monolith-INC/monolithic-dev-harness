# Audit Checklist (Phase 7)

Run AFTER all Stories are created and structurally verified. Retrieve each work item **fresh from
Azure** (not the local draft) — the draft is what you meant to send; the Azure item is what landed.

## a) Fidelity
- [ ] The Azure description matches the approved enriched draft (no truncation, no MCP re-encoding).
- [ ] ASCII diagrams render intact.
- [ ] Story points and tags persisted.

## b) Coverage (the safeguard against silent requirement loss)
Build a parent-requirement → Story map:
- [ ] Every requirement / acceptance criterion in the PARENT text maps to ≥1 child Story.
- [ ] Flag any **orphan requirement** (in the parent, in no Story) — a dropped requirement.
- [ ] Flag any **unanchored Story scope** (in a Story, not in the parent) — scope creep.

Emit the map as a requirement-by-requirement pass/gap report.

## c) Definition of Ready
For each Story:
- [ ] Clear-objective title.
- [ ] Detailed description.
- [ ] Story points set.
- [ ] Parented to the Feature.

## Outcome
- All pass → report the coverage map and stop.
- Any gap → STOP and report; do not patch silently.
