"""Versioned retry, gate, and degradation policy decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .adapters.base import (
    AttemptLedger, FailureReason, GATE_KINDS, GateDecision, HostCapability,
    IsolationMode, RetryDecision, WorkflowClass, WorkflowContext,
    _register_origin, _snapshot_attempt_ledger, _snapshot_workflow_context,
    _validate_origin, invalid_policy, normalize_executor_constraint,
)
from .schema import InvalidSchemaError


POLICY_SCHEMA_VERSION = 1
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "workflow-policy.json"


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
        try:
            digest = _policy_document_digest(self)
        except Exception:
            raise invalid_policy("invalid_policy_document") from None
        _register_origin(self, "PolicyDocument", digest)


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
        if not isinstance(items, list) or any(
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
    return MappingProxyType({
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
    if not isinstance(value["stages"], list) or not value["stages"]:
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
    try:
        non_executable_classes = tuple(
            WorkflowClass(name) for name in value["non_executable_classes"]
        )
    except Exception:
        raise invalid_policy("invalid_workflow_safety_anchor") from None
    if (
        type(value["non_executable_classes"]) is not list
        or non_executable_classes != (WorkflowClass.INVESTIGATION,)
    ):
        raise invalid_policy("invalid_workflow_safety_anchor")
    return MappingProxyType({
        "schema_version": 1,
        "common": _safety_stage_set(value["common"]),
        "classes": MappingProxyType({
            WorkflowClass(name): _safety_stage_set(stage_set)
            for name, stage_set in classes.items()
        }),
        "promotion": MappingProxyType({
            name: _safety_stage_set(stage_set)
            for name, stage_set in promotion.items()
        }),
        "non_executable_classes": non_executable_classes,
    })


def _plain_policy_value(value: object) -> object:
    if type(value) in {FailureReason, HostCapability, IsolationMode, WorkflowClass}:
        return value.value
    if isinstance(value, Mapping):
        return {
            _plain_policy_value(key): _plain_policy_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain_policy_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_plain_policy_value(item) for item in value),
            key=lambda item: repr(item),
        )
    return value


def _stage_set_payload(value: object) -> dict:
    return {"stages": _plain_policy_value(value)}


def _policy_document_payload(document: PolicyDocument) -> dict:
    anchor = document.workflow_safety_anchor
    classes = anchor["classes"]
    promotion = anchor["promotion"]
    forbidden = []
    for item in document.forbidden_downgrades:
        if type(item) is tuple and len(item) == 2:
            forbidden.append({
                "from": _plain_policy_value(item[0]),
                "to": _plain_policy_value(item[1]),
            })
        else:
            forbidden.append(_plain_policy_value(item))
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "retry": {
            "budgets": _plain_policy_value(document.retry_budgets),
            "identical_signature_limit": document.identical_signature_limit,
        },
        "gates": {
            "risk_human_approval": _plain_policy_value(
                document.risk_human_approval,
            ),
        },
        "isolation": {
            "order": _plain_policy_value(document.isolation_order),
            "forbidden_downgrades": forbidden,
        },
        "capability_names": [value.value for value in HostCapability],
        "workflow_safety_anchor": {
            "schema_version": anchor["schema_version"],
            "common": _stage_set_payload(anchor["common"]),
            "classes": {
                _plain_policy_value(kind): _stage_set_payload(stage_set)
                for kind, stage_set in classes.items()
            },
            "promotion": {
                _plain_policy_value(name): _stage_set_payload(stage_set)
                for name, stage_set in promotion.items()
            },
            "non_executable_classes": _plain_policy_value(
                anchor["non_executable_classes"],
            ),
        },
        "economics": {"mode": document.economics_mode},
    }


def _policy_document_digest(document: PolicyDocument) -> str:
    payload = _policy_document_payload(document)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_policy_document(document: PolicyDocument) -> PolicyDocument:
    if type(document) is not PolicyDocument:
        raise invalid_policy("invalid_policy_document")
    try:
        digest = _policy_document_digest(document)
        _validate_origin(document, "PolicyDocument", digest)
        return _normalize_policy_payload(_policy_document_payload(document))
    except InvalidSchemaError:
        raise
    except Exception:
        raise invalid_policy("invalid_policy_document") from None


def _normalize_policy_payload(payload: object) -> PolicyDocument:
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
    if not isinstance(risk_values, list) or any(
        type(value) is not str or value not in ("low", "medium", "high", "critical")
        for value in risk_values
    ) or len(risk_values) != len(set(risk_values)):
        raise invalid_policy("invalid_gate_policy")

    isolation = _exact_keys(payload["isolation"], {"order", "forbidden_downgrades"},
                            "invalid_isolation_policy")
    try:
        order = tuple(IsolationMode(value) for value in isolation["order"])
    except (TypeError, ValueError):
        raise invalid_policy("unknown_isolation_mode") from None
    if len(order) != len(IsolationMode) or set(order) != set(IsolationMode):
        raise invalid_policy("invalid_isolation_order")
    forbidden = set()
    if not isinstance(isolation["forbidden_downgrades"], list):
        raise invalid_policy("invalid_isolation_policy")
    for item in isolation["forbidden_downgrades"]:
        item = _exact_keys(item, {"from", "to"}, "invalid_isolation_policy")
        try:
            forbidden.add((IsolationMode(item["from"]), IsolationMode(item["to"])))
        except (TypeError, ValueError):
            raise invalid_policy("unknown_isolation_mode") from None

    capability_names = payload["capability_names"]
    if not isinstance(capability_names, list) or any(type(value) is not str for value in capability_names):
        raise invalid_policy("unknown_capability_name")
    if len(capability_names) != len(set(capability_names)):
        raise invalid_policy("duplicate_capability_name")
    try:
        declared_capabilities = {HostCapability(value) for value in capability_names}
    except ValueError:
        raise invalid_policy("unknown_capability_name") from None
    if declared_capabilities != set(HostCapability):
        raise invalid_policy("unknown_capability_name")

    economics = _exact_keys(payload["economics"], {"mode"}, "invalid_economics_policy")
    if economics["mode"] != "proposal_only":
        raise invalid_policy("economics_must_be_proposal_only")
    return PolicyDocument(
        MappingProxyType(safe_budgets), convergence_limit, tuple(risk_values), order,
        frozenset(forbidden), _workflow_safety_anchor(payload["workflow_safety_anchor"]),
        economics["mode"],
    )


def load_policy(path: Optional[Path] = None) -> PolicyDocument:
    source = Path(path) if path is not None else DEFAULT_POLICY_PATH
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
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
        try:
            normalized = reason if type(reason) is FailureReason else FailureReason(reason)
        except (TypeError, ValueError):
            raise invalid_policy("unknown_failure_reason") from None
        try:
            attempts = _snapshot_attempt_ledger(attempts)
        except Exception:
            raise invalid_policy("invalid_attempt_ledger") from None
        if signature is not None and (type(signature) is not str or not signature):
            raise invalid_policy("invalid_failure_signature")
        count = attempts.count(normalized)
        budget = self._policy.retry_budgets[normalized]
        history = attempts.history(normalized)
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
