# enrich-work-item — Azure DevOps Source Ingest

Resolve an Azure DevOps work-item URL (or numeric id) into an **enrichment input bundle**: work-item
fields, attachment contents, and any external sources referenced in the description. Read this file when
`source` is an Azure URL or id before routing the enricher.

Shared create/link/update rules remain in `../../references/azure-mechanics.md`.

---

## Detect Azure source

Treat `source` as Azure when it matches any of:

| Pattern | Example |
| --- | --- |
| `dev.azure.com` work-item URL | `https://dev.azure.com/{org}/{project}/_workitems/edit/6871` |
| `dev.azure.com` view URL | `https://dev.azure.com/{org}/{project}/_workitems/view/6871` |
| `visualstudio.com` work-item URL | `https://{org}.visualstudio.com/{project}/_workitems/edit/6871` |
| Bare numeric id | `6871` (when the user names Azure or a parent URL implies the same org/project) |

Extract **work item id** — the last numeric path segment before query string:

```
.../_workitems/edit/6871          → 6871
.../_workitems/view/6871?fullScreen=true → 6871
6871                              → 6871
```

Record **org** and **project** from the URL when present; MCP calls use the configured project when
the URL omits it.

---

## Fetch work item (primary: Azure DevOps MCP)

**Preferred:** Azure DevOps MCP (`azure-devops` server configured in `.mcp.json` / `.cursor/mcp.json`).

```
wit_get_work_item(id=<work_item_id>, expand=relations)
```

Capture at minimum:

| Field | Use |
| --- | --- |
| `System.Title` | Title suggestion; filename slug |
| `System.Description` | **Descrição Original** (verbatim) |
| `System.WorkItemType` | Cross-check against user `work_item_type` |
| `System.Parent` | Default `parent` when not supplied |
| `Microsoft.VSTS.Scheduling.StoryPoints` | Complexity hint for user-story |
| `Microsoft.VSTS.Common.AcceptanceCriteria` | AC when stored outside Description |
| `relations` | Attachments, parent link, hyperlinks |

If MCP is unavailable, **REST fallback** (read-only):

```
GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?$expand=All&api-version=7.1
```

Auth (first match):

1. MCP server credentials (already configured for the host).
2. `AZURE_DEVOPS_EXT_PAT` or `ADO_PAT` environment variable (Basic auth, empty username).
3. `az devops` logged-in session (`az login` + `az devops configure`).

On 401/403: STOP — report missing auth; do not enrich from a partial fetch.

---

## Enumerate attachments

From `relations`, collect entries where `rel` is `AttachedFile` (case-insensitive).

Each relation provides:

- `url` — attachment API URL containing the attachment GUID
- `attributes.name` — filename (e.g. `spec.pdf`, `screenshot.png`)

Parse **attachmentId** (GUID) from the relation `url`:

```
.../_apis/wit/attachments/00000000-0000-0000-0000-000000000000 → GUID
```

Build `attachments[] = { id, fileName, relationUrl }`.

---

## Parse description for external references

Scan `System.Description` (and `AcceptanceCriteria` when present) for sources the author expects the
reader to use. Include a hit when any of the following match:

| Signal | Examples |
| --- | --- |
| Markdown links | `[spec](https://...)`, `[doc](./path.md)` |
| Bare URLs | `https://`, `http://` |
| Wiki / doc phrases (PT or EN) | `ver anexo`, `see attached`, `conforme documento`, `referência:` |
| Filename echo | Description mentions `requirements.docx` and an attachment has that name |
| Local / repo paths | `docs/plan.md`, `Specs/6800-foo-spec.md` |
| Azure wiki / other work items | `/_wiki/`, `/_workitems/edit/` links |

**Do not** re-fetch the work item's own URL. Deduplicate by URL, attachment id, and path.

---

## Fetch attachment and reference content

### Azure attachments (all `AttachedFile` relations)

