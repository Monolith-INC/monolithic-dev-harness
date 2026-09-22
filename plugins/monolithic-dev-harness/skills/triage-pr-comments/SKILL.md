---
name: triage-pr-comments
description: Use when human reviewers have left comments on a pull request, to list every comment with its file and line, fact-check each one for accuracy and relevance, and present the results for the user to decide on.
---

# Triage PR Comments

Human reviewers are usually right and sometimes not. This skill collects every comment on a pull
request, fact-checks each one adversarially, and presents the results so the user can decide what to
accept and what to push back on.

This skill **decides nothing and posts nothing**. It produces the analysis; the user makes the call.
Acting on the outcome belongs to `respond-pr-comments`.

Requires `.monolithic-code-review/sources.json` and authenticated tooling for its configured SCM
provider.

## Procedure

### 1. List every comment

Read `scm.provider`, `scm.capabilities`, and the repository identity fields from the configuration.
Execute `list_review_threads` with the PR identifier and configured repository identity. If it is
unsupported or authentication fails, stop and name the missing capability; never fall back to a
different SCM.

For GitHub, prefer a GraphQL mapping because it exposes resolved and outdated state that REST does
not:

```bash
gh api graphql -f query='
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first: 20) {
            nodes { databaseId body author { login } path line originalLine createdAt }
          }
        }
      }
    }
  }
}' -F owner=<owner> -F repo=<repo> -F number=<PR>
```

Map each thread: `thread_id` from the root comment's `databaseId`, `file` from `path`, `line` from
`line` falling back to `originalLine`, `reviewer` from the root author, and the full comment chain as
context.

Skip threads where `isResolved` or `isOutdated` is true, and report how many you skipped.

If the configured GitHub mapping uses REST, **keep only roots** — comments where `in_reply_to_id` is
null. Without that filter every reply is miscounted as a separate thread:

```bash
gh api repos/<owner>/<repo>/pulls/<PR>/comments --paginate
```

Also execute `list_conversation_comments` when supported; these comments carry no file anchor. A
GitHub mapping typically uses:

```bash
gh api repos/<owner>/<repo>/issues/<PR>/comments --paginate
```

Then execute `get_pull_request_diff`, so each comment can be judged against what the code actually
does. For GitHub this is typically:

```bash
gh pr diff <PR> -R <owner>/<repo>
```

### 2. Fact-check each comment adversarially

For every comment, establish what it actually claims, then test that claim. Read the code it points
at — the current content, not just the diff. Where the comment depends on library, framework, or API
behaviour, verify against current official documentation via Context7 or web search rather than
recall. Where it appeals to a project convention, find that convention in the repository and cite it,
or note that it is not written down anywhere.

When `.monolithic-code-review/sources.json` records a `knowledge.root`, that lookup is addressed
rather than open-ended. Follow the cost ladder — routing table, then search, then one unit — over
`4-rules/*` for standards, workflow, and security constraints, and `2-structure/architecture` for a
claim about layering or dependency direction. Cite the unit `id` alongside the convention.

This makes both answers defensible. A convention the store records as `derived` or `stated` supports
the reviewer's claim; one it does not record at all makes "it is not written down anywhere" a
checked result rather than an assertion. A `provenance: assumed` unit supports neither side — treat
the claim as `INCONCLUSIVE` and say which unit was inconclusive and why.

Create an evidence record for every material reviewer claim: `id`, falsifiable `claim`, `expected`
invariant or convention, decisive `evidence`, and, when applicable, same-measure `baseline` and
`treatment`; include `confounds` when present. Then assign these independent attributes:

| Attribute        | Values                    | Meaning                                                                    |
| ---------------- | ------------------------- | --------------------------------------------------------------------------- |
| **Evidence verdict** | `VERIFIED` / `NOT VERIFIED` / `INCONCLUSIVE` | Is the factual claim supported, contradicted, or undecidable? Cite the evidence. |
| **Suggestion**   | `accept` / `decline`      | Should the requested change be made?                                         |
| **Risk**         | `high` / `medium` / `low` | What is at stake if this comment is ignored?                                 |
| **Justification**| free text                 | Required whenever the verdict is not `VERIFIED` or suggestion is `decline`.  |

