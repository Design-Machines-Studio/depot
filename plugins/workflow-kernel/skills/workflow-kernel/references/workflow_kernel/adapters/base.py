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
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from threading import RLock
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


def _validate_host_name(value: object) -> str:
    """Return one exact, format-valid host name without caller callbacks."""
    if type(value) is not str or _HOST_NAME.fullmatch(value) is None:
        raise invalid_policy("invalid_host_name")
    return value


def _normalize_enum(enum_type: type[Enum], value: object, reason_code: str) -> Enum:
    """Normalize one public enum scalar without leaking ordinary exceptions."""
    if type(value) is enum_type:
        return value
    if type(value) is not str:
        raise invalid_policy(reason_code)
    try:
        return enum_type(value)
    except Exception:
        raise invalid_policy(reason_code) from None


def _safe_membership(value: object, candidates: object, reason_code: str) -> bool:
    """Evaluate caller-controlled membership with a stable ordinary failure."""
    try:
        return value in candidates
    except Exception:
        raise invalid_policy(reason_code) from None


def _safe_equal(left: object, right: object, reason_code: str) -> bool:
    """Compare a caller scalar without intercepting BaseException control flow."""
    try:
        return bool(left == right)
    except Exception:
        raise invalid_policy(reason_code) from None


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
PROVIDERS = frozenset({"anthropic", "openai", "openrouter"})
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
AGENTIC_DISPATCH_RAILS = frozenset({"native", "codex_companion", "openrouter_exec"})
ROUTE_SCOPED_CAPABILITIES = frozenset(
    set(DISPATCH_RAIL_CAPABILITIES.values()).union(
        *EXECUTOR_CAPABILITIES.values(),
    )
)


class _IdentitySealRegistry:
    """Weak identity registry whose keys cannot be rewritten through values."""

    def __init__(self) -> None:
        self._entries = {}
        self._lock = RLock()

    def register(self, value: object, kind: str, primitives: object) -> None:
        identity = id(value)

        def discard(reference: weakref.ReferenceType, identity: int = identity) -> None:
            with self._lock:
                current = self._entries.get(identity)
                if current is not None and current[0] is reference:
                    del self._entries[identity]

        reference = weakref.ref(value, discard)
        with self._lock:
            current = self._entries.get(identity)
            if current is not None and current[0]() is not None:
                raise ValueError
            self._entries[identity] = (reference, kind, primitives)

    def validate(self, value: object, kind: str, primitives: object) -> None:
        with self._lock:
            current = self._entries.get(id(value))
            if (
                current is None
                or current[0]() is not value
                or current[1] != kind
                or current[2] != primitives
            ):
                raise ValueError

    def size(self) -> int:
        with self._lock:
            return len(self._entries)


_ORIGIN_SEALS = _IdentitySealRegistry()


def _register_origin(value: object, kind: str, primitives: object) -> None:
    _ORIGIN_SEALS.register(value, kind, primitives)


def _validate_origin(value: object, kind: str, primitives: object) -> None:
    _ORIGIN_SEALS.validate(value, kind, primitives)


def _validate_capture(
    value: object, kind: str, captured: tuple, primitives: object,
) -> tuple:
    """Validate one seal and return the exact payload used to derive it."""
    _validate_origin(value, kind, primitives)
    return captured


def _origin_seal_registry_size() -> int:
    """Return live seal count for lifecycle regression tests."""
    return _ORIGIN_SEALS.size()


@dataclass(frozen=True, repr=False)
class HostRoute:
    """One concrete provider/executor/dispatch authorization tuple."""

    provider: str
    capability: HostCapability
    rail: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("HostRoute is final")

    def __post_init__(self) -> None:
        if type(self.provider) is not str or self.provider not in PROVIDERS:
            raise invalid_policy("invalid_host_route")
        if type(self.rail) is not str or self.rail not in DISPATCH_RAIL_CAPABILITIES:
            raise invalid_policy("invalid_host_route")
        try:
            capability = _normalize_enum(
                HostCapability, self.capability, "invalid_host_route",
            )
        except Exception:
            raise invalid_policy("invalid_host_route") from None
        if capability not in set().union(*EXECUTOR_CAPABILITIES.values()):
            raise invalid_policy("invalid_host_route")
        coherent = (
            self.rail == "native"
            and (
                self.provider == "anthropic"
                and capability in EXECUTOR_CAPABILITIES["claude"]
                or self.provider == "openai"
                and capability is HostCapability.CODEX_EXECUTION
            )
        ) or (
            self.rail == "codex_companion"
            and self.provider == "openai"
            and capability is HostCapability.CODEX_EXECUTION
        ) or (
            self.rail in {"wrapper", "openrouter_exec"}
            and self.provider == "openrouter"
            and capability in {
                HostCapability.OPENROUTER_EXECUTION,
                HostCapability.CLAUDE_EXECUTION,
                HostCapability.CODEX_EXECUTION,
            }
        )
        if not coherent or (
            capability is HostCapability.ANTHROPIC_NATIVE_EXECUTION
            and (self.provider, self.rail) != ("anthropic", "native")
        ):
            raise invalid_policy("incoherent_host_route")
        object.__setattr__(self, "capability", capability)
        _register_origin(
            self, "HostRoute", (self.provider, capability.value, self.rail),
        )

    @property
    def dispatch_capability(self) -> HostCapability:
        route = _snapshot_host_route(self)
        return DISPATCH_RAIL_CAPABILITIES[route.rail]

    @property
    def agentic(self) -> bool:
        return _snapshot_host_route(self).rail in AGENTIC_DISPATCH_RAILS

    def __repr__(self) -> str:
        try:
            route = _snapshot_host_route(self)
        except InvalidSchemaError:
            return "HostRoute([INVALID])"
        return "HostRoute(provider={!r}, capability={!r}, rail={!r})".format(
            route.provider, route.capability, route.rail,
        )


