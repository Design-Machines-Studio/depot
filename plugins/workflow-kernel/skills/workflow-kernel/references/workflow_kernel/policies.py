"""Versioned retry, gate, and degradation policy decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .adapters.base import (
    AttemptLedger, FailureReason, GATE_KINDS, GateDecision, HostCapability,
    IsolationMode, RetryDecision, WorkflowClass, WorkflowContext, invalid_policy,
)


POLICY_SCHEMA_VERSION = 1
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "workflow-policy.json"


@dataclass(frozen=True)
class PolicyDocument:
    retry_budgets: Mapping[FailureReason, int]
    identical_signature_limit: int
    risk_human_approval: Tuple[str, ...]
    isolation_order: Tuple[IsolationMode, ...]
    forbidden_downgrades: frozenset[tuple[IsolationMode, IsolationMode]]
    economics_mode: str


def _exact_keys(value: object, expected: set[str], reason: str) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise invalid_policy(reason)
    return value


def load_policy(path: Optional[Path] = None) -> PolicyDocument:
    source = Path(path) if path is not None else DEFAULT_POLICY_PATH
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise invalid_policy("invalid_policy_json") from None
    payload = _exact_keys(payload, {
        "schema_version", "retry", "gates", "isolation", "capability_names",
        "economics",
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
        frozenset(forbidden), economics["mode"],
    )


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
        if type(attempts) is not AttemptLedger:
            raise invalid_policy("invalid_attempt_ledger")
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
    def __init__(self, path: Optional[Path] = None):
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
        if gate_kind is not None and (
            type(gate_kind) is not str or gate_kind not in GATE_KINDS
        ):
            raise invalid_policy("unknown_gate_kind")
        if not isinstance(required_evidence, (list, tuple)) or any(
            type(value) is not str or not value for value in required_evidence
        ):
            raise invalid_policy("invalid_gate_evidence")
        required_evidence = tuple(required_evidence)
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
