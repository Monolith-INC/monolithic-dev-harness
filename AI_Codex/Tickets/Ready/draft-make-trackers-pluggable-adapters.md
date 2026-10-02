---
date: 2026-09-24
type: ticket
work_item_type: Feature
provider: local
language: en
tags: [ticket, feature, trackers, adapters]
---

# Make trackers pluggable adapters

## 🎯 What

As a team adopting the harness, we need to choose the tracker our backlog lives in, from the trackers the
harness ships or one we onboard ourselves, so that the harness works with our tracker instead of only with
Azure DevOps.

## 💡 Why

The harness owns the delivery workflow: backlog, spec, build, and verify. Today it is also tied to one tracker.
Bootstrap requires an Azure organization, the backlog skills call Azure's tools directly, and the approval hooks
recognize only Azure writes. A team on Linear, on a tracker of its own, or with no external tracker cannot adopt
the harness without rewriting it.

## 📋 Expected Behavior

```text
bootstrap
  -> lists the installed trackers (Azure DevOps, Linear, local) and "onboard a new tracker"
  -> the chosen tracker describes its shape: artifacts, hierarchy, states, id format, write operations
  -> backlog, spec, build, and verify run through that tracker's adapter
  -> hooks gate the chosen tracker's writes and protect its items
```

A tracker is an adapter, the same way Claude Code and Cursor are host adapters. Each tracker lives in its own
folder with its manifest, adapter, MCP connection, enrichment templates, instructions, and health check. The
harness workflow knows no tracker by name.

## ✅ Acceptance Criteria

- [ ] The harness ships three trackers: Azure DevOps, Linear, and a local tracker.
- [ ] Bootstrap asks which tracker to use and configures every stage from that one answer.
- [ ] The backlog skills take the artifact list, hierarchy, and templates from the chosen tracker.
- [ ] The approval and protected-items hooks work for every shipped tracker without naming any of them.
- [ ] A user can onboard a new tracker from its documentation, answering only what the documentation does not.
- [ ] An Azure DevOps repository bootstrapped before this Feature keeps working without changes.

## 🔧 Technical Notes

- Design: `AI_Codex/Specs/2026-09-24-trackers-are-adapters-design.md`. Decision: ADR-0009.
- Pattern to follow: `scripts/host_adapters/` and the example plugin's tracker choice at bootstrap.
- Existing seam to build on: `TrackerAdapter` in `scripts/integrations/adapters.py` and the gateway tools.

## 📊 Complexity

Sum of Stories: 44 points across 7 Stories.

## 📄 Original Description

"Right now it's tied to Azure and that's it, but we should make it more flexible so people could use different
trackers if they want. Trackers should be like features that you add. We could ship two or three, Azure for sure,
a local tracker, and perhaps a third option, and make it easy for the user to onboard a new tracker."

"When the user selects the tracker, the tracker will have in its folder its interface, its tools, its MCP. Our
backlog tools do not belong to any particular tracker. They belong to the harness. The trackers are just how
these things are going to be consolidated. We can use the same concept that we use for hosts."

"One thing that we're going to ask the user is: point us to the documentation for that tracker. We try to
identify which tracker this is and what its rules are. If we don't get answers, we go back to the user."
