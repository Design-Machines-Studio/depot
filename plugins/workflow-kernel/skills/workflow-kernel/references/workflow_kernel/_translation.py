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
import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Optional, Tuple

from .model import GateDecision, HostCapability, NodeSpec, WorkflowClass
from .redaction import (
    MAX_PAYLOAD_DEPTH, MAX_PAYLOAD_ITEMS, MAX_STRING_LENGTH,
    MAX_TOTAL_STRING_BYTES, bounded_iterable, contains_high_confidence_secret,
    freeze_json, normalize_evidence_reference, redact, sanitize_durable_payload,
    thaw,
)
from .schema import KernelError, WorkflowEvent
from .transitions import MAX_EVENT_ITEMS


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
    "branch_mode", "branch_mode_defaulted", "expected_feature_head",
    "final_review_mode", "final_review_mode_defaulted",
    "final_review_rationale", "final_review_effective_mode",
    "final_review_escalation",
    "contract_id", "schema_version", "revision", "contract_digest",
    "contract_ref", "previous_contract_digest", "reason_code",
    "verification_contract_bound", "verification_profile_id",
    "verification_profile_digest", "verification_profile_ref",
    "verification_contract_provenance",
    "chunk_id", "usage_scope", "measurement_source", "usage_estimated",
    "input_usage_count", "output_usage_count", "cache_read_usage_count",
    "cache_write_usage_count", "reasoning_usage_count", "input_bytes",
    "failure_kind", "identity_provenance", "source_receipt_digest",
    "source_invocation_id", "source_request_digest", "implementer_family",
    "reviewer_family",
    "resolution_reason",
    "source_finding_id", "canonical_finding_id", "finding_disposition",
    "agreement", "decision_reason_code", "source_severity", "evidence_ref",
    "action",
    "finding_path", "finding_anchor", "finding_category", "finding_root_cause",
    "raw_finding_count", "decision_count", "contribution_count",
    "coverage_complete", "synthesis_decisions_ref",
    "synthesis_decisions_digest", "raw_finding_inventory_ref",
    "raw_finding_inventory_digest", "lane_receipts_ref",
    "lane_receipts_digest", "raw_lane_outputs_ref",
    "raw_lane_outputs_digest",
    "human_intervention_id", "human_intervention_reason",
    "human_intervention", "missing_case_ids", "recovery_receipt_digests",
    "target_run_id", "target_sequence", "target_stage",
    "target_receipt_digest", "target_contract_digest",
    "reconciliation_reason",
    "matrix_snapshot_date", "rung_rationale", "diff_scope",
    "full_diff_override", "slice_status",
    "selective_rerun", "lanes_rerun", "lanes_skipped", "rerun_reasons",
    "selection_fallback_reason", "promoted_to_full", "full_fanout_override",
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
    "branchMode": "branch_mode",
    "branchModeDefaulted": "branch_mode_defaulted",
    "expectedFeatureHead": "expected_feature_head",
    "finalReviewMode": "final_review_mode",
    "finalReviewModeDefaulted": "final_review_mode_defaulted",
    "finalReviewRationale": "final_review_rationale",
    "finalReviewEffectiveMode": "final_review_effective_mode",
    "finalReviewEscalation": "final_review_escalation",
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
    "chunkId": "chunk_id",
    "usageScope": "usage_scope",
    "measurementSource": "measurement_source",
    "usageEstimated": "usage_estimated",
    "inputUsageCount": "input_usage_count",
    "inputBytes": "input_bytes",
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
    "sourceSeverity": "source_severity",
    "evidenceRef": "evidence_ref",
    "findingPath": "finding_path",
    "findingAnchor": "finding_anchor",
    "findingCategory": "finding_category",
    "findingRootCause": "finding_root_cause",
    "humanInterventionId": "human_intervention_id",
    "humanInterventionReason": "human_intervention_reason",
    "missingCaseIds": "missing_case_ids",
    "recoveryReceipts": "recovery_receipts",
    "matrixSnapshotDate": "matrix_snapshot_date",
    "rungRationale": "rung_rationale",
    "diffScope": "diff_scope",
    "fullDiffOverride": "full_diff_override",
    "sliceStatus": "slice_status",
    # Legacy producer vocabulary. The durable kernel name is deliberately
    # neutral because not every provider reports tokens.
    "tokens": "usage_count",
}

