"""Host-neutral workflow policy and adapter value types.

Session handles and results are immutable receipts bound to one
run/node/attempt and to the provider, concrete dispatch rail, and executor
capability actually used. Builder outcomes are closed; observations are
evidence only and never node lifecycle transitions.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Mapping, Optional, Protocol, Tuple

from ..redaction import (
    MAX_STRING_LENGTH, MAX_TOTAL_STRING_BYTES, bounded_iterable, is_secret_key,
    normalize_evidence_reference,
)
from ..schema import (
    ErrorDetailKey, ErrorMessage, InvalidSchemaError, WorkflowEvent,
)


_HOST_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]*$")
_CONTEXT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_CREDENTIAL_LIKE = re.compile(
    r"^(?:sk-|gh[pousr]_|xox[baprs]-|bearer\s)", re.IGNORECASE,
)
MAX_CHANGED_PATHS = 1_024
MAX_CHANGED_PATH_LENGTH = 4_096


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
    CLAUDE_EXECUTION = "claude_execution"
    CODEX_EXECUTION = "codex_execution"
    OPENROUTER_EXECUTION = "openrouter_execution"
    ANTHROPIC_NATIVE_EXECUTION = "anthropic_native_execution"


EXECUTOR_CAPABILITIES = {
    "claude": frozenset({
        HostCapability.CLAUDE_EXECUTION,
        HostCapability.ANTHROPIC_NATIVE_EXECUTION,
    }),
    "codex": frozenset({HostCapability.CODEX_EXECUTION}),
    "openrouter": frozenset({HostCapability.OPENROUTER_EXECUTION}),
}
DEFAULT_EXECUTOR_CAPABILITY = {
    "claude": HostCapability.CLAUDE_EXECUTION,
    "codex": HostCapability.CODEX_EXECUTION,
    "openrouter": HostCapability.OPENROUTER_EXECUTION,
}
DEFAULT_DISPATCH_CAPABILITY = {
    "claude": HostCapability.NATIVE_DISPATCH,
    "codex": HostCapability.NATIVE_DISPATCH,
    "openrouter": HostCapability.OPENROUTER_EXEC,
}
EXECUTOR_PROVIDERS = {
    "claude": "anthropic",
    "codex": "openai",
    "openrouter": "openrouter",
}
DISPATCH_RAIL_CAPABILITIES = {
    "native": HostCapability.NATIVE_DISPATCH,
    "codex_companion": HostCapability.COMPANION_DISPATCH,
    "wrapper": HostCapability.WRAPPER_DISPATCH,
    "openrouter_exec": HostCapability.OPENROUTER_EXEC,
}
GATE_KINDS = frozenset(
    {
        "cleanup",
        "deterministic_validation",
        "evidence",
        "human_approval",
        "investigation_promotion",
        "next_action",
        "risk",
    }
)
EXECUTORS = frozenset(EXECUTOR_CAPABILITIES)


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
        if not isinstance(self.changed_paths, (list, tuple)):
            raise invalid_policy("invalid_workflow_context")
        normalized_paths = []
        try:
            paths = bounded_iterable(self.changed_paths, max_items=MAX_CHANGED_PATHS)
            for value in paths:
                if (
                    type(value) is not str
                    or not value
                    or len(value) > MAX_CHANGED_PATH_LENGTH
                    or "\\" in value
                    or any(unicodedata.category(character) == "Cc" for character in value)
                ):
                    raise invalid_policy("invalid_changed_path")
                path = PurePosixPath(value)
                if path.is_absolute() or value == "." or any(part == ".." for part in path.parts):
                    raise invalid_policy("invalid_changed_path")
                normalized = path.as_posix()
                if normalized in ("", "."):
                    raise invalid_policy("invalid_changed_path")
                normalized_paths.append(normalized)
        except TypeError:
            raise invalid_policy("invalid_changed_path")
        if len(normalized_paths) != len(set(normalized_paths)):
            raise invalid_policy("invalid_changed_path")
        object.__setattr__(self, "changed_paths", tuple(normalized_paths))
        if not isinstance(self.evidence, (list, tuple)) or any(
            type(value) is not str or not value for value in self.evidence
        ):
            raise invalid_policy("invalid_workflow_context")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if self.requested_executor is not None and (
            type(self.requested_executor) is not str
            or self.requested_executor not in EXECUTORS
        ):
            raise invalid_policy("unknown_executor")
        if self.risk not in ("low", "medium", "high", "critical"):
            raise invalid_policy("unknown_risk_level")
        if type(self.human_approved) is not bool or type(self.promotion_approved) is not bool:
            raise invalid_policy("invalid_workflow_context")
        if type(self.investigation_promotion) is not bool:
            raise invalid_policy("invalid_workflow_context")
        if self.economics_preference is not None and (
            type(self.economics_preference) is not str or not self.economics_preference
        ):
            raise invalid_policy("invalid_workflow_context")


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason_code: str
    missing_evidence: Tuple[str, ...] = ()
    human_required: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.allowed) is not bool
            or type(self.reason_code) is not str
            or not self.reason_code
            or type(self.human_required) is not bool
            or not isinstance(self.missing_evidence, (list, tuple))
            or any(type(value) is not str or not value for value in self.missing_evidence)
        ):
            raise invalid_policy("invalid_gate_decision")
        values = tuple(self.missing_evidence)
        if len(values) != len(set(values)):
            raise invalid_policy("invalid_gate_decision")
        coherent = (
            self.reason_code == "gate_not_required"
            and self.allowed
            and not values
            and not self.human_required
        ) or (
            self.reason_code == "gate_satisfied"
            and self.allowed
            and not values
        ) or (
            self.reason_code == "missing_mandatory_evidence"
            and not self.allowed
            and bool(values)
            and not self.human_required
        ) or (
            self.reason_code == "human_approval_required"
            and not self.allowed
            and not values
            and self.human_required
        )
        if not coherent:
            raise invalid_policy("invalid_gate_decision")
        object.__setattr__(self, "missing_evidence", values)


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
    required_capability: Optional[HostCapability] = None
    required_dispatch_capability: Optional[HostCapability] = None
    executor_overridable: bool = False

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
        if self.gate_kind is not None and (
            type(self.gate_kind) is not str or self.gate_kind not in GATE_KINDS
        ):
            raise invalid_policy("unknown_gate_kind")
        if self.executor is not None and (
            type(self.executor) is not str or self.executor not in EXECUTORS
        ):
            raise invalid_policy("unknown_executor")
        if self.routing_reason is not None and (
            type(self.routing_reason) is not str or not self.routing_reason
        ):
            raise invalid_policy("invalid_node_spec")
        if type(self.gate_decision) is not GateDecision:
            raise invalid_policy("invalid_gate_decision")
        try:
            gate_decision = GateDecision(
                self.gate_decision.allowed,
                self.gate_decision.reason_code,
                self.gate_decision.missing_evidence,
                self.gate_decision.human_required,
            )
        except (AttributeError, TypeError):
            raise invalid_policy("invalid_gate_decision") from None
        object.__setattr__(self, "gate_decision", gate_decision)
        if self.gate_kind is None:
            if self.required_evidence or not self.gate_decision.allowed or self.gate_decision.reason_code != "gate_not_required":
                raise invalid_policy("inconsistent_gate_decision")
        elif self.gate_decision.reason_code == "gate_not_required":
            raise invalid_policy("inconsistent_gate_decision")
        if self.required_capability is not None:
            try:
                required = (
                    self.required_capability
                    if type(self.required_capability) is HostCapability
                    else HostCapability(self.required_capability)
                )
            except (TypeError, ValueError):
                raise invalid_policy("unknown_capability_name") from None
            object.__setattr__(self, "required_capability", required)
        if self.required_dispatch_capability is not None:
            try:
                required_dispatch = (
                    self.required_dispatch_capability
                    if type(self.required_dispatch_capability) is HostCapability
                    else HostCapability(self.required_dispatch_capability)
                )
            except (TypeError, ValueError):
                raise invalid_policy("unknown_capability_name") from None
            if required_dispatch not in set(DISPATCH_RAIL_CAPABILITIES.values()):
                raise invalid_policy("inconsistent_dispatch_capability")
            object.__setattr__(self, "required_dispatch_capability", required_dispatch)
        if type(self.executor_overridable) is not bool:
            raise invalid_policy("invalid_node_spec")
        expected_capabilities = EXECUTOR_CAPABILITIES.get(self.executor, frozenset())
        if self.executor is None and (
            self.required_capability is not None
            or self.required_dispatch_capability is not None
        ):
            raise invalid_policy("inconsistent_executor_capability")
        if self.executor is not None and (
            self.required_capability not in expected_capabilities
            or self.required_dispatch_capability is None
        ):
            raise invalid_policy("inconsistent_executor_capability")
        if (
            self.executor == "openrouter"
            and self.required_dispatch_capability is not HostCapability.OPENROUTER_EXEC
        ):
            raise invalid_policy("inconsistent_dispatch_capability")
        if self.executor is None and self.executor_overridable:
            raise invalid_policy("inconsistent_executor_capability")


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
        for reason, history in safe_signatures.items():
            if reason not in safe_counts or len(history) > safe_counts[reason]:
                raise invalid_policy("invalid_attempt_ledger")
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
            raw_values = list(self.capabilities)
            converted = [
                value if type(value) is HostCapability else HostCapability(value)
                for value in raw_values
            ]
        except (TypeError, ValueError):
            raise invalid_policy("unknown_capability_name") from None
        if len(converted) != len(set(converted)):
            raise invalid_policy("duplicate_capability_name")
        values = frozenset(converted)
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
class ResumeStateContext:
    """Final provenance binding for one run/node/attempt/provider/rail receipt."""

    run_id: str
    node_id: str
    attempt_id: str
    provider: str
    rail: str
    capability: HostCapability

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("ResumeStateContext is final")

    def __post_init__(self) -> None:
        for name in ("run_id", "node_id", "attempt_id", "provider"):
            value = getattr(self, name)
            if (
                type(value) is not str
                or len(value) > MAX_STRING_LENGTH
                or _CONTEXT_ID.fullmatch(value) is None
            ):
                raise invalid_policy("invalid_session_resume_context")
        if type(self.rail) is not str or self.rail not in DISPATCH_RAIL_CAPABILITIES:
            raise invalid_policy("invalid_session_resume_context")
        try:
            capability = (
                self.capability
                if type(self.capability) is HostCapability
                else HostCapability(self.capability)
            )
        except (TypeError, ValueError):
            raise invalid_policy("invalid_session_resume_context") from None
        if capability not in set().union(*EXECUTOR_CAPABILITIES.values()):
            raise invalid_policy("invalid_session_resume_context")
        object.__setattr__(self, "capability", capability)

    def __repr__(self) -> str:
        try:
            context = _snapshot_resume_context(self)
        except InvalidSchemaError:
            return "ResumeStateContext([INVALID])"
        return (
            "ResumeStateContext(run_id={!r}, node_id={!r}, attempt_id={!r}, "
            "provider={!r}, rail={!r}, capability={!r})"
        ).format(
            context.run_id, context.node_id, context.attempt_id, context.provider,
            context.rail, context.capability,
        )

    def to_dict(self) -> dict:
        context = _snapshot_resume_context(self)
        return {
            "run_id": context.run_id,
            "node_id": context.node_id,
            "attempt_id": context.attempt_id,
            "provider": context.provider,
            "rail": context.rail,
            "capability": context.capability.value,
        }


def _snapshot_resume_context(context: ResumeStateContext) -> ResumeStateContext:
    if type(context) is not ResumeStateContext:
        raise invalid_policy("invalid_session_resume_context")
    try:
        return ResumeStateContext(
            context.run_id, context.node_id, context.attempt_id, context.provider,
            context.rail, context.capability,
        )
    except (AttributeError, TypeError):
        raise invalid_policy("invalid_session_resume_context") from None


@dataclass(frozen=True, repr=False)
class SessionHandle:
    """Final host receipt bound to actual provider, rail, capability, and attempt."""
    host_name: str
    opaque_handle: str
    created_at: str
    resume_capable: bool
    context: ResumeStateContext

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("SessionHandle is final")

    def __post_init__(self) -> None:
        if (
            type(self.host_name) is not str
            or _HOST_NAME.fullmatch(self.host_name) is None
            or type(self.opaque_handle) is not str
            or not self.opaque_handle
            or len(self.opaque_handle) > MAX_STRING_LENGTH
            or type(self.created_at) is not str
            or not self.created_at
            or len(self.created_at) > MAX_STRING_LENGTH
            or type(self.resume_capable) is not bool
            or type(self.context) is not ResumeStateContext
        ):
            raise invalid_policy("invalid_session_handle")
        try:
            self.opaque_handle.encode("utf-8")
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except (UnicodeError, ValueError):
            raise invalid_policy("invalid_session_handle") from None
        if created.tzinfo is None:
            raise invalid_policy("invalid_session_handle")
        object.__setattr__(self, "context", _snapshot_resume_context(self.context))

    def __repr__(self) -> str:
        try:
            handle = _snapshot_session_handle(self)
        except InvalidSchemaError:
            return "SessionHandle([INVALID])"
        return (
            "SessionHandle(host_name={!r}, opaque_handle='[REDACTED]', "
            "created_at={!r}, resume_capable={!r}, context={!r})"
        ).format(
            handle.host_name, handle.created_at, handle.resume_capable, handle.context,
        )

    def to_dict(self) -> dict:
        handle = _snapshot_session_handle(self)
        digest = hashlib.sha256(handle.opaque_handle.encode("utf-8")).hexdigest()
        return {
            "host_name": handle.host_name,
            "opaque_digest": "sha256:" + digest,
            "created_at": handle.created_at,
            "resume_capable": handle.resume_capable,
            "context": handle.context.to_dict(),
        }


def _snapshot_session_handle(handle: SessionHandle) -> SessionHandle:
    if type(handle) is not SessionHandle:
        raise invalid_policy("invalid_session_handle")
    try:
        return SessionHandle(
            host_name=handle.host_name,
            opaque_handle=handle.opaque_handle,
            created_at=handle.created_at,
            resume_capable=handle.resume_capable,
            context=handle.context,
        )
    except (AttributeError, TypeError):
        raise invalid_policy("invalid_session_handle") from None


@dataclass(frozen=True, repr=False)
class ValidationFeedback:
    node_id: str
    reason_code: str
    evidence: Tuple[str, ...] = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("ValidationFeedback is final")

    def __post_init__(self) -> None:
        if (
            type(self.node_id) is not str
            or _CONTEXT_ID.fullmatch(self.node_id) is None
            or len(self.node_id) > MAX_STRING_LENGTH
        ):
            raise invalid_policy("invalid_validation_feedback")
        if (
            type(self.reason_code) is not str
            or _REASON_CODE.fullmatch(self.reason_code) is None
            or len(self.reason_code) > MAX_STRING_LENGTH
        ):
            raise invalid_policy("invalid_validation_feedback")
        object.__setattr__(
            self, "evidence",
            _normalize_safe_evidence(self.evidence, "invalid_validation_feedback"),
        )

    def __repr__(self) -> str:
        try:
            feedback = _snapshot_validation_feedback(self)
        except InvalidSchemaError:
            return "ValidationFeedback([INVALID])"
        return "ValidationFeedback(node_id={!r}, reason_code={!r}, evidence={!r})".format(
            feedback.node_id, feedback.reason_code, feedback.evidence,
        )

    def to_dict(self) -> dict:
        feedback = _snapshot_validation_feedback(self)
        return {
            "node_id": feedback.node_id,
            "reason_code": feedback.reason_code,
            "evidence": list(feedback.evidence),
        }


def _snapshot_validation_feedback(feedback: ValidationFeedback) -> ValidationFeedback:
    if type(feedback) is not ValidationFeedback:
        raise invalid_policy("invalid_validation_feedback")
    try:
        return ValidationFeedback(
            feedback.node_id, feedback.reason_code, feedback.evidence,
        )
    except (AttributeError, TypeError):
        raise invalid_policy("invalid_validation_feedback") from None


def _normalize_safe_evidence(values: object, reason_code: str) -> Tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise invalid_policy(reason_code)
    normalized = []
    total_bytes = 0
    try:
        for value in bounded_iterable(values, max_items=1_024):
            if type(value) is not str or not value:
                raise ValueError
            reference = normalize_evidence_reference(value)
            if not reference.startswith(("sha256:", "url-sha256:")):
                for segment in reference.split("/"):
                    if _CREDENTIAL_LIKE.match(segment) is not None or is_secret_key(segment):
                        raise ValueError
            total_bytes += len(reference.encode("utf-8"))
            if total_bytes > MAX_TOTAL_STRING_BYTES:
                raise ValueError
            normalized.append(reference)
    except (TypeError, ValueError, UnicodeError):
        raise invalid_policy(reason_code) from None
    result = tuple(normalized)
    if len(result) != len(values) or len(result) != len(set(result)):
        raise invalid_policy(reason_code)
    return result


class SessionStatus(str, Enum):
    """Closed outcomes returned by a host adapter session."""

    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    FAILED = "failed"
    WAITING = "waiting"


@dataclass(frozen=True, repr=False)
class SessionResult:
    """Closed, secret-safe adapter result bound to its originating receipt."""

    status: SessionStatus
    context: ResumeStateContext
    evidence: Tuple[str, ...] = ()
    reason_code: Optional[str] = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("SessionResult is final")

    def __post_init__(self) -> None:
        try:
            status = self.status if type(self.status) is SessionStatus else SessionStatus(self.status)
        except (TypeError, ValueError):
            raise invalid_policy("invalid_session_result") from None
        if type(self.context) is not ResumeStateContext:
            raise invalid_policy("invalid_session_result")
        values = _normalize_safe_evidence(self.evidence, "invalid_session_result")
        if self.reason_code is not None and (
            type(self.reason_code) is not str
            or _REASON_CODE.fullmatch(self.reason_code) is None
            or len(self.reason_code) > MAX_STRING_LENGTH
        ):
            raise invalid_policy("invalid_session_result")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "context", _snapshot_resume_context(self.context))
        object.__setattr__(self, "evidence", values)

    def __repr__(self) -> str:
        try:
            result = _snapshot_session_result(self)
        except InvalidSchemaError:
            return "SessionResult([INVALID])"
        return (
            "SessionResult(status={!r}, context={!r}, evidence={!r}, reason_code={!r})"
        ).format(result.status, result.context, result.evidence, result.reason_code)

    def to_dict(self) -> dict:
        result = _snapshot_session_result(self)
        return {
            "status": result.status.value,
            "context": result.context.to_dict(),
            "evidence": list(result.evidence),
            "reason_code": result.reason_code,
        }


def _snapshot_session_result(result: SessionResult) -> SessionResult:
    if type(result) is not SessionResult:
        raise invalid_policy("invalid_session_result")
    try:
        return SessionResult(
            result.status, result.context, result.evidence, result.reason_code,
        )
    except (AttributeError, TypeError):
        raise invalid_policy("invalid_session_result") from None


MAX_RESUME_STATE_BYTES = 65_536


@dataclass(frozen=True, repr=False)
class ResumeStateBlob:
    """Opaque trusted-store blob excluded from every ordinary workflow record.

    Raw bytes may live only in protected permission-restricted storage with an
    explicit retention/deletion policy. They must never enter receipts, events,
    evidence, artifacts, shadow reports, Airlift payloads, or checkpoints.
    """

    _payload: bytes

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("ResumeStateBlob is final")

    def __post_init__(self) -> None:
        if type(self._payload) is not bytes or len(self._payload) > MAX_RESUME_STATE_BYTES:
            raise invalid_policy("invalid_session_resume_state")

    def __repr__(self) -> str:
        try:
            payload = _snapshot_resume_blob(self)
        except InvalidSchemaError:
            return "ResumeStateBlob([INVALID])"
        return "ResumeStateBlob(sha256:{})".format(hashlib.sha256(payload).hexdigest())

    def to_dict(self) -> dict:
        payload = _snapshot_resume_blob(self)
        return {
            "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "authenticity": "trusted_store_only",
        }

    def to_trusted_bytes(self) -> bytes:
        """Return persistence bytes for a package-owned trusted store; never log them."""
        return bytes(_snapshot_resume_blob(self))


def _snapshot_resume_blob(blob: ResumeStateBlob) -> bytes:
    if type(blob) is not ResumeStateBlob:
        raise invalid_policy("invalid_session_resume_state")
    try:
        payload = blob._payload
        if type(payload) is not bytes or len(payload) > MAX_RESUME_STATE_BYTES:
            raise invalid_policy("invalid_session_resume_state")
        return bytes(payload)
    except (AttributeError, TypeError):
        raise invalid_policy("invalid_session_resume_state") from None


class BuilderObservation(str, Enum):
    """Builder repair evidence; these values are not node lifecycle transitions."""

    BUILDER_DISPATCHED = "builder_dispatched"
    BUILDER_REPLACEMENT_DISPATCHED = "builder_replacement_dispatched"
    DISPATCH_BLOCKED = "dispatch_blocked"
    SESSION_RESUMED = "session_resumed"
    SESSION_RESUME_UNAVAILABLE = "session_resume_unavailable"

    @property
    def evidence_reference(self) -> str:
        return "builder-observation/" + self.value.replace("_", "-")


class BuilderOutcome(str, Enum):
    """Closed manager outcomes from which all public decision facts derive."""

    BUILDER_DISPATCHED = "builder_dispatched"
    SESSION_RESUMED = "session_resumed"
    REPLACEMENT_DISPATCHED = "replacement_dispatched"
    SESSION_RESUME_UNAVAILABLE = "session_resume_unavailable"
    NODE_GATE_BLOCKED = "node_gate_blocked"
    HOST_CAPABILITY_UNAVAILABLE = "host_capability_unavailable"
    ADAPTER_CAPABILITIES_FAILED = "adapter_capabilities_failed"
    ADAPTER_DISPATCH_FAILED = "adapter_dispatch_failed"
    INVALID_SESSION_HANDLE = "invalid_session_handle"
    SESSION_HANDLE_UNAVAILABLE = "session_handle_unavailable"
    REPLACEMENT_ADAPTER_DISPATCH_FAILED = "replacement_adapter_dispatch_failed"
    REPLACEMENT_INVALID_SESSION_HANDLE = "replacement_invalid_session_handle"
    REPLACEMENT_SESSION_HANDLE_UNAVAILABLE = "replacement_session_handle_unavailable"


_OUTCOME_FACTS = {
    BuilderOutcome.BUILDER_DISPATCHED: ("dispatched", "builder_dispatched", False,
        (BuilderObservation.BUILDER_DISPATCHED,)),
    BuilderOutcome.SESSION_RESUMED: ("resumed", "session_resumed", True,
        (BuilderObservation.SESSION_RESUMED,)),
    BuilderOutcome.REPLACEMENT_DISPATCHED: ("replacement_dispatched", "session_resume_unavailable", False,
        (BuilderObservation.SESSION_RESUME_UNAVAILABLE,
         BuilderObservation.BUILDER_REPLACEMENT_DISPATCHED)),
    BuilderOutcome.SESSION_RESUME_UNAVAILABLE: ("resume_unavailable", "session_resume_unavailable", False,
        (BuilderObservation.SESSION_RESUME_UNAVAILABLE,)),
    BuilderOutcome.NODE_GATE_BLOCKED: ("blocked", "node_gate_blocked", False,
        (BuilderObservation.DISPATCH_BLOCKED,)),
    BuilderOutcome.HOST_CAPABILITY_UNAVAILABLE: ("blocked", "host_capability_unavailable", False,
        (BuilderObservation.DISPATCH_BLOCKED,)),
    BuilderOutcome.ADAPTER_CAPABILITIES_FAILED: ("blocked", "adapter_capabilities_failed", False,
        (BuilderObservation.DISPATCH_BLOCKED,)),
    BuilderOutcome.ADAPTER_DISPATCH_FAILED: ("blocked", "adapter_dispatch_failed", False,
        (BuilderObservation.DISPATCH_BLOCKED,)),
    BuilderOutcome.INVALID_SESSION_HANDLE: ("blocked", "invalid_session_handle", False,
        (BuilderObservation.DISPATCH_BLOCKED,)),
    BuilderOutcome.SESSION_HANDLE_UNAVAILABLE: ("blocked", "session_handle_unavailable", False,
        (BuilderObservation.DISPATCH_BLOCKED,)),
    BuilderOutcome.REPLACEMENT_ADAPTER_DISPATCH_FAILED: ("blocked", "adapter_dispatch_failed", False,
        (BuilderObservation.SESSION_RESUME_UNAVAILABLE, BuilderObservation.DISPATCH_BLOCKED)),
    BuilderOutcome.REPLACEMENT_INVALID_SESSION_HANDLE: ("blocked", "invalid_session_handle", False,
        (BuilderObservation.SESSION_RESUME_UNAVAILABLE, BuilderObservation.DISPATCH_BLOCKED)),
    BuilderOutcome.REPLACEMENT_SESSION_HANDLE_UNAVAILABLE: ("resume_unavailable", "session_resume_unavailable", False,
        (BuilderObservation.SESSION_RESUME_UNAVAILABLE,)),
}


@dataclass(frozen=True, repr=False)
class BuilderSessionDecision:
    """Coherent closed builder outcome with observation-only projection."""

    outcome: BuilderOutcome
    handle: Optional[SessionHandle] = None
    result: Optional[SessionResult] = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("BuilderSessionDecision is final")

    def __post_init__(self) -> None:
        try:
            outcome = self.outcome if type(self.outcome) is BuilderOutcome else BuilderOutcome(self.outcome)
        except (TypeError, ValueError):
            raise invalid_policy("invalid_builder_session_decision") from None
        requires_handle = outcome in {
            BuilderOutcome.BUILDER_DISPATCHED,
            BuilderOutcome.SESSION_RESUMED,
            BuilderOutcome.REPLACEMENT_DISPATCHED,
        }
        requires_result = outcome is BuilderOutcome.SESSION_RESUMED
        if (self.handle is None) == requires_handle or (self.result is None) == requires_result:
            raise invalid_policy("invalid_builder_session_decision")
        object.__setattr__(self, "outcome", outcome)
        if self.handle is not None:
            object.__setattr__(self, "handle", _snapshot_session_handle(self.handle))
        if self.result is not None:
            object.__setattr__(self, "result", _snapshot_session_result(self.result))
        if (
            outcome is BuilderOutcome.SESSION_RESUMED
            and self.handle.context != self.result.context
        ):
            raise invalid_policy("invalid_builder_session_decision")

    @property
    def status(self) -> str:
        return _snapshot_builder_decision(self)[0][0]

    @property
    def reason_code(self) -> str:
        return _snapshot_builder_decision(self)[0][1]

    @property
    def resumed_original(self) -> bool:
        return _snapshot_builder_decision(self)[0][2]

    @property
    def observations(self) -> Tuple[BuilderObservation, ...]:
        return _snapshot_builder_decision(self)[0][3]

    @property
    def evidence_references(self) -> Tuple[str, ...]:
        return tuple(value.evidence_reference for value in self.observations)

    def __repr__(self) -> str:
        try:
            _, decision = _snapshot_builder_decision(self)
        except InvalidSchemaError:
            return "BuilderSessionDecision([INVALID])"
        return (
            "BuilderSessionDecision(outcome={!r}, handle={!r}, result={!r})"
        ).format(decision.outcome, decision.handle, decision.result)

    def to_evidence_event(
        self, *, run_id: str, sequence: int, node_id: str, occurred_at: str,
    ) -> WorkflowEvent:
        """Project observations only into Chunk01's legal evidence vocabulary.

        A downstream translator must also require an authoritative receipt
        reference and safely merge ``result.evidence`` when a result exists.
        This helper never fabricates that receipt or treats observations as it.
        """
        return WorkflowEvent(
            1, sequence, run_id, node_id, "evidence.recorded", occurred_at,
            {"evidence": list(self.evidence_references)},
        )


def _snapshot_builder_decision(
    decision: BuilderSessionDecision,
) -> tuple[tuple, BuilderSessionDecision]:
    if type(decision) is not BuilderSessionDecision:
        raise invalid_policy("invalid_builder_session_decision")
    try:
        outcome = (
            decision.outcome
            if type(decision.outcome) is BuilderOutcome
            else BuilderOutcome(decision.outcome)
        )
        facts = _OUTCOME_FACTS.get(outcome)
        if facts is None:
            raise ValueError
        snapshot = BuilderSessionDecision(outcome, decision.handle, decision.result)
        return facts, snapshot
    except (AttributeError, KeyError, TypeError, ValueError):
        raise invalid_policy("invalid_builder_session_decision") from None


class HostAdapter(Protocol):
    def capabilities(self) -> HostCapabilities: ...

    def dispatch(
        self, node: NodeSpec, context: ResumeStateContext,
    ) -> Optional[SessionHandle]: ...

    def resume(
        self,
        handle: SessionHandle,
        feedback: ValidationFeedback,
    ) -> SessionResult: ...
