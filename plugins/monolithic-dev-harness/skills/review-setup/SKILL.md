---
name: review-setup
description: Use once per repository, before any other review skill, to record where requirements and definitions of done live and which pull-request host is in use. Run again when the tracker, remote, or vault layout changes.
---

# Review Setup

Every other skill in this toolkit needs three answers: **where do requirements live**, **where do
pull requests live**, and **what does this project already require of any change**. This skill
establishes all three, confirms them with the user, and writes them to
`.monolithic-code-review/sources.json` in the repository being reviewed.

The first two are pointers to systems outside the repository. The third is the project itself, and
it is built by `discover-project-knowledge` into a store this skill locates and records.

This toolkit names no tracker vendor. Which system holds requirements is the consuming repository's
business — Linear, Jira, Azure DevOps, YouTrack, GitHub issues, or plain files. Map whatever is
present onto the capability contract below.

## The capability contract

Three capabilities are all the review skills need:

| Capability                | Returns                                                           | Used by                          |
| ------------------------- | ----------------------------------------------------------------- | -------------------------------- |
| `fetch_work_item(id)`     | title, description, requirements, acceptance criteria / DoD        | every review skill               |
| `fetch_parent(id)`        | the parent item — task → story, story → feature                    | `review-feature`, scope checks   |
| `list_linked_artifacts(id)` | specs, design docs, attachments, linked URLs                     | post-flight fact-checking        |

A source satisfies the contract if it can answer all three. Partial sources are allowed — record what
is missing so dependent skills degrade honestly instead of inventing requirements.

## Procedure

### 1. Detect the pull-request host

```bash
git remote get-url origin
git branch --show-current
```

Identify the provider from the origin URL, then inspect the provider-specific tools actually
available in the session (MCP tools, a first-party CLI, or an authenticated API client). Do not
assume GitHub and do not substitute a different provider because its tooling is convenient.

Map the provider onto the SCM capability contract below. Record missing capabilities in
`scm.unsupported`; a missing or unauthenticated client is a warning, not a reason to abandon the
requirements configuration. If the origin is ambiguous, propose what was inferred and confirm it
with the user.

| Capability                 | Purpose |
| -------------------------- | ------- |
| `get_pull_request`         | PR metadata, refs, author, changed files |
| `get_pull_request_diff`    | remote unified diff or equivalent changed-file patches |
| `list_review_threads`      | review threads with status, comments, paths, and lines |
| `list_conversation_comments` | general PR comments without line anchors |
| `post_inline_comment`      | create a comment anchored to a changed line |
| `post_summary_comment`     | create a general PR comment |
| `reply_to_review_thread`   | reply to an existing review thread |

Concrete values may be MCP tool names or command templates. Authentication checks are
provider-specific: for example `gh auth status` for GitHub or `az account show` plus
`az devops configure --list` for Azure DevOps.

### 2. Enumerate what is actually available

Do not assume. Check, in this order, and report what you find:

1. **Tracker MCP tools in this session.** Look for tool names matching a tracker
   (`*linear*`, `*jira*`, `*azure*devops*`, `*youtrack*`, `*shortcut*`). Note the exact tool names —
   they are what gets recorded, not a vendor label.
2. **A local vault.** Look for `AI_Codex/`, `docs/specs/`, `.codex-workflows/`, `specs/`, or a
   comparable directory holding features, stories, or tickets. Read one file to learn the layout.
3. **SCM work items/issues**, if the configured provider exposes them — use only as a fallback.

### 3. Propose a mapping and confirm it

Present both candidate mappings to the user and **ask for confirmation before writing**. Show which
SCM and tracker capability resolves to which concrete tool, command, or path, and name anything you
could not satisfy. If more than one requirements source is available, ask which is authoritative; a
vault and a tracker often disagree, and the user decides which wins.


### 3b. Detect quality lens defaults

Determine whether this repository is a TypeScript codebase. Treat it as TypeScript when any of
these hold at the repository root or in a primary app/package directory the user identifies:

- `tsconfig.json` exists
- `package.json` lists `typescript` in `dependencies` or `devDependencies`
- More than a trivial fraction of tracked source files use `.ts` or `.tsx` (investigate with
  read-only file inventory when ambiguous)

Record the result in `quality_lenses.typescript`:

- `mandatory` — TypeScript codebase; lifecycle reviews run the TypeScript lens when the changed
  scope includes `.ts`/`.tsx` or when the repository default applies.
- `off` — not a TypeScript codebase; the TypeScript lens runs only when changed scope includes
  `.ts`/`.tsx` or the user passes `--lenses typescript`.