_MISSING = object()
_CONTRACT_STAGES = frozenset({"verification_contract_bound"})
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
    "verification_profile_id", "verification_profile_digest",
    "verification_profile_ref",
})
_CONTRACT_BINDING_MARKERS = _CONTRACT_FIELDS - frozenset({"reason_code"})
_RECEIPT_ENVELOPE_FIELDS = COMMON_RECEIPT_FIELDS | frozenset({
    "run_id", "sequence", "occurred_at", "node_id", "authoritative_receipt",
})
_CONTRACT_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTRACT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_CONTRACT_REASON = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_PROFILE_ID = re.compile(r"profile-sha256:[0-9a-f]{64}\Z")
_CREDENTIAL_LIKE = re.compile(
    r"(?i)^(?:sk-|gh[pousr]_|xox[baprs]-|bearer\s)",
)
_USAGE_SCOPES = frozenset({"attempt", "run"})
_WAIT_CATEGORIES = frozenset({"human_gate", "external_dependency", "capacity", "ci"})
_RUNG_RATIONALE_AXES = frozenset({"cost", "context", "strength", "availability"})
_SLICE_STATUSES = frozenset({
    "sliced", "not_sliced", "unclassified", "slice_failed",
    "full_diff_override",
})
_REVIEW_RERUN_REASONS = frozenset({
    "a_prior_unresolved_finding", "b_fix_file_trigger", "security_signoff",
    "initial_full_fanout", "selection_fail_open",
})
_REVIEW_ITERATION_FIELDS = frozenset({
    "selective_rerun", "lanes_rerun", "lanes_skipped", "rerun_reasons",
    "selection_fallback_reason", "promoted_to_full", "full_fanout_override",
})
_DIFF_SCOPE = re.compile(r"scoped\(([1-9][0-9]*) files of ([1-9][0-9]*)\)\Z")
# Every field that counts *something* about an attempt. The set is named for
# measurement rather than usage because `input_bytes` is a byte count, not a
# token count: the previous name promised token semantics to anything iterating
# it, while the member list quietly broke that promise.
_MEASUREMENT_FIELDS = frozenset({
    "usage_count", "input_usage_count", "output_usage_count",
    "cache_read_usage_count", "cache_write_usage_count",
    "reasoning_usage_count", "input_bytes",
})
# A row may legitimately carry no measurement, but only by saying so. Silence
# is the thing this backbone exists to remove: an absent row and a lane that
# never ran are indistinguishable, and the spend disappears with it.
# `attempt_unmeasured` is the explicit claim -- the lane ran, and nothing on
# this host reported usage for it.
_MEASUREMENTLESS_SOURCES = frozenset({
    "openrouter_receipt_no_usage", "openrouter_receipt_failed",
    "attempt_unmeasured",
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
_CANONICAL_FINDING_ID = re.compile(r"finding-v1:sha256\(([0-9a-f]{64})\)\Z")
_LINE_ANCHOR = re.compile(r"lines=([1-9][0-9]*)-([1-9][0-9]*)\Z")
_MAX_MISSING_CASE_IDS = 256
_MAX_MISSING_CASE_ID_BYTES = 16_384
LEGACY_BROWSER_RECONCILIATION_STAGE = "legacy_browser_reconciliation"
LEGACY_BROWSER_RECONCILIATION_REASON = (
    "legacy_browser_recovery_missing_canonical_proof"
)
_LEGACY_BROWSER_RECONCILIATION_FIELDS = frozenset({
    "target_run_id", "target_sequence", "target_stage",
    "target_receipt_digest", "target_contract_digest",
    "reconciliation_reason",
})
_LEGACY_BROWSER_RECONCILIATION_RECEIPT_FIELDS = (
    _LEGACY_BROWSER_RECONCILIATION_FIELDS | frozenset({
        "run_id", "sequence", "stage", "status", "occurred_at",
        "authoritative_receipt", "contract_digest",
    })
)


def required_text(value: object, field: str) -> str:
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError("invalid " + field)
    return value


def canonical_finding_identity(
    path: object, anchor: object, category: object, root_cause: object,
) -> tuple[str, dict[str, str]]:
    """Normalize and hash the public dm-review finding identity contract."""
    values = {
        "path": required_text(path, "finding path").replace("\\", "/").lower(),
        "anchor": " ".join(required_text(anchor, "finding anchor").lower().split()),
        "category": " ".join(required_text(category, "finding category").lower().split()),
        "root_cause": " ".join(
            required_text(root_cause, "finding root cause").lower().split()
        ),
    }
    path_parts = values["path"].split("/")
    if (
        values["path"].startswith("/") or values["path"].endswith("/")
        or "" in path_parts or any(part in {".", ".."} for part in path_parts)
    ):
        raise ValueError("invalid finding path")
    line_match = _LINE_ANCHOR.fullmatch(values["anchor"])
    if values["anchor"].startswith("lines=") and (
        line_match is None or int(line_match.group(1)) > int(line_match.group(2))
    ):
        raise ValueError("invalid finding anchor")
    normalized_key = "\n".join(f"{key}={values[key]}" for key in (
        "path", "anchor", "category", "root_cause",
    ))
    digest = hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()
    return f"finding-v1:sha256({digest})", values


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
_PROFILE_RUN_SPEC_FIELDS = _LEGACY_RUN_SPEC_FIELDS | frozenset({
    "decision_profile", "decision_profile_defaulted",
})
_RUN_SPEC_FIELDS = _PROFILE_RUN_SPEC_FIELDS | frozenset({
    "branch_mode", "branch_mode_defaulted", "expected_feature_head",
    "final_review_mode", "final_review_mode_defaulted",
    "final_review_rationale",
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
_BRANCH_MODES = frozenset({"create", "reuse"})
_FINAL_REVIEW_MODES = frozenset({"full", "quick"})
_EXACT_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


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
    # RunSpec and durable receipt payloads must carry one identical projection.
    # The receipt boundary digests strings beyond 256 characters and normalizes
    # URI-shaped text, so canonicalize the source profile through that same
    # policy before either representation can diverge.
    rationale = sanitize_durable_payload(rationale)
    if type(rationale) is not str:
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
    branch_mode: str = "create"
    branch_mode_defaulted: bool = True
    expected_feature_head: Optional[str] = None
    final_review_mode: str = "full"
    final_review_mode_defaulted: bool = True
    final_review_rationale: Optional[str] = None

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
        if self.branch_mode not in _BRANCH_MODES:
            raise ValueError("invalid RunSpec branch mode")
        if type(self.branch_mode_defaulted) is not bool:
            raise ValueError("invalid RunSpec branch mode provenance")
        if self.branch_mode_defaulted and self.branch_mode != "create":
            raise ValueError("invalid RunSpec branch mode provenance")
        if self.branch_mode == "reuse":
            if (
                type(self.expected_feature_head) is not str
                or _EXACT_COMMIT.fullmatch(self.expected_feature_head) is None
            ):
                raise ValueError("invalid RunSpec expected feature head")
        elif self.expected_feature_head is not None:
            raise ValueError("invalid RunSpec expected feature head")
        if self.final_review_mode not in _FINAL_REVIEW_MODES:
            raise ValueError("invalid RunSpec final review mode")
        if type(self.final_review_mode_defaulted) is not bool:
            raise ValueError("invalid RunSpec final review mode provenance")
        if self.branch_mode_defaulted != self.final_review_mode_defaulted:
            raise ValueError("incomplete RunSpec orchestration provenance")
        if self.final_review_mode_defaulted:
            if self.final_review_mode != "full" or self.final_review_rationale is not None:
                raise ValueError("invalid RunSpec final review mode provenance")
        else:
            rationale = required_text(
                self.final_review_rationale, "final review rationale",
            )
            if contains_high_confidence_secret(rationale):
                raise ValueError("invalid RunSpec final review rationale")
            rationale = sanitize_durable_payload(rationale)
            if type(rationale) is not str:
                raise ValueError("invalid RunSpec final review rationale")
            object.__setattr__(self, "final_review_rationale", rationale)
        if (
            self.final_review_mode == "quick"
            and (
                self.decision_profile is None
                or self.decision_profile["consequence"] == "high"
            )
        ):
            raise ValueError("quick final review requires non-high consequence")

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
            or set(value) not in {
                _LEGACY_RUN_SPEC_FIELDS, _PROFILE_RUN_SPEC_FIELDS,
                _RUN_SPEC_FIELDS,
            }
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
            legacy_orchestration = "branch_mode" not in value
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
                "create" if legacy_orchestration else value["branch_mode"],
                True if legacy_orchestration else value["branch_mode_defaulted"],
                None if legacy_orchestration else value["expected_feature_head"],
                "full" if legacy_orchestration else value["final_review_mode"],
                True if legacy_orchestration else value["final_review_mode_defaulted"],
                None if legacy_orchestration else value["final_review_rationale"],
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
            "branch_mode": self.branch_mode,
            "branch_mode_defaulted": self.branch_mode_defaulted,
            "expected_feature_head": self.expected_feature_head,
            "final_review_mode": self.final_review_mode,
            "final_review_mode_defaulted": self.final_review_mode_defaulted,
            "final_review_rationale": self.final_review_rationale,
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


_MODEL_FAMILY = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_INDEPENDENT_REVIEW_LANES = frozenset({
    "security-auditor-codex-signoff", "second-perspective",
})
_NATIVE_MODEL_FAMILIES = (
    ("openai", ("gpt-", "o1", "o3", "o4", "codex")),
    ("anthropic", ("claude-", "opus", "sonnet", "haiku")),
    ("google", ("gemini-",)),
    ("moonshotai", ("kimi-",)),
    ("z-ai", ("glm-",)),
)


def model_family_members(value: object, field: str) -> frozenset[str]:
    """Validate normalized family provenance and return its atomic members."""
    text = required_text(value, field)
    if _MODEL_FAMILY.fullmatch(text):
        return frozenset({text})
    if not text.startswith("mixed(") or not text.endswith(")"):
        raise ValueError("invalid " + field.replace("_", " "))
    members = text[6:-1].split(",")
    if (
        len(members) < 2
        or members != sorted(set(members))
        or any(_MODEL_FAMILY.fullmatch(member) is None for member in members)
    ):
        raise ValueError("invalid " + field.replace("_", " "))
    return frozenset(members)


def reviewer_family_from_model(value: object) -> str:
    """Derive one closed reviewer family from recorded model provenance."""
    model = required_text(value, "model").lower()
    if "/" in model:
        if model.count("/") != 1:
            raise ValueError("reviewer model has no recognized family")
        family, model_name = model.split("/", 1)
        if (
            _MODEL_FAMILY.fullmatch(family) is None
            or not model_name
        ):
            raise ValueError("reviewer model has no recognized family")
        return family
    for family, prefixes in _NATIVE_MODEL_FAMILIES:
        if model.startswith(prefixes):
            return family
    raise ValueError("reviewer model has no recognized family")


def validate_family_independence(receipt: Mapping[str, object]) -> None:
    implementers = model_family_members(
        receipt.get("implementer_family"), "implementer_family",
    )
    reviewers = model_family_members(
        receipt.get("reviewer_family"), "reviewer_family",
    )
    required_text(receipt.get("resolution_reason"), "resolution reason")
    if receipt.get("lane") in _INDEPENDENT_REVIEW_LANES:
        derived_reviewer = reviewer_family_from_model(receipt.get("model"))
        if reviewers != frozenset({derived_reviewer}):
            raise ValueError("reviewer family does not match model")
        if implementers & reviewers:
            raise ValueError("independent review family overlap")


def _validate_observation_receipt(
    receipt: dict, *, allow_legacy_browser_missing_proof: bool = False,
) -> dict:
    """Validate optional telemetry without treating it as authoritative."""
    receipt.pop("human_intervention", None)
    if "decision_profile" in receipt:
        receipt["decision_profile"] = normalize_decision_profile(
            receipt["decision_profile"],
        )
    if "decision_profile_defaulted" in receipt and type(
        receipt["decision_profile_defaulted"]
    ) is not bool:
        raise ValueError("invalid decision profile provenance")
    if "branch_mode" in receipt and receipt["branch_mode"] not in _BRANCH_MODES:
        raise ValueError("invalid branch mode")
    if "branch_mode_defaulted" in receipt and type(
        receipt["branch_mode_defaulted"]
    ) is not bool:
        raise ValueError("invalid branch mode provenance")
    if "expected_feature_head" in receipt and receipt["expected_feature_head"] is not None and (
        type(receipt["expected_feature_head"]) is not str
        or _EXACT_COMMIT.fullmatch(receipt["expected_feature_head"]) is None
    ):
        raise ValueError("invalid expected feature head")
    for field in ("final_review_mode", "final_review_effective_mode"):
        if field in receipt and receipt[field] not in _FINAL_REVIEW_MODES:
            raise ValueError("invalid " + field.replace("_", " "))
    if "final_review_mode_defaulted" in receipt and type(
        receipt["final_review_mode_defaulted"]
    ) is not bool:
        raise ValueError("invalid final review mode provenance")
    if "final_review_rationale" in receipt:
        rationale = required_text(
            receipt["final_review_rationale"], "final review rationale",
        )
        if contains_high_confidence_secret(rationale):
            raise ValueError("invalid final review rationale")
        receipt["final_review_rationale"] = sanitize_durable_payload(rationale)
    if "final_review_escalation" in receipt and receipt[
        "final_review_escalation"
    ] not in {"none", "security-sensitive-path"}:
        raise ValueError("invalid final review escalation")
    if "final_review_effective_mode" in receipt:
        requested = receipt.get("final_review_mode")
        escalation = receipt.get("final_review_escalation", "none")
        effective = receipt["final_review_effective_mode"]
        if requested not in _FINAL_REVIEW_MODES or (
            escalation == "none" and effective != requested
        ) or (
            escalation == "security-sensitive-path"
            and not (requested == "quick" and effective == "full")
        ):
            raise ValueError("invalid final review effective mode")
    for field in _MEASUREMENT_FIELDS:
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
    if "matrix_snapshot_date" in receipt:
        value = required_text(receipt["matrix_snapshot_date"], "matrix snapshot date")
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError("invalid matrix snapshot date")
        try:
            from datetime import datetime
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError("invalid matrix snapshot date") from None
    if "rung_rationale" in receipt and receipt["rung_rationale"] not in _RUNG_RATIONALE_AXES:
        raise ValueError("invalid rung rationale")
    iteration_fields = _REVIEW_ITERATION_FIELDS & set(receipt)
    if iteration_fields and receipt.get("stage") != "review_iteration":
        raise ValueError("review iteration fields on another stage")
    if receipt.get("stage") == "review_iteration":
        boolean_fields = (
            "selective_rerun", "promoted_to_full", "full_fanout_override",
        )
        if any(type(receipt.get(field)) is not bool for field in boolean_fields):
            raise ValueError("invalid review iteration selection")
        lanes = {}
        for field in ("lanes_rerun", "lanes_skipped"):
            values = receipt.get(field)
            if (
                type(values) is not list
                or any(type(value) is not str or not value for value in values)
                or len(values) != len(set(values))
            ):
                raise ValueError("invalid review iteration lanes")
            lanes[field] = values
        if set(lanes["lanes_rerun"]) & set(lanes["lanes_skipped"]):
            raise ValueError("invalid review iteration lanes")
        reasons = receipt.get("rerun_reasons")
        if type(reasons) is not dict or set(reasons) != set(lanes["lanes_rerun"]):
            raise ValueError("invalid review iteration reasons")
        for lane, values in reasons.items():
            if (
                type(lane) is not str or not lane
                or type(values) is not list or not values
                or len(values) != len(set(values))
                or any(value not in _REVIEW_RERUN_REASONS for value in values)
            ):
                raise ValueError("invalid review iteration reasons")
        fallback_reason = receipt.get("selection_fallback_reason")
        if fallback_reason is not None:
            receipt["selection_fallback_reason"] = required_text(
                fallback_reason, "selection fallback reason",
            )
        lane_reasons_fail_open = any(
            "selection_fail_open" in values for values in reasons.values()
        )
        selection_failed_open = fallback_reason is not None
        if (
            not selection_failed_open and lane_reasons_fail_open
            or selection_failed_open and any(
                "selection_fail_open" not in values
                for values in reasons.values()
            )
            or selection_failed_open and receipt["selective_rerun"]
            or lanes["lanes_skipped"] and not receipt["selective_rerun"]
            or receipt["selective_rerun"] and not lanes["lanes_skipped"]
            or receipt["selective_rerun"] and receipt["promoted_to_full"]
            or receipt["full_fanout_override"] and (
                receipt["selective_rerun"] or lanes["lanes_skipped"]
            )
            or receipt["promoted_to_full"] and lanes["lanes_skipped"]
        ):
            raise ValueError("incoherent review iteration selection")
    scope_present = {"diff_scope", "full_diff_override", "slice_status"} & set(receipt)
    if scope_present:
        if scope_present != {"diff_scope", "full_diff_override", "slice_status"}:
            raise ValueError("incomplete review diff scope")
        scope = required_text(receipt["diff_scope"], "diff scope")
        scoped = _DIFF_SCOPE.fullmatch(scope)
        if scope != "full" and scoped is None:
            raise ValueError("invalid review diff scope")
        if scoped is not None and int(scoped.group(1)) > int(scoped.group(2)):
            raise ValueError("invalid review diff scope")
        override = receipt["full_diff_override"]
        status = receipt["slice_status"]
        if type(override) is not bool or status not in _SLICE_STATUSES:
            raise ValueError("invalid review diff scope")
        coherent = (
            scoped is not None and not override and status == "sliced"
        ) or (
            scope == "full" and (
                override and status == "full_diff_override"
                or not override and status in {
                    "not_sliced", "unclassified", "slice_failed",
                }
            )
        )
        if not coherent:
            raise ValueError("invalid review diff scope")

    scoped = "usage_scope" in receipt
    detailed = bool((_MEASUREMENT_FIELDS - {"usage_count"}) & set(receipt))
    provenance = bool({"measurement_source", "usage_estimated"} & set(receipt))
    if detailed or provenance:
        scoped = True
    if scoped:
        if receipt.get("usage_scope") not in _USAGE_SCOPES:
            raise ValueError("invalid usage scope")
        required_text(receipt.get("measurement_source"), "measurement source")
        if type(receipt.get("usage_estimated")) is not bool:
            raise ValueError("invalid usage estimated flag")
        if not ((_MEASUREMENT_FIELDS & set(receipt)) or "cost_usd" in receipt):
            # Honest-absence allowance, exactly two provenance strings wide.
            # An OpenRouter receipt can carry no counters and no cost for two
            # distinct reasons: the attempt failed, or it succeeded and
            # reported nothing.  Both rows must survive intake so the
            # run-cost summary reports them as present-but-unmeasured rather
            # than silently dropping them -- an attempt that vanishes from the
            # cost picture is indistinguishable from one that never ran.  The
            # two are separate strings because a failed attempt may still have
            # been billed.  Every other measurement_source with no measurement
            # still fails closed.
            if receipt.get("measurement_source") not in _MEASUREMENTLESS_SOURCES:
                raise ValueError("scoped usage row has no measurement")
        if receipt.get("measurement_source") == "openrouter_receipt_failed":
            required_text(receipt.get("failure_kind"), "failure kind")
        elif "failure_kind" in receipt:
            raise ValueError("failure kind on a non-failed usage row")
        if "source_receipt_digest" in receipt:
            digest = receipt["source_receipt_digest"]
            if (
                type(digest) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
                or not receipt["measurement_source"].startswith("openrouter_")
            ):
                raise ValueError("invalid OpenRouter source receipt digest")
        for field in ("source_invocation_id", "source_request_digest"):
            if field in receipt and (
                type(receipt[field]) is not str
                or re.fullmatch(r"[0-9a-f]{64}", receipt[field]) is None
                or not receipt["measurement_source"].startswith("openrouter_")
            ):
                raise ValueError("invalid OpenRouter " + field.replace("_", " "))
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
            "decision_reason_code", "lane", "requested_provider",
            "attempted_provider", "implemented_by", "provider", "model",
            "finding_path", "finding_anchor", "finding_category",
            "finding_root_cause", "source_severity",
        ):
            required_text(receipt.get(field), field.replace("_", " "))
        validate_family_independence(receipt)
        canonical_id, normalized_identity = canonical_finding_identity(
            receipt["finding_path"], receipt["finding_anchor"],
            receipt["finding_category"], receipt["finding_root_cause"],
        )
        if (
            _CANONICAL_FINDING_ID.fullmatch(receipt["canonical_finding_id"]) is None
            or receipt["canonical_finding_id"] != canonical_id
        ):
            raise ValueError("invalid canonical finding identity")
        receipt.update({
            "finding_" + key: value for key, value in normalized_identity.items()
        })
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

    if receipt.get("stage") == "finding_contribution_coverage":
        if (
            receipt.get("status") != "complete"
            or receipt.get("coverage_complete") is not True
        ):
            raise ValueError("incomplete finding contribution coverage")
        for field in (
            "raw_finding_count", "decision_count", "contribution_count",
        ):
            _nonnegative_number(receipt.get(field), field, integer=True)
        if not (
            receipt["raw_finding_count"] == receipt["decision_count"]
            == receipt["contribution_count"]
        ):
            raise ValueError("incomplete finding contribution coverage")
        for field in (
            "synthesis_decisions_ref", "raw_finding_inventory_ref",
            "lane_receipts_ref", "raw_lane_outputs_ref",
        ):
            receipt[field] = safe_reference(receipt.get(field))
        for field in (
            "synthesis_decisions_digest", "raw_finding_inventory_digest",
            "lane_receipts_digest", "raw_lane_outputs_digest",
        ):
            value = receipt.get(field)
            if type(value) is not str or _CONTRACT_DIGEST.fullmatch(value) is None:
                raise ValueError("invalid contribution coverage digest")

    browser_recoveries = ()
    if receipt.get("stage") == "browser_recovery":
        recovery_values = receipt.get("recovery_receipts")
        if (
            type(recovery_values) is not list or not recovery_values
        ) and not allow_legacy_browser_missing_proof:
            raise ValueError("browser recovery lacks canonical proof")
        if recovery_values:
            try:
                from .browser_evidence import BrowserRecoveryReceipt
                browser_recoveries = tuple(
                    BrowserRecoveryReceipt.from_dict(value)
                    for value in recovery_values
                )
            except (TypeError, ValueError):
                raise ValueError("browser recovery lacks canonical proof") from None
            receipt["recovery_receipt_digests"] = [
                "sha256:" + hashlib.sha256(json.dumps(
                    value.to_dict(), sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")).hexdigest()
                for value in browser_recoveries
            ]

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
            if (
                not allow_legacy_browser_missing_proof
                and len(browser_recoveries) != len(cases)
            ):
                raise ValueError("browser intervention lacks recovery proof")
            if not allow_legacy_browser_missing_proof and (
                tuple(value.case_id for value in browser_recoveries) != tuple(cases)
                or any(
                    value.status != "blocked"
                    or value.reason_code != "human_help_required"
                    or value.missing_case_ids != (value.case_id,)
                    for value in browser_recoveries
                )
            ):
                raise ValueError("browser intervention lacks recovery proof")
        receipt["human_intervention"] = True
    return receipt


def canonical_observation_receipt_digest(receipt: object) -> str:
    """Digest one exact bounded raw receipt without rewriting its history."""
    if type(receipt) is not dict:
        raise ValueError("invalid reconciliation target")

    def require_exact_json(value: object, depth: int = 0) -> None:
        if depth > MAX_PAYLOAD_DEPTH:
            raise ValueError("invalid reconciliation target")
        if value is None or type(value) in {bool, str, int, float}:
            return
        if type(value) is list:
            for item in bounded_iterable(value, max_items=MAX_PAYLOAD_ITEMS):
                require_exact_json(item, depth + 1)
            return
        if type(value) is dict:
            for key in bounded_iterable(value, max_items=MAX_PAYLOAD_ITEMS):
                if type(key) is not str:
                    raise ValueError("invalid reconciliation target")
                require_exact_json(value[key], depth + 1)
            return
        raise ValueError("invalid reconciliation target")

    try:
        require_exact_json(receipt)
        snapshot = thaw(freeze_json(
            receipt,
            max_depth=MAX_PAYLOAD_DEPTH,
            max_items=MAX_PAYLOAD_ITEMS,
            max_string_length=MAX_STRING_LENGTH,
            max_total_string_bytes=MAX_TOTAL_STRING_BYTES,
        ))
        if snapshot != receipt:
            raise ValueError("invalid reconciliation target")
        encoded = json.dumps(
            snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (OverflowError, TypeError, ValueError, RecursionError):
        raise ValueError("invalid reconciliation target") from None
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _legacy_browser_reconciliations(values: tuple[dict, ...]) -> dict[int, dict]:
    claims = []
    for position, raw in enumerate(values):
        normalized = _normalized_receipt_fields(raw)
        if normalized.get("stage") == LEGACY_BROWSER_RECONCILIATION_STAGE:
            claims.append((position, normalized))
    if not claims:
        return {}

    targets = {}
    for position, claim in claims:
        if set(claim) != _LEGACY_BROWSER_RECONCILIATION_RECEIPT_FIELDS:
            raise ValueError("incomplete legacy browser reconciliation")
        if (
            claim.get("status") != "recorded"
            or claim.get("reconciliation_reason")
            != LEGACY_BROWSER_RECONCILIATION_REASON
            or claim.get("target_stage") != "browser_recovery"
            or type(claim.get("target_sequence")) is not int
            or claim["target_sequence"] < 0
            or claim["target_sequence"] >= position
            or claim.get("target_run_id") != claim.get("run_id")
            or type(claim.get("target_receipt_digest")) is not str
            or _CONTRACT_DIGEST.fullmatch(claim["target_receipt_digest"]) is None
            or type(claim.get("target_contract_digest")) is not str
            or claim.get("contract_digest") != claim["target_contract_digest"]
        ):
            raise ValueError("invalid legacy browser reconciliation")
        target_position = claim["target_sequence"]
        if target_position in targets:
            raise ValueError("duplicate legacy browser reconciliation")
        target = values[target_position]
        normalized_target = _normalized_receipt_fields(target)
        if (
            normalized_target.get("sequence") != target_position
            or normalized_target.get("run_id") != claim["target_run_id"]
            or normalized_target.get("stage") != claim["target_stage"]
            or normalized_target.get("status") != "blocked"
            or normalized_target.get("reason_code") != "human_help_required"
            or normalized_target.get("contract_digest")
            != claim["target_contract_digest"]
            or "recovery_receipts" in normalized_target
            or canonical_observation_receipt_digest(target)
            != claim["target_receipt_digest"]
        ):
            raise ValueError("legacy browser reconciliation target mismatch")
        targets[target_position] = claim
    return targets


def _safe_receipt_payload(receipt: Mapping[str, object], reference: str) -> dict:
    payload = {}
    for key in COMMON_RECEIPT_FIELDS:
        if key not in receipt:
            continue
        # Preserve field identity while sanitizing. The redaction policy uses
        # both key and value shape; wrapping everything under a neutral key
        # allowed credential-shaped telemetry to survive durable translation.
        if key == "canonical_finding_id":
            # This colon-bearing public identifier has already been recomputed
            # and exact-format validated. Generic evidence-reference handling
            # would otherwise misclassify it as an unsupported URL scheme.
            payload[key] = receipt[key]
            continue
        normalized = redact({key: sanitize_durable_payload(receipt[key])})
        if not isinstance(normalized, dict):
            raise ValueError("unsafe receipt payload")
        if key in normalized:
            payload[key] = normalized[key]
    payload["authoritative_receipt"] = reference
    payload["evidence"] = [reference]
    if receipt.get("stage") == "verification_contract_bound":
        payload["evidence"].append("verification_contract_bound")
    if receipt.get("stage") == "finding_contribution":
        payload["evidence"].append(receipt["evidence_ref"])
    elif receipt.get("stage") == "finding_contribution_coverage":
        payload["evidence"].extend((
            receipt["synthesis_decisions_ref"],
            receipt["raw_finding_inventory_ref"],
            receipt["lane_receipts_ref"],
            receipt["raw_lane_outputs_ref"],
        ))
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
    profile_id = receipt["verification_profile_id"]
    profile_digest = receipt["verification_profile_digest"]
    profile_ref = _contract_reference(
        receipt["verification_profile_ref"], "verification profile ref",
        nullable=True,
    )
    if (profile_id is None) != (profile_digest is None) or (
        profile_id is not None and (
            type(profile_id) is not str or _PROFILE_ID.fullmatch(profile_id) is None
            or type(profile_digest) is not str
            or _CONTRACT_DIGEST.fullmatch(profile_digest) is None
            or profile_ref != "verification-profiles/sha256-"
            + profile_digest.removeprefix("sha256:") + ".json"
        )
    ) or (profile_id is None and profile_ref is not None):
        raise ValueError("invalid verification profile binding receipt")
    stage = receipt["stage"]
    if (
        stage != "verification_contract_bound" or current is not None
        or revision != 1 or previous is not None
    ):
        raise ValueError("invalid verification contract continuity")
    return (
        contract_id, receipt["schema_version"], revision, digest,
        profile_id, profile_digest, profile_ref,
    )


def translate_receipts(
    receipts: Iterable[Mapping[str, object]], allowed_stages: frozenset, *,
    isolation_default: object = None,
    allow_legacy_browser_reconciliation: bool = False,
) -> Tuple[WorkflowEvent, ...]:
    if isolation_default is not None and isolation_default not in ISOLATION_STRATEGIES:
        raise ValueError("invalid isolation strategy")
    try:
        values = tuple(bounded_iterable(receipts, max_items=MAX_EVENT_ITEMS))
    except Exception:
        raise ValueError("invalid receipts") from None
    if any(type(receipt) is not dict for receipt in values):
        raise ValueError("receipt must be an object")
    reconciled_targets = (
        _legacy_browser_reconciliations(values)
        if allow_legacy_browser_reconciliation else {}
    )
    normalized_values = []
    for position, receipt in enumerate(values):
        normalized_values.append(_validate_observation_receipt(
            _normalized_receipt_fields(receipt),
            allow_legacy_browser_missing_proof=position in reconciled_targets,
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
    branch_mode = None
    branch_mode_defaulted = None
    expected_feature_head = None
    final_review_mode = None
    final_review_mode_defaulted = None
    final_review_rationale = None
    isolation_strategy = None
    current_contract = None
    contribution_sources = set()
    contribution_artifact_reviewers = {}
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
        branch_was_present = "branch_mode" in receipt
        current_branch_mode = receipt.get(
            "branch_mode", branch_mode or "create",
        )
        if current_branch_mode not in _BRANCH_MODES:
            raise ValueError("invalid branch mode")
        if "branch_mode_defaulted" in receipt:
            current_branch_defaulted = receipt["branch_mode_defaulted"]
        else:
            current_branch_defaulted = (
                not branch_was_present if position == 0
                else branch_mode_defaulted if not branch_was_present else False
            )
        current_expected_head = receipt.get(
            "expected_feature_head", expected_feature_head,
        )
        if current_branch_mode == "reuse":
            if (
                type(current_expected_head) is not str
                or _EXACT_COMMIT.fullmatch(current_expected_head) is None
            ):
                raise ValueError("invalid expected feature head")
        elif current_expected_head is not None:
            raise ValueError("invalid expected feature head")
        final_review_was_present = "final_review_mode" in receipt
        current_final_review_mode = receipt.get(
            "final_review_mode", final_review_mode or "full",
        )
        if current_final_review_mode not in _FINAL_REVIEW_MODES:
            raise ValueError("invalid final review mode")
        if "final_review_mode_defaulted" in receipt:
            current_final_review_defaulted = receipt["final_review_mode_defaulted"]
        else:
            current_final_review_defaulted = (
                not final_review_was_present if position == 0
                else final_review_mode_defaulted
                if not final_review_was_present else False
            )
        if current_branch_defaulted != current_final_review_defaulted:
            raise ValueError("incomplete orchestration provenance")
        current_final_review_rationale = receipt.get(
            "final_review_rationale", final_review_rationale,
        )
        if current_final_review_defaulted:
            if (
                current_final_review_mode != "full"
                or current_final_review_rationale is not None
            ):
                raise ValueError("invalid final review mode provenance")
        elif current_final_review_rationale is None:
            raise ValueError("invalid final review rationale")
        if (
            current_final_review_mode == "quick"
            and (
                current_profile is None
                or current_profile["consequence"] == "high"
            )
        ):
            raise ValueError("quick final review requires non-high consequence")
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
            branch_mode = current_branch_mode
            branch_mode_defaulted = current_branch_defaulted
            expected_feature_head = current_expected_head
            final_review_mode = current_final_review_mode
            final_review_mode_defaulted = current_final_review_defaulted
            final_review_rationale = current_final_review_rationale
            isolation_strategy = current_isolation
        elif (
            run_id, current_class, current_mode, current_defaulted,
            current_profile, current_profile_defaulted, current_isolation,
            current_branch_mode, current_branch_defaulted, current_expected_head,
            current_final_review_mode, current_final_review_defaulted,
            current_final_review_rationale,
        ) != (
            run_identity, workflow_class, execution_mode, workflow_class_defaulted,
            decision_profile, decision_profile_defaulted, isolation_strategy,
            branch_mode, branch_mode_defaulted, expected_feature_head,
            final_review_mode, final_review_mode_defaulted,
            final_review_rationale,
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
        occurred_at = required_text(receipt.get("occurred_at"), "occurred_at")
        node_id = receipt.get("node_id")
        if node_id is not None:
            node_id = required_text(node_id, "node id")
        reference = safe_reference(receipt.get("authoritative_receipt"))
        if stage in _CONTRACT_STAGES:
            current_contract = _validate_contract_receipt(receipt, current_contract)
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
        normalized_receipt["branch_mode"] = current_branch_mode
        normalized_receipt["branch_mode_defaulted"] = current_branch_defaulted
        if current_expected_head is None:
            normalized_receipt.pop("expected_feature_head", None)
        else:
            normalized_receipt["expected_feature_head"] = current_expected_head
        normalized_receipt["final_review_mode"] = current_final_review_mode
        normalized_receipt["final_review_mode_defaulted"] = (
            current_final_review_defaulted
        )
        if current_final_review_rationale is None:
            normalized_receipt.pop("final_review_rationale", None)
        else:
            normalized_receipt["final_review_rationale"] = (
                current_final_review_rationale
            )
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