**Preferred MCP** (when the server exposes it):

```
wit_get_work_item_attachment(project=<project>, attachmentId=<guid>, fileName=<name>)
```

Returns base64 content — decode and interpret by extension:

| Extension | Treatment |
| --- | --- |
| `.md`, `.txt`, `.csv`, `.json`, `.yaml`, `.xml` | Include full text in bundle |
| `.pdf`, `.docx`, `.xlsx` | Extract or summarize text; note `[binary: <name>]` if extraction fails |
| `.png`, `.jpg`, `.gif`, `.webp` | Describe visually when the enricher needs UI context; otherwise note `[image: <name>]` |
| Other | Note `[attachment: <name>, type=<ext>]` and include any extractable text |

**REST fallback:**

```
GET https://dev.azure.com/{org}/{project}/_apis/wit/attachments/{attachmentId}?fileName={fileName}&download=true&api-version=7.1
```

Same PAT auth as work-item fetch.

### Description-referenced URLs (non-attachment)

For each external URL found in the description (and not already an attachment relation):

1. `WebFetch` / `curl` / host fetch tool — retrieve readable content.
2. On failure: record `fetch_failed: true` and the URL; continue.
3. Cap very large pages — summarize key requirements; keep URL in bundle metadata.

### Artifacts / filesystem paths

When the description references a path under the Codex local or repo:

1. Resolve relative to artifacts root (`bin/agile-backlog-toolkit config --show`) or repo root.
2. `Read` the file when it exists; include verbatim or summarized per size.
3. On missing file: note in bundle; do not invent content.

### Optional `attachment` input

When the user also passes `--attachment`, fetch it **in addition** to Azure-discovered sources (same
rules as above). Deduplicate if it matches an attachment already on the work item.

---

## Build enrichment input bundle

Normalize before PHASE 2 (route enricher):

```text
{
  source_kind:           "azure"
  provider_id:              <int>
  azure_url:             <canonical url or null>
  title:                 <System.Title>
  description_original:  <System.Description verbatim — Descrição Original source>
  acceptance_criteria:   <field or parsed from description>
  work_item_type_azure:  <System.WorkItemType>
  parent_id:             <System.Parent or user parent>
  story_points:          <number | null>
  supplementary_context: [
    {
      kind:    "attachment" | "url" | "path"
      name:    <filename or label>
      ref:     <url or path>
      content: <extracted or summarized text>
      status:  "ok" | "binary" | "fetch_failed"
    },
    ...
  ]
}
```

**Enricher input rules:**

- Pass `description_original` unchanged into the enricher's **Descrição Original** section.
- Merge `supplementary_context[].content` into enricher reasoning (scope, AC, technical notes) — not
  into Descrição Original unless the source text explicitly quotes it there.
- When attachment content contradicts the description, prefer the description for Descrição Original
  and surface conflicts in enrichment notes or ask the user at the gate.
- List successfully ingested sources in user-story `## 📎 Anexos / Referências` when the enricher
  calls for that section.

---

## Failure handling

| Condition | Action |
| --- | --- |
| Invalid URL / no id | STOP — ask for a valid Azure URL or id |
| Work item not found | STOP — report id and project |
| Auth failure | STOP — report env/MCP setup |
| Attachment fetch fails | Continue; note failure in bundle and optional Anexos section |
| External URL fetch fails | Continue; cite URL without invented content |
| Type mismatch (user vs Azure) | WARN once; proceed with user `work_item_type` unless user corrects |

---

## MCP tools (enrich-work-item)

| Tool | Purpose |
| --- | --- |
| `wit_get_work_item` | Work item fields + relations |
| `wit_get_work_item_attachment` | Download attachment content (when available on server) |
| `wit_get_work_items_batch_by_ids` | Parent chain batch fetch |

If `wit_get_work_item_attachment` is missing on an older MCP build, use the REST attachment GET
documented above.
