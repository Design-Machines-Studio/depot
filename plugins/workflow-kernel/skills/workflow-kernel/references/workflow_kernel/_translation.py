"""Shared receipt-translation core for the pipeline and dm-review adapters.

Both adapters translate authoritative artifacts into observation-only events
and must agree on the execution-mode vocabulary, the redaction-safe receipt
field set, dual-format (camelCase/snake_case) key resolution, and receipt
event translation. This module is the single owner of that shared core so a
refactor of one adapter cannot silently break the other.
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Optional, Tuple

from .model import GateDecision, HostCapability, NodeSpec, WorkflowClass
from .redaction import (
    contains_high_confidence_secret, normalize_evidence_reference, redact,
)
from .schema import KernelError, WorkflowEvent


# Single execution-mode vocabulary, matching the Markdown contract
# (execution-orchestrator.md progress ledger / chunk receipts) and the
# closed `executionMode` set declared in manifest-schema.md.
EXECUTION_MODES = frozenset({
    "full_cli", "codex_native", "manual_walkthrough", "generic",
    "generic_host",
})
ISOLATION_STRATEGIES = frozenset({
    "per-chunk-worktree", "sequential-on-branch",
})
COMMON_RECEIPT_FIELDS = frozenset({
    "stage", "status", "host", "mechanism", "workflow_class", "provider",
    "model", "attempt", "duration_seconds", "wait_category", "first_pass", "fallback_reason",
    "retry_reason", "isolation_mode", "isolation_strategy",
    "persona_expected", "persona_passed",
    "persona_recovered", "persona_missing", "cleanup_removed",
    "cleanup_retained", "cleanup_blocked", "cleanup_foreign", "usage_count",
    "cost_usd", "time_to_clean_seconds", "requested_executor",
    "attempted_executor", "implemented_by", "fallback_path", "finding_id",
    "severity", "reviewer", "requested_lanes", "expected_lanes",
    "completed_lanes", "failed_lanes", "degraded_lanes", "unavailable_lanes",
    "prior_findings_signature", "finding_count", "convergence_signature",
    "browser_expected", "browser_passed", "browser_recovered",
    "browser_missing",
    "execution_mode", "requested_provider", "attempted_provider", "lane",
    "fallback", "cleanup_policy", "cleanup_disposition", "resource_kind",
    "resource_name", "topology", "topology_node", "topology_edge",
    "workflow_class_defaulted",
    "decision_profile", "decision_profile_defaulted",
    "contract_id", "schema_version", "revision", "contract_digest",
    "contract_ref", "previous_contract_digest", "reason_code",
    "human_approval_evidence_ref", "verification_contract_bound",
    "verification_contract_provenance",
    "chunk_id", "usage_scope", "measurement_source", "usage_estimated",
    "input_usage_count", "output_usage_count", "cache_read_usage_count",
    "cache_write_usage_count", "reasoning_usage_count",
    "source_finding_id", "canonical_finding_id", "finding_disposition",
    "agreement", "decision_reason_code", "evidence_ref", "action",
    "human_intervention_id", "human_intervention_reason",
    "human_intervention", "missing_case_ids",
    "record_kind", "record_ref", "record_digest", "rule_id", "category",
    "path", "anchor", "source_agents", "build_binding_ref",
    "browser_bundle_refs", "lane_id", "state", "expected_coverage",
    "partial_output", "output_ref", "coverage_gap_reason",
    "source_scope_digest", "finding_refs",
})
# Documented camelCase receipt spellings (pipeline and dm-review instruct
# producers to emit these provider-evidence fields) mapped to the canonical
# snake_case receipt schema. A conflicting duplicate is rejected, never
# silently dropped.
RECEIPT_FIELD_ALIASES = {
    "executionMode": "execution_mode",
    "workflowClass": "workflow_class",
    "workflowClassDefaulted": "workflow_class_defaulted",
    "decisionProfile": "decision_profile",
    "decisionProfileDefaulted": "decision_profile_defaulted",
    "requestedProvider": "requested_provider",
    "attemptedProvider": "attempted_provider",
    "implementedBy": "implemented_by",
    "fallbackReason": "fallback_reason",
    # Documented model-descent evidence field: Claude/Codex receipts spell the
    # resolved model as `modelUsed`; it normalizes to the canonical `model`
    # metrics dimension instead of being silently dropped.
    "modelUsed": "model",
    # Worktree isolation is a strategy separate from the closed executionMode
    # set (execution-orchestrator.md Step 1c): per-chunk-worktree or
    # sequential-on-branch.
    "isolationStrategy": "isolation_strategy",
    "contractId": "contract_id",
    "schemaVersion": "schema_version",
    "contractRevision": "revision",
    "contractDigest": "contract_digest",
    "claimedContractDigest": "contract_digest",
    "contractRef": "contract_ref",
    "previousContractDigest": "previous_contract_digest",
    "reasonCode": "reason_code",
    "humanApprovalEvidenceRef": "human_approval_evidence_ref",
    "chunkId": "chunk_id",
    "usageScope": "usage_scope",
    "measurementSource": "measurement_source",
    "usageEstimated": "usage_estimated",
    "inputUsageCount": "input_usage_count",
    "outputUsageCount": "output_usage_count",
    "cacheReadUsageCount": "cache_read_usage_count",
    "cacheWriteUsageCount": "cache_write_usage_count",
    "reasoningUsageCount": "reasoning_usage_count",
    "costUsd": "cost_usd",
    "durationSeconds": "duration_seconds",
    "waitCategory": "wait_category",
    "sourceFindingId": "source_finding_id",
    "canonicalFindingId": "canonical_finding_id",
    "findingDisposition": "finding_disposition",
    "decisionReasonCode": "decision_reason_code",
    "evidenceRef": "evidence_ref",
    "humanInterventionId": "human_intervention_id",
    "humanInterventionReason": "human_intervention_reason",
    "missingCaseIds": "missing_case_ids",
    "recordKind": "record_kind", "recordRef": "record_ref",
    "recordDigest": "record_digest", "ruleId": "rule_id",
    "sourceAgents": "source_agents", "buildBindingRef": "build_binding_ref",
    "browserBundleRefs": "browser_bundle_refs", "laneId": "lane_id",
    "expectedCoverage": "expected_coverage", "partialOutput": "partial_output",
    "outputRef": "output_ref", "coverageGapReason": "coverage_gap_reason",
    "sourceScopeDigest": "source_scope_digest", "findingRefs": "finding_refs",
    # Legacy producer vocabulary. The durable kernel name is deliberately
    # neutral because not every provider reports tokens.
    "tokens": "usage_count",
}

_MISSING = object()
_CONTRACT_STAGES = frozenset({
    "verification_contract_bound", "verification_contract_revised",
})
_VALIDATION_INTERVENTION_REASONS = frozenset({
    "identical_failure_convergence", "retry_budget_exhausted",
    "replacement_adapter_dispatch_failed", "replacement_invalid_session_handle",
    "replacement_session_handle_unavailable",
})
_PRE_CONTRACT_STAGES = frozenset({
    "progress", "manifest_validation", "dependency_ready",
})
_CONTRACT_FIELDS = frozenset({
    "contract_id", "schema_version", "revision", "contract_digest",
    "contract_ref", "previous_contract_digest", "reason_code",
    "human_approval_evidence_ref",
})
_CONTRACT_BINDING_MARKERS = _CONTRACT_FIELDS - frozenset({"reason_code"})
_RECEIPT_ENVELOPE_FIELDS = COMMON_RECEIPT_FIELDS | frozenset({
    "run_id", "sequence", "occurred_at", "node_id", "authoritative_receipt",
})
_CONTRACT_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTRACT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_CONTRACT_REASON = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_CREDENTIAL_LIKE = re.compile(
    r"(?i)^(?:sk-|gh[pousr]_|xox[baprs]-|bearer\s)",
)
_USAGE_SCOPES = frozenset({"attempt", "run"})
_WAIT_CATEGORIES = frozenset({"human_gate", "external_dependency", "capacity", "ci"})
_USAGE_COUNT_FIELDS = frozenset({
    "usage_count", "input_usage_count", "output_usage_count",
    "cache_read_usage_count", "cache_write_usage_count",
    "reasoning_usage_count",
})
_CONTRIBUTION_DISPOSITIONS = frozenset({"retained", "merged", "discarded"})
_CONTRIBUTION_AGREEMENTS = frozenset({"unique", "corroborated", "disputed"})
_CONTRIBUTION_REASON_DISPOSITION = {
    "retained-unique": "retained",
    "retained-corroborated": "retained",
    "retained-disagreement": "retained",
    "exact-duplicate": "merged",
    "same-root-cause-merge": "merged",
    "superseded-by-stronger-evidence": "discarded",
    "out-of-scope": "discarded",
    "not-reproducible": "discarded",
    "agent-findings-cap": "discarded",
}
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}\Z")
_MAX_MISSING_CASE_IDS = 256
_MAX_MISSING_CASE_ID_BYTES = 16_384
_REVIEW_RECORD_STAGES = frozenset({"finding_record", "lane_record"})
_REVIEW_LANE_STATES = frozenset({
    "requested", "completed", "failed", "degraded", "unavailable",
    "missing", "unknown",
})
_REVIEW_FINDING_ID = re.compile(r"finding-v1:sha256:[0-9a-f]{64}\Z")


def required_text(value: object, field: str) -> str:
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError("invalid " + field)
    return value


def _bounded_identity(value: object, field: str) -> str:
    value = required_text(value, field)
    if _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid " + field)
    return value


def dual_key(mapping: Mapping[str, object], snake: str, camel: str, default: object = _MISSING) -> object:
    """Resolve one dual-format key with camelCase-primary precedence.

    The documented artifact schemas (manifest-schema.md, the dm-review
    request.json) are camelCase-primary; snake_case is the accepted legacy
    spelling. Both adapters must resolve aliases through this one helper.
    When both spellings are present they must agree.
    """
    has_camel = camel in mapping
    has_snake = snake in mapping
    if has_camel and has_snake:
        try:
            agree = bool(mapping[camel] == mapping[snake])
        except Exception:
            raise ValueError(
                "conflicting values for " + snake + "/" + camel,
            ) from None
        if not agree:
            raise ValueError("conflicting values for " + snake + "/" + camel)
    if has_camel:
        return mapping[camel]
    if has_snake:
        return mapping[snake]
    if default is _MISSING:
        raise ValueError("missing " + camel)
    return default


@dataclass(frozen=True)
class ChunkSpec:
    node_id: str
    dependencies: Tuple[str, ...]

    def __post_init__(self) -> None:
        required_text(self.node_id, "chunk id")
        if not isinstance(self.dependencies, (list, tuple)) or any(
            type(item) is not str or not item for item in self.dependencies
        ):
            raise ValueError("invalid chunk dependencies")
        values = tuple(self.dependencies)
        if len(values) != len(set(values)) or self.node_id in values:
            raise ValueError("invalid chunk dependencies")
        object.__setattr__(self, "dependencies", values)

    def to_dict(self) -> dict:
        return {"id": self.node_id, "depends_on": list(self.dependencies)}


_LEGACY_RUN_SPEC_FIELDS = frozenset({
    "run_id", "workflow_class", "workflow_class_defaulted",
    "execution_mode", "host_name", "nodes", "chunks",
    "execution_levels", "execution_plan_disagreement",
    "required_lanes", "review_mode", "observation_only",
})
_RUN_SPEC_FIELDS = _LEGACY_RUN_SPEC_FIELDS | frozenset({
    "decision_profile", "decision_profile_defaulted",
})
_NODE_FIELDS = frozenset({
    "id", "depends_on", "gate_kind", "required_evidence",
    "executor", "routing_reason", "gate_decision",
    "required_capability", "required_dispatch_capability",
    "executor_overridable",
})
_GATE_FIELDS = frozenset({
    "allowed", "reason_code", "missing_evidence", "human_required",
})
_DECISION_LEVELS = frozenset({"low", "medium", "high"})


def normalize_decision_profile(value: object) -> dict:
    if type(value) is not dict or set(value) != {
        "uncertainty", "consequence", "rationale",
    }:
        raise ValueError("invalid decision profile")
    if (
        value["uncertainty"] not in _DECISION_LEVELS
        or value["consequence"] not in _DECISION_LEVELS
    ):
        raise ValueError("invalid decision profile")
    rationale = required_text(value["rationale"], "decision profile rationale")
    if contains_high_confidence_secret(rationale):
        raise ValueError("invalid decision profile")
    return {
        "uncertainty": value["uncertainty"],
        "consequence": value["consequence"],
        "rationale": rationale,
    }


@dataclass(frozen=True)
class RunSpec:
    """A host-neutral description; it contains no dispatch authority."""

    run_id: str
    workflow_class: WorkflowClass
    workflow_class_defaulted: bool
    execution_mode: str
    host_name: str
    nodes: Tuple[NodeSpec, ...]
    chunks: Tuple[ChunkSpec, ...] = ()
    execution_levels: Tuple[Tuple[str, ...], ...] = ()
    execution_plan_disagreement: bool = False
    required_lanes: Tuple[str, ...] = ()
    review_mode: Optional[str] = None
    decision_profile: Optional[Mapping[str, str]] = None
    decision_profile_defaulted: bool = True

    def __post_init__(self) -> None:
        """Single validation layer: the constructor owns every field rule."""
        required_text(self.run_id, "run_id")
        if type(self.workflow_class) is not WorkflowClass:
            raise ValueError("invalid RunSpec workflow_class")
        if type(self.workflow_class_defaulted) is not bool:
            raise ValueError("invalid RunSpec workflow_class_defaulted")
        if (
            type(self.execution_mode) is not str
            or self.execution_mode not in EXECUTION_MODES
        ):
            raise ValueError("invalid RunSpec execution_mode")
        required_text(self.host_name, "host_name")
        if not isinstance(self.nodes, (list, tuple)) or any(
            type(item) is not NodeSpec for item in self.nodes
        ):
            raise ValueError("invalid RunSpec nodes")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        if not isinstance(self.chunks, (list, tuple)) or any(
            type(item) is not ChunkSpec for item in self.chunks
        ):
            raise ValueError("invalid RunSpec chunks")
        object.__setattr__(self, "chunks", tuple(self.chunks))
        if not isinstance(self.execution_levels, (list, tuple)):
            raise ValueError("invalid RunSpec levels")
        levels = []
        for level in self.execution_levels:
            if not isinstance(level, (list, tuple)) or any(
                type(item) is not str or not item for item in level
            ):
                raise ValueError("invalid RunSpec levels")
            levels.append(tuple(level))
        object.__setattr__(self, "execution_levels", tuple(levels))
        if type(self.execution_plan_disagreement) is not bool:
            raise ValueError("invalid RunSpec plan disagreement")
        if not isinstance(self.required_lanes, (list, tuple)) or any(
            type(item) is not str or not item for item in self.required_lanes
        ):
            raise ValueError("invalid RunSpec lanes")
        lanes = tuple(self.required_lanes)
        if len(lanes) != len(set(lanes)):
            raise ValueError("invalid RunSpec lanes")
        object.__setattr__(self, "required_lanes", lanes)
        if self.review_mode is not None and type(self.review_mode) is not str:
            raise ValueError("invalid RunSpec review mode")
        if type(self.decision_profile_defaulted) is not bool:
            raise ValueError("invalid RunSpec decision profile provenance")
        if self.decision_profile is None:
            if not self.decision_profile_defaulted:
                raise ValueError("invalid RunSpec decision profile provenance")
        else:
            profile = normalize_decision_profile(self.decision_profile)
            if self.decision_profile_defaulted:
                raise ValueError("invalid RunSpec decision profile provenance")
            object.__setattr__(
                self, "decision_profile", MappingProxyType(profile),
            )

    @classmethod
    def from_dict(cls, value: object) -> "RunSpec":
        """Structural builder only; field validation lives in the constructors.

        Exact key-set checks reject unknown or missing keys; list-type guards
        protect every ``tuple()`` conversion from string/mapping reinterpretation.
        Everything else is validated once, by ``RunSpec``/``NodeSpec``/
        ``GateDecision`` construction.
        """
        if (
            type(value) is not dict
            or set(value) not in {_LEGACY_RUN_SPEC_FIELDS, _RUN_SPEC_FIELDS}
            or value["observation_only"] is not True
        ):
            raise ValueError("invalid RunSpec")
        try:
            nodes = []
            for item in value["nodes"]:
                if type(item) is not dict or set(item) != _NODE_FIELDS:
                    raise ValueError("invalid RunSpec node")
                gate = item["gate_decision"]
                if type(gate) is not dict or set(gate) != _GATE_FIELDS:
                    raise ValueError("invalid RunSpec gate")
                if (
                    type(item["depends_on"]) is not list
                    or type(item["required_evidence"]) is not list
                    or type(gate["missing_evidence"]) is not list
                ):
                    raise ValueError("invalid RunSpec node")
                nodes.append(NodeSpec(
                    item["id"], tuple(item["depends_on"]), item["gate_kind"],
                    tuple(item["required_evidence"]), item["executor"],
                    item["routing_reason"], GateDecision(
                        gate["allowed"], gate["reason_code"],
                        tuple(gate["missing_evidence"]), gate["human_required"],
                    ),
                    None if item["required_capability"] is None else HostCapability(item["required_capability"]),
                    None if item["required_dispatch_capability"] is None else HostCapability(item["required_dispatch_capability"]),
                    item["executor_overridable"],
                ))
            chunks = []
            for item in value["chunks"]:
                if (
                    type(item) is not dict or set(item) != {"id", "depends_on"}
                    or type(item["depends_on"]) is not list
                ):
                    raise ValueError("invalid RunSpec chunk")
                chunks.append(ChunkSpec(item["id"], tuple(item["depends_on"])))
            if type(value["execution_levels"]) is not list or any(
                type(level) is not list for level in value["execution_levels"]
            ):
                raise ValueError("invalid RunSpec levels")
            if type(value["required_lanes"]) is not list:
                raise ValueError("invalid RunSpec lanes")
            legacy_profile = "decision_profile" not in value
            return cls(
                value["run_id"],
                WorkflowClass(value["workflow_class"]),
                value["workflow_class_defaulted"],
                value["execution_mode"],
                value["host_name"],
                tuple(nodes), tuple(chunks),
                tuple(tuple(level) for level in value["execution_levels"]),
                value["execution_plan_disagreement"],
                tuple(value["required_lanes"]), value["review_mode"],
                None if legacy_profile else value["decision_profile"],
                True if legacy_profile else value["decision_profile_defaulted"],
            )
        except (KernelError, KeyError, TypeError, ValueError) as error:
            message = str(error) if type(error) is ValueError else "invalid RunSpec"
            raise ValueError(message or "invalid RunSpec") from None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "workflow_class": self.workflow_class.value,
            "workflow_class_defaulted": self.workflow_class_defaulted,
            "execution_mode": self.execution_mode,
            "host_name": self.host_name,
            "nodes": [
                {
                    "id": node.node_id,
                    "depends_on": list(node.dependencies),
                    "gate_kind": node.gate_kind,
                    "required_evidence": list(node.required_evidence),
                    "executor": node.executor,
                    "routing_reason": node.routing_reason,
                    "gate_decision": {
                        "allowed": node.gate_decision.allowed,
                        "reason_code": node.gate_decision.reason_code,
                        "missing_evidence": list(node.gate_decision.missing_evidence),
                        "human_required": node.gate_decision.human_required,
                    },
                    "required_capability": (
                        node.required_capability.value
                        if node.required_capability is not None else None
                    ),
                    "required_dispatch_capability": (
                        node.required_dispatch_capability.value
                        if node.required_dispatch_capability is not None else None
                    ),
                    "executor_overridable": node.executor_overridable,
                }
                for node in self.nodes
            ],
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "execution_levels": [list(level) for level in self.execution_levels],
            "execution_plan_disagreement": self.execution_plan_disagreement,
            "required_lanes": list(self.required_lanes),
            "review_mode": self.review_mode,
            "decision_profile": (
                None if self.decision_profile is None
                else dict(self.decision_profile)
            ),
            "decision_profile_defaulted": self.decision_profile_defaulted,
            "observation_only": True,
        }


def safe_reference(value: object) -> str:
    reference = required_text(value, "authoritative receipt")
    try:
        return normalize_evidence_reference(reference)
    except ValueError:
        raise ValueError("unsafe authoritative receipt") from None


def _normalized_receipt_fields(receipt: Mapping[str, object]) -> dict:
    """Fold documented camelCase aliases into the canonical snake_case schema.

    A camelCase spelling that conflicts with its snake_case field is rejected;
    accepting either silently would drop the provider/fallback evidence this
    schema exists to preserve.
    """
    normalized = dict(receipt)
    for camel, snake in RECEIPT_FIELD_ALIASES.items():
        if camel not in normalized:
            continue
        candidate = normalized.pop(camel)
        if snake in normalized:
            existing = normalized[snake]
            if snake == "decision_profile":
                candidate = normalize_decision_profile(candidate)
                existing = normalize_decision_profile(existing)
                conflicting = candidate != existing
            else:
                conflicting = (
                    type(candidate) not in {str, bool, int, float, type(None)}
                    or type(existing) is not type(candidate)
                    or existing != candidate
                )
            if conflicting:
                raise ValueError(
                    "conflicting receipt field " + snake + "/" + camel,
                )
            normalized[snake] = existing
            continue
        normalized[snake] = candidate
    return normalized


def _nonnegative_number(value: object, field: str, *, integer: bool) -> object:
    valid_type = type(value) is int if integer else type(value) in {int, float}
    if (
        not valid_type or value < 0
        or type(value) is float and not math.isfinite(value)
    ):
        raise ValueError("invalid receipt numeric field " + field)
    return value


def _validate_observation_receipt(receipt: dict) -> dict:
    """Validate optional telemetry without assigning it workflow authority."""
    receipt.pop("human_intervention", None)
    if "decision_profile" in receipt:
        receipt["decision_profile"] = normalize_decision_profile(
            receipt["decision_profile"],
        )
    if "decision_profile_defaulted" in receipt and type(
        receipt["decision_profile_defaulted"]
    ) is not bool:
        raise ValueError("invalid decision profile provenance")
    for field in _USAGE_COUNT_FIELDS:
        if field in receipt:
            _nonnegative_number(receipt[field], field, integer=True)
    for field in ("cost_usd", "duration_seconds"):
        if field in receipt:
            _nonnegative_number(receipt[field], field, integer=False)
    if "attempt" in receipt and (
        type(receipt["attempt"]) is not int or receipt["attempt"] < 1
    ):
        raise ValueError("invalid receipt attempt")
    for field in (
        "chunk_id", "reviewer", "lane", "requested_provider",
        "attempted_provider", "implemented_by", "provider", "model", "host",
        "source_finding_id", "canonical_finding_id", "human_intervention_id",
        "human_intervention_reason",
    ):
        if field in receipt and receipt[field] is not None:
            required_text(receipt[field], field.replace("_", " "))
    if "wait_category" in receipt and receipt["wait_category"] not in _WAIT_CATEGORIES:
        raise ValueError("invalid wait category")

    if receipt.get("stage") in _REVIEW_RECORD_STAGES:
        stage = receipt["stage"]
        receipt["record_ref"] = safe_reference(receipt.get("record_ref"))
        digest = required_text(receipt.get("record_digest"), "record digest")
        if _CONTRACT_DIGEST.fullmatch(digest) is None:
            raise ValueError("invalid review record digest")
        receipt["build_binding_ref"] = safe_reference(
            receipt.get("build_binding_ref"),
        )
        browser_refs = receipt.get("browser_bundle_refs")
        if type(browser_refs) is not list or len(browser_refs) > 256:
            raise ValueError("invalid browser bundle references")
        browser_refs = [safe_reference(value) for value in browser_refs]
        if len(browser_refs) != len(set(browser_refs)):
            raise ValueError("invalid browser bundle references")
        receipt["browser_bundle_refs"] = browser_refs
        agents = receipt.get("source_agents")
        if type(agents) is not list or not agents or len(agents) > 64:
            raise ValueError("invalid source agents")
        agents = [_bounded_identity(value, "source agent") for value in agents]
        if len(agents) != len(set(agents)):
            raise ValueError("invalid source agents")
        receipt["source_agents"] = agents
        if stage == "finding_record":
            for field in ("source_finding_id", "rule_id", "lane_id"):
                receipt[field] = _bounded_identity(receipt.get(field), field)
            scope_digest = required_text(
                receipt.get("source_scope_digest"), "source scope digest",
            )
            if _CONTRACT_DIGEST.fullmatch(scope_digest) is None:
                raise ValueError("invalid source scope digest")
            canonical = required_text(
                receipt.get("canonical_finding_id"), "canonical finding id",
            )
            if _REVIEW_FINDING_ID.fullmatch(canonical) is None:
                raise ValueError("invalid canonical finding id")
            if receipt.get("severity") not in {"P1", "P2", "P3"}:
                raise ValueError("invalid severity")
            for field in ("category", "path", "anchor"):
                required_text(receipt.get(field), field)
        else:
            receipt["lane_id"] = _bounded_identity(receipt.get("lane_id"), "lane id")
            if receipt.get("state") not in _REVIEW_LANE_STATES:
                raise ValueError("invalid lane state")
            expected = receipt.get("expected_coverage")
            missing = receipt.get("missing_case_ids")
            if type(expected) is not list or type(missing) is not list:
                raise ValueError("invalid lane coverage")
            receipt["expected_coverage"] = [
                _bounded_identity(value, "expected coverage") for value in expected
            ]
            receipt["missing_case_ids"] = [
                _bounded_identity(value, "missing case id") for value in missing
            ]
            if (len(expected) > 256 or len(missing) > 256
                    or len(expected) != len(set(expected))
                    or len(missing) != len(set(missing))):
                raise ValueError("invalid lane coverage")
            if type(receipt.get("partial_output")) is not bool:
                raise ValueError("invalid partial output")
            output_ref = receipt.get("output_ref")
            if output_ref is not None:
                receipt["output_ref"] = safe_reference(output_ref)
            gap = receipt.get("coverage_gap_reason")
            if receipt["state"] == "completed":
                if missing or receipt["partial_output"] or gap is not None:
                    raise ValueError("completed lane contains coverage gap")
            elif not required_text(gap, "coverage gap reason"):
                raise ValueError("incomplete lane lacks coverage gap reason")
            if receipt["partial_output"] and output_ref is None:
                raise ValueError("partial lane lacks output reference")
            finding_refs = receipt.get("finding_refs")
            if type(finding_refs) is not list or len(finding_refs) > 256:
                raise ValueError("invalid lane finding references")
            finding_refs = [safe_reference(value) for value in finding_refs]
            if len(finding_refs) != len(set(finding_refs)):
                raise ValueError("invalid lane finding references")
            receipt["finding_refs"] = finding_refs

    scoped = "usage_scope" in receipt
    detailed = bool((_USAGE_COUNT_FIELDS - {"usage_count"}) & set(receipt))
    provenance = bool({"measurement_source", "usage_estimated"} & set(receipt))
    if detailed or provenance:
        scoped = True
    if scoped:
        if receipt.get("usage_scope") not in _USAGE_SCOPES:
            raise ValueError("invalid usage scope")
        required_text(receipt.get("measurement_source"), "measurement source")
        if type(receipt.get("usage_estimated")) is not bool:
            raise ValueError("invalid usage estimated flag")
        if not ((_USAGE_COUNT_FIELDS & set(receipt)) or "cost_usd" in receipt):
            raise ValueError("scoped usage row has no measurement")
        if receipt["usage_scope"] == "attempt":
            if (
                "attempt" not in receipt or not receipt.get("node_id")
                or not receipt.get("chunk_id") or "duration_seconds" not in receipt
            ):
                raise ValueError("attempt usage lacks stable identity")
            for field in (
                "requested_provider", "attempted_provider", "implemented_by",
                "model", "host",
            ):
                required_text(receipt.get(field), field.replace("_", " "))
        elif any(field in receipt for field in (
            "attempt", "chunk_id", "reviewer", "lane",
        )):
            raise ValueError("run usage carries attempt identity")

    if receipt.get("stage") == "finding_contribution":
        for field in (
            "source_finding_id", "canonical_finding_id", "reviewer",
            "decision_reason_code",
        ):
            required_text(receipt.get(field), field.replace("_", " "))
        if receipt.get("finding_disposition") not in _CONTRIBUTION_DISPOSITIONS:
            raise ValueError("invalid finding disposition")
        if receipt.get("agreement") not in _CONTRIBUTION_AGREEMENTS:
            raise ValueError("invalid finding agreement")
        reason = receipt["decision_reason_code"]
        if _CONTRIBUTION_REASON_DISPOSITION.get(reason) != receipt["finding_disposition"]:
            raise ValueError("invalid finding decision reason")
        if "attempt" not in receipt or not (
            receipt.get("node_id") or receipt.get("chunk_id")
        ):
            raise ValueError("finding contribution lacks stable identity")
        receipt["evidence_ref"] = safe_reference(receipt.get("evidence_ref"))

    validation_help = (
        receipt.get("stage") == "deterministic_validation"
        and receipt.get("action") == "human_help_required"
    )
    browser_help = (
        receipt.get("stage") == "browser_recovery"
        and receipt.get("status") == "blocked"
        and receipt.get("reason_code") == "human_help_required"
    )
    if validation_help or browser_help:
        required_text(receipt.get("human_intervention_id"), "human intervention id")
        reason = required_text(
            receipt.get("human_intervention_reason"), "human intervention reason",
        )
        allowed_reasons = (
            _VALIDATION_INTERVENTION_REASONS
            if validation_help else {"browser_evidence_unavailable"}
        )
        if reason not in allowed_reasons:
            raise ValueError("invalid human intervention reason")
        if not (receipt.get("node_id") or receipt.get("chunk_id")):
            raise ValueError("human intervention lacks stable identity")
        if validation_help and "attempt" not in receipt:
            raise ValueError("validation intervention lacks attempt identity")
        if browser_help:
            cases = receipt.get("missing_case_ids")
            if (
                type(cases) is not list or not cases
                or len(cases) > _MAX_MISSING_CASE_IDS
            ):
                raise ValueError("browser intervention lacks case identity")
            try:
                cases = [
                    _bounded_identity(item, "missing case id") for item in cases
                ]
            except ValueError:
                raise ValueError("browser intervention lacks case identity") from None
            if (
                len(cases) != len(set(cases))
                or sum(len(item.encode("utf-8")) for item in cases)
                > _MAX_MISSING_CASE_ID_BYTES
            ):
                raise ValueError("browser intervention lacks case identity")
            receipt["missing_case_ids"] = cases
        receipt["human_intervention"] = True
    return receipt


def _safe_receipt_payload(receipt: Mapping[str, object], reference: str) -> dict:
    payload = {}
    for key in COMMON_RECEIPT_FIELDS:
        if key not in receipt:
            continue
        # The canonical record identity contains a colon-delimited namespace,
        # which the generic durable-string normalizer intentionally treats as
        # URL-like. The content-addressed record is authoritative; its bounded
        # record_ref carries the identity into events without duplicating it.
        if receipt.get("stage") == "finding_record" and key == "canonical_finding_id":
            continue
        # Redact each value under a neutral key. Field names such as `tokens`
        # and `fallback_path` are reliability facts, not credentials or local
        # filesystem evidence, and must retain their documented meaning.
        normalized = redact({"value": receipt[key]})
        if not isinstance(normalized, dict) or "value" not in normalized:
            raise ValueError("unsafe receipt payload")
        payload[key] = normalized["value"]
    payload["authoritative_receipt"] = reference
    payload["evidence"] = [reference]
    if receipt.get("stage") == "verification_contract_bound":
        payload["evidence"].append("verification_contract_bound")
    elif receipt.get("stage") == "verification_contract_revised":
        payload["evidence"].extend((
            "verification_contract_bound", "verification_contract_revised",
        ))
    if receipt.get("stage") == "finding_contribution":
        payload["evidence"].append(receipt["evidence_ref"])
    elif receipt.get("stage") in _REVIEW_RECORD_STAGES:
        payload["evidence"].append(receipt["record_ref"])
        payload["evidence"].extend(receipt["browser_bundle_refs"])
        if receipt.get("stage") == "lane_record":
            payload["evidence"].extend(receipt["finding_refs"])
    return payload


def _contract_reference(value: object, field: str, *, nullable: bool = False):
    if value is None and nullable:
        return None
    try:
        normalized = safe_reference(value)
        if _CREDENTIAL_LIKE.match(normalized):
            raise ValueError
        return normalized
    except ValueError:
        raise ValueError("invalid verification contract receipt") from None


def _validate_contract_receipt(receipt: dict, current: object):
    if set(receipt) - _RECEIPT_ENVELOPE_FIELDS:
        raise ValueError("invalid verification contract receipt")
    if not _CONTRACT_FIELDS <= set(receipt):
        raise ValueError("invalid verification contract receipt")
    if receipt["schema_version"] != 1 or type(receipt["schema_version"]) is not int:
        raise ValueError("invalid verification contract receipt")
    contract_id = required_text(receipt["contract_id"], "contract id")
    revision = receipt["revision"]
    digest = receipt["contract_digest"]
    previous = receipt["previous_contract_digest"]
    if (
        _CONTRACT_ID.fullmatch(contract_id) is None
        or type(revision) is not int or revision < 1
        or type(digest) is not str or _CONTRACT_DIGEST.fullmatch(digest) is None
        or previous is not None and (
            type(previous) is not str
            or _CONTRACT_DIGEST.fullmatch(previous) is None
        )
    ):
        raise ValueError("invalid verification contract receipt")
    contract_ref = _contract_reference(receipt["contract_ref"], "contract ref")
    expected_ref = (
        "verification-contracts/sha256-"
        + digest.removeprefix("sha256:") + ".json"
    )
    if contract_ref != expected_ref or any(
        field in receipt
        for field in (
            "verification_contract_bound", "verification_contract_provenance",
        )
    ):
        raise ValueError("invalid verification contract receipt")
    reason = required_text(receipt["reason_code"], "contract reason code")
    if _CONTRACT_REASON.fullmatch(reason) is None:
        raise ValueError("invalid verification contract receipt")
    _contract_reference(
        receipt["human_approval_evidence_ref"], "contract approval",
        nullable=True,
    )
    stage = receipt["stage"]
    if stage == "verification_contract_bound":
        if current is not None or revision != 1 or previous is not None:
            raise ValueError("invalid verification contract continuity")
    elif (
        current is None
        or contract_id != current[0]
        or receipt["schema_version"] != current[1]
        or revision != current[2] + 1
        or previous != current[3]
    ):
        raise ValueError("invalid verification contract continuity")
    return contract_id, receipt["schema_version"], revision, digest


def translate_receipts(
    receipts: Iterable[Mapping[str, object]], allowed_stages: frozenset, *,
    isolation_default: object = None,
) -> Tuple[WorkflowEvent, ...]:
    if isolation_default is not None and isolation_default not in ISOLATION_STRATEGIES:
        raise ValueError("invalid isolation strategy")
    try:
        values = tuple(receipts)
    except Exception:
        raise ValueError("invalid receipts") from None
    normalized_values = []
    for receipt in values:
        if type(receipt) is not dict:
            raise ValueError("receipt must be an object")
        normalized_values.append(_validate_observation_receipt(
            _normalized_receipt_fields(receipt),
        ))
    has_contract_binding = any(
        receipt.get("stage") in _CONTRACT_STAGES
        for receipt in normalized_values
    )
    if not has_contract_binding and any(
        _CONTRACT_BINDING_MARKERS & set(receipt) for receipt in normalized_values
    ):
        raise ValueError("mixed legacy and verification contract receipts")
    events = []
    run_identity = None
    workflow_class = None
    execution_mode = None
    workflow_class_defaulted = None
    decision_profile = None
    decision_profile_defaulted = None
    isolation_strategy = None
    current_contract = None
    contribution_sources = set()
    contribution_artifact_reviewers = {}
    review_record_identities = {}
    for position, receipt in enumerate(normalized_values):
        run_id = required_text(receipt.get("run_id"), "run id")
        sequence = receipt.get("sequence")
        if type(sequence) is not int or sequence != position:
            raise ValueError("invalid receipt sequence")
        class_was_present = "workflow_class" in receipt
        current_class = required_text(
            receipt.get("workflow_class", workflow_class or "feature"),
            "workflow class",
        )
        try:
            current_class = WorkflowClass(current_class).value
        except ValueError:
            raise ValueError("invalid workflow class") from None
        if "workflow_class_defaulted" in receipt:
            current_defaulted = receipt["workflow_class_defaulted"]
            if type(current_defaulted) is not bool:
                raise ValueError("invalid workflow class provenance")
            if position == 0 and not class_was_present and not current_defaulted:
                # The run's class was just derived from the default; a receipt
                # that omits workflow_class cannot claim explicit non-defaulted
                # provenance (receipt-side residue of the 064 request fix).
                raise ValueError("invalid workflow class provenance")
        else:
            current_defaulted = (
                not class_was_present if position == 0 else
                workflow_class_defaulted if not class_was_present else False
            )
        profile_was_present = "decision_profile" in receipt
        current_profile = receipt.get("decision_profile", decision_profile)
        if "decision_profile_defaulted" in receipt:
            current_profile_defaulted = receipt["decision_profile_defaulted"]
        else:
            current_profile_defaulted = (
                not profile_was_present if position == 0
                else decision_profile_defaulted
                if not profile_was_present else False
            )
        if (
            current_profile is None and not current_profile_defaulted
            or current_profile is not None and current_profile_defaulted
        ):
            raise ValueError("invalid decision profile provenance")
        current_mode = required_text(
            receipt.get("execution_mode", execution_mode or "generic"),
            "execution mode",
        )
        if current_mode not in EXECUTION_MODES:
            raise ValueError("invalid execution mode")
        current_isolation = receipt.get("isolation_strategy", _MISSING)
        isolation_was_present = current_isolation is not _MISSING
        if current_isolation is _MISSING:
            current_isolation = (
                isolation_strategy
                if isolation_strategy is not None else isolation_default
            )
        if isolation_was_present or current_isolation is not None:
            current_isolation = required_text(
                current_isolation, "isolation strategy",
            )
            if current_isolation not in ISOLATION_STRATEGIES:
                raise ValueError("invalid isolation strategy")
        if position == 0:
            run_identity, workflow_class, execution_mode = run_id, current_class, current_mode
            workflow_class_defaulted = current_defaulted
            decision_profile = current_profile
            decision_profile_defaulted = current_profile_defaulted
            isolation_strategy = current_isolation
        elif (
            run_id, current_class, current_mode, current_defaulted,
            current_profile, current_profile_defaulted, current_isolation,
        ) != (
            run_identity, workflow_class, execution_mode, workflow_class_defaulted,
            decision_profile, decision_profile_defaulted, isolation_strategy,
        ):
            raise ValueError("receipt context discontinuity")
        stage = required_text(receipt.get("stage"), "stage")
        if stage not in allowed_stages:
            raise ValueError("unknown receipt stage")
        if stage == "finding_contribution":
            source = (receipt["evidence_ref"], receipt["source_finding_id"])
            if source in contribution_sources:
                raise ValueError("source finding has multiple decisions")
            contribution_sources.add(source)
            prior_reviewer = contribution_artifact_reviewers.setdefault(
                receipt["evidence_ref"], receipt["reviewer"],
            )
            if prior_reviewer != receipt["reviewer"]:
                raise ValueError("source artifact reviewer discontinuity")
        elif stage in _REVIEW_RECORD_STAGES:
            identity = (
                receipt["source_scope_digest"] if stage == "finding_record"
                else receipt["lane_id"]
            )
            content = (receipt["record_digest"], receipt["record_ref"])
            prior = review_record_identities.setdefault((stage, identity), content)
            if prior != content:
                raise ValueError("conflicting review record identity")
        occurred_at = required_text(receipt.get("occurred_at"), "occurred_at")
        node_id = receipt.get("node_id")
        if node_id is not None:
            node_id = required_text(node_id, "node id")
        reference = safe_reference(receipt.get("authoritative_receipt"))
        if stage in _CONTRACT_STAGES:
            current_contract = _validate_contract_receipt(
                receipt, current_contract,
            )
        elif has_contract_binding:
            claimed = receipt.get("contract_digest", _MISSING)
            if current_contract is None:
                if (
                    stage not in _PRE_CONTRACT_STAGES
                    or claimed is not _MISSING
                ):
                    raise ValueError("verification contract not yet bound")
            elif (
                type(claimed) is not str
                or claimed != current_contract[3]
            ):
                raise ValueError("verification contract digest mismatch")
        normalized_receipt = dict(receipt)
        normalized_receipt["workflow_class"] = current_class
        normalized_receipt["workflow_class_defaulted"] = current_defaulted
        if current_profile is None:
            normalized_receipt.pop("decision_profile", None)
        else:
            normalized_receipt["decision_profile"] = current_profile
        normalized_receipt["decision_profile_defaulted"] = (
            current_profile_defaulted
        )
        normalized_receipt["execution_mode"] = current_mode
        if current_isolation is None:
            normalized_receipt.pop("isolation_strategy", None)
        else:
            normalized_receipt["isolation_strategy"] = current_isolation
        normalized_receipt["verification_contract_bound"] = (
            current_contract is not None
        )
        normalized_receipt["verification_contract_provenance"] = (
            "authoritative_receipt" if current_contract is not None else
            "pre_binding" if has_contract_binding else "legacy_default_absent"
        )
        events.append(WorkflowEvent(
            1, sequence, run_id, node_id, "evidence.recorded", occurred_at,
            _safe_receipt_payload(normalized_receipt, reference),
        ))
    return tuple(events)
