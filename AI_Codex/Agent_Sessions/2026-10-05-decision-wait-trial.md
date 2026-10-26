# Candidate harness decision wait trial

Date: 2026-10-05

## Scope

Process test only, using candidate `plugins/monolithic-dev-harness/bin/harness` in the disposable project `/tmp/harness-decision-trial.Kb9uM2`. It contains `review.md`, a short review artifact. No files in the candidate harness were changed by this trial. No installed host hook or native question control was tested.

## Question presented

> Should this trial advance to the next workflow step?

Options:
- Continue
- Stop

The text adapter returned `transport: chat`, `state: waiting_for_human`, and decision id `HD-bb6d8c15247d6327`. It instructed the caller to show the question in chat, end the turn, and wait for the actual human reply.

## Evidence

- `harness decision status --repo /tmp/harness-decision-trial.Kb9uM2` returned the same decision id, `status: pending`, `answer: ""`, and options `Continue` and `Stop`.
- A valid attempted advance, `harness workflow checkpoint --repo /tmp/harness-decision-trial.Kb9uM2 --stage build --point 1 --label 'Attempt to advance with unanswered decision'`, returned: `wait for the human's answer before advancing the workflow`.
- A following decision status still returned `status: pending` and `answer: ""`.
- `harness workflow status` reported `no workflow has been saved`. Therefore this proves the pending-decision gate refused the checkpoint; it does not prove an existing workflow remained at a particular stage.
- An earlier checkpoint attempt used a text value for numeric `--point` and was rejected by argument parsing. It was corrected to `--point 1`; only the corrected attempt is evidence of the waiting gate.

No human response was entered or inferred, and no decision was resolved.

## Files read

- `/home/monolith/.codex/memories/MEMORY.md` (task-relevant guidance)
- `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/references/human-decisions.md`

CLI help was read from command output. Candidate code and host adapter implementation were not read as files.

## Command count

- 9 shell-tool invocations in this trial, counting the initial repo/memory inspection and final evidence check.
- 10 candidate CLI invocations, including help, presentation, status, and checkpoint attempts. One checkpoint used an invalid point argument; one corrected checkpoint was refused by the pending-decision gate.

## Relayed genuine reply and retry

The human's actual reply in the main chat was exactly `continue` (lowercase). At the user's direction, this exact reply was relayed as the `prompt` field to the candidate Codex prompt hook using process testing:

`printf '%s' '{"cwd":"/tmp/harness-decision-trial.Kb9uM2","prompt":"continue"}' | python3 plugins/monolithic-dev-harness/scripts/harness/hook.py --host codex --event prompt`

This is a relayed genuine human reply in a process test. It is not evidence of native installed host-hook capture. The reply was not normalized by the operator.

After the hook call, `harness decision status` still showed `status: pending` and `answer: ""`. The same checkpoint command was retried and returned `wait for the human's answer before advancing the workflow`. A final status read again showed the decision pending; `workflow status` again reported `no workflow has been saved`.

The offered option was `Continue` with an uppercase C, while the actual reply was lowercase `continue`. The candidate prompt hook did not match these values, so this attempt stopped at the pending-decision gate. No other answer was tried, and the decision remains unresolved.

## Case-insensitive candidate retry

Following the candidate update described by the coordinating agent, the already received genuine reply was replayed exactly as `continue` through the candidate Codex prompt hook in the same temporary project:

`printf '%s' '{"cwd":"/tmp/harness-decision-trial.Kb9uM2","prompt":"continue"}' | python3 plugins/monolithic-dev-harness/scripts/harness/hook.py --host codex --event prompt`

The hook returned `[harness] human decision recorded: Continue`. Decision status then showed `status: answered` and `answer: "Continue"`. This was a relayed genuine reply in process testing, not native installed host-hook capture.

Retrying the checkpoint command returned `no workflow has been saved`. A final decision status remained answered, and workflow status independently confirmed `no workflow has been saved`. Per the test scope, no workflow setup was invented and the trial stops here.

## Codex asynchronous-button delivery trial

This is process testing with the candidate package only. It does not establish native installed host-hook capture.

The prepared project was `/tmp/harness-async-decision-ready.BYqCms`. Before presentation, it received a saved workflow (`Process-test asynchronous human decision delivery`) and a valid minimal `.harness/settings.json` copied in shape from `plugins/monolithic-dev-harness/tests/settings_fixture.py::MINIMAL`. This fixture-based setup is explicit test preparation. A first scratch directory had been presented before settings were written; that scratch was abandoned and its pending question was never bound or answered. The reported test uses the fresh ready project only.

The required `harness decision present --host codex --async-available` call returned:

- `host: codex`, `transport: async`, `tool: request_user_input_async`, `isBlocking: false`
- Button payload: `questions: [{title: "Should this focused test continue to its next step?", options: ["Continue", "Stop"]}]`
- End-turn instruction: `Show the review, deliver the buttons, end the turn immediately, and wait for the actual human reply. Delivery is not an answer.`
- Prepared decision id: `HD-059fad177d40ae82`

For process testing, the candidate ask hook received this clearly labeled test call id: `call-async-process-test-001`. The payload used `tool_name: request_user_input_async` and the exact title/options above. Decision status then showed `status: pending`, `transport: async`, id `call-async-process-test-001`, and `presentation_id: HD-059fad177d40ae82`.

A delivery acknowledgment was sent through the candidate answer hook as `tool_response: {"accepted": true}` with the bound test call id. It did not supply a choice. Status remained pending with an empty answer. A workflow checkpoint attempt returned `wait for the human's answer before advancing the workflow`; final status still showed pending. No human answer was simulated or entered. The prepared workflow remains active at setup.

Counts for this focused run: 17 shell-tool invocations total, including repository and fixture inspection, preparation, hook events, status checks, and report updates; 12 candidate CLI/hook invocations, including one discarded-scratch attempt; 9 unique candidate source/reference/test files read. No implementation files were changed.

## Actual main-chat button reply: stopped

After the human reported that the first buttons disappeared before selection, the same question
was displayed again. The actual main-chat reply selected `Stop`, with question item identity
`["request_user_input_async", "call_ofFyiXSyX2uDO50TA4LYFSah", 0]`.

The focused live test is ended by the human. No checkpoint was advanced and no implementation was
started. This proves receipt of the actual UI selection in the main chat, not installed candidate
hook capture. The process fixture has a different bound test call id and remains diagnostic;
its identity was not rewritten to manufacture a successful native reply-resolution result.
The prepared realistic application project remains available for later tests in this session.
