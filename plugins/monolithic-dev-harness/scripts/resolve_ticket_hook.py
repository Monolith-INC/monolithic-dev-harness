"""Resolve-ticket completion hook.

Returns a structured directive when specs or the resolution report are missing.
"""

from __future__ import annotations

import os
import sys
from typing import Any

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from resolution_runtime import ResolutionPlan


def on_resolve_ticket(plan: ResolutionPlan) -> dict[str, Any] | None:
    if not plan.spec_artifacts:
        return {
            "hook": "resolve-ticket-specs",
            "action": "invoke-write-spec",
            "ticket_id": plan.ticket_id,
            "message": (
                f"Ticket {plan.ticket_id} has no specification artifacts. "
                "Run /write-spec before /resolve-ticket."
            ),
        }

    if plan.resolution_required:
        return {
            "hook": "resolve-ticket-report",
            "action": "invoke-resolve-report",
            "ticket_id": plan.ticket_id,
            "artifact_kind": "resolution_report",
            "spec_artifacts": list(plan.spec_artifacts),
            "source_hints": plan.source_hints,
            "message": (
                f"Ticket {plan.ticket_id} needs a resolution report artifact "
                "before completion. Draft via Actor-Critic, then publish when the Critic is clean."
            ),
        }

    return None