Use the shared disposition deterministically:

| Evidence verdict | Disposition |
| --- | --- |
| `VERIFIED` | `report` |
| `NOT VERIFIED` | `drop` |
| `INCONCLUSIVE` | `local-uncertainty` |

Only `VERIFIED` claims are eligible for a confirmed finding. `NOT VERIFIED` claims are dropped as
findings. Keep `INCONCLUSIVE` claims visible in the local uncertainty section so the user knows the
reviewer claim could not be decided; never present either non-verified verdict as a confirmed
pull-request finding.

The interesting cases are where evidence and suggestion diverge:

- **`VERIFIED` + `decline`** — the reviewer is factually right, but the change is out of scope, or the
  cost outweighs the benefit. Justify it; this is the one the user most needs to see.
- **`NOT VERIFIED` + `accept`** — the stated reason is wrong but the underlying instinct is sound. Say what
  the real reason is.
- **`NOT VERIFIED` + `decline`** — needs the most careful justification, because it will be read as
  defensive. Cite evidence.

Risk reflects consequence, not tone. A politely-worded comment about an unhandled null in a payment
path is `high`. A strongly-worded comment about naming is `low`.

Weigh authority honestly but do not let it decide: a tech lead's objection raises the cost of
declining and the standard of justification required, but it does not make a false claim true. Note
the reviewer's role when the configuration or the user has established one.

### 3. Present for decision

Build a canvas — an artifact — as the primary output. It is a decision surface: the user needs to
scan every comment, see the four attributes at a glance, and click through to each thread.

Include per comment: reviewer, `file:line` (or `[general]`), the comment text, fact-check verdict with
evidence, suggestion verdict, risk, justification, and a link to the thread. Group by risk, highest
first. Lead with counts — total, accepted, declined, not verified, and inconclusive — and call out
the `VERIFIED + decline` and `NOT VERIFIED + decline` cases, which are the ones needing a human
decision.

Also print a compact terminal summary, so the user gets the shape of it without opening the canvas.
Show local uncertainty separately rather than in the confirmed-comment list:

```text
## PR #<n> comment triage — <m> threads (<k> skipped: resolved/outdated)

accept <a> · decline <d> · not verified <f> · local uncertainty <u>

[high]   src/auth/token.ts:42   @reviewer   VERIFIED / accept   Expired token returned on renew failure
[medium] src/api/orders.ts:118  @lead       VERIFIED / decline  Out of scope — belongs to AGE-41
```

### Local uncertainty

```text
[medium] src/integration/client.ts:31 @reviewer INCONCLUSIVE / decline
Production-only behavior is inaccessible; this is not a confirmed finding.
```

Then stop and ask what the user wants to do. **Do not reply to any thread and do not change any code
from this skill.**

## Manual evaluation cases

- Supported claim: a reviewer identifies a changed null path that reaches a documented payment API
  without a guard; cite the code and contract, mark `VERIFIED`, and show it as a confirmed triage
  result with its independent suggestion and risk.
- Disproved claim: a reviewer says an API is deprecated, while current official documentation and
  the code prove the API remains supported; mark `NOT VERIFIED`, drop it as a finding, and retain
  the evidence in the triage rationale.
- Inaccessible evidence: a reviewer asserts a production-only timing regression that cannot be
  measured from the PR or available environment; mark `INCONCLUSIVE` with the access confound and
  show it only in local uncertainty, never as a confirmed finding.

## Constraints

- Never resolve, dismiss, or approve a thread.
- Every non-`VERIFIED` verdict and every `decline` carries a justification with evidence.
- Do not soften a finding because of who wrote the comment, and do not sharpen one either.
- Report skipped resolved and outdated threads rather than silently dropping them.
- If a comment is ambiguous, say so and ask the user rather than guessing at intent.

## Success criteria

- Every unresolved thread appears exactly once, with its file and line.
- All four attributes assigned to every comment.
- Fact-checks cite evidence — documentation, code, or repository convention.
- Output is a canvas plus a terminal summary, and the skill ends by asking, not acting.
