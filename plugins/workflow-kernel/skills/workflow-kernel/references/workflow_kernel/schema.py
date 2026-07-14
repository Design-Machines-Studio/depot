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
    freeze_error_details, freeze_json, normalize_durable_string, normalize_evidence_reference, redact, thaw,
    validate_durable_key,
)


SCHEMA_VERSION = 1
MAX_EVIDENCE_ITEMS = 1_024


class ErrorMessage(str, Enum):
    GENERIC = "workflow kernel error"
    AUTHORITATIVE_LEDGER_MISSING = "authoritative event ledger is missing or empty"
    EMPTY_RECONSTRUCTION = "cannot reconstruct an empty event ledger"
    CLEANUP_RECONCILED_BOOLEAN = "cleanup_reconciled must be boolean"
    EVENT_LOCKING_UNAVAILABLE = "crash-safe event locking is unavailable"
    RUN_LOCKING_UNAVAILABLE = "crash-safe run locking is unavailable"
    EVENT_UNSAFE_DURABLE_DATA = "event contains unsafe durable data"
    ILLEGAL_FOR_STATE = "event is illegal for current state"
    EVENT_INVALID_JSON = "event is not valid JSON"
    LEDGER_CONFLICTING_RUN_IDS = "event ledger contains conflicting run ids"
    LEDGER_SIZE_LIMIT = "event ledger exceeds size limit"
    LEDGER_ANOTHER_WRITER = "event ledger has another writer"
    LEDGER_PATH_UNSAFE = "event ledger path is unsafe"
    LEDGER_SEQUENCE_NONCONTIGUOUS = "event ledger sequence is not contiguous"
    LEDGER_PROJECTED_SIZE_LIMIT = "event ledger would exceed size limit"
    EVENT_LOCK_IDENTITY_CHANGED = "event lock identity changed"
    EVENT_LOCK_PATH_UNSAFE = "event lock path is unsafe"
    EVENT_MUST_BE_OBJECT = "event must be an object"
    EVENT_PAYLOAD_STRING_LIST = "event payload field must be a string list"
    EVENT_RECORD_SIZE_LIMIT = "event record exceeds size limit"
    EVENT_RUN_ID_CONFLICT = "event run id conflicts with ledger"
    EVENT_RUN_ID_STATE_MISMATCH = "event run id does not match state"
    EVENT_SEQUENCE_LEDGER_MISMATCH = "event sequence does not match ledger"
    EVENT_SEQUENCE_STATE_MISMATCH = "event sequence does not match state revision"
    EVENT_UNKNOWN_RUN_MODE = "event specifies unknown run mode"
    EVIDENCE_ITEM_LIMIT = "evidence item limit exceeded"
    EVIDENCE_RECEIPT_UNSAFE = "evidence receipt contains unsafe data"
    EVIDENCE_REFERENCE_UNSAFE = "evidence reference is unsafe"
    FIELD_DUPLICATES = "field contains duplicates"
    FIELD_LIST_REQUIRED = "field must be a list"
    FIRST_EVENT_INITIALIZE = "first event must initialize the run"
    INVALID_COMMAND_ARGUMENTS = "invalid command arguments"
    INVALID_EVENT_RECORD = "invalid event record"
    INVALID_EXPECTED_REVISION = "invalid expected revision"
    INVALID_EXPECTED_SEQUENCE = "invalid expected sequence"
    INVALID_INTEGER_FIELD = "invalid integer field"
    INVALID_STRING_FIELD = "invalid string field"
    INVALID_TIMESTAMP = "invalid timestamp"
    STATE_LEDGER_MISMATCH = "materialized state does not match event ledger"
    STATE_SIZE_LIMIT = "materialized state exceeds size limit"
    STATE_CORRUPT = "materialized state is corrupt"
    STATE_PATH_UNSAFE = "materialized state path is unsafe"
    NODE_DEPENDENCY_GRAPH_INVALID = "node dependency graph is invalid"
    NODE_DEPENDENCY_INVALID = "node dependency is invalid"
    NODE_DEPENDENCY_MISSING = "node dependency is missing"
    NODE_KEYS_UNSAFE_URI = "node keys contain an unsafe URI"
    NODE_KEYS_STRINGS = "node keys must be strings"
    NODE_KEYS_MISMATCH = "node keys must match immutable node states"
    NODE_OBJECT_REQUIRED = "node must be an object"
    NODES_OBJECT_REQUIRED = "nodes must be an object"
    PAYLOAD_NON_JSON_SAFE = "payload contains a non-JSON-safe value"
    PAYLOAD_MAPPING_REQUIRED = "payload must be a mapping"
    PREPARED_STATE_WRONG_STORE = "prepared state belongs to another store"
    PREPARED_STATE_RUN_STATE_REQUIRED = "prepared state requires a validated RunState"
    RECEIPT_NON_JSON_SAFE = "receipt contains a non-JSON-safe value"
    RUN_WRITER_LEASE_HELD = "run already has a live writer lease"
    RUN_DIRECTORY_INITIALIZED = "run directory is already initialized"
    RUN_DIRECTORY_UNINITIALIZED = "run directory is not initialized"
    RUN_LEASE_IDENTITY_CHANGED = "run lease identity changed"
    RUN_LEASE_PATH_UNSAFE = "run lease path is unsafe"
    SCHEMA_FIELDS_MISMATCH = "schema fields do not match"
    SCHEMA_KEYS_UNSAFE_URI = "schema keys contain an unsafe URI"
    SCHEMA_KEYS_STRINGS = "schema keys must be strings"
    STATE_MISSING_AT_REVISION = "state does not exist at expected revision"
    STATE_OBJECT_REQUIRED = "state must be an object"
    STATE_REVISION_BACKWARD = "state revision cannot move backward"
    STATE_REVISION_CHANGED = "state revision changed"
    STATE_LEASE_REQUIRED = "state write requires its acquired run lease"
    STRING_UNSAFE_URI = "string field contains an unsafe URI"
    TERMINAL_RUN_MUTATION = "terminal run rejects mutation"
    TIMESTAMP_TIMEZONE_REQUIRED = "timestamp must include timezone"
    TRANSITION_EVIDENCE_REQUIRED = "transition requires evidence"
    UNKNOWN_EVENT_KIND = "unknown event kind"
    UNKNOWN_NODE_STATUS = "unknown node status"
    UNKNOWN_RUN_ENUM = "unknown run enum"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported schema version"
    OPERATION_FAILED = "workflow kernel operation failed"


