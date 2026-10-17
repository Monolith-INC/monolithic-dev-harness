# Provider contract

All skills work with the same artifact fields:

- `work_item_type`: `Epic`, `Feature`, `User Story`, or `Task`.
- `provider`: `local`, `azure-devops`, or `linear`.
- `provider_id`: provider-issued identifier as a string. Omit before creation.
- `parent_id`: immediate parent identifier as a string. Omit for Epics.

Hierarchy is always Epic -> Feature -> User Story -> Task.

## Local

Persist the neutral frontmatter without translating identifiers.

## Azure DevOps

Use native work item types and native parent relations. After creation, store the returned numeric
ID as a string in `provider_id`. Never write Azure-specific identity keys to local artifacts.

## Linear

Create all four levels as issues. Pass the immediate parent as `parentId`. Apply exactly one managed
type label: `agile:epic`, `agile:feature`, `agile:user-story`, or `agile:task`. Linear Projects are
not Agile Epics. After creation, store the issue identifier in `provider_id`.

Provider writes remain approval-gated. Read each created or updated item back and verify its parent,
type, title, and description before reporting success.
