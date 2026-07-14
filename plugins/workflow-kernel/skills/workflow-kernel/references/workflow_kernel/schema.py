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
    MAX_TOTAL_STRING_BYTES, NOOP_WORK_BUDGET, bounded_iterable,
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


class ErrorDetailKey(str, Enum):
    ACTUAL_REVISION = "actual_revision"
    ACTUAL_SEQUENCE = "actual_sequence"
    BYTE_OFFSET = "byte_offset"
    CANDIDATE_REVISION = "candidate_revision"
    DETAIL = "detail"
    DIRECTORY = "directory"
    EVENT_SEQUENCE = "event_sequence"
    EXCEPTION_TYPE = "exception_type"
    EXPECTED_REVISION = "expected_revision"
    EXPECTED_SEQUENCE = "expected_sequence"
    FIELD = "field"
    KIND = "kind"
    LEDGER_REVISION = "ledger_revision"
    LIMIT_BYTES = "limit_bytes"
    LIMIT_ITEMS = "limit_items"
    MATERIALIZED_REVISION = "materialized_revision"
    MINIMUM = "minimum"
    MISSING = "missing"
    MODE = "mode"
    NODE_ID = "node_id"
    OFFSET = "offset"
    OPTION = "option"
    PATH = "path"
    REASON_CODE = "reason_code"
    RECORD = "record"
    REVISION = "revision"
    RUN_STATUS = "run_status"
    SCHEMA_VERSION = "schema_version"
    SEQUENCE = "sequence"
    STATE_PATH = "state_path"
    STATUS = "status"
    UNKNOWN = "unknown"


_ERROR_DETAIL_KEYS = frozenset(key.value for key in ErrorDetailKey)


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


class WorkflowEventField(str, Enum):
    """Developer-owned field vocabulary for serialized workflow events."""

    SCHEMA_VERSION = "schema_version"
    SEQUENCE = "sequence"
    RUN_ID = "run_id"
    NODE_ID = "node_id"
    KIND = "kind"
    OCCURRED_AT = "occurred_at"
    PAYLOAD = "payload"


WORKFLOW_EVENT_FIELDS = frozenset(field.value for field in WorkflowEventField)


@dataclass(frozen=True)
class ErrorEnvelope:
    code: ErrorCode
    message: ErrorMessage
    details: Mapping[str, object]


