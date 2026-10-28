# Human decisions

The harness asks the human in only two shapes. Use the shape that fits; never invent a third.

| Shape | When | How | Recorded |
| --- | --- | --- | --- |
| **Menu** | One choice with up to three options: a route, a plan checkpoint, an approval | `harness decision present` | Decision record; the answer is reused while the content is unchanged |
| **Question batch** | Several open questions that investigation could not settle | One chat message, then end the turn | Answers go into the plan and its memlog |

The host adapter normalizes a delayed native reply only when its presentation id, exact question,
options, conversation and transport match the pending record. This applies to lifecycle controls as
well as work decisions. Tool acceptance is not the human answer, and model-authored hook JSON is
never replayed as one. After dismissal or a delivery error, preserve the staged choice and use its
typed fallback or recovery control.

Never ask the questions of a batch one at a time, and never ask a menu question in your own words.

A skill's own catalog (elicitation methods, party rooms, review findings to triage) is shown the way
that skill specifies: a numbered list that accepts any form of reply. It is not a recorded decision
and opens no write window.

## Menu

Standard questions come from the catalog in `config/gates.toml`, already written in every supported
language. Ask them by id; the harness shows the version for the project's language. Never word,
reword, or translate a standard question yourself.

```text
harness decision present --repo <project> --host <host> \
  --gate <id> [--value name=value]... [--recommended <option id>] [--artifact <path>]... \
  [--blocking-available] [--async-available]
```

| Gate | Asked when |
| --- | --- |
| `language` | The user wants to change the optional language preference |
| `setup-confirm` | The setup proposal is ready |
| `next-step` | Setup is done and the request did not say what to do |
| `starting-point` | An idea arrives with no clear starting point |
| `idea-continue` | The idea route ends: continue into technical discovery, or stop with the brief or spec |
| `refined-start` | The item the user started from is already refined: rework it, or use it as it is (`--value item=`) |
| `planning-depth` | Discovery is done and the depth (Light, Standard, Hardcore) is not chosen yet |
| `planning-methods` | Standard or Hardcore depth: shortlist, full catalog, or recommended methods |
| `plan-checkpoint` | The discovery plan is ready (`--artifact` the plan) |
| `refinement-split` | A proposed split of an Epic, Feature or Story is ready (`--artifact` the outline); no write |
| `harness-controls` | The user wants to suspend, resume, or use free mode |
| `publish-items` (`--value count= --value items= --value tracker=`), `move-item` (`--value item= --value status= --value ref=`), `approve-spec`, `implementation-confirm`, `approve-document`, `publish-branch` (`--value branch=`), `reply-pr` (`--value pr=`), `pause-tracking` | Approvals; see the harness skill's approval protocol. `publish-items` lists the exact `key:<existing-key>` and/or `title:<new-item-title>` identities in `items`, matching `count`, so generated tracker keys can be verified after creation. `publish-items`, `implementation-confirm` and `approve-document` require the files shown first: run `harness workflow show`, put its output in your reply, run `harness decision status` (the host records a reply only once another tool runs), then ask |

- Never pass a session id: the harness asks in the project's current work session, or
  project-wide when there is none. Asking never requires a session to exist.
- `--value` fills the gate's `{slots}`; the command names any that are missing.
- `--recommended` names an option id to mark instead of the gate's default.
- Pass every reviewed file with `--artifact`. A changed file invalidates the earlier answer.
- Claude Code gets its native question control by default. Other hosts pass
  `--blocking-available` when theirs can. Codex selection requires an observed runtime profile:
  availability flags cannot establish mode, permission, root identity or structured UI qualification.
  Missing mode evidence leaves required structured decisions pending with
  `unsupported_decision_transport`; use the recovery command below for the same typed menu.

A **one-off question** that no gate covers (a product choice specific to this work) uses
`--question`, `--option` (at most three), `--detail` per option, `--recommended <label>`, and
`--allow-free-text` when a typed direction is a valid answer. Write it in the project's language.
Approvals are never one-off: they always come from a gate, which fixes what they are tied to.

The command returns one of:

- `"state": "already_answered"`: the human already answered this question about the same,
  unchanged content. Do not ask again. Continue with `answer`, and mention the earlier choice in one
  line so the human can reopen it. An approval is reused while it holds (not revoked, its work
  session still running, and what it is tied to unchanged).
- `"state": "waiting_for_human"`, with a `transport`:
  - `blocking` or `async`: invoke the returned native control using its `questions` payload
    verbatim. Keep each question ID, question text, option label, and description unchanged. Show
    the review first.
  - `chat`: show the review, then `menu` exactly as written, and end the turn.

### Fallback

Delivery problems are recoverable. When a control fails to show, or its
reply is not captured, run `harness decision fallback --repo <project> --host
<host>` (add `--async-available` when that control is callable). It moves the same question to the
next transport (blocking → async → chat) with the same options, details, and menu text. A
fallback is for that one question: present the next question with native controls again. Never
replace the question, ask the human to diagnose hooks, or show internal errors. Reuse a captured
answer rather than asking again. If an optional preference was not captured, continue with its
default; do not keep retrying controls or repeat the preference question.

For Codex, availability flags never qualify another native transport. A typed recovery preserves
the pending decision and may capture a genuine human answer, but its `structured_qualified: false`
does not satisfy a workflow or release requirement for native structured controls. Report a
required transport incompatibility as a blocker; do not silently declare chat equivalent.

