# Glossary Usage

Technical term verification and EN → pt-BR translation using the bundled skill glossary.

**File:** `./references/assets/tech-glossary-en-pt-br.json`

## Schema (read the file header)

| Field | Role |
| --- | --- |
| `terms` | Object keyed by **lowercased English** term; each value has `pt` and `source` |
| `aliases` | Maps original-cased forms (e.g. `IDE`, `I/O`) to lowercased keys |
| `schema.lookup_*` | Example `jq` one-liners for exact, substring, and reverse lookup |

**Count:** ~236 terms (see `count` in the JSON header).

## Lookup protocol

For each candidate term `T` in the draft:

1. **Exact EN → pt:** resolve key via `aliases[T]` or `T.lower()`; read `terms[key].pt`.
2. **Substring scan:** when the term is multi-word or inflected, search `terms` keys containing a
   stem (e.g. `commit` → `commit`, `version control`).
3. **Reverse pt → EN:** when normalizing pt-BR calques, search `terms[].pt` for matches.
4. **Miss:** paraphrase in plain language; do not invent jargon. Note in chat **Term notes** only.

### Shell examples (from glossary `schema`)

```bash
# Exact EN → pt
jq -r --arg t "reliability" '(.aliases[$t] // ($t|ascii_downcase)) as $k | .terms[$k].pt // "NOT_FOUND"' \
  ./references/assets/tech-glossary-en-pt-br.json

# Substring
jq -r '.terms | to_entries[] | select(.key|contains("commit")) | "\(.key) -> \(.value.pt)"' \
  ./references/assets/tech-glossary-en-pt-br.json
```

Prefer in-agent lookup (Read + parse) when Bash is unavailable.

## When to run

| Condition | Action |
| --- | --- |
| `language: pt-br` | Full pass on every technical term |
| `language: en` | Spot-check domain terms and consistency |
| Sub-skill from `generate-work-item` / `enrich-work-item` / `decompose-backlog` | Match parent skill locale; glossary when pt-BR |

## Translation rules (pt-BR)

- Use glossary `pt` when an entry exists.
- Avoid calques: "gate" → "ponto de aprovação"; "circuit breaker" → "regra de parada" / "disjuntor"
  (use glossary or plain paraphrase).
- Keep repository identifiers (`file` names, `seed`, API symbols) in original form with a one-clause
  explanation on first use.
- Reread the translation standalone as a native speaker before delivering.

## Gherkin disambiguation

Keys prefixed with `gherkin ` (via `aliases` for `Feature`, `Scenario`, etc.) are **BDD keywords**,
not backlog "Feature" work items. Do not confuse them when enriching agile artifacts.
