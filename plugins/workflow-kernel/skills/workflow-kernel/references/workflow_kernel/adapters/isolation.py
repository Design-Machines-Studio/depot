"""Capability-only isolation selection with explicit degradation receipts."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import (
    HostCapabilities, HostCapability, IsolationDecision, IsolationMode,
    IsolationRequirements, invalid_policy,
)
from ..policies import load_policy


_MODE_CAPABILITY = {
    IsolationMode.REMOTE_SANDBOX: HostCapability.REMOTE_SANDBOX,
    IsolationMode.CONTAINER: HostCapability.CONTAINER,
    IsolationMode.WORKTREE: HostCapability.WORKTREE,
    IsolationMode.SEQUENTIAL_BRANCH: HostCapability.SEQUENTIAL_BRANCH,
}


class IsolationSelector:
    def __init__(self, path: Optional[Path] = None):
        policy = load_policy(path)
        self._order = policy.isolation_order
        self._forbidden = policy.forbidden_downgrades

    def select(
        self,
        requirements: IsolationRequirements,
        capabilities: HostCapabilities,
    ) -> IsolationDecision:
        if type(requirements) is not IsolationRequirements:
            raise invalid_policy("invalid_isolation_requirements")
        if type(capabilities) is not HostCapabilities:
            raise invalid_policy("invalid_host_capabilities")
        preferred = requirements.preferred
        if capabilities.supports(_MODE_CAPABILITY[preferred]):
            return IsolationDecision(preferred, False, "preferred_isolation_available")
        if not requirements.allow_degradation:
            return IsolationDecision(
                None, True, "isolation_degradation_disallowed", preferred, None,
            )
        start = self._order.index(preferred) + 1
        for candidate in self._order[start:]:
            if not capabilities.supports(_MODE_CAPABILITY[candidate]):
                continue
            if (preferred, candidate) in self._forbidden:
                return IsolationDecision(
                    None, True, "isolation_downgrade_forbidden", preferred, candidate,
                )
            return IsolationDecision(
                candidate, False, "preferred_isolation_unavailable", preferred, candidate,
            )
        return IsolationDecision(
            None, True, "no_isolation_capability", preferred, None,
        )
