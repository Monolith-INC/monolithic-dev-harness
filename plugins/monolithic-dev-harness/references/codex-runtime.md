# Codex native subagent governance

## Native identity and work-session scope

Observed Codex CLI 0.162.1 events provide the main agent's `session_id` and each subagent's
`agent_id` on shell and patch calls. Native start/stop notifications supply the same relationship.
The adapter binds those identities to an existing active harness work session before accepting
subagent writes. A session ID alone cannot establish subagent identity.

The adapter retains private identity/turn observations under
`.harness/state/host_sessions/codex/children/`. The shared process bus stores generic process
state under `.harness/state/host_sessions/processes/`. The first record establishes the native
execution context; the second is authoritative for permission withdrawal. Both must allow a
subsequent guarded write. Neither record supplies human approval.

The main agent provides the governing plan, intended role, assigned files and effect limits in
its delegation. It retains actual returned identities and checks execution evidence. Preparing a
brief or naming a tool does not demonstrate successful delegation.

Subagents return human decisions and harness control requests to the main agent. They cannot
record human authority, switch work sessions, execute harness control commands or invoke nested
collaboration controls. The main agent runs test/build commands: a subagent assignment does not
authorize opaque shell programs whose file effects cannot be established.

## Assign before work

For every native delegation, first request a tool-free `READY` response in an independent context.
Read the real scoped process list, then bind an immutable assignment through the authenticated
main-agent tool. For example, using the actually selected model and effort:

```bash
harness process assign <process-id> --repo . --assignment '{"role":"worker","owned_paths":["docs/planning/proof.md"],"model":"gpt-5.6-luna","effort":"low"}'
```

Use `role: reviewer` with an empty `owned_paths` list for review-only work. Only after the adapter
acknowledges the assignment, send the actual task through the native follow-up tool to that same
subagent. A completed READY execution can receive its first assignment; it does not regain
execution permission until a fresh native turn. Assignments cannot be broadened or replaced;
create a new delegation when a different assignment is needed. Cancellation remains permanent.

The shared assignment policy requires exact owned files for edits, rejects symlink edits, and
denies external tools, unknown wrappers and delegation. Reviewer edits are always denied.
Read tools and the following restricted shell forms remain available from the repository root:
`pwd`, `cat -- <repo-path>`, `rg --no-config -n -- <pattern> <repo-path>` and
`sed -n '<start>,<end>p' -- <repo-path>`. Return other inspection/verification needs to the main
agent. Existing harness laws still apply after assignment checks; an assignment grants no human
approval and cannot override protected paths.

Each native pre-tool model observation must match the assignment's exact model. The effort
field records the requested policy; current hook observations do not independently attest actual
reasoning effort. Use explicit native spawn settings, retain genuine native activity evidence,
and do not describe that declaration alone as enforced runtime effort. Custom-agent sandbox
settings do not override the parent's sandbox in the current official contract; these are
harness-enforced restrictions, not a separate operating-system sandbox.

## Standard process messages

All adapters use the catalog in `harness/process_messages.py` and the `MessageBus` interface in
`harness/process_bus.py`. The common consumer checks identity, work session, protocol version,
event deduplication, expected revision and execution history. Vendor parsing stays in the adapter.

The main agent can inspect and control its delegated permissions with:

```bash
harness process list --repo .
harness process status <process-id> --repo .
harness process cancel <process-id> --repo .
```

Use the exact process identifier returned by the scoped list. The adapter derives the sender
from the actual native invocation and selects the central cancellation message. Permission
withdrawal is persisted before the command acknowledges it. A standalone CLI invocation cannot
write a lifecycle record or invent the required adapter observation.

The main agent then uses its actual native interruption tool. When its actual result/status
reports interruption, the main agent can select the standard report message:

```bash
harness process report <process-id> --status interrupted --repo .
```

This updates `reported_status` with main-agent origin. It does not replace `runtime_status`, the
last host observation, or claim that an already-running OS command was killed. `revoked: true`
continues to block subsequent guarded writes regardless of later reports or running notifications.
A new registration cannot reset a revoked process record.

Native stop closes an observed turn. A legitimate follow-up turn requires a different nonempty,
never-completed turn ID, the same main agent/project/work session and permission that has not
been withdrawn. Stale stop messages cannot close a newer execution. Start notifications are not
an enforceable spawn veto. Existing repository opt-out and suspension behavior is preserved.

## Verification and limits

A source-installed isolated CLI trial on 2026-10-24 observed a legitimate subagent write, standard
cancellation through the adapter and bus, a main-agent interruption report, and a denied subsequent
write by the same subagent. The generic record retained permission withdrawal and the fixture
file stayed unchanged after cancellation. This is development-source evidence, not a new release
or an upgrade of the active Desktop profile.

The assignment channel now enforces declared roles, exact owned paths and observed model
matching. Actual reasoning-effort ceilings, native cancellation of an in-flight OS command,
Desktop behavior and all workflow families still require their own evidence. Hooks are not a
universal security sandbox. Installed-candidate assignment acceptance remains pending until
its actual trial is recorded.

The Python subprocess subagent contract remains unsupported. It is separate from the native
model tools and this adapter's standard process message channel. Other adapters can use the same
bus and catalog; their native process integrations remain explicitly unsupported until connected
and verified.
