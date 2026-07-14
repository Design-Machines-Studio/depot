"""Versioned retry, gate, and degradation policy decisions."""

from __future__ import annotations

import json
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .adapters.base import (
    AttemptLedger, FailureReason, GATE_KINDS, GateDecision, HostCapability,
    IsolationMode, RetryDecision, WorkflowClass, WorkflowContext,
    _normalize_enum,
    _register_origin, _snapshot_attempt_ledger, _snapshot_workflow_context,
    _validate_capture, invalid_policy, normalize_executor_constraint,
)
from .schema import InvalidSchemaError
from .redaction import MAX_PAYLOAD_DEPTH, MAX_PAYLOAD_ITEMS


POLICY_SCHEMA_VERSION = 1
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "workflow-policy.json"
_MAPPING_PROXY_TYPE = type(MappingProxyType({}))
_MALFORMED_POLICY_VALUE = object()


class _TrustedPolicyMap(tuple, MappingABC):
    """Exact, tuple-backed mapping created only from normalized policy data."""

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("_TrustedPolicyMap is final")

    def __new__(cls, values: dict):
        if type(values) is not dict:
            raise TypeError
        return tuple.__new__(cls, tuple(values.items()))

    def __len__(self) -> int:
        return tuple.__len__(self)

    def __iter__(self):
        return (pair[0] for pair in _trusted_policy_items(self))

    def __getitem__(self, key: object) -> object:
        for candidate, value in _trusted_policy_items(self):
            if candidate == key:
                return value
        raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        return any(candidate == key for candidate, _ in _trusted_policy_items(self))

    def __eq__(self, other: object) -> bool:
        return MappingABC.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        equal = self.__eq__(other)
        return equal if equal is NotImplemented else not equal

    __hash__ = None


def _trusted_policy_items(value: object) -> tuple:
    if type(value) is not _TrustedPolicyMap:
        raise ValueError
    items = tuple.__getitem__(value, slice(None))
    if type(items) is not tuple or any(
        type(pair) is not tuple or len(pair) != 2 for pair in items
    ):
        raise ValueError
    return items


def _classify_policy_value(value: object) -> str:
    """Return the single exact-type taxonomy used by policy traversals."""
    value_type = type(value)
    if value is None or value_type in {bool, int, str}:
        return "scalar"
    if value_type in {
        FailureReason, HostCapability, IsolationMode, WorkflowClass,
    }:
        return "enum"
    if value_type is dict:
        return "dict"
    if value_type is list:
        return "list"
    if value_type is tuple:
        return "tuple"
    if value_type is set:
        return "set"
    if value_type is frozenset:
        return "frozenset"
    if value_type is _TrustedPolicyMap:
        return "trusted_map"
    if value_type is _MAPPING_PROXY_TYPE:
        return "untrusted_mappingproxy"
    return "other"


_POLICY_CONTAINER_KINDS = frozenset({
    "dict", "list", "tuple", "set", "frozenset", "trusted_map",
})


class _PolicyTraversal:
    def __init__(self) -> None:
        self.count = 0
        self.active = set()

    def enter(self, value: object, depth: int) -> tuple[str, Optional[int]]:
        if depth > MAX_PAYLOAD_DEPTH:
            raise ValueError
        self.count += 1
        if self.count > MAX_PAYLOAD_ITEMS:
            raise ValueError
        kind = _classify_policy_value(value)
        identity = None
        if kind in _POLICY_CONTAINER_KINDS:
            identity = id(value)
            if identity in self.active:
                raise ValueError
            self.active.add(identity)
        return kind, identity

    def leave(self, identity: Optional[int]) -> None:
        if identity is not None:
            self.active.remove(identity)


@dataclass(frozen=True)
class PolicyDocument:
    retry_budgets: Mapping[FailureReason, int]
    identical_signature_limit: int
    risk_human_approval: Tuple[str, ...]
    isolation_order: Tuple[IsolationMode, ...]
    forbidden_downgrades: frozenset[tuple[IsolationMode, IsolationMode]]
    workflow_safety_anchor: Mapping[str, object]
    economics_mode: str

    def __post_init__(self) -> None:
        captured = (
            self.retry_budgets, self.identical_signature_limit,
            self.risk_human_approval, self.isolation_order,
            self.forbidden_downgrades, self.workflow_safety_anchor,
            self.economics_mode,
        )
        try:
            primitives = _policy_origin_primitives(captured)
        except Exception:
            raise invalid_policy("invalid_policy_document") from None
        _register_origin(
            self, "PolicyDocument", primitives,
        )