Always write `quality_lenses.maintainability: "off"`. Maintainability runs only when the user
passes `--lenses maintainability` or `--lenses all` on a lifecycle review.

### 3c. Choose where project knowledge is stored

Review skills read a **project knowledge store**: a file-shaped index of what this repository is,
how it is built, and how it is allowed to change. Without it, a review can measure a diff against
its work item but not against the project's own architecture, conventions, or rules.

Ask the user which root to use, and present the trade-off rather than picking silently:

| Option | Root | Trade-off |
| --- | --- | --- |
| **Per-developer** | `.monolithic-code-review/knowledge/` | Beside `sources.json`, gitignored with it. No diff noise, no review burden — but each developer rebuilds it, and nobody inherits the answers the others gave |
| **Committed anchor** | `.monolithic-code-review/knowledge/`, tracked | The team shares one store and can hand-edit it. Highest value, because human-authored identity and rules survive the person who knew them — but generated content lands in pull requests and needs a refresh policy |
| **Inside the vault** | A directory under `vault.root`, such as `<vault.root>/Project_Knowledge/` | One knowledge home when the repository already keeps a vault. Offer this option only when step 2 found one |

Record the answer as `knowledge.root` and `knowledge.committed`. If the user chooses a committed
root, do **not** add it to `.gitignore`; if they choose per-developer, it is covered by the
`.monolithic-code-review/` entry described in step 4.

### 3d. Build the store

Run `discover-project-knowledge` to populate the chosen root. That skill owns the taxonomy, the
unit schema, and the refresh contract; this one only decides where the store lives and records it.

It derives structure, mechanics and evolution from the tree, and **asks** about purpose, ownership
and rules — those are human-authored facts, and a review that cites an invented rule is worse than
one that cites none.

A store is not required for the other skills to function. If the user declines, record
`knowledge.root: null` and say that reviews will run without project context.

### 4. Write the configuration

Write `.monolithic-code-review/sources.json` in the repository root:

```json
{
  "version": 1,
  "scm": {
    "provider": "github",
    "owner": "<owner>",
    "repo": "<repo>",
    "capabilities": {
      "get_pull_request": "gh pr view {pr} -R {owner}/{repo} --json title,body,baseRefName,headRefName,headRefOid,author,files",
      "get_pull_request_diff": "gh pr diff {pr} -R {owner}/{repo}",
      "list_review_threads": "gh api graphql ...",
      "list_conversation_comments": "gh api repos/{owner}/{repo}/issues/{pr}/comments --paginate",
      "post_inline_comment": "gh api repos/{owner}/{repo}/pulls/{pr}/comments ...",
      "post_summary_comment": "gh pr comment {pr} -R {owner}/{repo} --body-file {file}",
      "reply_to_review_thread": "gh api repos/{owner}/{repo}/pulls/{pr}/comments ..."
    },
    "unsupported": []
  },
  "tracker": {
    "kind": "mcp",
    "label": "Linear",
    "authoritative": true,
    "capabilities": {
      "fetch_work_item": "mcp__linear__get_issue",
      "fetch_parent": "mcp__linear__get_issue",
      "list_linked_artifacts": "mcp__linear__list_documents"
    },
    "scope": { "team": "AGE" },
    "unsupported": []
  },
  "vault": {
    "root": "AI_Codex",
    "features": "Features/",
    "stories": "Tickets/",
    "specs": "docs/specs/"
  },
  "conventions": {
    "tag_pr_author": true,
    "work_item_pattern": "AGE-\d+",
    "language": "en",
    "requirement_headings": {
      "requirements": "## Requirements",
      "definition_of_done": "## Definition of Done"
    }
  },
  "quality_lenses": {
    "typescript": "mandatory",
    "maintainability": "off"
  },
  "knowledge": {
    "root": ".monolithic-code-review/knowledge",
    "committed": false,
    "schema_version": 1,
    "derived_from_commit": "<sha>",
    "tiers_present": [1, 2, 3, 4, 5],
    "mcp_server": "mcrt-knowledge"
  }
}
```

Field notes:

- `scm.provider` — the provider detected for this repository, such as `github` or `azure-devops`.
- `scm.capabilities` — concrete tool names or command templates for this repository's provider;
  downstream PR skills execute these mappings instead of assuming a CLI.
- `scm.unsupported` — SCM capabilities that could not be mapped. Dependent skills must degrade
  honestly and must not silently use another provider.
- `tracker.kind` — `mcp`, `cli`, `files`, or `none`.
- `tracker.capabilities` — concrete tool names or path templates, never vendor labels. A `files`
  tracker uses path templates such as `AI_Codex/Tickets/**/{id}*.md`.