class ErrorCode(str, Enum):
    KERNEL_ERROR = "kernel_error"
    INVALID_SCHEMA = "invalid_schema"
    CORRUPT_EVENT = "corrupt_event"
    CORRUPT_STATE = "corrupt_state"
    SEQUENCE_CONFLICT = "sequence_conflict"
    REVISION_CONFLICT = "revision_conflict"
    LEASE_CONFLICT = "lease_conflict"
    ILLEGAL_TRANSITION = "illegal_transition"
    MISSING_EVIDENCE = "missing_evidence"
    UNSAFE_PAYLOAD = "unsafe_payload"


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
    _error_code = ErrorCode.KERNEL_ERROR

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "code" in cls.__dict__:
            delattr(cls, "code")

    def __init__(self, message: object, details: Optional[Mapping[str, object]] = None):
        safe_message = message if isinstance(message, ErrorMessage) else ErrorMessage.GENERIC
        candidate_code = getattr(type(self), "_error_code", ErrorCode.KERNEL_ERROR)
        safe_code = candidate_code if isinstance(candidate_code, ErrorCode) else ErrorCode.KERNEL_ERROR
        super().__init__(safe_message.value)
        object.__setattr__(self, "_safe_message", safe_message)
        object.__setattr__(self, "_safe_code", safe_code)
        try:
            safe_details = freeze_error_details(dict(details or {}))
        except (TypeError, ValueError):
            safe_details = freeze_error_details({"detail": "[UNSAFE]"})
        object.__setattr__(self, "_details", safe_details)

    def __setattr__(self, name: str, value: object) -> None:
        protected = {
            "message", "args", "_safe_message", "code", "_safe_code", "_error_code",
            "details", "_details",
        }
        if name in protected and hasattr(self, "_safe_message"):
            raise AttributeError("kernel error public state is immutable")
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name in {
            "message", "args", "_safe_message", "code", "_safe_code", "_error_code",
            "details", "_details",
        }:
            raise AttributeError("kernel error public state is immutable")
        super().__delattr__(name)

    def _message_value(self) -> str:
        try:
            candidate = object.__getattribute__(self, "_safe_message")
        except AttributeError:
            return ErrorMessage.GENERIC.value
        return candidate.value if isinstance(candidate, ErrorMessage) else ErrorMessage.GENERIC.value

    def _code_value(self) -> str:
        try:
            candidate = object.__getattribute__(self, "_safe_code")
        except AttributeError:
            return ErrorCode.KERNEL_ERROR.value
        return candidate.value if isinstance(candidate, ErrorCode) else ErrorCode.KERNEL_ERROR.value

    @property
    def message(self) -> str:
        return self._message_value()

    @property
    def code(self) -> str:
        return self._code_value()

    @property
    def details(self) -> Mapping[str, object]:
        return self._details

    def __str__(self) -> str:
        return self._message_value()

    def to_dict(self) -> dict:
        return {"error": {"code": self._code_value(), "message": self._message_value(),
                          "details": thaw(self._details)}}


