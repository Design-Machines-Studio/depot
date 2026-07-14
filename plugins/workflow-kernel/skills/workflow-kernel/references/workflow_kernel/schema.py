"""Versioned immutable workflow-kernel schema and normalized errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from .redaction import (
    MAX_PAYLOAD_DEPTH, MAX_PAYLOAD_ITEMS, MAX_STRING_LENGTH,
    freeze_json, normalize_durable_string, normalize_evidence_reference, redact, thaw,
    validate_durable_key,
)


SCHEMA_VERSION = 1
MAX_EVIDENCE_ITEMS = 1_024


class RunMode(str, Enum):
    SHADOW = "shadow"
    ENFORCE = "enforce"
    NATIVE = "native"


class RunStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class NodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class KernelError(Exception):
    code = "kernel_error"

    def __init__(self, message: str, details: Optional[Mapping[str, object]] = None):
        self.message = message
        try:
            self.details = redact(dict(details or {}))
        except (TypeError, ValueError):
            self.details = {"detail": "[UNSAFE]"}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class InvalidSchemaError(KernelError):
    code = "invalid_schema"


class CorruptEventError(KernelError):
    code = "corrupt_event"


class CorruptStateError(KernelError):
    code = "corrupt_state"


class SequenceConflictError(KernelError):
    code = "sequence_conflict"


class RevisionConflictError(KernelError):
    code = "revision_conflict"


class LeaseConflictError(KernelError):
    code = "lease_conflict"


class IllegalTransitionError(KernelError):
    code = "illegal_transition"


class MissingEvidenceError(KernelError):
    code = "missing_evidence"


class UnsafePayloadError(KernelError):
    code = "unsafe_payload"


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidSchemaError("invalid integer field", {"field": name, "minimum": minimum})
    return value


def _validated_string(value: object, name: str, *, optional: bool = False) -> Optional[str]:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > MAX_STRING_LENGTH:
        raise InvalidSchemaError("invalid string field", {"field": name})
    return value


def _string(value: object, name: str, *, optional: bool = False) -> Optional[str]:
    text = _validated_string(value, name, optional=optional)
    if text is None:
        return None
    try:
        return normalize_durable_string(text)
    except ValueError as exc:
        raise UnsafePayloadError("string field contains an unsafe URI", {"field": name}) from exc


def _timestamp(value: object, name: str = "occurred_at") -> str:
    text = _validated_string(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidSchemaError("invalid timestamp", {"field": name}) from exc
    if parsed.tzinfo is None:
        raise InvalidSchemaError("timestamp must include timezone", {"field": name})
    return text


def _only(data: Mapping[str, object], fields: set, required: set) -> None:
    keys = tuple(data)
    if any(not isinstance(key, str) for key in keys):
        raise InvalidSchemaError("schema keys must be strings")
    try:
        for key in keys:
            validate_durable_key(key)
    except ValueError as exc:
        raise InvalidSchemaError("schema keys contain an unsafe URI") from exc
    unknown = sorted(set(keys) - fields)
    missing = sorted(required - set(keys))
    if unknown or missing:
        raise InvalidSchemaError("schema fields do not match", {"unknown": unknown, "missing": missing})


def _payload(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidSchemaError("payload must be a mapping", {"field": "payload"})
    try:
        safe = freeze_json(value, max_depth=MAX_PAYLOAD_DEPTH,
                           max_items=MAX_PAYLOAD_ITEMS,
                           max_string_length=MAX_STRING_LENGTH)
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError("payload contains a non-JSON-safe value") from exc
    return safe


def _plain(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return thaw(value)


def _validate_dependency_graph(nodes: Mapping[str, "NodeState"]) -> None:
    indegree = {node_id: len(node.dependencies) for node_id, node in nodes.items()}
    dependents = {node_id: [] for node_id in nodes}
    for node_id, node in nodes.items():
        for dependency in node.dependencies:
            if dependency == node_id:
                raise InvalidSchemaError("node dependency graph is invalid", {"reason_code": "self_dependency"})
            if dependency not in nodes:
                raise InvalidSchemaError("node dependency graph is invalid", {"reason_code": "missing_dependency"})
            dependents[dependency].append(node_id)
    ready = deque(node_id for node_id, count in indegree.items() if count == 0)
    visited = 0
    while ready:
        dependency = ready.popleft()
        visited += 1
        for dependent in dependents[dependency]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if visited != len(nodes):
        raise InvalidSchemaError("node dependency graph is invalid", {"reason_code": "dependency_cycle"})


@dataclass(frozen=True)
class WorkflowEvent:
    schema_version: int
    sequence: int
    run_id: str
    node_id: Optional[str]
    kind: str
    occurred_at: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _strict_int(self.schema_version, "schema_version", minimum=1))
        if self.schema_version != SCHEMA_VERSION:
            raise InvalidSchemaError("unsupported schema version", {"schema_version": self.schema_version})
        object.__setattr__(self, "sequence", _strict_int(self.sequence, "sequence"))
        object.__setattr__(self, "run_id", _string(self.run_id, "run_id"))
        object.__setattr__(self, "node_id", _string(self.node_id, "node_id", optional=True))
        object.__setattr__(self, "kind", _string(self.kind, "kind"))
        object.__setattr__(self, "occurred_at", _timestamp(self.occurred_at))
        object.__setattr__(self, "payload", _payload(self.payload))

    @classmethod
    def from_dict(cls, data: object) -> "WorkflowEvent":
        if not isinstance(data, Mapping):
            raise InvalidSchemaError("event must be an object")
        fields = {"schema_version", "sequence", "run_id", "node_id", "kind", "occurred_at", "payload"}
        _only(data, fields, fields)
        return cls(**dict(data))

    def to_dict(self) -> dict:
        return {name: _plain(getattr(self, name)) for name in (
            "schema_version", "sequence", "run_id", "node_id", "kind", "occurred_at", "payload"
        )}


@dataclass(frozen=True)
class NodeState:
    node_id: str
    status: NodeStatus = NodeStatus.PENDING
    dependencies: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _string(self.node_id, "node_id"))
        try:
            status = self.status if isinstance(self.status, NodeStatus) else NodeStatus(self.status)
        except (ValueError, TypeError) as exc:
            raise InvalidSchemaError("unknown node status", {"status": self.status}) from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "dependencies", _string_tuple(self.dependencies, "dependencies"))
        object.__setattr__(self, "evidence", _string_tuple(self.evidence, "evidence", references=True))

    @classmethod
    def from_dict(cls, data: object) -> "NodeState":
        if not isinstance(data, Mapping):
            raise InvalidSchemaError("node must be an object")
        fields = {"node_id", "status", "dependencies", "evidence"}
        _only(data, fields, fields)
        return cls(data["node_id"], data["status"], data["dependencies"], data["evidence"])

    def to_dict(self) -> dict:
        return {"node_id": self.node_id, "status": self.status.value,
                "dependencies": list(self.dependencies), "evidence": list(self.evidence)}


def _string_tuple(value: object, name: str, *, references: bool = False) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise InvalidSchemaError("field must be a list", {"field": name})
    result = tuple(_string(item, name) for item in value)
    if references:
        try:
            result = tuple(normalize_evidence_reference(item) for item in result)
        except ValueError as exc:
            raise UnsafePayloadError("evidence reference is unsafe") from exc
    if len(result) != len(set(result)):
        raise InvalidSchemaError("field contains duplicates", {"field": name})
    return result


@dataclass(frozen=True)
class RunState:
    schema_version: int
    revision: int
    run_id: str
    mode: RunMode
    status: RunStatus
    created_at: str
    updated_at: str
    nodes: Mapping[str, NodeState] = field(default_factory=dict)
    evidence: Tuple[str, ...] = ()
    cleanup_reconciled: bool = False

    def __post_init__(self) -> None:
        version = _strict_int(self.schema_version, "schema_version", minimum=1)
        if version != SCHEMA_VERSION:
            raise InvalidSchemaError("unsupported schema version", {"schema_version": version})
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "revision", _strict_int(self.revision, "revision"))
        object.__setattr__(self, "run_id", _string(self.run_id, "run_id"))
        try:
            mode = self.mode if isinstance(self.mode, RunMode) else RunMode(self.mode)
            status = self.status if isinstance(self.status, RunStatus) else RunStatus(self.status)
        except (ValueError, TypeError) as exc:
            raise InvalidSchemaError("unknown run enum", {"mode": self.mode, "status": self.status}) from exc
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_at", _timestamp(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _timestamp(self.updated_at, "updated_at"))
        if not isinstance(self.nodes, Mapping):
            raise InvalidSchemaError("nodes must be an object")
        nodes = dict(self.nodes)
        if any(not isinstance(key, str) for key in nodes):
            raise InvalidSchemaError("node keys must be strings")
        try:
            for key in nodes:
                validate_durable_key(key)
        except ValueError as exc:
            raise InvalidSchemaError("node keys contain an unsafe URI") from exc
        if any(not isinstance(node, NodeState) or key != node.node_id
               for key, node in nodes.items()):
            raise InvalidSchemaError("node keys must match immutable node states")
        _validate_dependency_graph(nodes)
        evidence = _string_tuple(self.evidence, "evidence", references=True)
        if len(evidence) + sum(len(node.evidence) for node in nodes.values()) > MAX_EVIDENCE_ITEMS:
            raise InvalidSchemaError("evidence item limit exceeded", {
                "reason_code": "evidence_limit_exceeded",
                "limit_items": MAX_EVIDENCE_ITEMS,
            })
        object.__setattr__(self, "nodes", MappingProxyType(nodes))
        object.__setattr__(self, "evidence", evidence)
        if not isinstance(self.cleanup_reconciled, bool):
            raise InvalidSchemaError("cleanup_reconciled must be boolean")

    @classmethod
    def new(cls, run_id: str, occurred_at: str, mode: RunMode = RunMode.SHADOW) -> "RunState":
        return cls(SCHEMA_VERSION, 0, run_id, mode, RunStatus.PLANNED,
                   occurred_at, occurred_at, MappingProxyType({}))

    @classmethod
    def from_dict(cls, data: object) -> "RunState":
        if not isinstance(data, Mapping):
            raise InvalidSchemaError("state must be an object")
        fields = {"schema_version", "revision", "run_id", "mode", "status", "created_at", "updated_at", "nodes", "evidence", "cleanup_reconciled"}
        _only(data, fields, fields)
        raw_nodes = data["nodes"]
        if not isinstance(raw_nodes, Mapping):
            raise InvalidSchemaError("nodes must be an object")
        if any(not isinstance(key, str) for key in raw_nodes):
            raise InvalidSchemaError("node keys must be strings")
        try:
            for key in raw_nodes:
                validate_durable_key(key)
        except ValueError as exc:
            raise InvalidSchemaError("node keys contain an unsafe URI") from exc
        nodes = {key: NodeState.from_dict(value) for key, value in raw_nodes.items()}
        return cls(data["schema_version"], data["revision"], data["run_id"], data["mode"], data["status"],
                   data["created_at"], data["updated_at"], MappingProxyType(nodes), data["evidence"],
                   data["cleanup_reconciled"])

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version, "revision": self.revision, "run_id": self.run_id,
            "mode": self.mode.value, "status": self.status.value, "created_at": self.created_at,
            "updated_at": self.updated_at, "nodes": {key: self.nodes[key].to_dict() for key in sorted(self.nodes)},
            "evidence": list(self.evidence), "cleanup_reconciled": self.cleanup_reconciled,
        }