class KernelError(Exception):
    _error_code = ErrorCode.KERNEL_ERROR
    _PROTECTED_NAMES = frozenset({"_envelope", "args"})

    def __init__(self, message: object, details: Optional[Mapping[str, object]] = None):
        safe_message = message if isinstance(message, ErrorMessage) else ErrorMessage.GENERIC
        candidate_code = getattr(type(self), "_error_code", ErrorCode.KERNEL_ERROR)
        safe_code = candidate_code if isinstance(candidate_code, ErrorCode) else ErrorCode.KERNEL_ERROR
        try:
            safe_details = freeze_error_details(
                details if details is not None else {}, known_keys=_ERROR_DETAIL_KEYS,
            )
        except (TypeError, ValueError):
            safe_details = MappingProxyType({ErrorDetailKey.DETAIL.value: "[UNSAFE]"})
        object.__setattr__(self, "_envelope", ErrorEnvelope(safe_code, safe_message, safe_details))
        Exception.__init__(self, safe_message.value)

    def __setattr__(self, name: str, value: object) -> None:
        if name in KernelError._PROTECTED_NAMES:
            try:
                object.__getattribute__(self, "_envelope")
            except AttributeError:
                pass
            else:
                raise AttributeError("kernel error public state is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in KernelError._PROTECTED_NAMES:
            raise AttributeError("kernel error public state is immutable")
        object.__delattr__(self, name)

    @property
    def message(self) -> str:
        return object.__getattribute__(self, "_envelope").message.value

    @property
    def code(self) -> str:
        return object.__getattribute__(self, "_envelope").code.value

    @property
    def details(self) -> Mapping[str, object]:
        return object.__getattribute__(self, "_envelope").details

    def __str__(self) -> str:
        return object.__getattribute__(self, "_envelope").message.value

    def to_dict(self) -> dict:
        return serialize_kernel_error(self)

    def __reduce__(self):
        envelope = object.__getattribute__(self, "_envelope")
        return (type(self), (envelope.message,))


def serialize_kernel_error(exc: KernelError) -> dict:
    """Serialize the captured safe envelope without subclass dispatch."""
    envelope = object.__getattribute__(exc, "_envelope")
    return {"error": {"code": envelope.code.value, "message": envelope.message.value,
                      "details": thaw(envelope.details)}}


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
    if type(value) is not int or value < minimum:
        raise InvalidSchemaError(ErrorMessage.INVALID_INTEGER_FIELD, {
            ErrorDetailKey.FIELD.value: name, ErrorDetailKey.MINIMUM.value: minimum,
        })
    return value


def _validated_string(value: object, name: str, *, optional: bool = False) -> Optional[str]:
    if optional and value is None:
        return None
    if type(value) is not str or not value or len(value) > MAX_STRING_LENGTH:
        raise InvalidSchemaError(ErrorMessage.INVALID_STRING_FIELD, {ErrorDetailKey.FIELD.value: name})
    return value


def _string(value: object, name: str, *, optional: bool = False) -> Optional[str]:
    text = _validated_string(value, name, optional=optional)
    if text is None:
        return None
    try:
        return normalize_durable_string(text)
    except ValueError:
        raise UnsafePayloadError(ErrorMessage.STRING_UNSAFE_URI, {ErrorDetailKey.FIELD.value: name}) from None


def _timestamp(value: object, name: str = "occurred_at") -> str:
    text = _validated_string(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise InvalidSchemaError(ErrorMessage.INVALID_TIMESTAMP, {ErrorDetailKey.FIELD.value: name}) from None
    if parsed.tzinfo is None:
        raise InvalidSchemaError(ErrorMessage.TIMESTAMP_TIMEZONE_REQUIRED, {ErrorDetailKey.FIELD.value: name})
    return text


def _only(data: Mapping[str, object], fields: set, required: set) -> None:
    keys = set(data)
    if any(type(key) is not str for key in keys):
        raise InvalidSchemaError(ErrorMessage.SCHEMA_KEYS_STRINGS)
    try:
        for key in keys:
            validate_durable_key(key)
    except ValueError:
        raise InvalidSchemaError(ErrorMessage.SCHEMA_KEYS_UNSAFE_URI) from None
    unknown = sorted(keys - fields)
    missing = sorted(required - keys)
    if unknown or missing:
        raise InvalidSchemaError(ErrorMessage.SCHEMA_FIELDS_MISMATCH, {
            ErrorDetailKey.UNKNOWN.value: unknown, ErrorDetailKey.MISSING.value: missing,
        })


def _payload(value: object, work=NOOP_WORK_BUDGET) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidSchemaError(ErrorMessage.PAYLOAD_MAPPING_REQUIRED, {ErrorDetailKey.FIELD.value: "payload"})
    try:
        safe = freeze_json(value, max_depth=MAX_PAYLOAD_DEPTH,
                           max_items=MAX_PAYLOAD_ITEMS,
                           max_string_length=MAX_STRING_LENGTH, work=work)
    except (TypeError, ValueError):
        raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE) from None
    return safe


def _bounded_mapping(value: object, required_message: ErrorMessage, *, text_budget=None) -> dict:
    if not isinstance(value, Mapping):
        raise InvalidSchemaError(required_message)
    result = {}
    try:
        for key in bounded_iterable(value, max_items=MAX_PAYLOAD_ITEMS):
            if type(key) is not str:
                raise InvalidSchemaError(ErrorMessage.SCHEMA_KEYS_STRINGS)
            if text_budget is not None:
                text_budget.consume_text(key)
            result[key] = value[key]
    except InvalidSchemaError:
        raise
    except (KeyError, TypeError, ValueError, RecursionError):
        raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE) from None
    return result


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
                raise InvalidSchemaError(ErrorMessage.NODE_DEPENDENCY_GRAPH_INVALID, {
                    ErrorDetailKey.REASON_CODE.value: "self_dependency",
                })
            if dependency not in nodes:
                raise InvalidSchemaError(ErrorMessage.NODE_DEPENDENCY_GRAPH_INVALID, {
                    ErrorDetailKey.REASON_CODE.value: "missing_dependency",
                })
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
        raise InvalidSchemaError(ErrorMessage.NODE_DEPENDENCY_GRAPH_INVALID, {
            ErrorDetailKey.REASON_CODE.value: "dependency_cycle",
        })