class InvalidSchemaError(KernelError):
    _error_code = ErrorCode.INVALID_SCHEMA


class CorruptEventError(KernelError):
    _error_code = ErrorCode.CORRUPT_EVENT


class CorruptStateError(KernelError):
    _error_code = ErrorCode.CORRUPT_STATE


class SequenceConflictError(KernelError):
    _error_code = ErrorCode.SEQUENCE_CONFLICT


class RevisionConflictError(KernelError):
    _error_code = ErrorCode.REVISION_CONFLICT


class LeaseConflictError(KernelError):
    _error_code = ErrorCode.LEASE_CONFLICT


class IllegalTransitionError(KernelError):
    _error_code = ErrorCode.ILLEGAL_TRANSITION


class MissingEvidenceError(KernelError):
    _error_code = ErrorCode.MISSING_EVIDENCE


class UnsafePayloadError(KernelError):
    _error_code = ErrorCode.UNSAFE_PAYLOAD


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidSchemaError(ErrorMessage.INVALID_INTEGER_FIELD, {"field": name, "minimum": minimum})
    return value


def _validated_string(value: object, name: str, *, optional: bool = False) -> Optional[str]:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > MAX_STRING_LENGTH:
        raise InvalidSchemaError(ErrorMessage.INVALID_STRING_FIELD, {"field": name})
    return value


def _string(value: object, name: str, *, optional: bool = False) -> Optional[str]:
    text = _validated_string(value, name, optional=optional)
    if text is None:
        return None
    try:
        return normalize_durable_string(text)
    except ValueError as exc:
        raise UnsafePayloadError(ErrorMessage.STRING_UNSAFE_URI, {"field": name}) from exc


def _timestamp(value: object, name: str = "occurred_at") -> str:
    text = _validated_string(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidSchemaError(ErrorMessage.INVALID_TIMESTAMP, {"field": name}) from exc
    if parsed.tzinfo is None:
        raise InvalidSchemaError(ErrorMessage.TIMESTAMP_TIMEZONE_REQUIRED, {"field": name})
    return text


def _only(data: Mapping[str, object], fields: set, required: set) -> None:
    keys = tuple(data)
    if any(not isinstance(key, str) for key in keys):
        raise InvalidSchemaError(ErrorMessage.SCHEMA_KEYS_STRINGS)
    try:
        for key in keys:
            validate_durable_key(key)
    except ValueError as exc:
        raise InvalidSchemaError(ErrorMessage.SCHEMA_KEYS_UNSAFE_URI) from exc
    unknown = sorted(set(keys) - fields)
    missing = sorted(required - set(keys))
    if unknown or missing:
        raise InvalidSchemaError(ErrorMessage.SCHEMA_FIELDS_MISMATCH, {"unknown": unknown, "missing": missing})


def _payload(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidSchemaError(ErrorMessage.PAYLOAD_MAPPING_REQUIRED, {"field": "payload"})
    try:
        safe = freeze_json(value, max_depth=MAX_PAYLOAD_DEPTH,
                           max_items=MAX_PAYLOAD_ITEMS,
                           max_string_length=MAX_STRING_LENGTH)
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE) from exc
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
                raise InvalidSchemaError(ErrorMessage.NODE_DEPENDENCY_GRAPH_INVALID, {"reason_code": "self_dependency"})
            if dependency not in nodes:
                raise InvalidSchemaError(ErrorMessage.NODE_DEPENDENCY_GRAPH_INVALID, {"reason_code": "missing_dependency"})
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
        raise InvalidSchemaError(ErrorMessage.NODE_DEPENDENCY_GRAPH_INVALID, {"reason_code": "dependency_cycle"})


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
            raise InvalidSchemaError(ErrorMessage.UNSUPPORTED_SCHEMA_VERSION, {"schema_version": self.schema_version})
        object.__setattr__(self, "sequence", _strict_int(self.sequence, "sequence"))
        object.__setattr__(self, "run_id", _string(self.run_id, "run_id"))
        object.__setattr__(self, "node_id", _string(self.node_id, "node_id", optional=True))
        object.__setattr__(self, "kind", _string(self.kind, "kind"))
        object.__setattr__(self, "occurred_at", _timestamp(self.occurred_at))
        object.__setattr__(self, "payload", _payload(self.payload))

    @classmethod
    def from_dict(cls, data: object) -> "WorkflowEvent":
        if not isinstance(data, Mapping):
            raise InvalidSchemaError(ErrorMessage.EVENT_MUST_BE_OBJECT)
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
            raise InvalidSchemaError(ErrorMessage.UNKNOWN_NODE_STATUS, {"status": self.status}) from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "dependencies", _string_tuple(self.dependencies, "dependencies"))
        object.__setattr__(self, "evidence", _string_tuple(self.evidence, "evidence", references=True))

    @classmethod
    def from_dict(cls, data: object) -> "NodeState":
        if not isinstance(data, Mapping):
            raise InvalidSchemaError(ErrorMessage.NODE_OBJECT_REQUIRED)
        fields = {"node_id", "status", "dependencies", "evidence"}
        _only(data, fields, fields)
        return cls(data["node_id"], data["status"], data["dependencies"], data["evidence"])

    def to_dict(self) -> dict:
        return {"node_id": self.node_id, "status": self.status.value,
                "dependencies": list(self.dependencies), "evidence": list(self.evidence)}