def _policy_origin_primitives(
    value: object, *, _state: Optional[_PolicyTraversal] = None, _depth: int = 0,
) -> tuple:
    """Capture policy structure without executing caller-defined behavior."""
    state = _state if _state is not None else _PolicyTraversal()
    kind, identity = state.enter(value, _depth)
    try:
        if kind == "scalar":
            return ("none",) if value is None else (type(value).__name__, value)
        if kind == "enum":
            return ("enum", id(type(value)), value.value)
        if kind in {"dict", "trusted_map"}:
            items = value.items() if kind == "dict" else _trusted_policy_items(value)
            return (
                kind,
                tuple(
                    (
                        _policy_origin_primitives(
                            key, _state=state, _depth=_depth + 1,
                        ),
                        _policy_origin_primitives(
                            item, _state=state, _depth=_depth + 1,
                        ),
                    )
                    for key, item in items
                ),
            )
        if kind in {"list", "tuple"}:
            return (
                kind,
                tuple(
                    _policy_origin_primitives(
                        item, _state=state, _depth=_depth + 1,
                    )
                    for item in value
                ),
            )
        if kind in {"set", "frozenset"}:
            return (
                kind,
                frozenset(
                    _policy_origin_primitives(
                        item, _state=state, _depth=_depth + 1,
                    )
                    for item in value
                ),
            )
        return (kind, id(type(value)), id(value))
    finally:
        state.leave(identity)


def _exact_keys(value: object, expected: set[str], reason: str) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise invalid_policy(reason)
    return value


def _safety_stage(value: object) -> Mapping[str, object]:
    value = _exact_keys(value, {
        "id", "gate_kind", "required_evidence", "executor",
        "required_capability", "required_dispatch_capability",
        "executor_overridable", "required_ancestors",
    }, "invalid_workflow_safety_anchor")
    if type(value["id"]) is not str or not value["id"]:
        raise invalid_policy("invalid_workflow_safety_anchor")
    gate_kind = value["gate_kind"]
    if gate_kind is not None and (
        type(gate_kind) is not str or gate_kind not in GATE_KINDS
    ):
        raise invalid_policy("invalid_workflow_safety_anchor")
    normalized_lists = {}
    for field in ("required_evidence", "required_ancestors"):
        items = value[field]
        if type(items) is not list or any(
            type(item) is not str or not item for item in items
        ) or len(items) != len(set(items)):
            raise invalid_policy("invalid_workflow_safety_anchor")
        normalized_lists[field] = tuple(items)
    if gate_kind not in (None, "cleanup") and not normalized_lists["required_evidence"]:
        raise invalid_policy("invalid_workflow_safety_anchor")
    try:
        executor, capability, dispatch = normalize_executor_constraint(
            value["executor"], value["required_capability"],
            value["required_dispatch_capability"],
        )
    except Exception:
        raise invalid_policy("invalid_workflow_safety_anchor") from None
    if type(value["executor_overridable"]) is not bool or (
        executor is None and value["executor_overridable"]
    ):
        raise invalid_policy("invalid_workflow_safety_anchor")
    return _TrustedPolicyMap({
        "id": value["id"],
        "gate_kind": gate_kind,
        "required_evidence": normalized_lists["required_evidence"],
        "executor": executor,
        "required_capability": capability,
        "required_dispatch_capability": dispatch,
        "executor_overridable": value["executor_overridable"],
        "required_ancestors": normalized_lists["required_ancestors"],
    })


def _safety_stage_set(value: object) -> tuple[Mapping[str, object], ...]:
    value = _exact_keys(value, {"stages"}, "invalid_workflow_safety_anchor")
    if type(value["stages"]) is not list or not value["stages"]:
        raise invalid_policy("invalid_workflow_safety_anchor")
    stages = tuple(_safety_stage(stage) for stage in value["stages"])
    if len({stage["id"] for stage in stages}) != len(stages):
        raise invalid_policy("invalid_workflow_safety_anchor")
    return stages


