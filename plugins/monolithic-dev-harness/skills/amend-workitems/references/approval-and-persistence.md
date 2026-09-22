# Approval and persistence

The change set is the only write input. It must show node, section, before/after content, linked
Task effects, related Implementation Plan effects, preserved fields, unresolved items, backup,
and revisions. Use single-select placement prompts and a final explicit approval prompt. Rejection
or cancellation performs no writes.

After approval, use the existing `enrich-work-item`, `generate-plain-language-documentation`,
`generate-breakdown-work-items`, and (only when explicitly approved) `generate-work-item` skills.
Use their Azure mechanics and read-back rules. Apply content updates top-down. Update Task child
lists without deleting or relinking existing children. Add only explicitly approved missing Tasks.
Update a related Implementation Plan before changing its Tasks, and ensure every affected acceptance
criterion remains covered. Validate changed Epic, Feature, and Story artifacts after read-back.

On any failed write, read-back, link check, or validation, stop immediately, report the failure and
backup path, and do not attempt an automatic rollback or a second mutation.