def _snapshot_host_route(route: HostRoute) -> HostRoute:
    if type(route) is not HostRoute:
        raise invalid_policy("invalid_host_route")
    try:
        captured = (route.provider, route.capability, route.rail)
        if (
            type(captured[0]) is not str
            or type(captured[1]) is not HostCapability
            or type(captured[2]) is not str
        ):
            raise ValueError
        primitives = (captured[0], captured[1].value, captured[2])
        captured = _validate_capture(route, "HostRoute", captured, primitives)
        return HostRoute(*captured)
    except Exception:
        raise invalid_policy("invalid_host_route") from None


def route_satisfies_node(route: HostRoute, node: "NodeSpec") -> bool:
    """Apply the one centralized route/executor/capability constraint."""
    if type(route) is not HostRoute or type(node) is not NodeSpec:
        return False
    try:
        route = _snapshot_host_route(route)
        node = _snapshot_node_spec(node)
    except InvalidSchemaError:
        return False
    if route.rail not in AGENTIC_DISPATCH_RAILS:
        return False
    if node.executor is None or route.capability is not node.required_capability:
        return False
    if (
        node.required_dispatch_capability is not None
        and DISPATCH_RAIL_CAPABILITIES[route.rail]
        is not node.required_dispatch_capability
    ):
        return False
    return True


def normalize_executor_constraint(
    executor: object,
    required_capability: object,
    required_dispatch_capability: object,
) -> tuple[Optional[str], Optional[HostCapability], Optional[HostCapability]]:
    """Normalize schema and runtime executor constraints through one rule."""
    if executor is not None and (type(executor) is not str or executor not in EXECUTORS):
        raise invalid_policy("unknown_executor")
    capability = (
        None if required_capability is None
        else _normalize_enum(
            HostCapability, required_capability, "unknown_capability_name",
        )
    )
    dispatch = (
        None if required_dispatch_capability is None
        else _normalize_enum(
            HostCapability, required_dispatch_capability,
            "unknown_capability_name",
        )
    )
    if dispatch is not None and dispatch not in set(DISPATCH_RAIL_CAPABILITIES.values()):
        raise invalid_policy("inconsistent_dispatch_capability")
    if executor is None and (capability is not None or dispatch is not None):
        raise invalid_policy("inconsistent_executor_capability")
    if executor is not None and capability not in EXECUTOR_CAPABILITIES[executor]:
        raise invalid_policy("inconsistent_executor_capability")
    allowed_dispatch = {
        "claude": {
            None, HostCapability.NATIVE_DISPATCH, HostCapability.OPENROUTER_EXEC,
        },
        "codex": {
            None, HostCapability.NATIVE_DISPATCH,
            HostCapability.COMPANION_DISPATCH, HostCapability.OPENROUTER_EXEC,
        },
        "openrouter": {None, HostCapability.OPENROUTER_EXEC},
    }
    if executor is not None and dispatch not in allowed_dispatch[executor]:
        raise invalid_policy("inconsistent_dispatch_capability")
    if capability is HostCapability.ANTHROPIC_NATIVE_EXECUTION and (
        executor != "claude" or dispatch is not HostCapability.NATIVE_DISPATCH
    ):
        raise invalid_policy("inconsistent_dispatch_capability")
    return executor, capability, dispatch


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
        except Exception:
            raise invalid_policy("invalid_changed_path")
        if len(normalized_paths) != len(set(normalized_paths)):
            raise invalid_policy("invalid_changed_path")
        object.__setattr__(self, "changed_paths", tuple(normalized_paths))
        try:
            if not isinstance(self.evidence, (list, tuple)) or any(
                type(value) is not str or not value for value in self.evidence
            ):
                raise ValueError
            evidence = tuple(self.evidence)
        except Exception:
            raise invalid_policy("invalid_workflow_context") from None
        object.__setattr__(self, "evidence", evidence)
        if self.requested_executor is not None and (
            type(self.requested_executor) is not str
            or self.requested_executor not in EXECUTORS
        ):
            raise invalid_policy("unknown_executor")
        if not _safe_membership(
            self.risk, ("low", "medium", "high", "critical"),
            "unknown_risk_level",
        ):
            raise invalid_policy("unknown_risk_level")
        if type(self.human_approved) is not bool or type(self.promotion_approved) is not bool:
            raise invalid_policy("invalid_workflow_context")
        if type(self.investigation_promotion) is not bool:
            raise invalid_policy("invalid_workflow_context")
        if self.economics_preference is not None and (
            type(self.economics_preference) is not str or not self.economics_preference
        ):
            raise invalid_policy("invalid_workflow_context")
        captured = (
            self.changed_paths, self.requested_executor, self.risk, self.evidence,
            self.human_approved, self.investigation_promotion,
            self.promotion_approved, self.economics_preference,
        )
        _register_origin(
            self, "WorkflowContext", _workflow_context_primitives(captured),
        )


