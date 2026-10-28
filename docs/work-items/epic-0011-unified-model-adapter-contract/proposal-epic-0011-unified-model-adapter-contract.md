---
title: Unified model adapter contract
type: proposal
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-24
---

# Unified model adapter contract

Owner proposal, 2026-10-24, tracked as EPIC-0011 and not yet accepted. Finish the ongoing
Codex adapter release before planning a product-wide migration. Accepting or discarding it follows
Article 8a of the [constitution](../../../CONSTITUTION.md).

## Problem

Independent vendor-specific additions can drift in behavior and leave gaps between adapters.
The product needs one harness-owned definition of the behavior every model adapter must satisfy.
Existing shared policy, subagent and message contracts provide a starting point; this proposal
does not assert that a single complete adapter interface already governs the whole product.

## Proposed architecture

- Define a generic, versioned adapter interface owned by the harness. It describes the contract
  between the harness and any model vendor, including requests, responses, events, capabilities,
  errors and enforcement obligations.
- Every model adapter implements that interface by translating the harness's dialect into native
  vendor operations and translating authentic native results back into the shared contract.
- Encode new harness features and changed behavior in the shared interface and central message
  catalog first. Keep vendor identifiers, payloads and implementation details inside adapters.
- Refactor adapter implementations when the interface evolves. Required behavior must be
  implemented and verified before claiming compliance with that contract version.
- Make missing implementations and contract mismatches fail automated conformance checks.
  Explicit unsupported results expose a gap; they do not establish feature parity or satisfy a
  required capability. Runtime acceptance tests still verify native behavior and enforcement.
- Define parity by harness outcomes and guarantees. Different vendors may implement those
  outcomes through different native mechanisms without weakening the harness's operational laws.

## Interim direction

Apply this separation to new work now wherever practical: shared authorization and assignment
policy, one standard message catalog, and adapter-only native translation. Do not introduce
independent vendor protocols or quietly duplicate policy in adapters. Do not expand the current
release into a general adapter rewrite; record any remaining structural gaps for evaluation.

## Later evaluation

Inventory existing interfaces and declarations, choose the smallest unifying contract and its
versioning policy, and design conformance checks across all adapters. Establish how mandatory
capabilities, optional capabilities and migration compatibility are represented. Estimate the
migration before proposing backlog work. No new transport service or broker is implied.

Related: [current architecture](../../01-architecture/architecture.md),
[Codex adapter decision](../../01-architecture/decisions/ADR-0010-codex-host-adapter.md), and
[current release plan](../epic-0008-codex-host-adapter/implementation-plan-epic-0008-codex-host-adapter.md).
