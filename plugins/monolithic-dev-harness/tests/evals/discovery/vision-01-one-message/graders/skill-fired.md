# Discovery skill use — manual trace grader

Pass only when the complete execution trace contains an explicit activation of the harness `discovery` skill, identified by `discovery` or its qualified name `monolithic-dev-harness:discovery` in the skill name or invocation arguments, or by an activation that identifies `skills/discovery/SKILL.md`. A host's equivalent skill-activation event counts when it identifies that same skill. Record the event and its identifying name or arguments.

Fail if the trace shows only unrelated skills, ordinary tool calls, or a statement that discovery was used without an identifying activation. If the relevant trace is unavailable or incomplete, report **inconclusive**.
