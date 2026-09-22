from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None

    @classmethod
    def allow(cls) -> PolicyDecision:
        return cls(allowed=True)

    @classmethod
    def deny(cls, reason: str) -> PolicyDecision:
        return cls(allowed=False, reason=reason)

    def is_denied(self) -> bool:
        return not self.allowed


@dataclass(frozen=True)
class CanonicalToolEvent:
    client: str
    tool_name: str
    command: str | None = None
    file_path: str | None = None
    workspace_root: str = ""
    branch: str = ""