- `tracker.unsupported` — capabilities this source cannot answer. Dependent skills must say so rather
  than proceed on assumption.
- `conventions.tag_pr_author` — whether posted PR comments `@`-mention the author. Ask the user;
  some teams consider it noise.
- `conventions.work_item_pattern` — regex for finding work-item ids in branch names and commit
  messages, so later skills can infer the item under review without being told.
- `conventions.language` — the language findings and posted pull-request comments are written in,
  as an IETF tag such as `en` or `pt-BR`. Ask; do not infer it from the repository's prose. These
  comments are read by a specific team.
- `conventions.requirement_headings` — the actual heading text that carries requirements and the
  definition of done in file-backed sources. Record what this repository uses; the defaults shown
  are English conventions, not a contract.
- `knowledge.root` — where the project knowledge store lives, or `null` when the user declined one.
  Consuming skills treat `null` the same way they treat an unsupported capability: they say so once
  and review without project context.
- `knowledge.committed` — whether the store is tracked in version control. Decides whether the root
  is added to `.gitignore` and whether a refresh produces reviewable diffs.
- `knowledge.derived_from_commit` — the commit the store was last derived from. Discovery uses it to
  refresh only the units whose inputs actually moved.
- `knowledge.mcp_server` — the configured knowledge MCP server name when its adapter is installed.
  Omit it when there is none; the store's layout is deterministic, so skills fall back to reading
  `catalog.tsv` and grepping the tree.

Add `.monolithic-code-review/` to the repository's `.gitignore` unless the user wants the
configuration shared with the team. Ask. When `knowledge.committed` is true and the store lives
under `.monolithic-code-review/`, negate the store path so the configuration stays private while
the knowledge stays shared.

### 5. Verify before declaring success

Resolve one real work item end to end through the recorded mapping and show the user the title and
acceptance criteria you got back. A configuration that has never successfully fetched anything is not
a working configuration.

## SCM provider recipes

Worked examples, not dependencies. Preserve the provider's native identifiers and fields in
`scm` (for example Azure DevOps `organization` and `project`) in addition to the common fields.

| Provider | Repository identity | Typical capability implementation |
| -------- | ------------------- | --------------------------------- |
| GitHub | `owner`, `repo` | `gh pr view`, `gh pr diff`, GraphQL review threads, and `gh api` comment endpoints |
| Azure DevOps | `organization`, `project`, `repo` | Azure DevOps MCP tools when present; otherwise `az repos pr show` for metadata and `az devops invoke` Git Pull Request/Thread APIs for diffs, threads, comments, and replies |
| Other | provider-native fields | available MCP tools, first-party CLI, or authenticated API command templates satisfying each SCM capability |

Do not record the illustrative recipe text itself as a capability. Inspect the installed tool's
actual command or tool signature and record an executable concrete mapping.

## Requirement-source recipes

Worked examples, not dependencies. An unlisted tracker works as long as the three capabilities
resolve to something.

| Source           | `fetch_work_item`                    | `fetch_parent`                          | `list_linked_artifacts`             |
| ---------------- | ------------------------------------ | --------------------------------------- | ----------------------------------- |
| Linear MCP       | `get_issue`                          | `get_issue` on `parent.id`; milestone for feature scope | `list_documents`, issue attachments |
| Jira MCP         | `getJiraIssue`                       | issue link of type *parent*             | remote links, attachments           |
| Azure DevOps MCP | `wit_get_work_item`                  | `System.Parent` relation                | work item `relations[]`             |
| YouTrack         | issue by id                          | `parent` link                           | issue attachments                   |
| GitHub issues    | `gh issue view <n> --json title,body` | parent from tracking checklist or label | links parsed from the issue body    |
| Local vault      | read `<stories>/**/{id}*.md`         | `feature:` frontmatter key              | `## Specs` links in the ledger      |

For file-backed sources, requirements and DoD are conventionally the `## Requirements` and
`## Definition of Done` sections. Record the actual heading names if the repository differs.

## Success criteria

- `.monolithic-code-review/sources.json` exists and parses.
- Every capability either resolves or is listed in `unsupported`.
- Every SCM capability either resolves or is listed in `scm.unsupported`.
- `quality_lenses` reflects the TypeScript detection outcome.
- One real work item has been fetched and shown to the user.
- The user has confirmed the mapping, the `tag_pr_author` convention, and the finding language.
- `knowledge.root` is either a store the user chose or an explicit `null`.
- When a store was built: `catalog.tsv` parses, and one routing-table lookup followed by one unit
  read returned a real unit. A store that has never been read back is not a working store.
