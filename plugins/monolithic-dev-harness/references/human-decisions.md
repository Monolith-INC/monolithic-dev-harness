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
revision. Only a reply that picks an offered option answers it; any other message stays an ordinary
prompt, so `harness revoke`, `harness suspend`, and typed approvals keep working while it waits. An
approval it records covers the work session of the conversation that answered. Without a session
id (Cursor), the one pending session decision is the one answered; with several, none is guessed. Other messages, delivery acknowledgments, expired time, and default selections are not
answers. A changed artifact cannot be approved from its earlier question. Revise or Stop can still
reject a stale review. Repeated responses cannot reopen its approval. There is no agent-facing
command to record a human answer. If the host cannot capture the actual reply, report that capability
blocker; do not forge a hook event to keep the workflow moving.

Status is available through `harness decision status --repo <project> --session-id <id>`. Pending decisions block
workflow advancement and writes. Suspending harness checks remains independently available on the
human's request; it preserves the pending decision rather than inventing an answer.

An unanswered decision must not block read-only diagnosis or `harness suspension status`.
Inspect the installed registration, event format, and project/state paths when a genuine reply
is not recorded. Do not ask the human to repeat a failed answer or suspend enforcement merely to
read diagnostics. A human suspension request works before onboarding and even when the saved
conversation binding is invalid. Capture exceptions are reported without including private reply
content; a successful hook exit does not prove that an answer was recorded.

Codex delayed button replies are read only from the actual human prompt event. The adapter checks
the saved tool-call id, question index, and question text before passing the choice to the shared
answer handler. Immediate tool completion cannot answer an asynchronous question. A typed chat
choice is matched without regard to capitalization; asynchronous replies still require their
question identity. For Codex asynchronous buttons, use the returned interruptible wait in short intervals and keep
the turn open. Do not send a final response before the actual answer. Do not ask another question
while waiting; unrelated messages leave the decision pending. The native countdown may hide the
panel without an answer; the user can reopen the same question with Answer question. Do not
automatically create a replacement question. If the host lacks interruptible waiting, report that
limitation. The harness does not change the native app timer.

A focused process replay is diagnostic evidence, not proof that installed host
hooks captured a live reply.
