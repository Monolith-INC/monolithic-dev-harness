---
name: respond-pr-comments
description: Use only when the user explicitly instructs you to answer or act on specific pull request review comments, to post replies or implement the requested changes. Never acts on its own initiative.
---

# Respond to PR Comments

Submitting code for review is a delicate stage. Objections, recommendations, requests, and demands —
particularly from a team lead or tech lead — get analysed rigorously, and the response is delivered
with care.

## The rule that governs this skill

**This skill acts only under explicit user instruction, never automatically.**

That means:

- It does not decide which comments to accept. `triage-pr-comments` produces the analysis; the user
  decides.
- It does not post a reply the user has not approved.
- It does not implement a change the user has not asked for.
- It does not act on remaining comments after handling the ones it was asked to handle.

There will be back and forth across several rounds. Each round needs its own instruction. If the
instruction is ambiguous about which threads it covers or whether to post, **ask before acting**.

## Optional bounded iterative remediation

Use this mode only when the user explicitly requests **iterative remediation** and names the target
finding or review-comment identifiers. It is not the default response to accepted comments.

Before starting, confirm all of the following:

- The user explicitly requested iterative remediation, not a single response round.
- Every target has a named finding or root review-comment identifier and an approved action.
- The maximum iteration count is a positive integer. Use **3** when the user did not specify it.

Do not start when the instruction omits target identifiers or iterative-remediation intent; ask for
the missing information. Reject zero, negative, non-numeric, and unlimited maximums. Do not add a
hook, background process, scheduled continuation, or any other autonomous loop.

Keep cycle state in the active conversation by default. Persist it only after the user separately
approves the specific write and location; this approval does not authorize code changes, replies,
or any other action beyond the approved persistence.

For each iteration, record a checkpoint containing:

- iteration number and declared maximum;
- every target identifier;
- changed paths;
- focused verification commands and actual results;
- re-review result and targets still remaining.

Then apply only the approved changes for the named open targets, run focused verification, and
re-review the changed scope against each target. Treat a target as closed only with `VERIFIED`
closure evidence that the requested remedy is present and its concrete consequence is addressed.
If verification fails or is inconclusive, leave the target open and record why.

Stop immediately with success only when **every** named target has verified closure evidence. If the
maximum is reached with any target open, stop and report the remaining identifiers, their latest
evidence, and the completed iteration count. Do not claim completion or success. A later attempt
requires a new explicit user instruction; it does not continue autonomously.

## Procedure

### 1. Confirm the instruction

Establish exactly which threads are in scope and what is being asked for on each: post a reply,
change code, or both. Read back the list and the intended action before doing anything, unless the
user has already been that specific.

Read `.monolithic-code-review/sources.json` for `scm.provider`, `scm.capabilities`, and the repository
identity fields. You need the provider's root thread/comment identifier from
`triage-pr-comments`, or from the configured `list_review_threads` capability. If required
capabilities are unsupported or authentication fails, stop and name them; never fall back to a
different SCM. For GitHub, the thread listing commonly expands to:

```bash
gh api repos/<owner>/<repo>/pulls/<PR>/comments --paginate
```

### 2. Implement accepted changes

For each thread the user accepted:

- Make the change the comment asks for, and only that change. A review reply is not an invitation to
  refactor the surrounding code.
- Match the file's existing conventions. Where `.monolithic-code-review/sources.json` records a
  `knowledge.root`, `4-rules/coding-standards` is the addressed source for what this project
  mandates or prohibits — prefer it over inferring a convention from the surrounding lines, and
  follow the cost ladder rather than reading the store whole.
- Run the project's tests and report the actual result. Where the store records one,
  `3-mechanics/testing` names the actual command; use it instead of guessing a runner. If they fail,
  say so with the output rather than proceeding.
- Keep each thread's change separately identifiable, so a reviewer can map commits back to comments.

If implementing the comment as written would break something, do not silently implement a variation.
Stop, explain what breaks, and propose the alternative.

### 3. Post replies

Reply to the root comment through `reply_to_review_thread`. For GitHub, this commonly expands to:

```bash
gh api repos/<owner>/<repo>/pulls/<PR>/comments \
  -f body="$BODY" \
  -F in_reply_to=<thread_id>
```

For GitHub, `in_reply_to` must reference a pull **review** comment id, not an issue comment id. For a
general conversation comment, use the configured `post_summary_comment` capability instead.

Reply content by outcome:

- **Accepted and done** — state what changed and where, in one or two lines. Reference the commit.
  No thanks-for-catching preamble, no restating the reviewer's point back to them.
- **Declined** — give the reason and the evidence, once, plainly. Do not argue, do not apologise, and
  do not re-litigate a point already made in an earlier round. If the reviewer is factually
  incorrect, cite the documentation or code that shows it, and leave the conclusion to them.
- **Deferred** — say what is deferred, where it is tracked, and why it is not being done now.

Write for the reviewer, not for the record. Compact, specific, no padding.

### 4. Report back

Tell the user exactly what was posted and what was changed, with comment URLs and file paths. Name
any thread that was in scope but could not be handled, and why.

## Manual evaluation cases

- **Unable to start:** the user asks to “keep fixing review feedback” but supplies neither named
  targets nor an explicit iterative-remediation instruction. Ask for both; make no changes, posts,
  persistence writes, or cycle checkpoint.
- **Verified success:** targets `RC-18` and `RC-21` have approved actions and a maximum of 3. After
  iteration 2, focused tests pass and re-review supplies verified closure evidence for both. Record
  both checkpoints and report success with the two target identifiers and evidence.
- **Maximum exhaustion:** targets `RC-18` and `RC-21` have a maximum of 2. After iteration 2,
  `RC-18` is verified closed but `RC-21` still fails focused verification. Stop, report `RC-21` and
  its failure evidence as remaining, and do not claim success or continue without a new explicit
  instruction.

## Constraints

- **Never resolve, dismiss, or approve a thread.** Marking a conversation resolved is the reviewer's
  prerogative.
- Never post to a thread outside the instruction, even an obviously easy one.
- Never approve or request changes on the pull request.
- Do not implement changes beyond what the accepted comment asks for.
- Report test failures faithfully rather than working around them.
- If new comments arrive mid-task, report them and stop. They are a new round and need a new
  instruction.
- Iterative remediation requires named targets, explicit instruction, and a positive bounded
  maximum; unlimited and autonomous continuation are prohibited.
- Persisted iterative state needs separate user approval.

## Success criteria

- Every action traces to an explicit user instruction.
- Replies posted only to the threads named, with `in_reply_to` set to a review comment id.
- No thread resolved, dismissed, or approved.
- Code changes limited to what was accepted, with real test results reported.
- The user knows exactly what was posted, what changed, and what was left.
- Iterative success is reported only when every named target has `VERIFIED` closure evidence;
  maximum exhaustion reports remaining targets without a success claim.
