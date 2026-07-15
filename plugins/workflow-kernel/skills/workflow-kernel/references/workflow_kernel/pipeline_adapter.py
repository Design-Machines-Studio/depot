"""Pure, observation-only adapters for authoritative pipeline artifacts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Optional, Tuple

from .adapters.base import (
    BuilderSessionDecision, GateDecision, HostCapabilities, HostCapability,
    NodeSpec, WorkflowClass, WorkflowContext,
)
from .redaction import normalize_evidence_reference, redact
from .schema import WorkflowEvent
from .workflows import WorkflowTemplates


EXECUTION_MODES = frozenset({
    "claude_full", "claude_full_cli", "codex_native", "generic",
    "generic_host",
})
PIPELINE_STAGES = frozenset({
    "progress", "manifest_validation", "dependency_ready", "dispatch",
    "deterministic_validation", "evaluation_gate", "browser_verification",
    "merge_disposition", "chunk_cleanup", "requirements_cross_check",
    "terminal_reconciliation", "run_summary",
})
COMMON_RECEIPT_FIELDS = frozenset({
    "stage", "status", "host", "mechanism", "workflow_class", "provider",
    "model", "attempt", "duration_seconds", "first_pass", "fallback_reason",
    "retry_reason", "isolation_mode", "persona_expected", "persona_passed",
    "persona_recovered", "persona_missing", "cleanup_removed",
    "cleanup_retained", "cleanup_blocked", "cleanup_foreign", "tokens",
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
})
_RUN_ID_SEPARATORS = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ChunkSpec:
    node_id: str
    dependencies: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {"id": self.node_id, "depends_on": list(self.dependencies)}


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

    @classmethod
    def from_dict(cls, value: object) -> "RunSpec":
        fields = {
            "run_id", "workflow_class", "workflow_class_defaulted",
            "execution_mode", "host_name", "nodes", "chunks",
            "execution_levels", "execution_plan_disagreement",
            "required_lanes", "review_mode", "observation_only",
        }
        node_fields = {
            "id", "depends_on", "gate_kind", "required_evidence",
            "executor", "routing_reason", "gate_decision",
            "required_capability", "required_dispatch_capability",
            "executor_overridable",
        }
        gate_fields = {
            "allowed", "reason_code", "missing_evidence", "human_required",
        }
        if type(value) is not dict or set(value) != fields:
            raise ValueError("invalid RunSpec")
        if (
            value.get("observation_only") is not True
            or type(value.get("workflow_class_defaulted")) is not bool
            or type(value.get("execution_plan_disagreement")) is not bool
            or type(value.get("nodes")) is not list
            or type(value.get("chunks")) is not list
            or type(value.get("execution_levels")) is not list
            or type(value.get("required_lanes")) is not list
            or value.get("review_mode") is not None
            and type(value.get("review_mode")) is not str
        ):
            raise ValueError("invalid RunSpec")
        nodes = []
        for item in value["nodes"]:
            if type(item) is not dict or set(item) != node_fields:
                raise ValueError("invalid RunSpec node")
            gate = item["gate_decision"]
            if type(gate) is not dict or set(gate) != gate_fields:
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
        if any(type(level) is not list for level in value["execution_levels"]):
            raise ValueError("invalid RunSpec levels")
        spec = cls(
            _required_text(value["run_id"], "run_id"),
            WorkflowClass(value["workflow_class"]),
            value["workflow_class_defaulted"],
            _required_text(value["execution_mode"], "execution_mode"),
            _required_text(value["host_name"], "host_name"),
            tuple(nodes), tuple(chunks),
            tuple(tuple(level) for level in value["execution_levels"]),
            value["execution_plan_disagreement"],
            tuple(value["required_lanes"]), value["review_mode"],
        )
        if (
            spec.execution_mode not in EXECUTION_MODES
            or any(type(item) is not str or not item for item in spec.required_lanes)
            or len(spec.required_lanes) != len(set(spec.required_lanes))
            or spec.to_dict() != value
        ):
            raise ValueError("invalid RunSpec")
        return spec

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
            "observation_only": True,
        }


def _required_text(value: object, field: str) -> str:
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError("invalid " + field)
    return value


def _run_identity(value: object) -> str:
    value = _required_text(value, "feature")
    normalized = _RUN_ID_SEPARATORS.sub("-", value.lower()).strip("-")
    if not normalized or len(normalized) > 255:
        raise ValueError("invalid feature")
    return normalized


def _safe_reference(value: object) -> str:
    reference = _required_text(value, "authoritative receipt")
    try:
        return normalize_evidence_reference(reference)
    except ValueError:
        raise ValueError("unsafe authoritative receipt") from None


def _chunks(value: object) -> Tuple[ChunkSpec, ...]:
    if not isinstance(value, list):
        raise ValueError("chunks must be a list")
    chunks = []
    identifiers = set()
    for raw in value:
        if type(raw) is not dict:
            raise ValueError("chunk must be an object")
        node_id = _required_text(raw.get("id"), "chunk id")
        dependencies = raw.get("dependsOn", raw.get("depends_on", []))
        if not isinstance(dependencies, list) or any(
            type(item) is not str or not item for item in dependencies
        ) or len(dependencies) != len(set(dependencies)):
            raise ValueError("invalid chunk dependencies")
        if node_id in identifiers:
            raise ValueError("duplicate chunk id")
        identifiers.add(node_id)
        chunks.append(ChunkSpec(node_id, tuple(dependencies)))
    for chunk in chunks:
        if chunk.node_id in chunk.dependencies or not set(chunk.dependencies) <= identifiers:
            raise ValueError("invalid chunk dependency graph")
    return tuple(chunks)


def _levels(chunks: Tuple[ChunkSpec, ...]) -> Tuple[Tuple[str, ...], ...]:
    by_id = {chunk.node_id: chunk for chunk in chunks}
    indegree = {chunk.node_id: len(chunk.dependencies) for chunk in chunks}
    dependents = {chunk.node_id: [] for chunk in chunks}
    for chunk in chunks:
        for dependency in chunk.dependencies:
            dependents[dependency].append(chunk.node_id)
    ready = deque(sorted(node_id for node_id, count in indegree.items() if count == 0))
    levels = []
    visited = 0
    while ready:
        current = tuple(ready)
        ready.clear()
        levels.append(current)
        visited += len(current)
        next_ready = []
        for node_id in current:
            for dependent in dependents[node_id]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    next_ready.append(dependent)
        ready.extend(sorted(next_ready))
    if visited != len(by_id):
        raise ValueError("chunk dependency cycle")
    return tuple(levels)


def _cached_plan(value: object) -> Optional[Tuple[Tuple[str, ...], ...]]:
    if value is None:
        return None
    if type(value) is dict:
        value = value.get("levels")
        if type(value) is not list:
            raise ValueError("invalid executionPlan")
        result = []
        for expected_level, raw in enumerate(value):
            if type(raw) is not dict or raw.get("level") != expected_level:
                raise ValueError("invalid executionPlan")
            strategy = raw.get("strategy")
            if strategy == "sequential":
                items = raw.get("chunks")
                if type(items) is not list:
                    raise ValueError("invalid executionPlan")
            elif strategy == "parallel":
                groups = raw.get("groups")
                if type(groups) is not dict or any(
                    type(key) is not str or type(group) is not list
                    for key, group in groups.items()
                ):
                    raise ValueError("invalid executionPlan")
                items = [item for key in sorted(groups) for item in groups[key]]
            else:
                raise ValueError("invalid executionPlan")
            if any(type(item) is not str or not item for item in items):
                raise ValueError("invalid executionPlan")
            result.append(tuple(items))
        return tuple(result)
    if type(value) is not list or any(type(level) is not list for level in value):
        raise ValueError("invalid executionPlan")
    result = []
    for level in value:
        if any(type(item) is not str or not item for item in level):
            raise ValueError("invalid executionPlan")
        result.append(tuple(level))
    return tuple(result)


def translate_manifest(manifest: Mapping[str, object], profile: HostCapabilities) -> RunSpec:
    if type(manifest) is not dict or type(profile) is not HostCapabilities:
        raise ValueError("invalid manifest or host profile")
    identity = manifest.get("feature")
    if identity is None:  # bounded legacy compatibility; canonical feature wins.
        identity = manifest.get("runId", manifest.get("run_id"))
    run_id = _run_identity(identity)
    raw_class = manifest.get("workflowClass")
    defaulted = raw_class is None
    try:
        workflow_class = WorkflowClass.FEATURE if defaulted else WorkflowClass(raw_class)
    except (TypeError, ValueError):
        raise ValueError("invalid workflowClass") from None
    execution_mode = manifest.get("executionMode", "generic")
    if type(execution_mode) is not str or execution_mode not in EXECUTION_MODES:
        raise ValueError("invalid executionMode")
    chunks = _chunks(manifest.get("chunks"))
    levels = _levels(chunks)
    cached = _cached_plan(manifest.get("executionPlan"))
    changed_paths = manifest.get("changedPaths", manifest.get("changed_paths", []))
    if not isinstance(changed_paths, list):
        raise ValueError("invalid changed paths")
    risk = manifest.get("risk", "low")
    requested_executor = manifest.get("requestedExecutor")
    context = WorkflowContext(
        changed_paths=tuple(changed_paths), requested_executor=requested_executor,
        risk=risk,
    )
    # WorkflowTemplates remains the single safety anchor. Host capability
    # aggregation is intentionally not treated as route authorization here.
    nodes = WorkflowTemplates().expand(workflow_class, context)
    return RunSpec(
        run_id, workflow_class, defaulted, execution_mode, profile.host_name,
        nodes, chunks, levels, cached is not None and cached != levels,
    )


def _safe_receipt_payload(receipt: Mapping[str, object], reference: str) -> dict:
    payload = {}
    for key in COMMON_RECEIPT_FIELDS:
        if key not in receipt:
            continue
        # Redact each value under a neutral key. Field names such as `tokens`
        # and `fallback_path` are reliability facts, not credentials or local
        # filesystem evidence, and must retain their documented meaning.
        normalized = redact({"value": receipt[key]})
        if not isinstance(normalized, dict) or "value" not in normalized:
            raise ValueError("unsafe receipt payload")
        # Keys containing `token` are credential-like in the durable schema;
        # use a neutral usage counter so aggregate counts survive redaction.
        output_key = "usage_count" if key == "tokens" else key
        payload[output_key] = normalized["value"]
    payload["authoritative_receipt"] = reference
    payload["evidence"] = [reference]
    return payload


def _translate_receipts(
    receipts: Iterable[Mapping[str, object]], allowed_stages: frozenset,
) -> Tuple[WorkflowEvent, ...]:
    try:
        values = tuple(receipts)
    except Exception:
        raise ValueError("invalid receipts") from None
    events = []
    run_identity = None
    workflow_class = None
    execution_mode = None
    workflow_class_defaulted = None
    for position, receipt in enumerate(values):
        if type(receipt) is not dict:
            raise ValueError("receipt must be an object")
        run_id = _required_text(receipt.get("run_id"), "run id")
        sequence = receipt.get("sequence")
        if type(sequence) is not int or sequence != position:
            raise ValueError("invalid receipt sequence")
        class_was_present = "workflow_class" in receipt
        current_class = _required_text(
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
        else:
            current_defaulted = (
                not class_was_present if position == 0 else
                workflow_class_defaulted if not class_was_present else False
            )
        current_mode = _required_text(
            receipt.get("execution_mode", execution_mode or "generic"),
            "execution mode",
        )
        if current_mode not in EXECUTION_MODES:
            raise ValueError("invalid execution mode")
        if position == 0:
            run_identity, workflow_class, execution_mode = run_id, current_class, current_mode
            workflow_class_defaulted = current_defaulted
        elif (run_id, current_class, current_mode, current_defaulted) != (
            run_identity, workflow_class, execution_mode, workflow_class_defaulted,
        ):
            raise ValueError("receipt context discontinuity")
        stage = _required_text(receipt.get("stage"), "stage")
        if stage not in allowed_stages:
            raise ValueError("unknown receipt stage")
        occurred_at = _required_text(receipt.get("occurred_at"), "occurred_at")
        node_id = receipt.get("node_id")
        if node_id is not None:
            node_id = _required_text(node_id, "node id")
        reference = _safe_reference(receipt.get("authoritative_receipt"))
        normalized_receipt = dict(receipt)
        normalized_receipt["workflow_class"] = current_class
        normalized_receipt["workflow_class_defaulted"] = current_defaulted
        normalized_receipt["execution_mode"] = current_mode
        events.append(WorkflowEvent(
            1, sequence, run_id, node_id, "evidence.recorded", occurred_at,
            _safe_receipt_payload(normalized_receipt, reference),
        ))
    return tuple(events)


def translate_pipeline_receipts(
    receipts: Iterable[Mapping[str, object]],
) -> Tuple[WorkflowEvent, ...]:
    return _translate_receipts(receipts, PIPELINE_STAGES)


def translate_builder_decision(
    decision: BuilderSessionDecision, *, authoritative_receipt_reference: str,
    sequence: int, occurred_at: str,
) -> WorkflowEvent:
    reference = _safe_reference(authoritative_receipt_reference)
    if type(decision) is not BuilderSessionDecision:
        raise ValueError("invalid builder decision")
    base = decision.to_evidence_event(
        run_id=decision.context.run_id, sequence=sequence,
        node_id=decision.context.node_id, occurred_at=occurred_at,
    )
    values = [reference]
    if decision.result is not None:
        values.extend(decision.result.evidence)
    values.extend(base.payload["evidence"])
    evidence = tuple(dict.fromkeys(values))
    return WorkflowEvent(
        1, sequence, base.run_id, base.node_id, "evidence.recorded",
        occurred_at, {
            "evidence": list(evidence),
            "authoritative_receipt": reference,
            "stage": "builder_continuity",
            "status": decision.status,
        },
    )
