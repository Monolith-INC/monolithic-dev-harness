# Fixture app candidate: support-ticket desk

Status: proposal for user review; not selected
Date: 2026-10-02

## Product

A small customer-support team uses a Flutter app to manage incoming customer issues. The product's purpose is to help agents receive, assign, discuss, and resolve support tickets. It is already in motion: the template should contain working flows, established data and UI patterns, tests, and documentation.

## What already works

- Create tickets with a requester, subject, description, and category.
- Assign tickets to an agent and set a priority.
- Move tickets through open, pending, resolved, and closed states.
- Add customer-visible replies and private internal notes.
- Search tickets and filter the queue by status, priority, and assignee.
- Persist tickets and their conversation history across app restarts.
- Cover ticket transitions and queue behavior with automated tests.

## Product-owner request for the trial

> “Agents need to merge duplicate tickets so they can handle the issue in one place without losing any of the customer's messages or the history of either ticket.”

This is a recognizable support-team request, but leaves real questions for technical discovery: which ticket remains primary, how messages and attachments are ordered, how references to the duplicate behave, what is recorded in the audit history, how concurrent updates are handled, whether a merge can be undone, and how the API and data store preserve consistency. The harness should inspect the codebase and report whether a new library is needed, rather than assume one.

## Why this is a useful trial fixture

The example starts from a functioning product with a defined purpose and multiple existing behaviors. The request is concrete enough to investigate, but not a prescribed solution. It exercises the default planning path the user described: inspect the real system, identify affected code and constraints, compare implementation choices, and prepare the supporting feature specification and implementation strategy before backlog creation or code changes.

The company and request are fictional test material, not evidence from a real support team. The template should describe them as a representative scenario, not claim customer research.
