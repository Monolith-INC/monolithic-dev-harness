---
name: branch-and-pr
description: Create the Story branch and, after review passes, push it and open a draft pull request in Azure Repos linked to the Story. Use at the start of implement-story (branch) and at the end of the review stage (push and PR).
---

# Branch and pull request (Azure Repos)

Adapted from cursor-team-kit's `new-branch-and-pr` (MIT), rewritten for Azure Repos through the
`azure-devops` MCP server (see the `azure-devops` skill and its `references/tool-map.md`). No `gh`.

## Branch

1. The working tree is clean, or its changes are explicitly handled.
2. Branch name: the repository's convention from `.codex-workflows/integrations.json` →
   `branchTemplate` (for example `{category}/{key}-{slug}` → `feature/9123-avatar-do-estudante`). The
   key is the Story id. The workflow policy hook rejects a branch without exactly one work-item key.
3. Base: `git.base_branch` from `.harness/policy.json` (for a stacked Feature, the Feature branch
   that `feature-implementation` names). Fetch it first and branch from the fresh remote ref.

## Pull request (after review)

Preconditions, all enforced by hooks:

- the review stage recorded a `ready` verdict for HEAD (`draft-reviewed-prs`);
- every applicable check passed for HEAD's tree (`draft-reviewed-prs`);
- an approval window is open (`approval-required`): show the user the push + PR batch and ask for `approve HB-…`.

Then:

1. `git push -u origin <branch>`.
2. `repo_pull_request_write[create]` with `repositoryId` and `project` from `.harness/policy.json`,
   `sourceRefName: refs/heads/<branch>`, `targetRefName: refs/heads/<base>`, **`isDraft: true`**
   (anything else is blocked), `workItems: "<storyId>"`, a title that follows the repository's
   convention, and a description of at most 4000 characters: summary, how each acceptance
   criterion was met, the test evidence, and any manual checks.
3. Read the pull request back and confirm the Story link. If the link is missing, add it with
   `wit_work_item_link_write[link_to_pull_request]`.

Publishing the draft and voting are human steps (gate G4); the hook blocks both.

## Output

The branch name, the pull request URL and id, the linked Story, and the evidence summary included
in the description.