def _workflow_safety_anchor(value: object) -> Mapping[str, object]:
    value = _exact_keys(
        value, {
            "schema_version", "common", "classes", "promotion",
            "non_executable_classes",
        },
        "invalid_workflow_safety_anchor",
    )
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise invalid_policy("unsupported_safety_anchor_version")
    classes = _exact_keys(
        value["classes"], {"hotfix", "security", "migration"},
        "invalid_workflow_safety_anchor",
    )
    promotion = _exact_keys(
        value["promotion"], {"investigation"},
        "invalid_workflow_safety_anchor",
    )
    if type(value["non_executable_classes"]) is not list:
        raise invalid_policy("invalid_workflow_safety_anchor")
    try:
        non_executable_classes = tuple(
            _normalize_enum(
                WorkflowClass, name, "invalid_workflow_safety_anchor",
            )
            for name in value["non_executable_classes"]
        )
    except Exception:
        raise invalid_policy("invalid_workflow_safety_anchor") from None
    if non_executable_classes != (WorkflowClass.INVESTIGATION,):
        raise invalid_policy("invalid_workflow_safety_anchor")
    return _TrustedPolicyMap({
        "schema_version": 1,
        "common": _safety_stage_set(value["common"]),
        "classes": _TrustedPolicyMap({
            _normalize_enum(
                WorkflowClass, name, "invalid_workflow_safety_anchor",
            ): _safety_stage_set(stage_set)
            for name, stage_set in classes.items()
        }),
        "promotion": _TrustedPolicyMap({
            name: _safety_stage_set(stage_set)
            for name, stage_set in promotion.items()
        }),
        "non_executable_classes": non_executable_classes,
    })


def _plain_policy_value(
    value: object, *, _state: Optional[_PolicyTraversal] = None, _depth: int = 0,
) -> object:
    """Project trusted policy values without traversing caller-defined types."""
    state = _state if _state is not None else _PolicyTraversal()
    kind, identity = state.enter(value, _depth)
    try:
        if kind == "scalar":
            return value
        if kind == "enum":
            return value.value
        if kind in {"dict", "trusted_map"}:
            items = value.items() if kind == "dict" else _trusted_policy_items(value)
            result = {}
            for key, item in items:
                projected_key = _plain_policy_value(
                    key, _state=state, _depth=_depth + 1,
                )
                projected_item = _plain_policy_value(
                    item, _state=state, _depth=_depth + 1,
                )
                if type(projected_key) is not str:
                    return _MALFORMED_POLICY_VALUE
                result[projected_key] = projected_item
            return result
        if kind in {"list", "tuple"}:
            return [
                _plain_policy_value(
                    item, _state=state, _depth=_depth + 1,
                )
                for item in value
            ]
        return value
    finally:
        state.leave(identity)


def _stage_set_payload(value: object) -> dict:
    if type(value) is dict and set(value) == {"stages"}:
        return value
    return {"stages": value}


def _safety_anchor_payload(
    value: object, state: _PolicyTraversal, depth: int,
) -> object:
    """Project normalized or malformed injected anchor state without validating."""
    anchor = _plain_policy_value(value, _state=state, _depth=depth)
    if type(anchor) is not dict:
        return anchor
    result = dict(anchor)
    if "common" in result:
        result["common"] = _stage_set_payload(result["common"])
    for name in ("classes", "promotion"):
        groups = result.get(name)
        if type(groups) is dict:
            result[name] = {
                key: _stage_set_payload(stage_set)
                for key, stage_set in groups.items()
            }
    return result


def _policy_document_payload(captured: tuple) -> dict:
    (
        retry_budgets, identical_signature_limit, risk_human_approval,
        isolation_order, forbidden_downgrades, workflow_safety_anchor,
        economics_mode,
    ) = captured
    state = _PolicyTraversal()
    if _classify_policy_value(forbidden_downgrades) == "frozenset":
        kind, identity = state.enter(forbidden_downgrades, 1)
        forbidden = []
        try:
            if kind != "frozenset":
                raise ValueError
            for item in forbidden_downgrades:
                item_kind, item_identity = state.enter(item, 2)
                try:
                    if item_kind == "tuple":
                        projected = [
                            _plain_policy_value(
                                member, _state=state, _depth=3,
                            )
                            for member in tuple.__iter__(item)
                        ]
                        if len(projected) == 2:
                            forbidden.append({
                                "from": projected[0],
                                "to": projected[1],
                            })
                        else:
                            forbidden.append(projected)
                    elif item_kind == "enum":
                        forbidden.append(item.value)
                    else:
                        forbidden.append(item)
                finally:
                    state.leave(item_identity)
        finally:
            state.leave(identity)
    else:
        forbidden = _plain_policy_value(
            forbidden_downgrades, _state=state, _depth=1,
        )
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "retry": {
            "budgets": _plain_policy_value(
                retry_budgets, _state=state, _depth=1,
            ),
            "identical_signature_limit": _plain_policy_value(
                identical_signature_limit, _state=state, _depth=1,
            ),
        },
        "gates": {
            "risk_human_approval": _plain_policy_value(
                risk_human_approval, _state=state, _depth=1,
            ),
        },
        "isolation": {
            "order": _plain_policy_value(
                isolation_order, _state=state, _depth=1,
            ),
            "forbidden_downgrades": forbidden,
        },
        "capability_names": [value.value for value in HostCapability],
        "workflow_safety_anchor": _safety_anchor_payload(
            workflow_safety_anchor, state, 1,
        ),
        "economics": {"mode": _plain_policy_value(
            economics_mode, _state=state, _depth=1,
        )},
    }


