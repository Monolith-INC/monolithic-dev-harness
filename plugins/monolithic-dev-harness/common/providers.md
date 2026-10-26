# Provider contract

All skills work with the same artifact fields:

- `work_item_type`: `Epic`, `Feature`, `User Story`, or `Task`.
- `provider`: the selected tracker's name (`tracker_describe`).
- `provider_id`: provider-issued identifier as a string. Omit before creation.
- `parent_id`: immediate parent identifier as a string. Omit for Epics.

Hierarchy is always Epic -> Feature -> User Story -> Task.

## Writing to the tracker

Write through the gateway only: `tracker_create_work_item` with the harness kind and the immediate
parent as `parentRef`, `tracker_update_work_item` for an existing item. The selected tracker's
adapter maps kinds, parent relations, labels and identifiers; `tracker_describe` says what the
tracker holds. After creation, store the returned key as a string in `provider_id`. With the local
tracker, creating the item turns its draft into the tracked ticket.

Provider writes remain approval-gated. Read each created or updated item back and verify its parent,
type, title, and description before reporting success.
