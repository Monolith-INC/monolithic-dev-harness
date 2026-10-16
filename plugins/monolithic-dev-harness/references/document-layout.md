# Document layout

Where every document the workflow writes lives, and what it is called. Specs, implementation
plans, preparation documents, the reading manifest, technical specs and the discovery approach all
follow it (owner, 2026-10-16).

## Names

A document is named `<document-type>-<scope>.md`. The scope names the work item it belongs to the
way the agile-backlog-toolkit names ticket files (`<number>-<title-slug>`), with the item's type in
front:

```text
<work-item-type>-<number>-<title-slug>
user-story-0001-show-to-do-and-done-task-counts-on-the-task-screen
```

| Document | Type in the name |
| --- | --- |
| Work-item spec (`generate-work-item`, `enrich-work-item`) | `spec` |
| Implementation plan (`generate-breakdown-work-items`) | `implementation-plan` |
| Risk document (preparation) | `risk-assessment` |
| Verification document (preparation) | `verification-plan` |
| Reading manifest (preparation) | `reading-manifest` |
| Technical spec (`write-spec`) | its kind: `tech-spec`, `design-doc`, `adr`, `api-contract` |
| Discovery approach (`bmad-build`) and its decision log | `approach` (log: `.memlog.md` beside it) |

The front matter `type` is the same document type.

## Folders

Each work item has a folder named by its scope inside the artifacts path, nested under its parents'
folders, so everything about one Story sits together under its Feature and Epic:

```text
<artifacts>/
  epic-0001-daybook-insights/
    feature-0002-task-list-summary/
      user-story-0003-show-to-do-and-done-task-counts-on-the-task-screen/
        spec-user-story-0003-show-to-do-and-done-task-counts-on-the-task-screen.md
        implementation-plan-user-story-0003-show-to-do-and-done-task-counts-on-the-task-screen.md
        risk-assessment-user-story-0003-….md
        verification-plan-user-story-0003-….md
        reading-manifest-user-story-0003-….md
```

A Story without a Feature sits at the top of the artifacts path. Ticket files stay in `Tickets/`
(the tracker); this layout is for documents.

## Getting a path

Never compose a name by hand. Ask the harness:

```bash
harness document path --type implementation-plan --item STORY-0003
harness document path --type spec --new user-story --title "<title>" --parent FEATURE-0002
harness document path --type ticket --new user-story --title "<title>" --parent FEATURE-0002
```

- `--item` names an item that exists; its parents are read from the tracker.
- `--new` names an item not created yet. On the local tracker its number is reserved as soon as its
  ticket draft (`--type ticket`, `Tickets/Ready/<number>-<title-slug>.md`) or any of its documents
  is written, and creating the item gives it that number. The draft and every document carry their
  final names from the start; nothing is renamed after the item is created. Ask again with the same
  title to get the same number.
- Azure DevOps and Linear assign an item's id only when they create it, so `--new` is refused
  there: write the item's documents once it exists, with `--item`.

## Before any item exists

Discovery starts before refinement decides which items to create. When the work session already
tracks an item, the approach is that item's (`--item`). When it starts from a request or a project
file, it is the approach for the item refinement will create from it: ask with `--new` and the
planned item's type and title, and create that item from it in refinement.
