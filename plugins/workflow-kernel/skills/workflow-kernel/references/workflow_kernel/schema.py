"""Versioned immutable workflow-kernel schema and normalized errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from .redaction import redact


SCHEMA_VERSION = 1


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
        except TypeError:
            self.details = {"detail": "[UNSAFE]"}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class InvalidSchemaError(KernelError):
    code = "invalid_schema"


class CorruptEventError(KernelError):
    code = "corrupt_event"


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


def _string(value: object, name: str, *, optional: bool = False) -> Optional[str]:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value:
        raise InvalidSchemaError("invalid string field", {"field": name})
    return value


def _timestamp(value: object, name: str = "occurred_at") -> str:
    text = _string(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidSchemaError("invalid timestamp", {"field": name}) from exc
    if parsed.tzinfo is None:
        raise InvalidSchemaError("timestamp must include timezone", {"field": name})
    return text


def _only(data: Mapping[str, object], fields: set, required: set) -> None:
    unknown = sorted(set(data) - fields)
    missing = sorted(required - set(data))
    if unknown or missing:
        raise InvalidSchemaError("schema fields do not match", {"unknown": unknown, "missing": missing})


def _payload(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidSchemaError("payload must be a mapping", {"field": "payload"})
    try:
        safe = redact(value)
    except TypeError as exc:
        raise UnsafePayloadError("payload contains a non-JSON-safe value") from exc
    return MappingProxyType(safe)


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


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

    @classmethod
    def from_dict(cls, data: object) -> "NodeState":
        if not isinstance(data, Mapping):
            raise InvalidSchemaError("node must be an object")
        fields = {"node_id", "status", "dependencies", "evidence"}
        _only(data, fields, fields)
        try:
            status = NodeStatus(data["status"])
        except (ValueError, TypeError) as exc:
            raise InvalidSchemaError("unknown node status", {"status": data.get("status")}) from exc
        dependencies = _string_tuple(data["dependencies"], "dependencies")
        evidence = _string_tuple(data["evidence"], "evidence")
        return cls(_string(data["node_id"], "node_id"), status, dependencies, evidence)

    def to_dict(self) -> dict:
        return {"node_id": self.node_id, "status": self.status.value,
                "dependencies": list(self.dependencies), "evidence": list(self.evidence)}


def _string_tuple(value: object, name: str) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise InvalidSchemaError("field must be a list", {"field": name})
    result = tuple(_string(item, name) for item in value)
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
        if not isinstance(self.nodes, MappingProxyType):
            object.__setattr__(self, "nodes", MappingProxyType(dict(self.nodes)))

    @classmethod
    def new(cls, run_id: str, occurred_at: str, mode: RunMode = RunMode.SHADOW) -> "RunState":
        if not isinstance(mode, RunMode):
            try:
                mode = RunMode(mode)
            except (ValueError, TypeError) as exc:
                raise InvalidSchemaError("unknown run mode", {"mode": mode}) from exc
        return cls(SCHEMA_VERSION, 0, _string(run_id, "run_id"), mode, RunStatus.PLANNED,
                   _timestamp(occurred_at, "created_at"), _timestamp(occurred_at, "updated_at"), MappingProxyType({}))

    @classmethod
    def from_dict(cls, data: object) -> "RunState":
        if not isinstance(data, Mapping):
            raise InvalidSchemaError("state must be an object")
        fields = {"schema_version", "revision", "run_id", "mode", "status", "created_at", "updated_at", "nodes", "evidence", "cleanup_reconciled"}
        _only(data, fields, fields)
        version = _strict_int(data["schema_version"], "schema_version", minimum=1)
        if version != SCHEMA_VERSION:
            raise InvalidSchemaError("unsupported schema version", {"schema_version": version})
        try:
            mode, status = RunMode(data["mode"]), RunStatus(data["status"])
        except (ValueError, TypeError) as exc:
            raise InvalidSchemaError("unknown run enum", {"mode": data.get("mode"), "status": data.get("status")}) from exc
        raw_nodes = data["nodes"]
        if not isinstance(raw_nodes, Mapping):
            raise InvalidSchemaError("nodes must be an object")
        nodes = {key: NodeState.from_dict(value) for key, value in raw_nodes.items()}
        if any(key != node.node_id for key, node in nodes.items()):
            raise InvalidSchemaError("node keys must match node ids")
        cleanup = data["cleanup_reconciled"]
        if not isinstance(cleanup, bool):
            raise InvalidSchemaError("cleanup_reconciled must be boolean")
        return cls(version, _strict_int(data["revision"], "revision"), _string(data["run_id"], "run_id"),
                   mode, status, _timestamp(data["created_at"], "created_at"), _timestamp(data["updated_at"], "updated_at"),
                   MappingProxyType(nodes), _string_tuple(data["evidence"], "evidence"), cleanup)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version, "revision": self.revision, "run_id": self.run_id,
            "mode": self.mode.value, "status": self.status.value, "created_at": self.created_at,
            "updated_at": self.updated_at, "nodes": {key: self.nodes[key].to_dict() for key in sorted(self.nodes)},
            "evidence": list(self.evidence), "cleanup_reconciled": self.cleanup_reconciled,
        }