def _workflow_context_primitives(captured: tuple) -> tuple[object, ...]:
    (
        changed_paths, requested_executor, risk, evidence, human_approved,
        investigation_promotion, promotion_approved, economics_preference,
    ) = captured
    if (
        type(changed_paths) is not tuple
        or any(type(value) is not str for value in changed_paths)
        or requested_executor is not None and type(requested_executor) is not str
        or type(risk) is not str
        or type(evidence) is not tuple
        or any(type(value) is not str for value in evidence)
        or type(human_approved) is not bool
        or type(investigation_promotion) is not bool
        or type(promotion_approved) is not bool
        or economics_preference is not None
        and type(economics_preference) is not str
    ):
        raise ValueError
    return captured


def _snapshot_workflow_context(context: WorkflowContext) -> WorkflowContext:
    if type(context) is not WorkflowContext:
        raise invalid_policy("invalid_workflow_context")
    try:
        captured = (
            context.changed_paths, context.requested_executor, context.risk,
            context.evidence, context.human_approved,
            context.investigation_promotion, context.promotion_approved,
            context.economics_preference,
        )
        captured = _validate_capture(
            context, "WorkflowContext", captured,
            _workflow_context_primitives(captured),
        )
        return WorkflowContext(
            changed_paths=captured[0], requested_executor=captured[1],
            risk=captured[2], evidence=captured[3], human_approved=captured[4],
            investigation_promotion=captured[5], promotion_approved=captured[6],
            economics_preference=captured[7],
        )
    except Exception:
        raise invalid_policy("invalid_workflow_context") from None


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason_code: str
    missing_evidence: Tuple[str, ...] = ()
    human_required: bool = False

    def __post_init__(self) -> None:
        try:
            if (
                type(self.allowed) is not bool
                or type(self.reason_code) is not str
                or not self.reason_code
                or type(self.human_required) is not bool
                or not isinstance(self.missing_evidence, (list, tuple))
                or any(
                    type(value) is not str or not value
                    for value in self.missing_evidence
                )
            ):
                raise ValueError
            values = tuple(self.missing_evidence)
        except Exception:
            raise invalid_policy("invalid_gate_decision") from None
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
        captured = (
            self.allowed, self.reason_code, self.missing_evidence,
            self.human_required,
        )
        _register_origin(
            self, "GateDecision", _gate_decision_primitives(captured),
        )


def _gate_decision_primitives(captured: tuple) -> tuple[object, ...]:
    allowed, reason_code, missing_evidence, human_required = captured
    if (
        type(allowed) is not bool
        or type(reason_code) is not str
        or type(missing_evidence) is not tuple
        or any(type(value) is not str for value in missing_evidence)
        or type(human_required) is not bool
    ):
        raise ValueError
    return captured


