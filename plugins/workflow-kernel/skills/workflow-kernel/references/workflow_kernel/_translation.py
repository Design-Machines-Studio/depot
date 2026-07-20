"""Shared receipt-translation core for the pipeline and dm-review adapters.

Both adapters translate authoritative artifacts into observation-only events
and must agree on the execution-mode vocabulary, the redaction-safe receipt
field set, dual-format (camelCase/snake_case) key resolution, and receipt
event translation. This module is the single owner of that shared core so a
refactor of one adapter cannot silently break the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Tuple

from .model import GateDecision, HostCapability, NodeSpec, WorkflowClass
from .redaction import normalize_evidence_reference, redact
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
# Documented camelCase receipt spellings (pipeline and dm-review instruct
# producers to emit these provider-evidence fields) mapped to the canonical
# snake_case receipt schema. A conflicting duplicate is rejected, never
# silently dropped.
RECEIPT_FIELD_ALIASES = {
    "executionMode": "execution_mode",
    "workflowClass": "workflow_class",
    "workflowClassDefaulted": "workflow_class_defaulted",
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
}

_MISSING = object()


def required_text(value: object, field: str) -> str:
    if type(value) is not str or not value or len(value) > 4096:
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


_RUN_SPEC_FIELDS = frozenset({
    "run_id", "workflow_class", "workflow_class_defaulted",
    "execution_mode", "host_name", "nodes", "chunks",
    "execution_levels", "execution_plan_disagreement",
    "required_lanes", "review_mode", "observation_only",
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
            or set(value) != _RUN_SPEC_FIELDS
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
        if snake in normalized and normalized[snake] != candidate:
            raise ValueError("conflicting receipt field " + snake + "/" + camel)
        normalized[snake] = candidate
    return normalized


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
    events = []
    run_identity = None
    workflow_class = None
    execution_mode = None
    workflow_class_defaulted = None
    isolation_strategy = None
    for position, receipt in enumerate(values):
        if type(receipt) is not dict:
            raise ValueError("receipt must be an object")
        receipt = _normalized_receipt_fields(receipt)
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
            isolation_strategy = current_isolation
        elif (run_id, current_class, current_mode, current_defaulted, current_isolation) != (
            run_identity, workflow_class, execution_mode, workflow_class_defaulted,
            isolation_strategy,
        ):
            raise ValueError("receipt context discontinuity")
        stage = required_text(receipt.get("stage"), "stage")
        if stage not in allowed_stages:
            raise ValueError("unknown receipt stage")
        occurred_at = required_text(receipt.get("occurred_at"), "occurred_at")
        node_id = receipt.get("node_id")
        if node_id is not None:
            node_id = required_text(node_id, "node id")
        reference = safe_reference(receipt.get("authoritative_receipt"))
        normalized_receipt = dict(receipt)
        normalized_receipt["workflow_class"] = current_class
        normalized_receipt["workflow_class_defaulted"] = current_defaulted
        normalized_receipt["execution_mode"] = current_mode
        if current_isolation is None:
            normalized_receipt.pop("isolation_strategy", None)
        else:
            normalized_receipt["isolation_strategy"] = current_isolation
        events.append(WorkflowEvent(
            1, sequence, run_id, node_id, "evidence.recorded", occurred_at,
            _safe_receipt_payload(normalized_receipt, reference),
        ))
    return tuple(events)
