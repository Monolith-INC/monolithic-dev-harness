"""Every gateway tool is classed: a read the rules let through, or a write that needs an approval.

A tool on neither list would run without the approval its write needs."""

from harness.rules import GATEWAY_WRITES
from integrations.gateway import READ_ONLY_OPERATIONS, TOOLS_BY_NAME

# Reads the rules let through that are not on the gateway's while-a-question-waits list.
OTHER_READS = frozenset({"workflow_resume_tracker"})


def test_every_gateway_tool_is_a_read_or_a_write() -> None:
    assert (
        set(TOOLS_BY_NAME) - GATEWAY_WRITES - READ_ONLY_OPERATIONS - OTHER_READS
        == set()
    )


def test_no_tool_is_both_a_read_and_a_write() -> None:
    assert set() == GATEWAY_WRITES & READ_ONLY_OPERATIONS


def test_changing_or_removing_a_published_document_needs_an_approval() -> None:
    assert {"tracker_revise_artifact", "tracker_remove_artifact"} <= GATEWAY_WRITES
