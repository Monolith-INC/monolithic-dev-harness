# Technical discovery

Use this local sequence for an existing feature request or named work item. It is ready with the
plugin and needs no project setup, generated files, dependency installation, or network access.

1. **Resolve the request.** Use the user's request as the starting point. Read an explicitly named
   project file directly. For a tracker item, retrieve it with `tracker_get_work_item` and read its
   parent with `tracker_list_children` when relevant. Search only if the given identifier cannot be
   retrieved. Do not ask the user to repeat a request or choose internal tools.
2. **Inspect only relevant code.** Locate the screen, state/provider, model, and tests named by the
   request. Read the files and nearby project documentation. Use the repository's existing checks
   and conventions. Search official language or library documentation only when the local code and
   docs do not settle an API question. Never install or download tools or files for discovery.
3. **Compare the smallest feasible approaches.** Keep current behavior that already satisfies the
   request. Name affected files and symbols, the selected change, meaningful alternatives, and any
   decisions the code cannot settle. Do not implement code at this stage.
4. **Prepare the plan.** Include the user-visible outcome, evidence from the current code, affected
   files, implementation outline, acceptance checks, and open questions. Do not invent a product
   answer to fill a gap.
5. **Review with the user.** Show the plan itself and ask one short clickable question: **Approve and
   continue**, **Revise**, or **Stop**. Use the native question control. Its built-in **Other** field
   handles an unlisted response; never add an Other option. Approval continues to backlog drafting
   only and does not publish work items.
6. **Save progress locally.** Record the plan and its digest in the harness workflow checkpoint.
   Planning and checkpoints do not need Git, a first commit, a branch, or an implementation session.
   If Git is unavailable or has no commit, omit revision claims and continue. Session and commit
   checks apply only when code implementation starts in a repository with a committed Git baseline.

If an optional tracker or documentation source is unavailable, state that briefly and continue with
the material already provided. Do not ask the user to repair or install harness infrastructure.
