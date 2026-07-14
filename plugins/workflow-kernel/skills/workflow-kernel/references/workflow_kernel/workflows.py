"""Data-driven workflow-class expansion and sensitive routing overrides."""

from __future__ import annotations

import fnmatch
import json
from collections import deque
from pathlib import Path
from typing import Mapping, Optional

from .adapters.base import (
    DEFAULT_EXECUTOR_CAPABILITY, GATE_KINDS, HostCapability, NodeSpec,
    WorkflowClass, WorkflowContext, _snapshot_workflow_context, invalid_policy,
    _normalize_enum, normalize_executor_constraint,
)
from .limits import JSONDocumentDepthError, load_json_document
from .policies import GatePolicy, load_policy


WORKFLOW_CLASSES_SCHEMA_VERSION = 1
DEFAULT_CLASSES_PATH = Path(__file__).resolve().parent.parent / "workflow-classes.json"


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
        "required_capability", "required_dispatch_capability",
        "executor_overridable",
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
    if value["gate_kind"] not in (None, "cleanup") and not required_evidence:
        raise invalid_policy("invalid_workflow_node")
    executor, required_capability, required_dispatch_capability = (
        normalize_executor_constraint(
            value["executor"], value["required_capability"],
            value["required_dispatch_capability"],
        )
    )
    if type(value["executor_overridable"]) is not bool:
        raise invalid_policy("invalid_workflow_node")
    if executor is None and value["executor_overridable"]:
        raise invalid_policy("inconsistent_executor_capability")
    return {
        "id": node_id,
        "depends_on": tuple(dependencies),
        "gate_kind": value["gate_kind"],
        "required_evidence": tuple(required_evidence),
        "executor": executor,
        "required_capability": required_capability,
        "required_dispatch_capability": required_dispatch_capability,
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


def _validate_promotion(records: tuple[dict, ...]) -> None:
    """Require every promoted execution path to cross a promotion gate."""
    ids = [record["id"] for record in records]
    if not records or len(ids) != len(set(ids)):
        raise invalid_policy("promotion_gate_required")
    by_id = {record["id"]: record for record in records}
    seen = set()
    for record in records:
        internal = {value for value in record["depends_on"] if value in by_id}
        if not internal <= seen:
            raise invalid_policy("promotion_gate_required")
        seen.add(record["id"])
    gates = {
        record["id"] for record in records
        if record["gate_kind"] == "investigation_promotion"
    }
    if not gates:
        raise invalid_policy("promotion_gate_required")
    for record in records:
        if record["executor"] is None:
            continue
        ancestors = set()
        pending = list(record["depends_on"])
        while pending:
            dependency = pending.pop()
            if dependency in ancestors:
                continue
            ancestors.add(dependency)
            if dependency in by_id:
                pending.extend(by_id[dependency]["depends_on"])
        if not gates <= ancestors:
            raise invalid_policy("promotion_gate_required")


def _ancestors(record: dict, by_id: dict[str, dict]) -> set[str]:
    result = set()
    pending = list(record["depends_on"])
    while pending:
        dependency = pending.pop()
        if dependency in result:
            continue
        result.add(dependency)
        if dependency in by_id:
            pending.extend(by_id[dependency]["depends_on"])
    return result


def _validate_required_stages(
    records: tuple[dict, ...], requirements: tuple[Mapping[str, object], ...],
) -> None:
    by_id = {record["id"]: record for record in records}
    for required in requirements:
        record = by_id.get(required["id"])
        if record is None or (
            record["gate_kind"] != required["gate_kind"]
            or record["required_evidence"] != required["required_evidence"]
            or record["executor"] != required["executor"]
            or record["required_capability"] != required["required_capability"]
            or record["required_dispatch_capability"]
            != required["required_dispatch_capability"]
            or record["executor_overridable"] != required["executor_overridable"]
            or not set(required["required_ancestors"]) <= _ancestors(record, by_id)
        ):
            raise invalid_policy("workflow_requirement_unsatisfied")


def _validate_anchored_execution(
    records: tuple[dict, ...], requirements: tuple[Mapping[str, object], ...],
) -> None:
    anchored = {required["id"] for required in requirements}
    if any(
        record["executor"] is not None and record["id"] not in anchored
        for record in records
    ):
        raise invalid_policy("workflow_requirement_unsatisfied")


def _validate_safety_anchor(
    anchor: Mapping[str, object],
    classes: dict[WorkflowClass, tuple[dict, ...]],
    promotion: tuple[dict, ...],
) -> None:
    for records in classes.values():
        _validate_required_stages(records, anchor["common"])
    for kind in anchor["non_executable_classes"]:
        if any(record["executor"] is not None for record in classes[kind]):
            raise invalid_policy("workflow_requirement_unsatisfied")
    for kind, required in anchor["classes"].items():
        _validate_required_stages(classes[kind], required)
        _validate_anchored_execution(classes[kind], required)
    for required in anchor["promotion"].values():
        _validate_required_stages(promotion, required)
        _validate_anchored_execution(promotion, required)


def _load_templates(
    path: Optional[Path], safety_anchor: Mapping[str, object],
) -> dict[WorkflowClass, tuple[dict, ...]]:
    source = Path(path) if path is not None else DEFAULT_CLASSES_PATH
    try:
        payload = load_json_document(source)
    except JSONDocumentDepthError:
        raise invalid_policy("invalid_workflow_classes_document") from None
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise invalid_policy("invalid_workflow_classes_json") from None
    if type(payload) is not dict or set(payload) != {
        "schema_version", "classes", "promotion",
    }:
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
        result[kind] = records
    promotion = payload["promotion"]
    if type(promotion) is not dict or set(promotion) != {"investigation"}:
        raise invalid_policy("invalid_promotion_policy")
    promoted = promotion["investigation"]
    if type(promoted) is not dict or set(promoted) != {"nodes"}:
        raise invalid_policy("invalid_promotion_policy")
    promotion_nodes = tuple(_node_record(item) for item in promoted["nodes"])
    _validate_promotion(promotion_nodes)
    _validate_safety_anchor(safety_anchor, result, promotion_nodes)
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
        policy = load_policy(policy_path)
        self._templates = _load_templates(path, policy.workflow_safety_anchor)
        self._gate_policy = GatePolicy(policy_document=policy)
        self._sensitive_globs = _load_sensitive_globs(routing_policy_path)

    def expand(
        self,
        kind: WorkflowClass,
        context: WorkflowContext,
    ) -> tuple[NodeSpec, ...]:
        normalized = _normalize_enum(
            WorkflowClass, kind, "unknown_workflow_class",
        )
        context = _snapshot_workflow_context(context)
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
            required_dispatch_capability = record["required_dispatch_capability"]
            executor_overridable = record["executor_overridable"]
            routing_reason = None
            if executor is not None:
                if sensitive:
                    executor = "claude"
                    required_capability = HostCapability.ANTHROPIC_NATIVE_EXECUTION
                    required_dispatch_capability = HostCapability.NATIVE_DISPATCH
                    executor_overridable = False
                    routing_reason = "sensitive_path_override"
                elif normalized is WorkflowClass.SECURITY:
                    executor = "claude"
                    required_capability = HostCapability.ANTHROPIC_NATIVE_EXECUTION
                    required_dispatch_capability = HostCapability.NATIVE_DISPATCH
                    executor_overridable = False
                    routing_reason = "security_workflow_override"
                elif context.requested_executor is not None and executor_overridable:
                    executor = context.requested_executor
                    required_capability = DEFAULT_EXECUTOR_CAPABILITY[executor]
                    required_dispatch_capability = None
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
                required_dispatch_capability=required_dispatch_capability,
                executor_overridable=executor_overridable,
            ))
        return tuple(nodes)