def _validated_workflow_event_projection(schema_version, sequence, run_id, node_id,
                                         kind, occurred_at, payload,
                                         work=NOOP_WORK_BUDGET):
    version = _strict_int(schema_version, "schema_version", minimum=1)
    if version != SCHEMA_VERSION:
        raise InvalidSchemaError(ErrorMessage.UNSUPPORTED_SCHEMA_VERSION, {
            ErrorDetailKey.SCHEMA_VERSION.value: version,
        })
    return (
        version,
        _strict_int(sequence, "sequence"),
        _string(run_id, "run_id"),
        _string(node_id, "node_id", optional=True),
        _string(kind, "kind"),
        _timestamp(occurred_at),
        _payload(payload, work),
    )


def _trusted_workflow_event(values) -> "WorkflowEvent":
    event = object.__new__(WorkflowEvent)
    for name, value in zip(
        ("schema_version", "sequence", "run_id", "node_id", "kind",
         "occurred_at", "payload"), values,
    ):
        object.__setattr__(event, name, value)
    return event


@dataclass(frozen=True)
class WorkflowEvent:
    schema_version: int
    sequence: int
    run_id: str
    node_id: Optional[str]
    kind: str
    occurred_at: str
    payload: Mapping[str, object]

    def __init_subclass__(cls, **_kwargs):
        raise TypeError("WorkflowEvent is final")

    def __post_init__(self) -> None:
        values = _validated_workflow_event_projection(
            self.schema_version, self.sequence, self.run_id, self.node_id,
            self.kind, self.occurred_at, self.payload,
        )
        for name, value in zip(self.__dataclass_fields__, values):
            object.__setattr__(self, name, value)

    @classmethod
    def from_dict(cls, data: object) -> "WorkflowEvent":
        snapshot = _bounded_mapping(data, ErrorMessage.EVENT_MUST_BE_OBJECT)
        _only(snapshot, WORKFLOW_EVENT_FIELDS, WORKFLOW_EVENT_FIELDS)
        return cls(**snapshot)

    def to_dict(self) -> dict:
        return {field.value: _plain(getattr(self, field.value)) for field in WorkflowEventField}


def _snapshot_workflow_event(event: WorkflowEvent,
                             work=NOOP_WORK_BUDGET) -> WorkflowEvent:
    """Rebuild one exact event field-wise before any public projection."""
    if type(event) is not WorkflowEvent:
        raise UnsafePayloadError(ErrorMessage.EVENT_UNSAFE_DURABLE_DATA)
    try:
        return _trusted_workflow_event(_validated_workflow_event_projection(
            event.schema_version, event.sequence, event.run_id, event.node_id,
            event.kind, event.occurred_at, event.payload, work,
        ))
    except KernelError:
        raise
    except (AttributeError, TypeError, ValueError, RecursionError):
        raise UnsafePayloadError(ErrorMessage.EVENT_UNSAFE_DURABLE_DATA) from None


class _StateItemBudget:
    """One aggregate budget shared by nodes and their state-tree collections."""

    def __init__(self, limit: int = MAX_PAYLOAD_ITEMS):
        self.limit = limit
        self.count = 0
        self.text_bytes = 0

    def consume(self) -> None:
        self.count += 1
        if self.count > self.limit:
            raise InvalidSchemaError(ErrorMessage.PAYLOAD_NON_JSON_SAFE, {
                ErrorDetailKey.LIMIT_ITEMS.value: self.limit,
            })

    def consume_text(self, value: object) -> None:
        if type(value) is not str:
            raise InvalidSchemaError(ErrorMessage.INVALID_STRING_FIELD)
        if len(value) > MAX_STRING_LENGTH:
            raise InvalidSchemaError(ErrorMessage.INVALID_STRING_FIELD)
        self.text_bytes += len(value.encode("utf-8"))
        if self.text_bytes > MAX_TOTAL_STRING_BYTES:
            raise InvalidSchemaError(ErrorMessage.PAYLOAD_NON_JSON_SAFE, {
                ErrorDetailKey.LIMIT_BYTES.value: MAX_TOTAL_STRING_BYTES,
            })


