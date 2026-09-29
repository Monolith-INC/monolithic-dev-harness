---
name: adopt-existing-implementation
description: Safely adopt code that already exists before a Story implementation session, mapping the real diff to the approved plan without fabricating TDD history or manipulating the index into fictional commits.
---

# Adopt existing implementation

Use this route when code was written before `implement-story` began, is on the wrong base, or spans
several planned Tasks. It converts inherited work into an auditable starting point; it does not
pretend the work was produced Task by Task.

## 1. Read-only assessment

1. Run
   `harness adoption assess <Story> --base-ref <intended base>`. It reads the Story and Tasks through
   the configured tracker, inventories branch ancestry, commits, staged/unstaged/untracked paths,
   artifacts, and exact-tree check evidence, then persists an immutable `HA-…` assessment.
2. Present the complete assessment. The deterministic classifications are `completed`,
   `incomplete`, `changed`, and `unverified`; a commit alone never makes a Task completed,
   and HEAD check evidence counts only when nothing uncommitted or untracked is being carried.
3. Run
   `harness adoption plan <HA-id> --branch <Story branch> --destination <separate worktree path>`.
   The branch must follow the settings' branch convention for this Story, so a session can start on
   it. Present the complete returned plan and ask one chat question containing its `HA-…` id with
   **Approve adoption** and **Not now** buttons. Wait for the click before materialization.

## 2. Safe materialization

1. Run `harness adoption materialize <HA-id>`. It refuses an unapproved or changed plan/source/base,
   creates the separate worktree and correctly based Story branch, transfers the assessed working
   delta from its real merge base, and verifies the pinned transfer digest before staging it. Changes
   that exist only on the Feature base remain intact. An overlap that cannot apply cleanly fails and
   removes the worktree and branch it created, so the plan can be retried once the conflict is
   resolved; a repeat run after success returns the recorded result. For a Feature workflow, the
   assessed base is the Feature branch.
2. The command leaves the inherited implementation staged and uncommitted. Work in the recovery
   worktree from here: run `harness session start <Story>` there (add
   `--workflow feature-implementation --base-ref <Feature branch>` for a Feature Story). The local
   tracker's records are shared by every worktree of the clone. Inspect the staged diff and run
   current-tree checks before creating the explicit adoption commit. Never use direct index
   plumbing, temporary half-versions of files, or hook bypasses.
3. Prefer one clearly labelled adoption commit when the existing diff cannot be separated without
   inventing history. Split commits only when the original commits or independent patches already
   provide truthful, verifiable boundaries.
4. Record inherited tests as inherited. Run them now and report their result; never claim they failed
   first unless evidence from the original work proves that.

## 3. Reconcile and finish

1. Implement only the missing spec/Task work through the normal `implement-story` Task loop.
2. Run checks against the exact committed tree. For staged guarded checks, the working files must
   exactly match the index.
3. Transition each Task according to the mapped evidence: done only when its acceptance and checks
   are satisfied; leave partial or unexplained Tasks open.
4. Report the recovery source, adoption commit(s), mapping, checks, Task transitions, and deviations.

`harness adoption status <HA-id>` shows the immutable assessment, bound plan, approval, and
materialization record at any time.
