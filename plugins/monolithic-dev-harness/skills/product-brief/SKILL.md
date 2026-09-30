---
name: product-brief
description: Create, update, or validate a concise product brief that captures a clear concept, its users, value, scope, and success criteria. Use when the user wants a one- or two-page product narrative before a PRD or product spec.
license: MIT
---

# Product Brief

Coach the user's product conviction into a concise narrative without fabricating differentiation or
doing strategic thinking on their behalf. Read
[`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) first.
When creating or re-rendering the brief, read
[`references/brief-template.md`](references/brief-template.md).

## Create

Invite a brain dump and any existing sources before asking granular questions. Establish the
brief's audience and stakes: a passion project, internal alignment, an investment case, and a public
launch require different rigor. Then use the coaching path or, when speed is requested, a fast path
with explicit `[ASSUMPTION]` tags.

Write `brief/PRODUCT-BRIEF.md`, aiming for one or two pages. Adapt the shape to the product; include
only sections that earn their place:

- executive summary;
- problem and cost of the status quo;
- proposed experience and outcome, not implementation;
- who it serves and who it does not;
- honest differentiation or acknowledged lack of moat;
- success criteria;
- first-version scope and explicit exclusions; and
- longer-term vision when it changes near-term decisions.

Put volunteered depth that matters later—rejected alternatives, technical constraints, sizing,
extended personas, parked roadmap—in `brief/addendum.md` instead of bloating the brief. Record each
accepted decision in `.decision-log.md` as it occurs.

## Update and validate

For an update, read the brief, addendum, decision log, and change signal; surface conflicts before
appending the accepted change and re-rendering. For validation, do not edit. Judge whether the brief
is right-sized, specific, honest about uncertainty, and useful to its stated audience; cite sections
and offer an update.

## Finish

Reconcile the brief against the decision log and inputs so no load-bearing idea disappeared. Resolve
blocking assumptions; list non-blocking questions with an owner or revisit condition. Offer
`product-requirements` when organizational agreement is needed, otherwise `product-spec`.

Adapted from BMad Method's Product Brief workflow (MIT, BMad Code, LLC).