def _node_status(value: object) -> NodeStatus:
    try:
        if type(value) is NodeStatus:
            return value
        if type(value) is str:
            return NodeStatus(value)
        raise TypeError("node status must be an exact enum or string")
    except (ValueError, TypeError):
        raise InvalidSchemaError(ErrorMessage.UNKNOWN_NODE_STATUS, {
            ErrorDetailKey.STATUS.value: value,
        }) from None


def _trusted_node_state(node_id: str, status: NodeStatus,
                        dependencies: Tuple[str, ...], evidence: Tuple[str, ...]) -> "NodeState":
    node = object.__new__(NodeState)
    object.__setattr__(node, "node_id", node_id)
    object.__setattr__(node, "status", status)
    object.__setattr__(node, "dependencies", dependencies)
    object.__setattr__(node, "evidence", evidence)
    return node


def _validated_node_projection(node_id: object, status: object, dependencies: object,
                               evidence: object, budget: _StateItemBudget) -> "NodeState":
    budget.consume_text(node_id)
    safe_node_id = _string(node_id, "node_id")
    safe_status = _node_status(status)
    safe_dependencies = _string_tuple(
        dependencies, "dependencies", budget=budget,
    )
    safe_evidence = _string_tuple(
        evidence, "evidence", references=True, budget=budget,
    )
    return _trusted_node_state(
        safe_node_id, safe_status, safe_dependencies, safe_evidence,
    )


@dataclass(frozen=True)
class NodeState:
    node_id: str
    status: NodeStatus = NodeStatus.PENDING
    dependencies: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()

    def __init_subclass__(cls, **_kwargs):
        raise TypeError("NodeState is final")

    def __post_init__(self) -> None:
        projection = _validated_node_projection(
            self.node_id, self.status, self.dependencies, self.evidence,
            _StateItemBudget(MAX_PAYLOAD_ITEMS),
        )
        object.__setattr__(self, "node_id", projection.node_id)
        object.__setattr__(self, "status", projection.status)
        object.__setattr__(self, "dependencies", projection.dependencies)
        object.__setattr__(self, "evidence", projection.evidence)

    @classmethod
    def from_dict(cls, data: object) -> "NodeState":
        return _node_state_from_mapping(data)

    def to_dict(self) -> dict:
        return {"node_id": self.node_id, "status": self.status.value,
                "dependencies": list(self.dependencies), "evidence": list(self.evidence)}


def _string_tuple(value: object, name: str, *, references: bool = False,
                  budget: Optional[_StateItemBudget] = None) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise InvalidSchemaError(ErrorMessage.FIELD_LIST_REQUIRED, {ErrorDetailKey.FIELD.value: name})
    limit = MAX_EVIDENCE_ITEMS if references else MAX_PAYLOAD_ITEMS
    try:
        result = []
        for item in bounded_iterable(value, max_items=limit):
            if budget is not None:
                budget.consume()
                budget.consume_text(item)
            result.append(_string(item, name))
        result = tuple(result)
    except TypeError:
        message = ErrorMessage.EVIDENCE_ITEM_LIMIT if references else ErrorMessage.PAYLOAD_NON_JSON_SAFE
        raise InvalidSchemaError(message, {ErrorDetailKey.LIMIT_ITEMS.value: limit}) from None
    if references:
        try:
            result = tuple(normalize_evidence_reference(item) for item in result)
        except ValueError:
            raise UnsafePayloadError(ErrorMessage.EVIDENCE_REFERENCE_UNSAFE) from None
    if len(result) != len(set(result)):
        raise InvalidSchemaError(ErrorMessage.FIELD_DUPLICATES, {ErrorDetailKey.FIELD.value: name})
    return result


def _snapshot_node_state(node: NodeState, budget: _StateItemBudget) -> NodeState:
    if type(node) is not NodeState:
        raise InvalidSchemaError(ErrorMessage.NODE_KEYS_MISMATCH)
    try:
        return _validated_node_projection(
            node.node_id, node.status, node.dependencies, node.evidence, budget,
        )
    except KernelError:
        raise
    except (AttributeError, TypeError, ValueError, RecursionError):
        raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE) from None


