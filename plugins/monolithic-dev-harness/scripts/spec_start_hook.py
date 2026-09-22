"""Start-ticket spec generation hook.

Invoked by the start-ticket orchestrator handler when a ticket is activated.
Returns a structured directive for the agent to run write-spec when specs are missing.
"""

from __future__ import annotations

import os
import sys
from typing import Any

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from spec_runtime import SpecPlan


def on_start_ticket(spec_plan: SpecPlan) -> dict[str, Any] | None:
    if not spec_plan.generation_required:
        return None
    return {
        "hook": "start-ticket-spec",
        "action": "invoke-write-spec",
        "ticket_id": spec_plan.ticket_id,
        "required_kinds": list(spec_plan.required_kinds),
        "missing_kinds": list(spec_plan.missing_kinds),
        "source_hints": spec_plan.source_hints,
        "message": (
            f"Ticket {spec_plan.ticket_id} has incomplete spec coverage. "
            f"Generate: {', '.join(spec_plan.missing_kinds)} via /write-spec before coding."
        ),
    }
