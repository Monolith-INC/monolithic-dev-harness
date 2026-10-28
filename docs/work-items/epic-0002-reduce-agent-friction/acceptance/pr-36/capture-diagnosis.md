---
title: PR 36 parent-mediated capture diagnosis
status: routing-gap-confirmed
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-07
---

# Parent-mediated capture diagnosis

The real native Standalone reply exists in the parent transcript. No answer was fabricated,
replayed through a hook, or written to the fixture decision.

## Verified evidence

- Parent conversation `01a115d8-5def-70a1-9f08-a614fc7d5a81` has workspace
  `/home/monolith/projects/monolithic-dev-harness`.
- Project agent `01a1176d-2568-7650-bcc8-3bca43dcde3a` also inherited that workspace in its
  transcript metadata. Explicit shell working directories targeted the disposable fixture, but
  do not relocate the parent native question call.
- The parent's transcript contains `request_user_input` call
  `call_qwfcJOQzwmIvReRIyZOo2lLY`, question `HD-a2811e0cbd10f7e5`, and its real output:
  `Standalone (Recommended)`. The project agent transcript contains no matching native exchange.
- The fixture decision remains `HD-a2811e0cbd10f7e5`, pending, with no presentation identity or
  saved answer. It was not rebound to the native call ID.
- `hook._question_repo` resolves the calling workspace through `_workspace`; it does not route
  an HD question ID to another project. Ask and answer handlers then resolve session context
  within that project. `handle_ask` normally binds the prepared decision to the native tool ID.
- Transcript recovery requires the same transcript/session/workspace and pending call ID. The
  fixture's prepared HD ID and the parent's native call ID differ, and the native exchange lives
  in the parent transcript.

Only relevant metadata and the specific exchange were inspected; full transcripts are not copied
into repository evidence. The daemon stderr log was empty and provided no hook execution trace.

## Conclusion and limits

The parent-mediated acceptance procedure lacks a supported cross-project question route. A parent
button cannot be assumed to update a child fixture simply because its question ID matches.
This is a confirmed design gap in the trial path, not proof that same-workspace capture works or
that the host executed its question hooks. Hook matcher/event delivery remains unverified.
The optional language policy successfully allowed startup, but did not repair this routing gap.

## Next design choice

Test native capture with the fixture as the actual chat workspace, or explicitly design a trusted
cross-project relay. The first isolates ordinary capture without expanding product scope; the
second changes the communication architecture and requires binding project, decision, conversation
and native call before accepting a reply. Do not scan arbitrary projects/transcripts for matching
answers, accept assistant relays as hook evidence, or add an agent-facing answer command.

No implementation change or trial continuation was made during diagnosis. The human's Standalone
choice remains known; its protected harness capture is still absent.
