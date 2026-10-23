# Codex native child governance

The adapter supports a narrow hook-based parent-scope check. This is not a claim of
complete Codex workflow parity or release qualification.

## Native identity and authority

Captured Codex CLI 0.162.1 events supply the parent's `session_id` and the child's
`agent_id` on child `Bash` and `apply_patch` calls. `SubagentStart` and `SubagentStop`
also supply that relationship. A parent session ID alone does not establish child
identity. Desktop support requires its own installed-host evidence.

Before delegation, the root must have an existing native conversation binding to
an active harness work session. A host-originated `SubagentStart` freezes that
binding for the observed child in the protected
`.harness/state/host_sessions/codex/children/` tree. There is no agent-facing command
that registers a child or grants authority.

Each governed child effect must match the saved child, parent, project and active
work-session scope. Missing, contradictory or unreadable lineage blocks the effect. A completed
turn cannot spend its former turn identity. Changing the root's work session does not move an existing child. Existing
harness rules and workflow prerequisites then evaluate the effect under that same
parent scope; a binding supplies no approval of its own.

## Worker instructions

The root invokes the host's actual native tools and supplies the governing plan,
project, work session, task, intended role, owned files and effect limits in the
brief. It must retain the actual returned identity and check real lifecycle
evidence before reporting completion or cancellation. Preparing a brief or mapping
a tool name is not evidence that delegation succeeded.

Children return human decision needs and harness control requests to the root.
They cannot ask native questions, record answers or prompts as human authority,
bind or switch sessions, execute harness CLI controls, or invoke native
collaboration controls. The `harness-python` runtime runner remains available for
ordinary test execution and diagnostics, including `-m pytest`; the existing host
hook execution prohibition still applies.

`SubagentStop` closes the observed child turn, including when the parent is paused.
Codex sends `SubagentStart` on child startup/fork, rather than every follow-up turn.
An authentic child `PreToolUse` can renew a completed child only with a different,
nonempty, never-completed turn ID and the same parent, project and active frozen
work-session scope. Legacy records without turn identity cannot renew this way.
`Interrupt` revokes observed matching children without claiming that cancellation
succeeded; a late stop or fresh turn cannot undo that revocation. A duplicate start
cannot revive an ended binding. Start notifications are not an enforceable spawn veto.

## Current limits

The captured spawn brief is encrypted. Role, model/effort ceilings and owned-path
limits cannot be authenticated from that brief by this adapter and are **not
enforced as child-specific permissions**. The persisted binding contains identity,
project, parent work-session scope and lifecycle status only. Common project rules
continue to govern paths and effects; they do not prove assignment-level ownership.

The RC5 installed CLI trial completed a legitimate planning-document write and
a same-child follow-up write with no failed worker hook callbacks. Its native
interruption reported the child interrupted but produced no observed Interrupt
hook; the saved binding stayed active on that turn. Fresh mismatching turns still
fail the lineage check, but persisted cancellation revocation and cancellation of
an underlying process are not qualified.

Deterministic tests verify additional adapter checks; they do not establish
all native lifecycle operations, every Claude workflow family, or complete law parity. Unknown mutating wrappers and absent
lineage coverage remain qualification blockers. Hooks are not a universal security
sandbox.

Python `codex_adapter.subagents()` still reports unsupported subprocess operations.
Native model-callable tools and subprocess transport are separate capabilities.