def _node_state_from_mapping(data: object,
                             budget: Optional[_StateItemBudget] = None) -> NodeState:
    snapshot = _bounded_mapping(data, ErrorMessage.NODE_OBJECT_REQUIRED)
    fields = {"node_id", "status", "dependencies", "evidence"}
    _only(snapshot, fields, fields)
    active_budget = budget if budget is not None else _StateItemBudget(MAX_PAYLOAD_ITEMS)
    return _validated_node_projection(
        snapshot["node_id"], snapshot["status"], snapshot["dependencies"],
        snapshot["evidence"], active_budget,
    )


def _trusted_run_state(values) -> "RunState":
    state = object.__new__(RunState)
    for name, value in zip(
        ("schema_version", "revision", "run_id", "mode", "status", "created_at",
         "updated_at", "nodes", "evidence", "cleanup_reconciled"), values,
    ):
        object.__setattr__(state, name, value)
    return state


def _validated_run_projection(schema_version, revision, run_id, mode, status,
                              created_at, updated_at, raw_nodes, raw_evidence,
                              cleanup_reconciled, *, nodes_from_dict=False,
                              budget=None, node_keys_budgeted=False,
                              include_counters=False):
    version = _strict_int(schema_version, "schema_version", minimum=1)
    if version != SCHEMA_VERSION:
        raise InvalidSchemaError(ErrorMessage.UNSUPPORTED_SCHEMA_VERSION, {
            ErrorDetailKey.SCHEMA_VERSION.value: version,
        })
    revision = _strict_int(revision, "revision")
    run_id = _string(run_id, "run_id")
    try:
        mode = mode if type(mode) is RunMode else RunMode(mode) if type(mode) is str else None
        status = status if type(status) is RunStatus else RunStatus(status) if type(status) is str else None
        if mode is None or status is None:
            raise TypeError("run enum must be an exact enum or string")
    except (ValueError, TypeError):
        raise InvalidSchemaError(ErrorMessage.UNKNOWN_RUN_ENUM, {
            ErrorDetailKey.MODE.value: mode, ErrorDetailKey.STATUS.value: status,
        }) from None
    created_at = _timestamp(created_at, "created_at")
    updated_at = _timestamp(updated_at, "updated_at")
    if not isinstance(raw_nodes, Mapping):
        raise InvalidSchemaError(ErrorMessage.NODES_OBJECT_REQUIRED)
    budget = budget if budget is not None else _StateItemBudget(MAX_PAYLOAD_ITEMS)
    nodes = {}
    node_count = 0
    edge_count = 0
    node_evidence_count = 0
    try:
        for key in bounded_iterable(raw_nodes, max_items=MAX_PAYLOAD_ITEMS):
            budget.consume()
            if type(key) is not str:
                raise InvalidSchemaError(ErrorMessage.NODE_KEYS_STRINGS)
            if not node_keys_budgeted:
                budget.consume_text(key)
            value = raw_nodes[key]
            node = (_node_state_from_mapping(value, budget) if nodes_from_dict
                    else _snapshot_node_state(value, budget))
            nodes[key] = node
            node_count += 1
            edge_count += len(node.dependencies)
            node_evidence_count += len(node.evidence)
    except InvalidSchemaError:
        raise
    except (KeyError, TypeError, ValueError, RecursionError):
        raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE) from None
    try:
        for key in nodes:
            validate_durable_key(key)
    except ValueError:
        raise InvalidSchemaError(ErrorMessage.NODE_KEYS_UNSAFE_URI) from None
    if any(key != node.node_id for key, node in nodes.items()):
        raise InvalidSchemaError(ErrorMessage.NODE_KEYS_MISMATCH)
    evidence = _string_tuple(raw_evidence, "evidence", references=True, budget=budget)
    _validate_dependency_graph(nodes)
    if len(evidence) + node_evidence_count > MAX_EVIDENCE_ITEMS:
        raise InvalidSchemaError(ErrorMessage.EVIDENCE_ITEM_LIMIT, {
            ErrorDetailKey.REASON_CODE.value: "evidence_limit_exceeded",
            ErrorDetailKey.LIMIT_ITEMS.value: MAX_EVIDENCE_ITEMS,
        })
    if type(cleanup_reconciled) is not bool:
        raise InvalidSchemaError(ErrorMessage.CLEANUP_RECONCILED_BOOLEAN)
    values = (version, revision, run_id, mode, status, created_at, updated_at,
              MappingProxyType(nodes), evidence, cleanup_reconciled)
    if include_counters:
        return values, (
            node_count, edge_count, node_evidence_count + len(evidence),
            budget.text_bytes,
        )
    return values


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

    def __init_subclass__(cls, **_kwargs):
        raise TypeError("RunState is final")

    def __post_init__(self) -> None:
        values = _validated_run_projection(
            self.schema_version, self.revision, self.run_id, self.mode, self.status,
            self.created_at, self.updated_at, self.nodes, self.evidence,
            self.cleanup_reconciled,
        )
        for name, value in zip(self.__dataclass_fields__, values):
            object.__setattr__(self, name, value)

    @classmethod
    def new(cls, run_id: str, occurred_at: str, mode: RunMode = RunMode.SHADOW) -> "RunState":
        return cls(SCHEMA_VERSION, 0, run_id, mode, RunStatus.PLANNED,
                   occurred_at, occurred_at, MappingProxyType({}))

    @classmethod
    def from_dict(cls, data: object) -> "RunState":
        snapshot = _bounded_mapping(data, ErrorMessage.STATE_OBJECT_REQUIRED)
        fields = {"schema_version", "revision", "run_id", "mode", "status", "created_at", "updated_at", "nodes", "evidence", "cleanup_reconciled"}
        _only(snapshot, fields, fields)
        budget = _StateItemBudget(MAX_PAYLOAD_ITEMS)
        raw_nodes = _bounded_mapping(
            snapshot["nodes"], ErrorMessage.NODES_OBJECT_REQUIRED, text_budget=budget,
        )
        return _trusted_run_state(_validated_run_projection(
            snapshot["schema_version"], snapshot["revision"], snapshot["run_id"],
            snapshot["mode"], snapshot["status"], snapshot["created_at"],
            snapshot["updated_at"], raw_nodes, snapshot["evidence"],
            snapshot["cleanup_reconciled"], nodes_from_dict=True, budget=budget,
            node_keys_budgeted=True,
        ))

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version, "revision": self.revision, "run_id": self.run_id,
            "mode": self.mode.value, "status": self.status.value, "created_at": self.created_at,
            "updated_at": self.updated_at,
            "nodes": {key: NodeState.to_dict(self.nodes[key]) for key in sorted(self.nodes)},
            "evidence": list(self.evidence), "cleanup_reconciled": self.cleanup_reconciled,
        }


