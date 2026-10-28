---
title: PR 36 first human decision evidence
status: partial
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-07
---

# PR36 acceptance trial: first human decision

## Actual human answer and capture blocker

The parent relayed the actual native button answer **English**, reporting that `functions.request_user_input` received the exact returned payload and returned:

```json
{"answers":{"HD-84469801a71e8fdb":{"answers":["English"]}}}
```

This is human-supplied parent tool evidence, not a tool call observed directly in this fixture context. After that relay, `harness decision status --repo /tmp/monolithic-dev-harness-trial-hfex7n7v/project` still returned `status=pending`, `answer=""`, `transport=blocking`, same decision ID (exit 0). The human choice is known; its harness capture is not complete.

Supported-path inspection was limited to installed skill/reference documentation and CLI help. `harness decision --help` (exit 0) exposes only `present`, `status`, and `fallback`, with no answer-ingestion operation. `harness --help` (exit 0) exposes no relayed-answer capture command. Installed `references/human-decisions.md` explicitly states: "The prompt and answer hooks record answers. There is no agent-facing command to record one" and prohibits forged hook events. A targeted reference search found no documented relay capture path. An initial `references/host*` search reported no matching path; listing installed references confirmed no such host reference. No implementation was inspected.

Precise capability blocker: the native answer was delivered in the parent context, while the fixture's decision remains pending; no documented agent-facing bridge is available to ingest that actual parent response into this fixture decision. Live hook capture and native conversation/tool identity binding remain unverified. This evidence does not establish the underlying hook failure cause.

No language question was repeated. No fallback, hook simulation, manual decision/answer/preference write, workflow advancement, or implementation occurred. The pending record and fixture remain preserved. Only this acceptance evidence document was updated. One attempted patch to this evidence document failed its context check without changing files, then the update was applied successfully.

Date: 2026-10-07. Fixture preserved: `/tmp/monolithic-dev-harness-trial-hfex7n7v/project`.

Human supplied desktop restart and installed-cache verification against `3d723e3dda51097ff66723aba4631e34a4411d75` (366 files in briefing). These were not independently reverified by source inspection. No parent history or harness implementation was read. Installed harness/bootstrap skills and human-decisions reference were read.

## Actual commands and results

Commands ran in the fixture unless a read names an absolute path.

1. `cat /home/monolith/projects/monolithic-dev-harness/docs/06-delivery/acceptance/pr-36/briefing.md`: exit 0; read filled briefing.
2. Read installed `skills/harness/SKILL.md` under `/home/bhave/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.6.2/`; exit 0. Tool metadata scan found harness integration tools; native `request_user_input` is available in this host.
3. `command -v harness`: `/home/bhave/.local/bin/harness`.
4. `harness begin --request "I can see how many tasks I still need to do, but I also want to see how many I have finished. Show both counts on the task screen." --repo /tmp/monolithic-dev-harness-trial-hfex7n7v/project`: exit 0; `state=setup_needed`, setup ready, language en but unconfirmed, local tracker/SCM, BMAD ready, waiting_for_answer false. Requested completion of bootstrap and repeat begin.
5. Read installed `skills/bootstrap/SKILL.md` and `references/human-decisions.md`: exit 0. Required language decision when unconfirmed.
6. `harness bootstrap --inspect --repo /tmp/monolithic-dev-harness-trial-hfex7n7v/project`: exit 0; ready, no missing settings, runtime and tracker storage ready, language unconfirmed; master at `4c8013b40d92130168ecf73c5e8c07ab78b78c1d`; workflow absent, no pending question, original_request empty. Artifacts destination `docs/planning`; tracker `.harness/tracker`; installed command `/home/bhave/.local/share/monolithic-dev-harness/marketplace/plugins/monolithic-dev-harness/bin/harness`.
7. `harness decision present --repo /tmp/monolithic-dev-harness-trial-hfex7n7v/project --host codex --gate language --blocking-available`: exit 0; returned exact payload below.
8. `harness decision status --repo /tmp/monolithic-dev-harness-trial-hfex7n7v/project`: exit 0; pending, blank answer, blocking transport. `rg --files --hidden .harness`: settings.json and state/decision.json only.
9. `cat .harness/state/decision.json`: exit 0; record below. `printenv CODEX_THREAD_ID CODEX_CONVERSATION_ID CODEX_TOOL_CALL_ID HARNESS_CONVERSATION_ID HARNESS_TOOL_CALL_ID`: exit 1 because some names absent; one UUID printed. A named JSON environment check using the requested installed `bin/harness-python` followed to disambiguate.

10. `/home/bhave/.local/share/monolithic-dev-harness/marketplace/plugins/monolithic-dev-harness/bin/harness-python -c 'import json, os; print(json.dumps(dict(map(lambda key: (key, os.environ.get(key)), ("CODEX_THREAD_ID", "CODEX_CONVERSATION_ID", "CODEX_TOOL_CALL_ID", "HARNESS_CONVERSATION_ID", "HARNESS_TOOL_CALL_ID")))))'`: exit 0; `CODEX_THREAD_ID=01a11631-1447-7213-bb2c-5a73340cf264`; the other four values were null.

## Exact returned control payload

```json
{"host":"codex","transport":"blocking","tool":"request_user_input","isBlocking":true,"questions":[{"id":"HD-84469801a71e8fdb","header":"Review","question":"Which language should this project use?","options":[{"label":"English","description":"Questions, plans, and work items in English."},{"label":"Português (Brasil)","description":"Questions, plans, and work items in Brazilian Portuguese."}]}],"decision_id":"HD-84469801a71e8fdb","state":"waiting_for_human"}
```

## Pending record

Path: `/tmp/monolithic-dev-harness-trial-hfex7n7v/project/.harness/state/decision.json`.

```json
{"allow_free_text":false,"answer":"","approval":false,"artifacts":[],"details":["Questions, plans, and work items in English.","Questions, plans, and work items in Brazilian Portuguese."],"gate":"language","id":"HD-84469801a71e8fdb","options":["English","Português (Brasil)"],"question":"Which language should this project use?","status":"pending","transport":"blocking"}
```

## Observations and limits

Normal begin consolidated setup inspection and correctly stopped for unconfirmed language. First human decision is onboarding, so grounded product discovery and its proposal have not yet been reached. The blocking payload is prepared; native control delivery is deferred to the parent as instructed. No answer, fallback, synthetic hook, preference change, implementation, delegation, or remote write was performed.

Missing livehook evidence: no live hook event or answer-capture evidence was exposed in these results. The pending record contains no native conversation or tool identity. A thread environment identifier alone cannot verify native identities for subagent tool events or prove correct conversation binding. Those expectations remain unverified; no hook events were fabricated. Parent must present the exact payload and relay the actual human answer before continuation.