def _snapshot_gate_decision(decision: GateDecision) -> GateDecision:
    if type(decision) is not GateDecision:
        raise invalid_policy("invalid_gate_decision")
    try:
        captured = (
            decision.allowed, decision.reason_code, decision.missing_evidence,
            decision.human_required,
        )
        captured = _validate_capture(
            decision, "GateDecision", captured,
            _gate_decision_primitives(captured),
        )
        return GateDecision(*captured)
    except Exception:
        raise invalid_policy("invalid_gate_decision") from None


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
            try:
                if not isinstance(values, (list, tuple)) or any(
                    type(value) is not str or not value for value in values
                ):
                    raise ValueError
                values = tuple(values)
            except Exception:
                raise invalid_policy("invalid_node_spec") from None
            if len(values) != len(set(values)):
                raise invalid_policy("duplicate_node_value")
            object.__setattr__(self, name, values)
        if self.gate_kind is not None and (
            type(self.gate_kind) is not str or self.gate_kind not in GATE_KINDS
        ):
            raise invalid_policy("unknown_gate_kind")
        if self.routing_reason is not None and (
            type(self.routing_reason) is not str or not self.routing_reason
        ):
            raise invalid_policy("invalid_node_spec")
        if type(self.gate_decision) is not GateDecision:
            raise invalid_policy("invalid_gate_decision")
        try:
            gate_decision = _snapshot_gate_decision(self.gate_decision)
        except Exception:
            raise invalid_policy("invalid_gate_decision") from None
        object.__setattr__(self, "gate_decision", gate_decision)
        if self.gate_kind is None:
            if self.required_evidence or not self.gate_decision.allowed or self.gate_decision.reason_code != "gate_not_required":
                raise invalid_policy("inconsistent_gate_decision")
        elif self.gate_decision.reason_code == "gate_not_required":
            raise invalid_policy("inconsistent_gate_decision")
        executor, required, required_dispatch = normalize_executor_constraint(
            self.executor, self.required_capability,
            self.required_dispatch_capability,
        )
        object.__setattr__(self, "executor", executor)
        object.__setattr__(self, "required_capability", required)
        object.__setattr__(self, "required_dispatch_capability", required_dispatch)
        if type(self.executor_overridable) is not bool:
            raise invalid_policy("invalid_node_spec")
        if self.executor is None and self.executor_overridable:
            raise invalid_policy("inconsistent_executor_capability")
        captured = (
            self.node_id, self.dependencies, self.gate_kind,
            self.required_evidence, self.executor, self.routing_reason,
            self.gate_decision, self.required_capability,
            self.required_dispatch_capability, self.executor_overridable,
        )
        _register_origin(self, "NodeSpec", _node_spec_primitives(captured))


def _node_spec_primitives(captured: tuple) -> tuple[object, ...]:
    (
        node_id, dependencies, gate_kind, required_evidence, executor,
        routing_reason, gate, required_capability,
        required_dispatch_capability, executor_overridable,
    ) = captured
    if (
        type(node_id) is not str
        or type(dependencies) is not tuple
        or any(type(value) is not str for value in dependencies)
        or gate_kind is not None and type(gate_kind) is not str
        or type(required_evidence) is not tuple
        or any(type(value) is not str for value in required_evidence)
        or executor is not None and type(executor) is not str
        or routing_reason is not None and type(routing_reason) is not str
        or type(gate) is not GateDecision
        or required_capability is not None
        and type(required_capability) is not HostCapability
        or required_dispatch_capability is not None
        and type(required_dispatch_capability) is not HostCapability
        or type(executor_overridable) is not bool
    ):
        raise ValueError
    gate_captured = (
        gate.allowed, gate.reason_code, gate.missing_evidence, gate.human_required,
    )
    gate_primitives = _gate_decision_primitives(gate_captured)
    _validate_origin(gate, "GateDecision", gate_primitives)
    return (
        node_id, dependencies, gate_kind, required_evidence, executor,
        routing_reason,
        gate_primitives,
        None if required_capability is None else required_capability.value,
        (
            None if required_dispatch_capability is None
            else required_dispatch_capability.value
        ),
        executor_overridable,
    )


def _snapshot_node_spec(node: NodeSpec) -> NodeSpec:
    if type(node) is not NodeSpec:
        raise invalid_policy("invalid_node_spec")
    try:
        gate = _snapshot_gate_decision(node.gate_decision)
        captured = (
            node.node_id, node.dependencies, node.gate_kind,
            node.required_evidence, node.executor, node.routing_reason, gate,
            node.required_capability, node.required_dispatch_capability,
            node.executor_overridable,
        )
        captured = _validate_capture(
            node, "NodeSpec", captured, _node_spec_primitives(captured),
        )
        return NodeSpec(
            node_id=captured[0], dependencies=captured[1], gate_kind=captured[2],
            required_evidence=captured[3], executor=captured[4],
            routing_reason=captured[5], gate_decision=captured[6],
            required_capability=captured[7],
            required_dispatch_capability=captured[8],
            executor_overridable=captured[9],
        )
    except Exception:
        raise invalid_policy("invalid_node_spec") from None