def _snapshot_run_state(state: RunState, *, include_counters=False):
    """Rebuild exact state and nodes field-wise under one aggregate budget."""
    if type(state) is not RunState:
        raise UnsafePayloadError(ErrorMessage.PREPARED_STATE_RUN_STATE_REQUIRED)
    try:
        projection = _validated_run_projection(
            state.schema_version, state.revision, state.run_id, state.mode, state.status,
            state.created_at, state.updated_at, state.nodes, state.evidence,
            state.cleanup_reconciled, include_counters=include_counters,
        )
        if include_counters:
            values, counters = projection
            return _trusted_run_state(values), counters
        return _trusted_run_state(projection)
    except KernelError:
        raise
    except (AttributeError, TypeError, ValueError, RecursionError):
        raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE) from None


def _trusted_run_state_update(state: RunState, **changes) -> RunState:
    """Internal reducer update after one public-boundary state validation."""
    values = {
        "schema_version": state.schema_version, "revision": state.revision,
        "run_id": state.run_id, "mode": state.mode, "status": state.status,
        "created_at": state.created_at, "updated_at": state.updated_at,
        "nodes": state.nodes, "evidence": state.evidence,
        "cleanup_reconciled": state.cleanup_reconciled,
    }
    values.update(changes)
    if "nodes" in changes and type(values["nodes"]) is not MappingProxyType:
        values["nodes"] = MappingProxyType(dict(values["nodes"]))
    return _trusted_run_state(tuple(values[name] for name in (
        "schema_version", "revision", "run_id", "mode", "status", "created_at",
        "updated_at", "nodes", "evidence", "cleanup_reconciled",
    )))
