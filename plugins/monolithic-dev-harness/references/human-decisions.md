# Human decisions

The shared workflow requests a decision, records that it is waiting, and advances only after the
matching human answer. The host adapter owns the question tool and response format. Prefer a
supported blocking control. When it is unavailable, the Codex adapter may use asynchronous buttons;
it records the pending question and keeps the turn open while waiting. Delivery never counts as an answer.
If no supported button tool exists,
show the complete review and question in chat, end the turn, and wait for the human reply.

Use `harness decision present --repo <project> --session-id <id> --host <host> --question "..." --option "..."`
with each offered option repeated and each reviewed file supplied through `--artifact <path>`.
Use `--blocking-available` only when the adapter's blocking tool is actually callable in this
session. Use `--async-available` when the Codex asynchronous button tool is callable but its blocking tool is unavailable. `--approval` explicitly identifies a review that authorizes the described writes; merely
choosing a route is not write approval. The command returns the adapter presentation and a pending
decision id. Present it faithfully and follow the adapter waiting instruction. Do not continue dependent work after delivery of a question.

The trusted prompt/answer hook resolves the offered choice for the same decision and artifact
revision. Approval questions require an offered option. Native routing questions prepared with
`--allow-free-text` also accept the UI's actual Other response. Direct Codex routing controls use
id `next_step` or `starting_point`; other direct questions remain closed choices. Free text never
authorizes a write. Other chat messages stay an ordinary
prompt, so `harness revoke`, `harness suspend`, and typed approvals keep working while it waits. An
approval it records covers the work session of the conversation that answered. Without a session
id (Cursor), the one pending session decision is the one answered; with several, none is guessed. Other messages, delivery acknowledgments, expired time, and default selections are not
answers. A changed artifact cannot be approved from its earlier question. Revise or Stop can still
reject a stale review. Repeated responses cannot reopen its approval. There is no agent-facing
command to record a human answer. Capture decodes JSON text and objects at the host boundary.
On a subsequent real Codex prompt, the hook can recover a missed blocking-tool answer from the
host-supplied transcript, checking its session, project, call id, question, and options. The current
prompt's revocations still apply. Never forge a hook event or reconstruct an answer from assistant prose.

Question delivery and capture failures are recoverable, not reasons to abandon the run. Quietly
try the next available method and re-ask when the question failed to land: blocking native
control, asynchronous native control, then ordinary chat. Use `harness decision fallback --repo
<project> --session-id <id> --host <host>`, adding `--async-available` when that method is callable.
It moves the same pending decision to a simpler transport and returns its presentation; it cannot
replace the question, choices, review, or answer. Invoke the returned control. Preserve existing
choices, artifacts, and progress, and resume this same run after the answer. Do not show internal
failure reports to the user or ask them to diagnose hooks. Reuse a captured answer rather than
asking it again. Only actual human input resolves the decision; delivery, silence, and timers do not.

Status is available through `harness decision status --repo <project> --session-id <id>`. Pending decisions block
workflow advancement and writes. Suspending harness checks remains independently available on the
human's request; it preserves the pending decision rather than inventing an answer.

An unanswered decision must not block read-only diagnosis, `harness suspension status`, or the
controlled `harness decision fallback` transport change.
Inspect the installed registration, event format, and project/state paths when a genuine reply
is not recorded. Recover a captured answer first; re-ask through an alternative method when delivery
failed. Do not suspend enforcement merely to
read diagnostics. A human suspension request works before onboarding and even when the saved
conversation binding is invalid. Capture diagnostics go to the agent without private reply content;
recover quietly instead of turning them into a user-facing blocker. A successful hook exit does not
prove that an answer was recorded.

Codex delayed button replies are read only from the actual human prompt event. The adapter checks
the saved tool-call id, question index, and question text before passing the choice to the shared
answer handler. Immediate tool completion cannot answer an asynchronous question. A typed chat
choice is matched without regard to capitalization; asynchronous replies still require their
question identity. For Codex asynchronous buttons, use the returned interruptible wait in short intervals and keep
the turn open. Do not send a final response before the actual answer. Do not ask another question
while waiting; unrelated messages leave the decision pending. The native countdown may hide the
panel without an answer; the user can reopen the same question with Answer question. Do not
create a replacement solely because the panel countdown elapsed. If delivery actually fails or
interruptible waiting is unavailable, use the next method and re-ask the same question. The harness
does not change the native app timer.

A focused process replay is diagnostic evidence, not proof that installed host
hooks captured a live reply.