@dataclass(frozen=True)
class AttemptLedger:
    counts: Mapping[FailureReason, int] = field(default_factory=dict)
    signatures: Mapping[FailureReason, Tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        safe_counts = {}
        safe_signatures = {}
        try:
            for raw_reason, count in self.counts.items():
                reason = _normalize_enum(
                    FailureReason, raw_reason, "invalid_attempt_ledger",
                )
                if type(count) is not int or count < 0:
                    raise ValueError
                safe_counts[reason] = count
            for raw_reason, values in self.signatures.items():
                reason = _normalize_enum(
                    FailureReason, raw_reason, "invalid_attempt_ledger",
                )
                if not isinstance(values, (list, tuple)) or any(
                    type(value) is not str or not value for value in values
                ):
                    raise ValueError
                safe_signatures[reason] = tuple(values)
        except Exception:
            raise invalid_policy("invalid_attempt_ledger") from None
        for reason, history in safe_signatures.items():
            if reason not in safe_counts or len(history) > safe_counts[reason]:
                raise invalid_policy("invalid_attempt_ledger")
        object.__setattr__(self, "counts", MappingProxyType(safe_counts))
        object.__setattr__(self, "signatures", MappingProxyType(safe_signatures))
        _register_origin(
            self, "AttemptLedger",
            _attempt_ledger_primitives((self.counts, self.signatures)),
        )

    def count(self, reason: FailureReason) -> int:
        normalized = _normalize_enum(
            FailureReason, reason, "unknown_failure_reason",
        )
        return _snapshot_attempt_ledger(self).counts.get(normalized, 0)

    def history(self, reason: FailureReason) -> Tuple[str, ...]:
        normalized = _normalize_enum(
            FailureReason, reason, "unknown_failure_reason",
        )
        return _snapshot_attempt_ledger(self).signatures.get(normalized, ())


def _attempt_ledger_primitives(captured: tuple) -> tuple[object, ...]:
    counts_value, signatures_value = captured
    try:
        counts = tuple(sorted(
            (reason.value, count) for reason, count in counts_value.items()
        ))
        signatures = tuple(sorted(
            (reason.value, tuple(values))
            for reason, values in signatures_value.items()
        ))
    except Exception:
        raise ValueError from None
    if (
        any(type(reason) is not str or type(count) is not int for reason, count in counts)
        or any(
            type(reason) is not str
            or type(values) is not tuple
            or any(type(value) is not str for value in values)
            for reason, values in signatures
        )
    ):
        raise ValueError
    return counts, signatures


def _snapshot_attempt_ledger(ledger: AttemptLedger) -> AttemptLedger:
    if type(ledger) is not AttemptLedger:
        raise invalid_policy("invalid_attempt_ledger")
    try:
        captured = (ledger.counts, ledger.signatures)
        primitives = _attempt_ledger_primitives(captured)
        _validate_capture(ledger, "AttemptLedger", captured, primitives)
        counts, signatures = primitives
        return AttemptLedger(
            {FailureReason(reason): count for reason, count in counts},
            {
                FailureReason(reason): values
                for reason, values in signatures
            },
        )
    except Exception:
        raise invalid_policy("invalid_attempt_ledger") from None


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
    routes: frozenset[HostRoute] = frozenset()

    def __post_init__(self) -> None:
        _validate_host_name(self.host_name)
        try:
            raw_values = list(self.capabilities)
            converted = [
                _normalize_enum(
                    HostCapability, value, "unknown_capability_name",
                )
                for value in raw_values
            ]
        except Exception:
            raise invalid_policy("unknown_capability_name") from None
        if len(converted) != len(set(converted)):
            raise invalid_policy("duplicate_capability_name")
        values = frozenset(converted)
        if values & ROUTE_SCOPED_CAPABILITIES:
            raise invalid_policy("route_capability_requires_route")
        try:
            raw_routes = list(self.routes)
            routes = frozenset(_snapshot_host_route(route) for route in raw_routes)
        except Exception:
            raise invalid_policy("invalid_host_route") from None
        if len(raw_routes) != len(routes):
            raise invalid_policy("duplicate_host_route")
        if type(self.transition_model_version) is not int or self.transition_model_version != 1:
            raise invalid_policy("unsupported_transition_model_version")
        if type(self.evidence_model_version) is not int or self.evidence_model_version != 1:
            raise invalid_policy("unsupported_evidence_model_version")
        derived = set(values)
        for route in routes:
            derived.add(route.capability)
            derived.add(DISPATCH_RAIL_CAPABILITIES[route.rail])
        object.__setattr__(self, "capabilities", frozenset(derived))
        object.__setattr__(self, "routes", routes)
        _register_origin(
            self, "HostCapabilities",
            _host_capabilities_primitives(
                self.host_name, self.capabilities,
                self.transition_model_version, self.evidence_model_version,
                tuple(routes),
            ),
        )

    def supports(self, capability: HostCapability) -> bool:
        snapshot = _snapshot_host_capabilities(self)
        capability = _normalize_enum(
            HostCapability, capability, "unknown_capability_name",
        )
        return capability in snapshot.capabilities

    def supports_route(self, route: HostRoute) -> bool:
        snapshot = _snapshot_host_capabilities(self)
        candidate = _snapshot_host_route(route)
        return candidate in snapshot.routes


def _snapshot_host_capabilities(capabilities: HostCapabilities) -> HostCapabilities:
    if type(capabilities) is not HostCapabilities:
        raise invalid_policy("invalid_host_capabilities")
    try:
        captured = (
            capabilities.host_name, capabilities.capabilities,
            capabilities.transition_model_version,
            capabilities.evidence_model_version, capabilities.routes,
        )
        if (
            type(captured[0]) is not str
            or type(captured[1]) is not frozenset
            or type(captured[2]) is not int
            or type(captured[3]) is not int
            or type(captured[4]) is not frozenset
        ):
            raise ValueError
        routes = tuple(
            _snapshot_host_route(route) for route in captured[4]
        )
        captured = captured[:4] + (routes,)
        primitives = _host_capabilities_primitives(
            captured[0], captured[1], captured[2], captured[3], captured[4],
        )
        captured = _validate_capture(
            capabilities, "HostCapabilities", captured, primitives,
        )
        return HostCapabilities(
            captured[0], captured[1] - ROUTE_SCOPED_CAPABILITIES,
            captured[2], captured[3], frozenset(captured[4]),
        )
    except Exception:
        raise invalid_policy("invalid_host_capabilities") from None


def _host_capabilities_primitives(
    host_name: object,
    capabilities: object,
    transition_version: object,
    evidence_version: object,
    routes: tuple[HostRoute, ...],
) -> tuple[object, ...]:
    if (
        type(host_name) is not str
        or type(capabilities) is not frozenset
        or any(type(value) is not HostCapability for value in capabilities)
        or type(transition_version) is not int
        or type(evidence_version) is not int
        or type(routes) is not tuple
    ):
        raise ValueError
    route_values = []
    for route in routes:
        if type(route) is not HostRoute:
            raise ValueError
        route_value = (route.provider, route.capability.value, route.rail)
        _validate_origin(route, "HostRoute", route_value)
        route_values.append(route_value)
    return (
        host_name,
        tuple(sorted(value.value for value in capabilities)),
        transition_version,
        evidence_version,
        tuple(sorted(route_values)),
    )


@dataclass(frozen=True)
class IsolationRequirements:
    preferred: IsolationMode
    allow_degradation: bool = True

    def __post_init__(self) -> None:
        preferred = _normalize_enum(
            IsolationMode, self.preferred, "unknown_isolation_mode",
        )
        if type(self.allow_degradation) is not bool:
            raise invalid_policy("invalid_isolation_requirements")
        object.__setattr__(self, "preferred", preferred)
        _register_origin(
            self, "IsolationRequirements", (preferred.value, self.allow_degradation),
        )


def _snapshot_isolation_requirements(
    requirements: IsolationRequirements,
) -> IsolationRequirements:
    if type(requirements) is not IsolationRequirements:
        raise invalid_policy("invalid_isolation_requirements")
    try:
        captured = (requirements.preferred, requirements.allow_degradation)
        if (
            type(captured[0]) is not IsolationMode
            or type(captured[1]) is not bool
        ):
            raise ValueError
        captured = _validate_capture(
            requirements, "IsolationRequirements", captured,
            (captured[0].value, captured[1]),
        )
        return IsolationRequirements(*captured)
    except Exception:
        raise invalid_policy("invalid_isolation_requirements") from None


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
        for name in ("run_id", "node_id", "attempt_id"):
            value = getattr(self, name)
            if (
                type(value) is not str
                or len(value) > MAX_STRING_LENGTH
                or _CONTEXT_ID.fullmatch(value) is None
            ):
                raise invalid_policy("invalid_session_resume_context")
        try:
            route = HostRoute(self.provider, self.capability, self.rail)
        except InvalidSchemaError:
            raise invalid_policy("invalid_session_resume_context") from None
        object.__setattr__(self, "provider", route.provider)
        object.__setattr__(self, "rail", route.rail)
        object.__setattr__(self, "capability", route.capability)
        captured = (
            self.run_id, self.node_id, self.attempt_id, self.provider,
            self.rail, self.capability,
        )
        _register_origin(
            self, "ResumeStateContext", _resume_context_primitives(captured),
        )

    @property
    def route(self) -> HostRoute:
        context = _snapshot_resume_context(self)
        return HostRoute(context.provider, context.capability, context.rail)

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
        captured = (
            context.run_id, context.node_id, context.attempt_id,
            context.provider, context.rail, context.capability,
        )
        captured = _validate_capture(
            context, "ResumeStateContext", captured,
            _resume_context_primitives(captured),
        )
        return ResumeStateContext(*captured)
    except Exception:
        raise invalid_policy("invalid_session_resume_context") from None


def _resume_context_primitives(
    captured: tuple,
) -> tuple[str, str, str, str, str, str]:
    run_id, node_id, attempt_id, provider, rail, capability = captured
    if (
        type(run_id) is not str
        or type(node_id) is not str
        or type(attempt_id) is not str
        or type(provider) is not str
        or type(rail) is not str
        or type(capability) is not HostCapability
    ):
        raise ValueError
    return run_id, node_id, attempt_id, provider, rail, capability.value


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
        captured = (
            self.host_name, self.opaque_handle, self.created_at,
            self.resume_capable, self.context,
        )
        _register_origin(
            self, "SessionHandle", _session_handle_primitives(captured),
        )

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
        context = _snapshot_resume_context(handle.context)
        captured = (
            handle.host_name, handle.opaque_handle, handle.created_at,
            handle.resume_capable, context,
        )
        captured = _validate_capture(
            handle, "SessionHandle", captured,
            _session_handle_primitives(captured),
        )
        return SessionHandle(
            host_name=captured[0], opaque_handle=captured[1],
            created_at=captured[2], resume_capable=captured[3],
            context=captured[4],
        )
    except Exception:
        raise invalid_policy("invalid_session_handle") from None


def _session_handle_primitives(captured: tuple) -> tuple[object, ...]:
    host_name, opaque_handle, created_at, resume_capable, context_value = captured
    if (
        type(host_name) is not str
        or type(opaque_handle) is not str
        or type(created_at) is not str
        or type(resume_capable) is not bool
        or type(context_value) is not ResumeStateContext
    ):
        raise ValueError
    context_captured = (
        context_value.run_id, context_value.node_id, context_value.attempt_id,
        context_value.provider, context_value.rail, context_value.capability,
    )
    context = _resume_context_primitives(context_captured)
    _validate_origin(context_value, "ResumeStateContext", context)
    return (
        host_name,
        len(opaque_handle),
        hashlib.sha256(opaque_handle.encode("utf-8")).hexdigest(),
        created_at,
        resume_capable,
        context,
    )


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
        captured = (self.node_id, self.reason_code, self.evidence)
        _register_origin(
            self, "ValidationFeedback",
            _validation_feedback_primitives(captured),
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
        captured = (feedback.node_id, feedback.reason_code, feedback.evidence)
        captured = _validate_capture(
            feedback, "ValidationFeedback", captured,
            _validation_feedback_primitives(captured),
        )
        return ValidationFeedback(*captured)
    except Exception:
        raise invalid_policy("invalid_validation_feedback") from None


def _validation_feedback_primitives(
    captured: tuple,
) -> tuple[object, ...]:
    node_id, reason_code, evidence = captured
    if (
        type(node_id) is not str
        or type(reason_code) is not str
        or type(evidence) is not tuple
        or any(type(value) is not str for value in evidence)
    ):
        raise ValueError
    return captured


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
    except Exception:
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
        status = _normalize_enum(
            SessionStatus, self.status, "invalid_session_result",
        )
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
        captured = (
            self.status, self.context, self.evidence, self.reason_code,
        )
        _register_origin(
            self, "SessionResult", _session_result_primitives(captured),
        )

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
        context = _snapshot_resume_context(result.context)
        captured = (
            result.status, context, result.evidence, result.reason_code,
        )
        captured = _validate_capture(
            result, "SessionResult", captured,
            _session_result_primitives(captured),
        )
        return SessionResult(*captured)
    except Exception:
        raise invalid_policy("invalid_session_result") from None


def _session_result_primitives(captured: tuple) -> tuple[object, ...]:
    status, context_value, evidence, reason_code = captured
    if (
        type(status) is not SessionStatus
        or type(context_value) is not ResumeStateContext
        or type(evidence) is not tuple
        or any(type(value) is not str for value in evidence)
        or reason_code is not None and type(reason_code) is not str
    ):
        raise ValueError
    context_captured = (
        context_value.run_id, context_value.node_id, context_value.attempt_id,
        context_value.provider, context_value.rail, context_value.capability,
    )
    context = _resume_context_primitives(context_captured)
    _validate_origin(context_value, "ResumeStateContext", context)
    return status.value, context, evidence, reason_code


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
        _register_origin(
            self, "ResumeStateBlob", _resume_blob_primitives(self._payload),
        )

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
        captured = (payload,)
        captured = _validate_capture(
            blob, "ResumeStateBlob", captured, _resume_blob_primitives(payload),
        )
        return bytes(captured[0])
    except Exception:
        raise invalid_policy("invalid_session_resume_state") from None


def _resume_blob_primitives(payload: bytes) -> tuple[int, str]:
    if type(payload) is not bytes:
        raise ValueError
    return len(payload), hashlib.sha256(payload).hexdigest()


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
    context: ResumeStateContext
    handle: Optional[SessionHandle] = None
    result: Optional[SessionResult] = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("BuilderSessionDecision is final")

    def __post_init__(self) -> None:
        outcome = _normalize_enum(
            BuilderOutcome, self.outcome, "invalid_builder_session_decision",
        )
        if type(self.context) is not ResumeStateContext:
            raise invalid_policy("invalid_builder_session_decision")
        object.__setattr__(self, "context", _snapshot_resume_context(self.context))
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
        if self.handle is not None and self.handle.context != self.context:
            raise invalid_policy("invalid_builder_session_decision")
        if self.result is not None and self.result.context != self.context:
            raise invalid_policy("invalid_builder_session_decision")
        captured = (self.outcome, self.context, self.handle, self.result)
        _register_origin(
            self, "BuilderSessionDecision",
            _builder_decision_primitives(captured),
        )

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
            "BuilderSessionDecision(outcome={!r}, context={!r}, handle={!r}, result={!r})"
        ).format(decision.outcome, decision.context, decision.handle, decision.result)

    def to_evidence_event(
        self, *, run_id: str, sequence: int, node_id: str, occurred_at: str,
    ) -> WorkflowEvent:
        """Project observations only into Chunk01's legal evidence vocabulary.

        A downstream translator must also require an authoritative receipt
        reference and safely merge ``result.evidence`` when a result exists.
        This helper never fabricates that receipt or treats observations as it.
        """
        facts, decision = _snapshot_builder_decision(self)
        if not _safe_equal(
            run_id, decision.context.run_id,
            "invalid_builder_session_event_context",
        ) or not _safe_equal(
            node_id, decision.context.node_id,
            "invalid_builder_session_event_context",
        ):
            raise invalid_policy("invalid_builder_session_event_context")
        return WorkflowEvent(
            1, sequence, run_id, node_id, "evidence.recorded", occurred_at,
            {"evidence": [value.evidence_reference for value in facts[3]]},
        )


def _snapshot_builder_decision(
    decision: BuilderSessionDecision,
) -> tuple[tuple, BuilderSessionDecision]:
    if type(decision) is not BuilderSessionDecision:
        raise invalid_policy("invalid_builder_session_decision")
    try:
        parent = (
            decision.outcome, decision.context, decision.handle,
            decision.result,
        )
        outcome_value, context_value, handle_value, result_value = parent
        context = _snapshot_resume_context(context_value)
        handle = (
            None if handle_value is None
            else _snapshot_session_handle(handle_value)
        )
        result = (
            None if result_value is None
            else _snapshot_session_result(result_value)
        )
        captured = (outcome_value, context, handle, result)
        captured = _validate_capture(
            decision, "BuilderSessionDecision", captured,
            _builder_decision_primitives(captured),
        )
        outcome = captured[0]
        facts = _OUTCOME_FACTS.get(outcome)
        if facts is None:
            raise ValueError
        snapshot = BuilderSessionDecision(*captured)
        return facts, snapshot
    except Exception:
        raise invalid_policy("invalid_builder_session_decision") from None


def _builder_decision_primitives(
    captured: tuple,
) -> tuple[object, ...]:
    outcome, context_value, handle_value, result_value = captured
    if (
        type(outcome) is not BuilderOutcome
        or type(context_value) is not ResumeStateContext
        or handle_value is not None and type(handle_value) is not SessionHandle
        or result_value is not None and type(result_value) is not SessionResult
    ):
        raise ValueError
    context_capture = (
        context_value.run_id, context_value.node_id, context_value.attempt_id,
        context_value.provider, context_value.rail, context_value.capability,
    )
    context = _resume_context_primitives(context_capture)
    _validate_origin(context_value, "ResumeStateContext", context)
    handle = None
    if handle_value is not None:
        handle_capture = (
            handle_value.host_name, handle_value.opaque_handle,
            handle_value.created_at, handle_value.resume_capable,
            handle_value.context,
        )
        handle = _session_handle_primitives(handle_capture)
        _validate_origin(handle_value, "SessionHandle", handle)
    result = None
    if result_value is not None:
        result_capture = (
            result_value.status, result_value.context, result_value.evidence,
            result_value.reason_code,
        )
        result = _session_result_primitives(result_capture)
        _validate_origin(result_value, "SessionResult", result)
    return outcome.value, context, handle, result


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
