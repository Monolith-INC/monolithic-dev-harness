# Intake and Selection UX

Reference for `generate-breakdown-work-items` PHASE 0. Selection only — no Artifacts or Azure writes.

## Prompt order

Collect inputs **one at a time** via the host UI. Skip a step only when the value was already
supplied (slash-command flag or prior conversational answer).

| Step | Input | Required | Default |
| --- | --- | --- | --- |
| 1 | Work item reference | yes | — |
| 2 | Output destination | yes | — (must ask) |
| 3 | Output language | no | `en` when omitted |

### Step 1 — Work item reference

Accept **one** of:

- Azure DevOps work item **ID** (numeric)
- Azure DevOps work item **URL** (`/_workitems/edit/{id}` or `/_workitems/view/{id}`)
- File system / Artifacts **path** (artifacts path Feature, Epic, or User Story markdown)

If none is provided: STOP and prompt before continuing. Do not invent a reference.

Resolve type later (User Story vs Feature vs Epic) in ingest/fan-out phases. Intake only captures
the raw reference string and a provisional `source_kind`: `id` | `url` | `path`.

### Step 2 — Output destination (invariant, single-select)

Present as a selectable list. Always include `other (inform or describe)` last.

1. `filesystem` — write Implementation Plan and Task drafts to the configured artifacts path
2. `Azure Task board` — create Azure Task children under the User Story
3. `both` — artifacts path and Azure
4. `other (inform or describe)` — user supplies a custom destination; clarify before continuing

Judgment: when the host team typically uses Azure + together, tag **`both`** as
`Recommended` and keep it **first** in the presented list (reorder so Recommended is first, then
the remaining options, then `other…` last).

Normalized values: `filesystem` | `azure` | `both` | `other:<user text>`.

### Step 3 — Output language

If the user already stated `en` or `pt-BR` / `pt-br`, accept it. If omitted, set **`en`** without
asking.

When asking (user wants to choose, or language is ambiguous), present:

1. `en` — English (default)
2. `pt-BR` — Brazilian Portuguese
3. `other (inform or describe)`

Normalize to `en` | `pt-BR` | `other:<user text>`. Treat `pt-br` / `pt_br` as `pt-BR`.

## Selection list rules (all phases)

These rules apply to every selectable list this skill shows — intake and later variant lists
(e.g. proposed Task lists).

### Invariant options

Known fixed sets (destinations, languages, yes/no gates). Render as selectable options.
Use **single-select** unless the step explicitly allows multiple.

### Variant options

Open or run-specific sets (e.g. generated Task titles for a Story). Render as **multi-select**
and always include:

- `all` — include every listed item
- `other (inform or describe)` — **last** on the list

### `other (inform or describe)`

Must be the **last** option on every selectable list and must always be included. If chosen,
prompt once for free-text detail before continuing.

### `Recommended`

When the choice requires judgment (non-obvious default), tag **exactly one** option
`Recommended`, place it **first** in the list, then list the remaining options, then `other…`
last. Do not tag `other…` as Recommended.

## Confirmed intake record

After all steps, present a short confirmation and STOP until the user accepts (or corrects).
Pass this record to downstream phases — do not re-prompt mid-run unless a value is `other:` and
still incomplete.

```text
{
  work_item_ref:   string
  source_kind:     "id" | "url" | "path"
  destination:     "filesystem" | "azure" | "both" | "other:<text>"
  language:        "en" | "pt-BR" | "other:<text>"
}
```

## Out of scope for this reference

- Reading Feature/Story bodies
- Writing Implementation Plans or Tasks
- Azure MCP calls
