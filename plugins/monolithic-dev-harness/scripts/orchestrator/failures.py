"""The orchestrator's failure taxonomy.

The retry loop has to decide whether running a capability again could produce a
different result. That decision used to be made by comparing the previous
error's ``str()`` to this one's, which conflates two unrelated failures that
happen to render the same sentence and is silently wrong the moment a message
is reworded.

The decision is made from types instead. A failure the orchestrator knows will
repeat says so by subclassing, and the loop pattern-matches on that. Anything
unclassified is assumed transient and keeps its retry budget, so an unforeseen
failure wastes work rather than aborting a run that might have succeeded.
"""

from __future__ import annotations

from dataclasses import dataclass


class SkillFailure(Exception):
    """Root of the failures the orchestrator classifies rather than inspects."""


class HandlerContractError(SkillFailure, TypeError):
    """A handler violated its protocol. Running the same code again cannot help."""


class InputContractError(SkillFailure, ValueError):
    """Arguments did not satisfy the declared input contract."""


class PolicyDenied(SkillFailure, ValueError):
    """A workflow policy refused the operation, and will refuse it identically."""


class SkillAssetMissing(SkillFailure, FileNotFoundError):
    """A capability asset is absent from disk; retrying will not create it."""


@dataclass(frozen=True)
class Fatal:
    """The code is wrong. Do not run it again."""


@dataclass(frozen=True)
class Deterministic:
    """The answer will not change within this call. Halt and surface it."""


@dataclass(frozen=True)
class Transient:
    """This may differ next time. Spend the retry budget."""


FailureKind = Fatal | Deterministic | Transient


def classify(error: BaseException) -> FailureKind:
    """Decide whether running the capability again could change the outcome."""
    match error:
        case HandlerContractError():
            return Fatal()
        case InputContractError() | PolicyDenied() | SkillAssetMissing():
            return Deterministic()
        case _:
            return Transient()
