# Intake and Selection UX

Reference for `generate-breakdown-work-items` PHASE 0. Selection only — no writes.

## Prompt order

Collect inputs **one at a time** via the host UI. Skip a step only when the value was already
supplied (slash-command flag or prior conversational answer).

| Step | Input | Required | Default |
| --- | --- | --- | --- |
| 1 | Work item reference | yes | — |
| 2 | Output language | no | the project's harness language |

### Step 1 — Work item reference

Accept **one** of:

- Tracker work item **id**
- Tracker work item **link** (its id is read with the tracker's `ids` patterns, `tracker_describe`)
- File system / Artifacts **path** (artifacts path Feature, Epic, or User Story markdown)

If none is provided: STOP and prompt before continuing. Do not invent a reference.

Resolve type later (User Story vs Feature vs Epic) in ingest/fan-out phases. Intake only captures
the raw reference string and a provisional `source_kind`: `id` | `url` | `path`.

The destination is always the selected tracker; it is never asked.

### Step 2 — Output language

If the user already stated `en` or `pt-BR` / `pt-br`, accept it. If omitted, use the project's harness
language without asking.

When asking (user wants to choose, or language is ambiguous), present:

1. `en` — English (default)
2. `pt-BR` — Brazilian Portuguese
3. `other (inform or describe)`

Normalize to `en` | `pt-BR` | `other:<user text>`. Treat `pt-br` / `pt_br` as `pt-BR`.

## Selection list rules (all phases)

These rules apply to every selectable list this skill shows — intake and later variant lists
(e.g. proposed Task lists).

In the harness, every list is asked with `harness decision present` (at most three options at a
time). The host's question control supplies the free-text **Other** field itself: do not add an
`other (inform or describe)` option. Approvals use the harness gates, never a selection list.

### Invariant options

Known fixed sets (languages, yes/no gates). Render as selectable options.
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
  language:        "en" | "pt-BR" | "other:<text>"
}
```

## Out of scope for this reference

- Reading Feature/Story bodies
- Writing Implementation Plans or Tasks
- Tracker calls
