"""Data-driven workflow-class expansion and sensitive routing overrides."""

from __future__ import annotations

import fnmatch
import json
from collections import deque
from pathlib import Path
from typing import Optional

from .adapters.base import (
    DEFAULT_EXECUTOR_CAPABILITY, EXECUTOR_CAPABILITIES, EXECUTORS, GATE_KINDS,
    HostCapability, NodeSpec, WorkflowClass, WorkflowContext, invalid_policy,
)
from .policies import GatePolicy


WORKFLOW_CLASSES_SCHEMA_VERSION = 1
DEFAULT_CLASSES_PATH = Path(__file__).resolve().parent.parent / "workflow-classes.json"
DEFAULT_CLASSES_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "workflow-classes-schema.json"
)


def _repository_file(relative: str) -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / relative
        if candidate.is_file():
            return candidate
    raise invalid_policy("routing_policy_unavailable")


def _load_sensitive_globs(path: Optional[Path]) -> tuple[str, ...]:
    source = Path(path) if path is not None else _repository_file(
        "plugins/pipeline/references/routing-policy.json"
    )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        globs = payload["security"]["neverRouteOffAnthropic"]["pathGlobs"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        raise invalid_policy("invalid_routing_policy") from None
    if not isinstance(globs, list) or any(type(value) is not str or not value for value in globs):
        raise invalid_policy("invalid_routing_policy")
    return tuple(globs)


def _node_record(value: object) -> dict:
    if type(value) is not dict:
        raise invalid_policy("invalid_workflow_node")
    allowed = {
        "id", "depends_on", "gate_kind", "required_evidence", "executor",
        "required_capability", "executor_overridable",
    }
    if "id" not in value:
        raise invalid_policy("missing_node_id")
    if set(value) != allowed:
        raise invalid_policy("invalid_workflow_node")
    node_id = value["id"]
    if type(node_id) is not str or not node_id:
        raise invalid_policy("missing_node_id")
    dependencies = value["depends_on"]
    required_evidence = value["required_evidence"]
    if not isinstance(dependencies, list) or any(
        type(item) is not str or not item for item in dependencies
    ) or len(dependencies) != len(set(dependencies)):
        raise invalid_policy("invalid_node_dependencies")
    if not isinstance(required_evidence, list) or any(
        type(item) is not str or not item for item in required_evidence
    ) or len(required_evidence) != len(set(required_evidence)):
        raise invalid_policy("invalid_node_evidence")
    if value["gate_kind"] is not None and (
        type(value["gate_kind"]) is not str or value["gate_kind"] not in GATE_KINDS
    ):
        raise invalid_policy("unknown_gate_kind")
    if value["executor"] is not None and (
        type(value["executor"]) is not str or value["executor"] not in EXECUTORS
    ):
        raise invalid_policy("unknown_executor")
    try:
        required_capability = (
            None if value["required_capability"] is None
            else HostCapability(value["required_capability"])
        )
    except (TypeError, ValueError):
        raise invalid_policy("unknown_capability_name") from None
    if type(value["executor_overridable"]) is not bool:
        raise invalid_policy("invalid_workflow_node")
    if value["executor"] is None and required_capability is not None:
        raise invalid_policy("inconsistent_executor_capability")
    if value["executor"] is not None and required_capability not in EXECUTOR_CAPABILITIES[value["executor"]]:
        raise invalid_policy("inconsistent_executor_capability")
    if value["executor"] is None and value["executor_overridable"]:
        raise invalid_policy("inconsistent_executor_capability")
    return {
        "id": node_id,
        "depends_on": tuple(dependencies),
        "gate_kind": value["gate_kind"],
        "required_evidence": tuple(required_evidence),
        "executor": value["executor"],
        "required_capability": required_capability,
        "executor_overridable": value["executor_overridable"],
    }


def _validate_graph(records: tuple[dict, ...]) -> None:
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise invalid_policy("duplicate_node_id")
    node_ids = set(ids)
    indegree = {record["id"]: len(record["depends_on"]) for record in records}
    dependents = {node_id: [] for node_id in node_ids}
    for record in records:
        for dependency in record["depends_on"]:
            if dependency not in node_ids:
                raise invalid_policy("missing_template_dependency")
            if dependency == record["id"]:
                raise invalid_policy("template_dependency_cycle")
            dependents[dependency].append(record["id"])
    ready = deque(node_id for node_id, count in indegree.items() if count == 0)
    visited = 0
    while ready:
        current = ready.popleft()
        visited += 1
        for dependent in dependents[current]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if visited != len(records):
        raise invalid_policy("template_dependency_cycle")
    seen = set()
    for record in records:
        if not set(record["depends_on"]) <= seen:
            raise invalid_policy("non_topological_dependency_order")
        seen.add(record["id"])
    if not records or records[-1]["id"] != "cleanup":
        raise invalid_policy("cleanup_node_required")
    terminal_nodes = {node_id for node_id, children in dependents.items() if not children}
    if terminal_nodes != {"cleanup"}:
        raise invalid_policy("cleanup_terminal_invariant")
    cleanup_ancestors = set()
    dependencies_by_id = {record["id"]: record["depends_on"] for record in records}
    pending = ["cleanup"]
    while pending:
        current = pending.pop()
        if current in cleanup_ancestors:
            continue
        cleanup_ancestors.add(current)
        pending.extend(dependencies_by_id[current])
    if cleanup_ancestors != node_ids:
        raise invalid_policy("cleanup_terminal_invariant")


def _load_boundaries() -> dict:
    try:
        schema = json.loads(DEFAULT_CLASSES_SCHEMA_PATH.read_text(encoding="utf-8"))
        boundaries = schema["x-kernel-boundaries"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        raise invalid_policy("invalid_workflow_boundary_schema") from None
    if type(boundaries) is not dict or set(boundaries) != {"classes", "promotion"}:
        raise invalid_policy("invalid_workflow_boundary_schema")
    return boundaries


def _validate_boundary(records: tuple[dict, ...], boundary: object, reason: str) -> None:
    if type(boundary) is not dict or set(boundary) != {
        "node_ids", "edges", "gates", "executors", "terminal_node",
    }:
        raise invalid_policy("invalid_workflow_boundary_schema")
    try:
        node_ids = tuple(boundary["node_ids"])
        edges = tuple(tuple(item) for item in boundary["edges"])
        gates = {
            node_id: (value["gate_kind"], tuple(value["required_evidence"]))
            for node_id, value in boundary["gates"].items()
        }
        executors = {
            node_id: (
                value["executor"], value["required_capability"],
                value["executor_overridable"],
            )
            for node_id, value in boundary["executors"].items()
        }
        terminal = boundary["terminal_node"]
    except (AttributeError, KeyError, TypeError):
        raise invalid_policy("invalid_workflow_boundary_schema") from None
    actual_edges = tuple(
        (dependency, record["id"])
        for record in records for dependency in record["depends_on"]
    )
    actual_gates = {
        record["id"]: (record["gate_kind"], record["required_evidence"])
        for record in records if record["gate_kind"] is not None
    }
    actual_executors = {
        record["id"]: (
            record["executor"],
            record["required_capability"].value,
            record["executor_overridable"],
        )
        for record in records if record["executor"] is not None
    }
    if (
        tuple(record["id"] for record in records) != node_ids
        or actual_edges != edges
        or actual_gates != gates
        or actual_executors != executors
        or not records
        or records[-1]["id"] != terminal
    ):
        raise invalid_policy(reason)


def _load_templates(path: Optional[Path]) -> dict[WorkflowClass, tuple[dict, ...]]:
    boundaries = _load_boundaries()
    class_boundaries = boundaries["classes"]
    if type(class_boundaries) is not dict or set(class_boundaries) != {
        kind.value for kind in WorkflowClass
    }:
        raise invalid_policy("invalid_workflow_boundary_schema")
    source = Path(path) if path is not None else DEFAULT_CLASSES_PATH
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise invalid_policy("invalid_workflow_classes_json") from None
    if type(payload) is not dict or set(payload) != {"schema_version", "classes", "promotion"}:
        raise invalid_policy("invalid_workflow_classes_document")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != WORKFLOW_CLASSES_SCHEMA_VERSION:
        raise invalid_policy("unsupported_policy_version")
    classes = payload["classes"]
    if type(classes) is not dict or set(classes) != {kind.value for kind in WorkflowClass}:
        raise invalid_policy("invalid_workflow_class_set")
    result = {}
    for kind in WorkflowClass:
        definition = classes[kind.value]
        if type(definition) is not dict or set(definition) != {"nodes"}:
            raise invalid_policy("invalid_workflow_class")
        if not isinstance(definition["nodes"], list):
            raise invalid_policy("invalid_workflow_class")
        records = tuple(_node_record(item) for item in definition["nodes"])
        _validate_graph(records)
        _validate_boundary(
            records, class_boundaries[kind.value],
            "mandatory_workflow_boundary_changed",
        )
        result[kind] = records
    promotion = payload["promotion"]
    if type(promotion) is not dict or set(promotion) != {"investigation"}:
        raise invalid_policy("invalid_promotion_policy")
    promoted = promotion["investigation"]
    if type(promoted) is not dict or set(promoted) != {"nodes"}:
        raise invalid_policy("invalid_promotion_policy")
    promotion_nodes = tuple(_node_record(item) for item in promoted["nodes"])
    _validate_boundary(
        promotion_nodes, boundaries["promotion"], "promotion_boundary_invalid",
    )
    result["promotion"] = promotion_nodes
    return result


class WorkflowTemplates:
    def __init__(
        self,
        path: Optional[Path] = None,
        *,
        policy_path: Optional[Path] = None,
        routing_policy_path: Optional[Path] = None,
    ):
        self._templates = _load_templates(path)
        self._gate_policy = GatePolicy(policy_path)
        self._sensitive_globs = _load_sensitive_globs(routing_policy_path)

    def expand(
        self,
        kind: WorkflowClass,
        context: WorkflowContext,
    ) -> tuple[NodeSpec, ...]:
        try:
            normalized = kind if type(kind) is WorkflowClass else WorkflowClass(kind)
        except (TypeError, ValueError):
            raise invalid_policy("unknown_workflow_class") from None
        if type(context) is not WorkflowContext:
            raise invalid_policy("invalid_workflow_context")
        records = list(self._templates[normalized])
        if (
            normalized is WorkflowClass.INVESTIGATION
            and context.investigation_promotion
            and context.promotion_approved
            and "promotion_decision" in context.evidence
        ):
            promotion = list(self._templates["promotion"])
            conclusion_index = next(
                index for index, record in enumerate(records)
                if record["id"] == "conclusion_next_action"
            )
            conclusion = dict(records[conclusion_index])
            conclusion["depends_on"] = ("promoted_build",)
            records[conclusion_index:conclusion_index + 1] = promotion + [conclusion]
        _validate_graph(tuple(records))
        sensitive = any(
            fnmatch.fnmatchcase(path, pattern)
            for path in context.changed_paths
            for pattern in self._sensitive_globs
        )
        nodes = []
        for record in records:
            executor = record["executor"]
            required_capability = record["required_capability"]
            executor_overridable = record["executor_overridable"]
            routing_reason = None
            if executor is not None:
                if sensitive:
                    executor = "claude"
                    required_capability = HostCapability.ANTHROPIC_NATIVE_EXECUTION
                    routing_reason = "sensitive_path_override"
                elif normalized is WorkflowClass.SECURITY:
                    executor = "claude"
                    required_capability = HostCapability.ANTHROPIC_NATIVE_EXECUTION
                    routing_reason = "security_workflow_override"
                elif context.requested_executor is not None and executor_overridable:
                    executor = context.requested_executor
                    required_capability = DEFAULT_EXECUTOR_CAPABILITY[executor]
                    routing_reason = "requested_executor"
                else:
                    routing_reason = "workflow_default"
            gate = self._gate_policy.decide(
                normalized, record["gate_kind"], record["required_evidence"], context,
            )
            nodes.append(NodeSpec(
                node_id=record["id"],
                dependencies=record["depends_on"],
                gate_kind=record["gate_kind"],
                required_evidence=record["required_evidence"],
                executor=executor,
                routing_reason=routing_reason,
                gate_decision=gate,
                required_capability=required_capability,
                executor_overridable=executor_overridable,
            ))
        return tuple(nodes)
