# No discovery skill use — manual trace grader

Pass only when the complete execution trace contains no explicit activation of the harness `discovery` skill, identified by `discovery` or its qualified name `monolithic-dev-harness:discovery` in a skill name or invocation arguments, or by an activation that identifies `skills/discovery/SKILL.md`. Check equivalent host-specific skill-activation events as well as `Skill` tool calls. Record the evidence examined.

Fail if an identifying discovery activation appears. Activations of unrelated skills do not by themselves fail this criterion. If the relevant trace is unavailable or incomplete, report **inconclusive**, not a pass.