def _string_tuple(value: object, name: str, *, references: bool = False) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise InvalidSchemaError(ErrorMessage.FIELD_LIST_REQUIRED, {"field": name})
    result = tuple(_string(item, name) for item in value)
    if references:
        try:
            result = tuple(normalize_evidence_reference(item) for item in result)
        except ValueError as exc:
            raise UnsafePayloadError(ErrorMessage.EVIDENCE_REFERENCE_UNSAFE) from exc
    if len(result) != len(set(result)):
        raise InvalidSchemaError(ErrorMessage.FIELD_DUPLICATES, {"field": name})
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
            raise InvalidSchemaError(ErrorMessage.UNSUPPORTED_SCHEMA_VERSION, {"schema_version": version})
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "revision", _strict_int(self.revision, "revision"))
        object.__setattr__(self, "run_id", _string(self.run_id, "run_id"))
        try:
            mode = self.mode if isinstance(self.mode, RunMode) else RunMode(self.mode)
            status = self.status if isinstance(self.status, RunStatus) else RunStatus(self.status)
        except (ValueError, TypeError) as exc:
            raise InvalidSchemaError(ErrorMessage.UNKNOWN_RUN_ENUM, {"mode": self.mode, "status": self.status}) from exc
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_at", _timestamp(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _timestamp(self.updated_at, "updated_at"))
        if not isinstance(self.nodes, Mapping):
            raise InvalidSchemaError(ErrorMessage.NODES_OBJECT_REQUIRED)
        nodes = dict(self.nodes)
        if any(not isinstance(key, str) for key in nodes):
            raise InvalidSchemaError(ErrorMessage.NODE_KEYS_STRINGS)
        try:
            for key in nodes:
                validate_durable_key(key)
        except ValueError as exc:
            raise InvalidSchemaError(ErrorMessage.NODE_KEYS_UNSAFE_URI) from exc
        if any(not isinstance(node, NodeState) or key != node.node_id
               for key, node in nodes.items()):
            raise InvalidSchemaError(ErrorMessage.NODE_KEYS_MISMATCH)
        _validate_dependency_graph(nodes)
        evidence = _string_tuple(self.evidence, "evidence", references=True)
        if len(evidence) + sum(len(node.evidence) for node in nodes.values()) > MAX_EVIDENCE_ITEMS:
            raise InvalidSchemaError(ErrorMessage.EVIDENCE_ITEM_LIMIT, {
                "reason_code": "evidence_limit_exceeded",
                "limit_items": MAX_EVIDENCE_ITEMS,
            })
        object.__setattr__(self, "nodes", MappingProxyType(nodes))
        object.__setattr__(self, "evidence", evidence)
        if not isinstance(self.cleanup_reconciled, bool):
            raise InvalidSchemaError(ErrorMessage.CLEANUP_RECONCILED_BOOLEAN)

    @classmethod
    def new(cls, run_id: str, occurred_at: str, mode: RunMode = RunMode.SHADOW) -> "RunState":
        return cls(SCHEMA_VERSION, 0, run_id, mode, RunStatus.PLANNED,
                   occurred_at, occurred_at, MappingProxyType({}))

    @classmethod
    def from_dict(cls, data: object) -> "RunState":
        if not isinstance(data, Mapping):
            raise InvalidSchemaError(ErrorMessage.STATE_OBJECT_REQUIRED)
        fields = {"schema_version", "revision", "run_id", "mode", "status", "created_at", "updated_at", "nodes", "evidence", "cleanup_reconciled"}
        _only(data, fields, fields)
        raw_nodes = data["nodes"]
        if not isinstance(raw_nodes, Mapping):
            raise InvalidSchemaError(ErrorMessage.NODES_OBJECT_REQUIRED)
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
