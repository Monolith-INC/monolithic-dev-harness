---
name: branch-and-pr
description: Create the Story branch and, after review passes, push it and open a draft pull request linked to the Story, on the repository host the settings select (Azure Repos or GitHub). Use at the start of implement-story (branch) and at the end of the review stage (push and PR).
---

# Branch and pull request

Adapted from cursor-team-kit's `new-branch-and-pr` (MIT), rewritten around the gateway's `scm_*`
tools, which work the same on Azure Repos and GitHub (`scm.name` in `.harness/settings.json`).

## Branch

Branch creation is an optional delivery choice after the user has reviewed the plan. It is never a
prerequisite for local implementation. Do not create a branch or start a session during bootstrap,
discovery, or ideation. If the user did not choose branch-based delivery, skip this section and
continue from the approved bundle in the existing working copy. If a decision or approval is needed, ask it as a menu ([human-decisions.md](../../references/human-decisions.md)):
a standard gate where one exists, which the harness presents through the host's best control and
falls back to chat on its own.

1. The working tree is clean, or its changes are explicitly handled.
2. Branch name: the repository's convention from `.harness/settings.json` →
   `branch_template` (for example `{category}/{key}-{slug}` → `feature/9123-avatar-do-estudante`). The
   key is the Story id, in the form the tracker's `ids.branch_key` accepts. The workflow policy hook
   rejects a new branch that does not follow the convention.
3. Base: `git.base_branch` from `.harness/settings.json` (for a stacked Feature, the Feature branch
   that `feature-implementation` names). Fetch it first and branch from the fresh remote ref.
4. Bind the Story to this checkout: `harness session start <story>` (`start-ticket` does this when
   it runs first).

## Pull request (after review)

Preconditions, all enforced by hooks:

- the review stage recorded a `ready` verdict for HEAD (`draft-reviewed-prs`);
- every applicable check passed for HEAD's tree (`draft-reviewed-prs`);
- an approval covers this branch (`approval-required`): say in plain words what will be pushed and opened, then ask the `publish-branch` gate with `--value branch=<branch>` (the harness skill's approval protocol). It covers pushing that branch and opening its draft pull request.

Then:

1. `git push -u origin <branch>`.
2. `scm_create_pull_request` with `sourceBranch`, `targetBranch: <base>`, **`isDraft: true`**
   (anything else is blocked), a title that follows the repository's convention, and a
   description: summary, how each acceptance criterion was met, the test evidence, and any manual
   checks. Azure Repos keeps the first 4000 characters.
3. `scm_link_work_item` with the pull request and the Story, then `tracker_link_development_artifact`
   so the Story shows the pull request too.
4. Read the pull request back with `scm_get_pull_request` and confirm the link.

On Azure Repos, use `scm_create_pull_request` through `workflow-integrations` and follow the same
draft and approval constraints.

Publishing the draft and voting are human steps (gate G4); the hook blocks both.

## Output

The branch name, the pull request URL and id, the linked Story, and the evidence summary included
in the description.