def _snapshot_policy_document(document: PolicyDocument) -> PolicyDocument:
    if type(document) is not PolicyDocument:
        raise invalid_policy("invalid_policy_document")
    try:
        captured = (
            document.retry_budgets, document.identical_signature_limit,
            document.risk_human_approval, document.isolation_order,
            document.forbidden_downgrades, document.workflow_safety_anchor,
            document.economics_mode,
        )
        origin = _policy_origin_primitives(captured)
        payload = _policy_document_payload(captured)
        normalization_error = None
        try:
            normalized = _normalize_policy_payload(payload)
        except InvalidSchemaError as error:
            normalization_error = error
            normalized = None
        _validate_capture(
            document, "PolicyDocument", captured, origin,
        )
        if normalization_error is not None:
            raise normalization_error
        return normalized
    except InvalidSchemaError:
        raise
    except Exception:
        raise invalid_policy("invalid_policy_document") from None


def _normalize_policy_payload(payload: object) -> PolicyDocument:
    try:
        _policy_origin_primitives(payload)
    except Exception:
        raise invalid_policy("invalid_policy_document") from None
    payload = _exact_keys(payload, {
        "schema_version", "retry", "gates", "isolation", "capability_names",
        "workflow_safety_anchor", "economics",
    }, "invalid_policy_document")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != POLICY_SCHEMA_VERSION:
        raise invalid_policy("unsupported_policy_version")

    retry = _exact_keys(payload["retry"], {"budgets", "identical_signature_limit"},
                        "invalid_retry_policy")
    budgets = _exact_keys(retry["budgets"], {reason.value for reason in FailureReason},
                          "invalid_retry_policy")
    safe_budgets = {}
    for reason in FailureReason:
        budget = budgets[reason.value]
        if type(budget) is not int or budget < 0:
            raise invalid_policy("invalid_retry_budget")
        safe_budgets[reason] = budget
    convergence_limit = retry["identical_signature_limit"]
    if type(convergence_limit) is not int or convergence_limit < 2:
        raise invalid_policy("invalid_convergence_limit")

    gates = _exact_keys(payload["gates"], {"risk_human_approval"}, "invalid_gate_policy")
    risk_values = gates["risk_human_approval"]
    if type(risk_values) is not list or any(
        type(value) is not str or value not in ("low", "medium", "high", "critical")
        for value in risk_values
    ) or len(risk_values) != len(set(risk_values)):
        raise invalid_policy("invalid_gate_policy")

    isolation = _exact_keys(payload["isolation"], {"order", "forbidden_downgrades"},
                            "invalid_isolation_policy")
    if type(isolation["order"]) is not list:
        raise invalid_policy("invalid_isolation_order")
    try:
        order = tuple(
            _normalize_enum(IsolationMode, value, "unknown_isolation_mode")
            for value in isolation["order"]
        )
    except InvalidSchemaError:
        raise
    except Exception:
        raise invalid_policy("unknown_isolation_mode") from None
    if len(order) != len(IsolationMode) or set(order) != set(IsolationMode):
        raise invalid_policy("invalid_isolation_order")
    forbidden = set()
    if type(isolation["forbidden_downgrades"]) is not list:
        raise invalid_policy("invalid_isolation_policy")
    for item in isolation["forbidden_downgrades"]:
        item = _exact_keys(item, {"from", "to"}, "invalid_isolation_policy")
        try:
            forbidden.add((
                _normalize_enum(
                    IsolationMode, item["from"], "unknown_isolation_mode",
                ),
                _normalize_enum(
                    IsolationMode, item["to"], "unknown_isolation_mode",
                ),
            ))
        except InvalidSchemaError:
            raise
        except Exception:
            raise invalid_policy("unknown_isolation_mode") from None

    capability_names = payload["capability_names"]
    if type(capability_names) is not list or any(type(value) is not str for value in capability_names):
        raise invalid_policy("unknown_capability_name")
    if len(capability_names) != len(set(capability_names)):
        raise invalid_policy("duplicate_capability_name")
    try:
        declared_capabilities = {
            _normalize_enum(
                HostCapability, value, "unknown_capability_name",
            )
            for value in capability_names
        }
    except InvalidSchemaError:
        raise
    except Exception:
        raise invalid_policy("unknown_capability_name") from None
    if declared_capabilities != set(HostCapability):
        raise invalid_policy("unknown_capability_name")

    economics = _exact_keys(payload["economics"], {"mode"}, "invalid_economics_policy")
    if type(economics["mode"]) is not str or economics["mode"] != "proposal_only":
        raise invalid_policy("economics_must_be_proposal_only")
    return PolicyDocument(
        _TrustedPolicyMap(safe_budgets), convergence_limit, tuple(risk_values), order,
        frozenset(forbidden), _workflow_safety_anchor(payload["workflow_safety_anchor"]),
        economics["mode"],
    )


