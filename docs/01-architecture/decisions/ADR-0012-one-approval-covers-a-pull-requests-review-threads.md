---
title: ADR-0012 One approval covers a pull request's review threads
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-22
---

# ADR-0012: One approval covers a pull request's review threads

## Status

Accepted

## Context

Working through a pull request's review comments takes four kinds of write: replying to a thread,
opening a thread on a line, editing a comment's text, and setting a thread's status. The `reply-pr`
gate's question names only replies. Asking a separate question for each kind of write would stop the
agent several times in one review pass.

## Decision

The `reply-pr` approval, tied to one pull request (`pr:{pr}`), covers all four review-thread writes
on that pull request: `scm_reply_to_thread`, `scm_create_review_thread`,
`scm_update_thread_comment` and `scm_set_thread_status`. Operating review threads needs all of them,
so the harness asks once.

The owner decided this on 2026-10-22: stopping for every capability makes a poor experience, and the
reach of this approval is not a security risk. It is limited to the comment threads of one pull
request; it cannot change code, branches, merges or any other pull request.

## Options Considered

- **One question per kind of write:** each write is named, but one review pass stops the agent up to
  four times for the same pull request.
- **One approval per pull request (chosen):** one stop per review pass, bound to that pull request.

## Consequences

### Positive

- A review pass asks once, and the write check still refuses every other pull request.

### Trade-offs

- The question's text says "replies"; the approval also covers opening, editing and resolving threads
  on that pull request.

## Validation

`tests/harness/test_bound_approvals.py::test_a_reply_approval_covers_review_thread_writes_on_that_pull_request_only`.

## References

- [ADR-0003](ADR-0003-human-only-approval-windows.md)
- [ADR-0011](ADR-0011-standard-questions-catalog.md)
