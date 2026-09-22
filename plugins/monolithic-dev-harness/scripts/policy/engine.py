"""Small provider-neutral policy primitives used by host hook adapters.

Provider state validation lives in ``hook_runtime`` and the integration adapters;
this module intentionally contains no provider-specific state or local persistence policy.
"""

from .events import CanonicalToolEvent, PolicyDecision


def evaluate(event: CanonicalToolEvent) -> PolicyDecision:
    """Allow by default; host-specific enforcement is evaluated at the boundary."""
    return PolicyDecision.allow()
