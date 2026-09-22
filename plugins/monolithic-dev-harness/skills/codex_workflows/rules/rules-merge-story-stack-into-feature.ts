/**
 * Rules for workflows-merge-story-stack-into-feature.md only.
 * Binding: skills/codex_workflows/resources/workflows-merge-story-stack-into-feature.md
 * Installed as: .agent/workflows/workflows-merge-story-stack-into-feature.md
 */
export const workflow = "workflows-merge-story-stack-into-feature.md" as const;

export const rules = [
  "INVOKE this stage only when stacked Story branches are ready to land into the Feature branch.",
  "DO NOT invent a new Feature or Story branch during merge-story-stack-into-feature.",
  "PROCESS unmerged Story branches in stack order from oldest to newest.",
  "DO NOT skip a middle Story in the stack when later descendants exist.",
  "USE merge commits only for Story→Feature; NEVER squash a Story into Feature.",
  "NEVER rebase a Story branch onto Feature during this stage.",
  "NEVER force-push Feature or Story branches.",
  "RESOLVE conflicts on the Feature branch that received the merge.",
  "KEEP every Story pull request base equal to the Feature branch.",
  "INVOKE reconcile-feature-stack when Feature is not an ancestor of the next Story before merging that Story.",
  "RUN reconcile-feature-stack for remaining open descendants after each successful Story→Feature merge.",
  "PUBLISH merge evidence to the Feature tracker work item after each Story lands.",
  "DO NOT retarget a Story pull request to trunk during this stage.",
  "DO NOT open the Feature→trunk pull request during this stage.",
] as const;