def load_policy(path: Optional[Path] = None) -> PolicyDocument:
    source = Path(path) if path is not None else DEFAULT_POLICY_PATH
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise invalid_policy("invalid_policy_json") from None
    try:
        return _normalize_policy_payload(payload)
    except InvalidSchemaError:
        raise
    except Exception:
        raise invalid_policy("invalid_policy_document") from None


class RetryPolicy:
    def __init__(self, path: Optional[Path] = None):
        self._policy = load_policy(path)

    @property
    def economics_mode(self) -> str:
        return self._policy.economics_mode

    def decide(
        self,
        reason: FailureReason,
        attempts: AttemptLedger,
        signature: Optional[str],
    ) -> RetryDecision:
        normalized = _normalize_enum(
            FailureReason, reason, "unknown_failure_reason",
        )
        try:
            attempts = _snapshot_attempt_ledger(attempts)
        except Exception:
            raise invalid_policy("invalid_attempt_ledger") from None
        if signature is not None and (type(signature) is not str or not signature):
            raise invalid_policy("invalid_failure_signature")
        count = attempts.counts.get(normalized, 0)
        budget = self._policy.retry_budgets[normalized]
        history = attempts.signatures.get(normalized, ())
        prior = history[-1] if history else None
        trailing = 0
        if signature is not None:
            for candidate in reversed(history):
                if candidate != signature:
                    break
                trailing += 1
        if signature is not None and prior == signature and trailing >= self._policy.identical_signature_limit:
            return RetryDecision(
                False, "identical_failure_convergence", budget, count, prior,
            )
        if count >= budget:
            return RetryDecision(False, "retry_budget_exhausted", budget, count, prior)
        return RetryDecision(True, "retry_allowed", budget, count, prior)


class GatePolicy:
    def __init__(
        self,
        path: Optional[Path] = None,
        *,
        policy_document: Optional[PolicyDocument] = None,
    ):
        if policy_document is not None:
            if path is not None or type(policy_document) is not PolicyDocument:
                raise invalid_policy("invalid_policy_document")
            self._policy = _snapshot_policy_document(policy_document)
        else:
            self._policy = load_policy(path)

    def decide(
        self,
        workflow_class: WorkflowClass,
        gate_kind: Optional[str],
        required_evidence: Tuple[str, ...],
        context: WorkflowContext,
    ) -> GateDecision:
        if type(workflow_class) is not WorkflowClass or type(context) is not WorkflowContext:
            raise invalid_policy("invalid_gate_context")
        try:
            context = _snapshot_workflow_context(context)
        except Exception:
            raise invalid_policy("invalid_gate_context") from None
        if gate_kind is not None and (
            type(gate_kind) is not str or gate_kind not in GATE_KINDS
        ):
            raise invalid_policy("unknown_gate_kind")
        try:
            if not isinstance(required_evidence, (list, tuple)) or any(
                type(value) is not str or not value
                for value in required_evidence
            ):
                raise ValueError
            required_evidence = tuple(required_evidence)
        except Exception:
            raise invalid_policy("invalid_gate_evidence") from None
        if len(required_evidence) != len(set(required_evidence)):
            raise invalid_policy("invalid_gate_evidence")
        if gate_kind is None and required_evidence:
            raise invalid_policy("inconsistent_gate_decision")
        if gate_kind is None:
            return GateDecision(True, "gate_not_required")
        missing = tuple(value for value in required_evidence if value not in context.evidence)
        if missing:
            return GateDecision(False, "missing_mandatory_evidence", missing)
        human_required = (
            gate_kind == "human_approval"
            or gate_kind == "investigation_promotion"
            or (gate_kind == "risk" and context.risk in self._policy.risk_human_approval)
        )
        approved = context.promotion_approved if gate_kind == "investigation_promotion" else context.human_approved
        if human_required and not approved:
            return GateDecision(False, "human_approval_required", (), True)
        return GateDecision(True, "gate_satisfied", (), human_required)