The fallback command accepts only `--repo`, `--session-id`, `--host`, and transport-availability
flags. Do not add a decision ID or a reason: the pending question is resolved from the saved
project/session state. If a native presentation is rejected because its payload does not match,
reuse the exact payload returned by `decision present`; do not invent a replacement question.

### Answers

Every decision has a type: `preference`, `required`, or `approval`. A preference has a safe default
or can be omitted and never blocks work. Language is a preference; use English if no choice was
captured. Required decisions objectively prevent the requested operation from proceeding correctly;
approvals authorize a specific protected action. Both retain their blocking and recording rules.
Older language decisions are preferences; unknown older decisions remain required. Approval records
cannot become nonblocking by declaring a preference type.

Only the human resolves a menu: a click, a Codex button reply, or a typed message. Typed replies
count on every transport, including after a dismissed picker or expired buttons, and are matched
loosely: `2`, `option 2`, `the second`, the label in any case or accents, a unique prefix, or a
unique set of its words (`feature` for `Start feature work`). A loose reply never selects an
approving option unless it says "approve" itself; a number or the full label always works. An
ambiguous reply, a question, or other conversation leaves the menu pending: answer it, then show
the same menu again. Delivery, silence, timers, and default selections are never answers.

The prompt and answer hooks record answers. There is no command accepting an agent-supplied answer;
never forge a hook event or reconstruct an answer from assistant prose. `harness revoke`, `harness
suspend`, and typed `approve HB-…` keep working while a menu waits.

### Relayed project-agent choices in Codex

When a project agent relays a non-approving choice through its parent, the parent first runs
`harness decision status --repo <project> --session-id <work-session>` to observe that exact pending
record, then presents its unchanged native question and options. After the actual human replies,
the root runs `harness decision recover --host codex --repo <project> --session-id <work-session>`.
This command reads the current root's canonical Codex desktop session transcript under the OS
account's `.codex/sessions`; caller-selected `CODEX_HOME`/`HOME` cannot redirect this source. Custom
log locations are not supported by this recovery path. It accepts no answer or
transcript path. It verifies the originating agent's parent relationship, the pending record shown
before delivery (including its unique instance, descriptions and reviewed artifacts), the exact
question/options, successful delivery and the subsequent actual user
message. Unmatched evidence leaves the question pending. The record retains source session,
question call and user-message IDs. The project agent then reads decision status and continues.

Recovery cannot grant approvals, qualify native structured transport or import a choice into a
different decision. It reuses the genuine recorded reply, so do not ask the human to repeat it.
Missing native transcript evidence remains a concrete capture blocker.

### While a menu waits

A pending required decision or approval blocks writes and workflow advancement in its scope (its work session, or the whole
project for an unscoped one). Read-only inspection, `harness decision status`, `harness
suspension status`, and `harness decision fallback` still run. For a Codex asynchronous control,
use a returned interruptible wait only when observed. Without a wait tool, end the turn while the
decision remains pending. Do not ask another question or do dependent work meanwhile.
Onboarding status, skip, dismissal, restart and mode selection are recovery controls, not answers.
They may discard optional onboarding prompts while preserving evidence, without granting approval.
Known onboarding prompts can be cancelled when onboarding is skipped, dismissed or restarted.
An unanswered settings-review proposal is abandoned, never accepted; its application is blocked
until a new review. Required product decisions and action approvals are not onboarding prompts.
Free mode supports skills without setup or sessions and keeps strict action governance intact.

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

## Automatic review checkpoints

Presenting a decision with artifacts adds a workflow review point when that workflow is active.
The pending decision owns recovery data until the checkpoint is applied. Failed decision storage
creates no checkpoint; an interrupted projection is completed once on workflow read or answer
capture. Recovery never answers for the user or grants approval. A conflict preserves both records
and stops advancement for inspection; do not replace either record or re-ask approval to bypass it.
Questions without a workflow or in a paused workflow continue without an automatic checkpoint.

## Codex delivery follows the observed mode

The immutable Codex runtime profile separates surface, actual collaboration mode, root identity,
advertised tools, permission and observed structured UI qualification. Selection never grants
approval. Plan may present a permitted domain decision through a qualified native control;
implementation must await an actual host mode switch. Default's optional question contract cannot
host a required approval. Optional Default input never claims `isBlocking: true`, and unanswered
preferences may use their safe defaults. Host permissions and sandbox escalations always use the
host's permission mechanism. Async delivery additionally requires the root, an observed async
tool and independent permission for required decisions. A native async hook can establish this
delivery contract within its exact session, turn and model. It does not establish a human answer
or rendered UI qualification. Use an observed interruptible wait when available; otherwise end
the turn with the pending decision intact.

Current native hook observations are stored under the protected
`.harness/state/host_sessions/codex/` directory and read only for the exact native conversation.
Each root observation replaces stale evidence. Hook `permission_mode` describes approval policy;
it does not prove collaboration mode. Existing hook observations consequently leave that mode
unknown and cannot qualify a structured control. No agent-facing mode or availability flag can
change this evidence. Required structured delivery remains a qualification blocker until a trusted
current observation establishes the needed contract. A real native trial and genuine human answer
remain necessary to establish live capture; synthetic fixtures and operator automation prove only
their stated technical boundary.
