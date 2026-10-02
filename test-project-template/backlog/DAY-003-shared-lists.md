# DAY-003: Share a task list across devices

**Kind:** Feature request
**Size:** Large
**State:** Draft; requires product and system decisions

## Product-owner request

“I want to open the same task list on my phone and computer, and let a family member help keep it current.”

## Investigation areas

- Decide how real accounts, list ownership, invitations, and access removal should work.
- Compare conflict handling when two people change the same task offline.
- Assess durable storage, synchronization, authorization, and recovery.
- The longer-term fixture may include TypeScript cloud functions with callable, HTTP request, and database-trigger handlers. Treat that as a candidate, not a prescribed design.
- Preserve the current local demo mode until a secure service design is approved.

## Acceptance checks after decisions

- Authorized members see the same current list on more than one device.
- Changes made while offline have a defined resolution when devices reconnect.
- A removed member can no longer read or change the list.
- Existing tasks and local-only behavior have a documented migration path.
