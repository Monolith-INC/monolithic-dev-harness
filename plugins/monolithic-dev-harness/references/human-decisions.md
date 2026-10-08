# Human decisions

The harness asks the human in only two shapes. Use the shape that fits; never invent a third.

| Shape | When | How | Recorded |
| --- | --- | --- | --- |
| **Menu** | One choice with up to three options: a route, a plan checkpoint, an approval | `harness decision present` | Decision record; the answer is reused while the content is unchanged |
| **Question batch** | Several open questions that investigation could not settle | One chat message, then end the turn | Answers go into the plan and its memlog |

Never ask the questions of a batch one at a time, and never ask a menu question in your own words.

A skill's own catalog (elicitation methods, party rooms, review findings to triage) is shown the way
that skill specifies: a numbered list that accepts any form of reply. It is not a recorded decision
and opens no write window.

## Menu

```text
harness decision present --repo <project> --session-id <id> --host <host> \
  --question "..." --option "..." [--detail "..."] [--recommended "..."] \
  [--artifact <path>] [--approval | --allow-free-text] \
  [--blocking-available] [--async-available]
```

- Repeat `--option` for each choice (at most three) and `--detail` for what each one means in
  practice, in the same order. Name the option you recommend with `--recommended`.
- Pass every reviewed file with `--artifact`. A changed file invalidates the earlier answer.
- `--approval` marks a review that authorizes protected writes; it needs an `Approve` option.
  `--allow-free-text` lets a typed reply that is not an option come back as the human's direction
  (routing and plan checkpoints). The two never combine: free text never authorizes a write.
- Say which controls are actually callable: `--blocking-available`, `--async-available`.

The command returns one of:

- `"state": "already_answered"`: the human already answered this question about the same,
  unchanged content. Do not ask again. Continue with `answer`, and mention the earlier choice in one
  line so the human can reopen it. An approval is reused only while its write window is open.
- `"state": "waiting_for_human"`, with a `transport`:
  - `blocking` or `async`: invoke the returned native control. Show the review first.
  - `chat`: show the review, then `menu` exactly as written, and end the turn.

### Fallback

Delivery problems are recoverable and invisible to the human. When a control fails to show, or its
reply is not captured, run `harness decision fallback --repo <project> --session-id <id> --host
<host>` (add `--async-available` when that control is callable). It moves the same question to the
next transport (blocking → async → chat) with the same options, details, and menu text. Never
replace the question, ask the human to diagnose hooks, or show internal errors. Reuse a captured
answer rather than asking again.

### Answers

Only the human resolves a menu: a click, a Codex button reply, or a typed message. Typed replies
count on every transport, including after a dismissed picker or expired buttons, and are matched
loosely: `2`, `option 2`, `the second`, the label in any case or accents, a unique prefix, or a
unique set of its words (`feature` for `Start feature work`). A loose reply never selects an
approving option unless it says "approve" itself; a number or the full label always works. An
ambiguous reply, a question, or other conversation leaves the menu pending: answer it, then show
the same menu again. Delivery, silence, timers, and default selections are never answers.

The prompt and answer hooks record answers. There is no agent-facing command to record one; never
forge a hook event or reconstruct an answer from assistant prose. `harness revoke`, `harness
suspend`, and typed `approve HB-…` keep working while a menu waits.

### While a menu waits

A pending menu blocks writes and workflow advancement in its scope (its work session, or the whole
project for an unscoped one). Read-only inspection, `harness decision status`, `harness
suspension status`, and `harness decision fallback` still run. For a Codex asynchronous control,
keep the turn open with the returned interruptible wait; do not ask another question meanwhile.

## Question batch

After investigation, put every open question in one message:

```markdown
1. **<question>**
   a. **<option>** — what it means in practice. *(recommended: one-line reason)*
   b. **<option>** — …
2. **<question>**
   …

Reply in any form: `1a 2b`, the option names, or "your recommendations".
```

End the turn. Accept any form; ask again only about an answer you cannot place, batched the same
way. Log each answer to the plan's memlog as it lands.

## Closing a series

A series of answers ends with one recap menu, such as the plan checkpoint, that lists every
recorded decision and lets the human change any of them. The recap is the single
acknowledgement; do not ask for each decision again.

## Never stall

Every turn ends with a menu, a question batch, or a status line that starts `Next:` and continues
working. Never end a turn with none of these.
