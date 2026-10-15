# Main-session-bubbled lower-tier run

Date: 2026-10-05
Status: local drafts approved by the user; no tracker publication or implementation

## Run path

The user confirmed the intended interaction: a lower-tier subagent sends its review gate to the main
session, and the main session shows the native choices and waits for the user's real answer. The
subagent was assigned GPT-6 Luna with low reasoning. It used the existing prepared test project and
its installed harness. The installed version was 0.5.2; candidate source 0.5.3 was not the package
under test. The subagent's tool context did not expose independent model or reasoning metadata.

The subagent investigated DAY-001, sent its proposal to the main session, and waited. The main
session presented the native Continue/Stop choice and relayed the user's exact answer. When the user
replied “break it in stories” to the first one-Story split, the main session passed that exact text
to the subagent. The subagent revised the split and waited for approval. The main session presented
the revised three-Story split; the user selected Continue. This confirms the app path can surface
subagent decisions through the main session and preserve the user's actual response.

The CUA result “no open windows” described what that subagent's computer-use surface could observe.
It did not mean the Codex app was unavailable. The earlier conclusion that the app-based route was
blocked was incorrect.

## Approved draft batch

The user approved these three Stories under Feature DAY-001:

1. **See active and completed task totals** — show both totals with correct zero/one/many wording;
   3 points.
2. **Update both task counts after status changes** — update both totals when a task changes between
   active and completed, including zero/one cases; 3 points; depends on Story 1.
3. **Keep task counts independent of search and status filters** — totals remain based on the full
   task list while visible rows change; 2 points; depends on Story 1.

The subagent initially wrote only two drafts and combined Story 3 with Story 1. The main session
caught the mismatch against the approved split and required correction. The final three local drafts
match the approved split, cover all four parent acceptance checks, and were re-read in full:

- `docs/planning/Tickets/Ready/draft-see-full-list-task-counts.md`
- `docs/planning/Tickets/Ready/draft-update-task-counts-after-status-changes.md`
- `docs/planning/Tickets/Ready/draft-keep-task-counts-independent-of-filters.md`

The user ended the live run after approving the drafts. Their contents are preserved in
[`approved local drafts`](2026-10-05-approved-local-drafts/), and the disposable project has been
removed.

All three passed the rule-based validator with 13 checks passed, no failures, and one expected
warning because they lack `provider_id` before publication. The hours plausibility check was skipped
because no hours estimate was supplied. No source change or tracker write occurred.

The main session showed the complete batch and received the exact response “Approve local drafts
only.” The subagent acknowledged that decision and stopped without publishing or implementing.

## Blocker and limits

The workflow checkpoint still records the earlier two-Story batch and stale artifact hashes. The
current `workflow checkpoint` command always appends a new point and moves the cursor; the subagent
stopped rather than advancing the workflow merely to update the record. The user approval is
captured in the main-session message and this report, not the stale workflow checkpoint. Fix this
checkpoint update path before relying on it for approval evidence.

The project settings selected the shipped local tracker, and setup created its local storage.
`harness tracker show local` reports onboarded trackers, so its “not onboarded” response did not
verify the selected shipped tracker through `tracker_describe`. This run did not verify provider
hierarchy, publish tracker items, or implement the change.

Reported direct content reads: 30 unique paths. The exact file list was not returned in the final
agent message. The lower-tier assignment was GPT-6 Luna/low, but independent execution metadata and
token usage were unavailable. Use this as app-session workflow evidence, not as independently
verified model-usage evidence.
