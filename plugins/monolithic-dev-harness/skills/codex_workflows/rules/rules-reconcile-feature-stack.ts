/**
 * Rules for workflows-reconcile-feature-stack.md only.
 * Binding: skills/codex_workflows/resources/workflows-reconcile-feature-stack.md
 * Installed as: .agent/workflows/workflows-reconcile-feature-stack.md
 */
export const workflow = "workflows-reconcile-feature-stack.md" as const;

export const rules = [
  "INVOKE this stage only when an ancestor Feature or Story advanced after a descendant Story branched.",
  "DO NOT invent a new Feature or Story branch during reconcile.",
  "PROCESS open Story branches in stack order from oldest to newest.",
  "MERGE the immediate ancestor into each Story before moving to the next descendant.",
  "USE Feature as the ancestor for the first open Story; USE the previous Story in the stack as the ancestor for later Stories when that previous Story is not yet merged into Feature.",
  "RESOLVE conflicts on the Story branch that received the merge.",
  "PUSH each reconciled Story branch before reconciling the next descendant.",
  "KEEP every Story pull request base equal to the Feature branch.",
  "DO NOT retarget a Story pull request to trunk during reconcile.",
  "DO NOT open the Feature→trunk pull request during reconcile.",
  "DO NOT skip a middle Story in the stack when later descendants exist.",
] as const;
