# Harness workflow storyboard

The harness owns the sequence and the meaning of each decision. The host shows decisions as clickable
question controls. In the Codex editor or command line, use `request_user_input` when available; in
the Codex desktop app, use `request_user_input_async` when available. Their default **Other** field handles
anything outside the listed choices, so never add an `Other` option yourself. A first request resumes
after setup instead of making the user repeat it.

| Stage | Entry | Work before stopping | Review point | Exit |
| --- | --- | --- | --- | --- |
| Setup | Any harness request | Inspect current project and workflow state; prepare the bundled local tracker in the background if its folders are missing; confirm this project's language; ask only for missing project choices | Show user-facing settings and get approval by click | Check once, then ask what to do next with clickable routes and the default Other field |
| Discover | Named existing task or request for a technical plan | Read the named item directly. Use tracker tools for tracker items; read an explicitly linked project file directly. Investigate fit and alternatives, then prepare a reviewed implementation plan. | Show the technical plan and review notes | Accepted plan enters backlog; no repeated starting-point question |
| Ideate | User selects idea exploration or submits a new idea | Use `plan-initiative` and only its needed routes: brainstorm, pressure-test, research, brief, requirements, UX, architecture, product spec | Show the product contract and critique | Accepted contract enters backlog; ideation is offered after setup |
| Backlog | Accepted product contract or sufficiently defined work item | Draft, enrich, decompose, create Story Tasks, and validate locally; check tracker readiness before publication | Show the complete Feature, Story, and Task batch and its destination; seek one approval for the specified external writes | Publish and read back the approved batch |
| Technical plan | A ready Story and its Tasks | Start the Story, draft and validate its Story-local technical spec | Present the exact spec revision, then seek the technical decision | Approved spec is pinned to its revision |
| Build | Approved spec and active implementation session | Work through atomic Tasks and checks | Stop only for a material decision or protected write | Verified implementation and evidence |
| Verify | Checked implementation | Review requirements, quality, and delivery evidence | Present verdict and any required staging or pull-request decision | Draft pull request or a clearly blocked result, then mark the workflow complete |

An agent continues through reversible local work within a stage. It stops for missing information that cannot be inferred, a material product choice, a review of a complete contract, or a write that policy protects. A `proceed` prompt for routine drafting is not a gate. Story breakdown precedes changing the Story to In Progress.

## After setup

When setup completes, use the available native question control with up to three routes that fit the request:

- Continue the named task or request.
- Prepare or organize work items.
- Explore an idea.

When no request was supplied, label the first route **Start feature work**. Do not add a literal
`Other` choice; the Codex control already provides a free-text field. Route the click or Other-field
answer and continue without asking the user to invoke the harness again.

## Ready reference: information and tools

Use this map instead of searching plugin files to rediscover workflow capabilities:

| Need | Source |
| --- | --- |
| Project language confirmation, tracker choices, missing settings | `harness bootstrap --inspect` |
| Current commit, branch, saved workflow, and local tracker readiness | `harness bootstrap --inspect` |
| Prepare missing bundled local tracker folders | `harness bootstrap --prepare-local-tracker` |
| Setup health | `harness doctor` |
| Tracker states, item kinds, hierarchy, required capabilities | `tracker_describe` |
| Named tracker item | `tracker_get_work_item` |
| Find an item when its identifier is uncertain | `tracker_search_work_items` |
| Parent and child context | `tracker_list_children` |
| Existing requirements/spec/review artifacts | `tracker_list_artifacts` |
| Active or saved workflow state | `harness workflow status` / `harness workflow list` |
| Settings and artifact folder for backlog work | `bin/agile-backlog-toolkit config --show` |
| Technical discovery | `skills/harness/references/technical-discovery.md` |
| Ideation and product shaping | `plan-initiative` and its listed optional routes |

For a named project file, open that file directly. Use the host's tool catalog and these known
capabilities; do not search source code to find tool names or infer settings already reported by a
command. The bundled local tracker needs no provider onboarding. Its records are under
`.harness/tracker/`; the configured artifact folder holds plans and drafts. A project file can be
planned directly even when it is not yet a tracker record.

## Workflow actions

- **Back:** return to the previous reversible decision or a chosen saved review point. Show which later drafts and approvals become stale; rebuild only those dependents. Never undo an external write silently.
- **Pause:** save the stage, review points, pending decision, artifact digests, completed external-write identities, and the next safe action. Stop work.
- **Resume:** offer the latest point or earlier saved points. Recheck files, repository state, tracker state, and approvals. A checkpoint is not permission to repeat a write.
- **Cancel:** end the active workflow without implying automatic continuation. Preserve completed work and the audit record. Starting a later workflow archives the cancelled record first.
- **Complete:** mark the requested outcome finished. Starting a later workflow archives the completed record first.

These actions are semantic choices. Show them as clickable host controls; never ask the user to type
an option or command. This also applies to permission for a branch or commit. If controls are
unavailable, pause before the decision. `harness session
pause/resume` still controls only an implementation checkout.

`harness workflow list` shows saved review points and the current point. `harness workflow status` shows the full saved record. Resuming can choose any listed point.

## Review and approval

An artifact decision identifies the exact path and content digest. Present the material needed to decide through the best available host surface: interactive canvas/document/editor, native rendered preview, an actually opened file with a structured summary, then faithful inline review. A link or summary alone is insufficient. The user sees the material before the approval question. A changed digest invalidates the decision.

An external tracker or source-control write still needs the existing approval hook. State precisely
what will be written and ask for approval through a clickable host control. If the control cannot
open an approval window, do not write; explain that approval is waiting for a host that supports
clickable controls. A routing choice, Back, Pause, Resume, Cancel, or Complete never opens a write
window.

## Language and setup

Ask for English or Português (Brasil) once for each project, even when another project has a saved
user-level preference. Store the preference outside the repository and a project confirmation under
`.harness/state/`; record the effective language in the workflow checkpoint. Repository settings
hold tracker and project choices. Default source control to local and do not expose provider setup
as a routine choice. Preserve unrelated user-owned settings. Do not silently select the bundled
Azure example. Check the selected tracker's required values and capabilities before any publication
batch. Check current commit state afresh on each run; a saved checkpoint can describe an earlier
state. Git metadata, an initial commit, branches, and hosted code are optional for setup and planning.
