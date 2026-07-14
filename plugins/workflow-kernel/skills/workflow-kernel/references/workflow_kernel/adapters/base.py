"""Host-neutral workflow policy and adapter value types."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional, Protocol, Tuple

from ..schema import ErrorDetailKey, ErrorMessage, InvalidSchemaError


_HOST_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def invalid_policy(reason_code: str) -> InvalidSchemaError:
    return InvalidSchemaError(
        ErrorMessage.OPERATION_FAILED,
        {ErrorDetailKey.REASON_CODE.value: reason_code},
    )


class WorkflowClass(str, Enum):
    CHORE = "chore"
    BUG = "bug"
    FEATURE = "feature"
    HOTFIX = "hotfix"
    SECURITY = "security"
    INVESTIGATION = "investigation"
    MIGRATION = "migration"


class IsolationMode(str, Enum):
    REMOTE_SANDBOX = "remote_sandbox"
    CONTAINER = "container"
    WORKTREE = "worktree"
    SEQUENTIAL_BRANCH = "sequential_branch"


class FailureReason(str, Enum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    DETERMINISTIC_VALIDATION_FAILURE = "deterministic_validation_failure"
    REVIEWER_FINDING = "reviewer_finding"
    BROWSER_RECOVERY = "browser_recovery"
    CLEANUP = "cleanup"
    INFRASTRUCTURE = "infrastructure"


class HostCapability(str, Enum):
    NATIVE_DISPATCH = "native_dispatch"
    COMPANION_DISPATCH = "companion_dispatch"
    WRAPPER_DISPATCH = "wrapper_dispatch"
    OPENROUTER_EXEC = "openrouter_exec"
    SESSION_RESUME = "session_resume"
    REMOTE_SANDBOX = "remote_sandbox"
    CONTAINER = "container"
    WORKTREE = "worktree"
    SEQUENTIAL_BRANCH = "sequential_branch"


@dataclass(frozen=True)
class WorkflowContext:
    changed_paths: Tuple[str, ...] = ()
    requested_executor: Optional[str] = None
    risk: str = "low"
    evidence: Tuple[str, ...] = ()
    human_approved: bool = False
    investigation_promotion: bool = False
    promotion_approved: bool = False
    economics_preference: Optional[str] = None

    def __post_init__(self) -> None:
        for field_name in ("changed_paths", "evidence"):
            values = getattr(self, field_name)
            if not isinstance(values, (list, tuple)) or any(
                type(value) is not str or not value for value in values
            ):
                raise invalid_policy("invalid_workflow_context")
            object.__setattr__(self, field_name, tuple(values))
        if self.requested_executor not in (None, "claude", "codex", "openrouter"):
            raise invalid_policy("unknown_executor")
        if self.risk not in ("low", "medium", "high", "critical"):
            raise invalid_policy("unknown_risk_level")
        if type(self.human_approved) is not bool or type(self.promotion_approved) is not bool:
            raise invalid_policy("invalid_workflow_context")
        if type(self.investigation_promotion) is not bool:
            raise invalid_policy("invalid_workflow_context")


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason_code: str
    missing_evidence: Tuple[str, ...] = ()
    human_required: bool = False


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    dependencies: Tuple[str, ...] = ()
    gate_kind: Optional[str] = None
    required_evidence: Tuple[str, ...] = ()
    executor: Optional[str] = None
    routing_reason: Optional[str] = None
    gate_decision: GateDecision = field(
        default_factory=lambda: GateDecision(True, "gate_not_required")
    )

    def __post_init__(self) -> None:
        if type(self.node_id) is not str or not self.node_id:
            raise invalid_policy("missing_node_id")
        for name in ("dependencies", "required_evidence"):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)) or any(
                type(value) is not str or not value for value in values
            ):
                raise invalid_policy("invalid_node_spec")
            values = tuple(values)
            if len(values) != len(set(values)):
                raise invalid_policy("duplicate_node_value")
            object.__setattr__(self, name, values)


@dataclass(frozen=True)
class AttemptLedger:
    counts: Mapping[FailureReason, int] = field(default_factory=dict)
    signatures: Mapping[FailureReason, Tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        safe_counts = {}
        safe_signatures = {}
        try:
            for raw_reason, count in self.counts.items():
                reason = raw_reason if type(raw_reason) is FailureReason else FailureReason(raw_reason)
                if type(count) is not int or count < 0:
                    raise ValueError
                safe_counts[reason] = count
            for raw_reason, values in self.signatures.items():
                reason = raw_reason if type(raw_reason) is FailureReason else FailureReason(raw_reason)
                if not isinstance(values, (list, tuple)) or any(
                    type(value) is not str or not value for value in values
                ):
                    raise ValueError
                safe_signatures[reason] = tuple(values)
        except (TypeError, ValueError):
            raise invalid_policy("invalid_attempt_ledger") from None
        object.__setattr__(self, "counts", MappingProxyType(safe_counts))
        object.__setattr__(self, "signatures", MappingProxyType(safe_signatures))

    def count(self, reason: FailureReason) -> int:
        return self.counts.get(reason, 0)

    def history(self, reason: FailureReason) -> Tuple[str, ...]:
        return self.signatures.get(reason, ())


@dataclass(frozen=True)
class RetryDecision:
    allowed: bool
    reason_code: str
    budget: int
    attempt_count: int
    prior_signature: Optional[str] = None


@dataclass(frozen=True)
class HostCapabilities:
    host_name: str
    capabilities: frozenset[HostCapability]
    transition_model_version: int = 1
    evidence_model_version: int = 1

    def __post_init__(self) -> None:
        if type(self.host_name) is not str or _HOST_NAME.fullmatch(self.host_name) is None:
            raise invalid_policy("invalid_host_name")
        try:
            values = frozenset(
                value if type(value) is HostCapability else HostCapability(value)
                for value in self.capabilities
            )
        except (TypeError, ValueError):
            raise invalid_policy("unknown_capability_name") from None
        if type(self.transition_model_version) is not int or self.transition_model_version != 1:
            raise invalid_policy("unsupported_transition_model_version")
        if type(self.evidence_model_version) is not int or self.evidence_model_version != 1:
            raise invalid_policy("unsupported_evidence_model_version")
        object.__setattr__(self, "capabilities", values)

    def supports(self, capability: HostCapability) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True)
class IsolationRequirements:
    preferred: IsolationMode
    allow_degradation: bool = True

    def __post_init__(self) -> None:
        try:
            preferred = (
                self.preferred if type(self.preferred) is IsolationMode
                else IsolationMode(self.preferred)
            )
        except (TypeError, ValueError):
            raise invalid_policy("unknown_isolation_mode") from None
        if type(self.allow_degradation) is not bool:
            raise invalid_policy("invalid_isolation_requirements")
        object.__setattr__(self, "preferred", preferred)


@dataclass(frozen=True)
class IsolationDecision:
    selected: Optional[IsolationMode]
    blocked: bool
    reason_code: str
    degraded_from: Optional[IsolationMode] = None
    degraded_to: Optional[IsolationMode] = None


@dataclass(frozen=True, repr=False)
class SessionHandle:
    host_name: str
    opaque_handle: str
    created_at: str
    resume_capable: bool

    def __post_init__(self) -> None:
        if (
            type(self.host_name) is not str
            or _HOST_NAME.fullmatch(self.host_name) is None
            or type(self.opaque_handle) is not str
            or not self.opaque_handle
            or type(self.created_at) is not str
            or not self.created_at
            or type(self.resume_capable) is not bool
        ):
            raise invalid_policy("invalid_session_handle")
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError:
            raise invalid_policy("invalid_session_handle") from None
        if created.tzinfo is None:
            raise invalid_policy("invalid_session_handle")

    def __repr__(self) -> str:
        return (
            "SessionHandle(host_name={!r}, opaque_handle='[REDACTED]', "
            "created_at={!r}, resume_capable={!r})"
        ).format(self.host_name, self.created_at, self.resume_capable)

    def to_dict(self) -> dict:
        digest = hashlib.sha256(self.opaque_handle.encode("utf-8")).hexdigest()
        return {
            "host_name": self.host_name,
            "opaque_digest": "sha256:" + digest,
            "created_at": self.created_at,
            "resume_capable": self.resume_capable,
        }


@dataclass(frozen=True)
class ValidationFeedback:
    node_id: str
    reason_code: str
    evidence: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.node_id) is not str or not self.node_id:
            raise invalid_policy("invalid_validation_feedback")
        if type(self.reason_code) is not str or not self.reason_code:
            raise invalid_policy("invalid_validation_feedback")
        if not isinstance(self.evidence, (list, tuple)) or any(
            type(value) is not str or not value for value in self.evidence
        ):
            raise invalid_policy("invalid_validation_feedback")
        object.__setattr__(self, "evidence", tuple(self.evidence))


@dataclass(frozen=True)
class SessionResult:
    status: str
    evidence: Tuple[str, ...] = ()
    reason_code: Optional[str] = None

    def __post_init__(self) -> None:
        if type(self.status) is not str or not self.status:
            raise invalid_policy("invalid_session_result")
        if not isinstance(self.evidence, (list, tuple)) or any(
            type(value) is not str or not value for value in self.evidence
        ):
            raise invalid_policy("invalid_session_result")
        object.__setattr__(self, "evidence", tuple(self.evidence))


@dataclass(frozen=True)
class BuilderSessionDecision:
    status: str
    reason_code: str
    handle: Optional[SessionHandle]
    result: Optional[SessionResult]
    resumed_original: bool
    events: Tuple[str, ...]


class HostAdapter(Protocol):
    def capabilities(self) -> HostCapabilities: ...

    def dispatch(self, node: NodeSpec) -> Optional[SessionHandle]: ...

    def resume(
        self,
        handle: SessionHandle,
        feedback: ValidationFeedback,
    ) -> SessionResult: ...
