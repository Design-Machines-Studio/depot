"""Data-driven workflow-class expansion and sensitive routing overrides."""

from __future__ import annotations

import fnmatch
import json
from collections import deque
from pathlib import Path
from typing import Optional

from .adapters.base import NodeSpec, WorkflowClass, WorkflowContext, invalid_policy
from .policies import GatePolicy


WORKFLOW_CLASSES_SCHEMA_VERSION = 1
DEFAULT_CLASSES_PATH = Path(__file__).resolve().parent.parent / "workflow-classes.json"
_GATE_KINDS = frozenset({
    "cleanup", "deterministic_validation", "evidence", "human_approval",
    "investigation_promotion", "next_action", "risk",
})
_EXECUTORS = frozenset({"claude", "codex", "openrouter"})


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
    allowed = {"id", "depends_on", "gate_kind", "required_evidence", "executor"}
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
    if value["gate_kind"] is not None and value["gate_kind"] not in _GATE_KINDS:
        raise invalid_policy("unknown_gate_kind")
    if value["executor"] is not None and value["executor"] not in _EXECUTORS:
        raise invalid_policy("unknown_executor")
    return {
        "id": node_id,
        "depends_on": tuple(dependencies),
        "gate_kind": value["gate_kind"],
        "required_evidence": tuple(required_evidence),
        "executor": value["executor"],
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
    if not records or records[-1]["id"] != "cleanup":
        raise invalid_policy("cleanup_node_required")


def _load_templates(path: Optional[Path]) -> dict[WorkflowClass, tuple[dict, ...]]:
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
        result[kind] = records
    promotion = payload["promotion"]
    if type(promotion) is not dict or set(promotion) != {"investigation"}:
        raise invalid_policy("invalid_promotion_policy")
    promoted = promotion["investigation"]
    if type(promoted) is not dict or set(promoted) != {"nodes"}:
        raise invalid_policy("invalid_promotion_policy")
    promotion_nodes = tuple(_node_record(item) for item in promoted["nodes"])
    if tuple(record["id"] for record in promotion_nodes) != ("promotion_gate", "promoted_build"):
        raise invalid_policy("invalid_promotion_policy")
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
            routing_reason = None
            if executor is not None:
                if normalized is WorkflowClass.SECURITY:
                    executor = "claude"
                    routing_reason = "security_workflow_override"
                elif sensitive:
                    executor = "claude"
                    routing_reason = "sensitive_path_override"
                elif context.requested_executor is not None:
                    executor = context.requested_executor
                    routing_reason = "requested_executor"
                else:
                    routing_reason = "workflow_default"
            gate = self._gate_policy.decide(
                normalized, record["gate_kind"], record["required_evidence"], context,
            )
            nodes.append(NodeSpec(
                record["id"], record["depends_on"], record["gate_kind"],
                record["required_evidence"], executor, routing_reason, gate,
            ))
        return tuple(nodes)
