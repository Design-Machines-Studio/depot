"""Pure, authority-free promotion evidence evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple


class PromotionState(str, Enum):
    SHADOW = "shadow"
    ENFORCE_AVAILABLE = "enforce_available"
    NATIVE_AVAILABLE = "native_available"
    NATIVE_DEFAULT = "native_default"


class EvidenceOrigin(str, Enum):
    FIXTURE = "fixture"
    REAL_RUN = "real_run"


@dataclass(frozen=True)
class PromotionEvidence:
    criterion: str
    satisfied: bool
    origin: EvidenceOrigin

    def __post_init__(self) -> None:
        if type(self.criterion) is not str or not self.criterion:
            raise ValueError("invalid promotion criterion")
        if type(self.satisfied) is not bool or type(self.origin) is not EvidenceOrigin:
            raise ValueError("invalid promotion evidence")


@dataclass(frozen=True)
class PromotionDecision:
    current_state: PromotionState
    target_state: PromotionState
    allowed: bool
    reason_codes: Tuple[str, ...]
    missing_evidence: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "current_state": self.current_state.value,
            "target_state": self.target_state.value,
            "allowed": self.allowed,
            "reason_codes": list(self.reason_codes),
            "missing_evidence": list(self.missing_evidence),
        }


ENFORCE_CRITERIA = (
    "zero_unexplained_receipt_gaps",
    "illegal_transition_scenarios_passed",
    "terminal_cleanup_scenarios_passed",
    "host_fixture_claude_passed",
    "host_fixture_codex_passed",
    "host_fixture_generic_passed",
    "persona_completeness_scenarios_passed",
    "browser_recovery_scenarios_passed",
    "provider_security_boundaries_unchanged",
)

NATIVE_CRITERIA = ENFORCE_CRITERIA + (
    "injected_interruption_reconstructs_state",
    "builder_resume_evidence",
    "builder_non_resume_evidence",
    "git_cleanup_success",
    "git_cleanup_failure",
    "git_cleanup_blocking",
    "docker_cleanup_success",
    "docker_cleanup_failure",
    "docker_cleanup_blocking",
)


# Canonical host IDs (shadow.CANONICAL_HOSTS drift-guarded by
# tests/test_shadow_parity.py): real-run promotion evidence is keyed by the
# canonical `claude-code` host ID, never the legacy `claude` spelling.
SUPPORTED_PROMOTION_HOSTS = ("claude-code", "codex", "generic")


def _state(value: object) -> PromotionState:
    if type(value) is PromotionState:
        return value
    if type(value) is not str:
        raise ValueError("invalid promotion state")
    try:
        return PromotionState(value)
    except ValueError:
        raise ValueError("invalid promotion state") from None


def _evidence(value: Iterable[PromotionEvidence]) -> tuple[PromotionEvidence, ...]:
    try:
        values = tuple(value)
    except (TypeError, RecursionError):
        raise ValueError("invalid promotion evidence") from None
    seen = {}
    for item in values:
        if type(item) is not PromotionEvidence:
            raise ValueError("invalid promotion evidence")
        key = (item.criterion, item.origin)
        prior = seen.get(key)
        if prior is not None and prior != item.satisfied:
            raise ValueError("conflicting promotion evidence")
        seen[key] = item.satisfied
    return values


def evaluate_promotion(
    current_state: object,
    target_state: object,
    evidence: Iterable[PromotionEvidence],
    *,
    supported_hosts: Iterable[str] = SUPPORTED_PROMOTION_HOSTS,
) -> PromotionDecision:
    """Evaluate one adjacent promotion without enabling workflow authority."""
    current = _state(current_state)
    target = _state(target_state)
    values = _evidence(evidence)

    if target is PromotionState.NATIVE_DEFAULT:
        return PromotionDecision(
            current, target, False,
            ("separate_human_approval_required",),
            ("separate_human_approval",),
        )

    allowed_transition = {
        PromotionState.SHADOW: PromotionState.ENFORCE_AVAILABLE,
        PromotionState.ENFORCE_AVAILABLE: PromotionState.NATIVE_AVAILABLE,
    }.get(current)
    if allowed_transition is not target:
        return PromotionDecision(
            current, target, False, ("invalid_promotion_transition",), (),
        )

    criteria = ENFORCE_CRITERIA
    real_run_criteria: tuple[str, ...] = ()
    if target is PromotionState.NATIVE_AVAILABLE:
        try:
            hosts = tuple(supported_hosts)
        except (TypeError, RecursionError):
            raise ValueError("invalid supported hosts") from None
        if (not hosts or any(type(host) is not str or not host for host in hosts)
                or len(hosts) != len(set(hosts))):
            raise ValueError("invalid supported hosts")
        criteria = NATIVE_CRITERIA
        real_run_criteria = tuple(f"real_shadow_run:{host}" for host in hosts)

    satisfied = {item.criterion for item in values if item.satisfied}
    real_satisfied = {
        item.criterion for item in values
        if item.satisfied and item.origin is EvidenceOrigin.REAL_RUN
    }
    missing = tuple(name for name in criteria if name not in satisfied)
    missing += tuple(name for name in real_run_criteria if name not in real_satisfied)
    if missing:
        return PromotionDecision(
            current, target, False, ("promotion_evidence_missing",), missing,
        )
    return PromotionDecision(
        current, target, True, ("promotion_allowed",), (),
    )


__all__ = [
    "EvidenceOrigin", "PromotionDecision", "PromotionEvidence",
    "PromotionState", "ENFORCE_CRITERIA", "NATIVE_CRITERIA",
    "SUPPORTED_PROMOTION_HOSTS", "evaluate_promotion",
]
