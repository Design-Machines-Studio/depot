"""Durable ownership records and side-effect-free cleanup plans."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Tuple

from workflow_kernel.adapters.base import invalid_policy
from workflow_kernel.schema import InvalidSchemaError, RunStatus


class ResourceKind(str, Enum):
    WORKTREE = "worktree"
    BRANCH = "branch"
    CONTAINER = "container"
    NETWORK = "network"
    VOLUME = "volume"


class CleanupDisposition(str, Enum):
    REMOVED = "removed"
    RETAINED_FOR_DEPENDENCY = "retained_for_dependency"
    BLOCKED = "blocked"
    FOREIGN = "foreign"
    MISSING = "missing"


TERMINAL_DISPOSITIONS = {CleanupDisposition.REMOVED, CleanupDisposition.MISSING}
VALID_LIFECYCLES = {"chunk", "run"}
VALID_CLEANUP_POLICIES = {"stop-remove", "remove-when-stopped", "retain"}
_SENSITIVE = re.compile(r"(?i)(authorization|password|passwd|secret|token|api[-_]?key)")
_MAX_RECEIPT_DEPTH = 5
_MAX_RECEIPT_ITEMS = 32
_MAX_RECEIPT_STRING = 256


@dataclass(frozen=True)
class CommandResult:
    argv: Tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ResourceRecord:
    resource_id: str
    kind: ResourceKind
    run_id: str
    node_id: str
    lifecycle: str
    cleanup_policy: str
    created_at: datetime
    dependent_node_ids: Tuple[str, ...] = ()
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(type(value) is str and value for value in (self.resource_id, self.run_id, self.node_id)):
            raise invalid_policy("invalid_resource_identity")
        try:
            kind = ResourceKind(self.kind)
        except Exception:
            raise invalid_policy("invalid_resource_kind") from None
        if self.lifecycle not in VALID_LIFECYCLES:
            raise invalid_policy("invalid_resource_lifecycle")
        if self.cleanup_policy not in VALID_CLEANUP_POLICIES:
            raise invalid_policy("invalid_cleanup_policy")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise invalid_policy("resource_created_at_requires_timezone")
        dependencies = tuple(self.dependent_node_ids)
        if any(type(value) is not str or not value for value in dependencies):
            raise invalid_policy("invalid_resource_dependency")
        try:
            labels = dict(self.labels)
        except Exception:
            raise invalid_policy("invalid_resource_labels") from None
        if any(type(key) is not str or not key or type(value) is not str for key, value in labels.items()):
            raise invalid_policy("invalid_resource_labels")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "dependent_node_ids", dependencies)
        object.__setattr__(self, "labels", labels)


@dataclass(frozen=True)
class ResourceDisposition:
    resource_id: str
    kind: ResourceKind
    run_id: str
    node_id: str
    lifecycle: str
    disposition: CleanupDisposition
    action: str
    reason: str
    evidence: Tuple[object, ...] = ()
    command: Tuple[str, ...] = ()
    follow_up: Optional[str] = None

    def __post_init__(self) -> None:
        try:
            kind = ResourceKind(self.kind)
            state = CleanupDisposition(self.disposition)
        except Exception:
            raise invalid_policy("invalid_resource_disposition") from None
        if not all(type(value) is str and value for value in (
            self.resource_id, self.run_id, self.node_id, self.lifecycle, self.action, self.reason,
        )):
            raise invalid_policy("invalid_resource_disposition")
        command = tuple(self.command)
        if any(type(value) is not str or not value for value in command):
            raise invalid_policy("invalid_cleanup_command")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "disposition", state)
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "command", command)


@dataclass(frozen=True)
class ResourceRegistrationIntent:
    kind: ResourceKind
    expected_name: Optional[str]
    run_id: str
    node_id: str
    lifecycle: str
    cleanup_policy: str
    labels: Mapping[str, str]
    dependent_node_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CleanupAction:
    resource_id: str
    kind: ResourceKind
    action: str
    argv: Tuple[str, ...]
    requires_success_of: Optional[int] = None
    run_id: str = ""
    node_id: str = ""
    lifecycle: str = "chunk"


@dataclass(frozen=True)
class CleanupScope:
    run_id: str
    node_id: Optional[str] = None
    terminal: bool = False
    stale_sweep: bool = False


@dataclass(frozen=True)
class CleanupPlan:
    scope: CleanupScope
    before: Tuple[str, ...]
    actions: Tuple[CleanupAction, ...]
    dispositions: Tuple[ResourceDisposition, ...]


@dataclass(frozen=True)
class CleanupReceipt:
    scope: CleanupScope
    before: Tuple[str, ...]
    after: Tuple[str, ...]
    dispositions: Tuple[ResourceDisposition, ...]
    schema_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "scope": {
                "run_id": self.scope.run_id,
                **({"node_id": self.scope.node_id} if self.scope.node_id is not None else {}),
                "terminal": self.scope.terminal,
                "stale_sweep": self.scope.stale_sweep,
            },
            "before": list(self.before),
            "after": list(self.after),
            "dispositions": [_receipt_disposition(value) for value in self.dispositions],
        }


@dataclass(frozen=True)
class CreationReceipt:
    command_succeeded: bool
    before: Tuple[str, ...]
    after: Tuple[str, ...]
    registered: Tuple[ResourceRecord, ...]
    dispositions: Tuple[ResourceDisposition, ...]


def disposition_for(
    record: ResourceRecord,
    disposition: CleanupDisposition,
    action: str,
    reason: str,
    *,
    evidence: Iterable[object] = (),
    command: Sequence[str] = (),
    follow_up: Optional[str] = None,
) -> ResourceDisposition:
    return ResourceDisposition(
        resource_id=record.resource_id,
        kind=record.kind,
        run_id=record.run_id,
        node_id=record.node_id,
        lifecycle=record.lifecycle,
        disposition=disposition,
        action=action,
        reason=reason,
        evidence=tuple(evidence),
        command=tuple(command),
        follow_up=follow_up,
    )


class ResourceRegistry:
    """Append-only kind+ID registry with immutable successful outcomes."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._records: dict[tuple[ResourceKind, str], ResourceRecord] = {}
        self._attempts: dict[tuple[ResourceKind, str], list[ResourceDisposition]] = {}
        if self.path.exists():
            self._replay()

    def _replay(self) -> None:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                event = json.loads(line)
                if event.get("event") == "registered":
                    self._apply_registration(_record_from_json(event["resource"]), persist=False)
                elif event.get("event") == "disposition":
                    self._apply_disposition(_disposition_from_json(event["disposition"]), persist=False)
                else:
                    raise invalid_policy("invalid_resource_registry_event")
        except InvalidSchemaError:
            raise
        except Exception:
            raise invalid_policy("invalid_resource_registry") from None

    def _append(self, event: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())

    def register(self, resource: ResourceRecord) -> None:
        self._apply_registration(resource, persist=True)

    def _apply_registration(self, resource: ResourceRecord, *, persist: bool) -> None:
        key = (resource.kind, resource.resource_id)
        existing = self._records.get(key)
        if existing is not None:
            if existing == resource:
                return
            raise invalid_policy("resource_registration_conflict")
        if persist:
            self._append({"event": "registered", "resource": _resource_json(resource)})
        self._records[key] = resource

    def resources_for(self, scope: CleanupScope | str, node_id: Optional[str] = None) -> Tuple[ResourceRecord, ...]:
        if isinstance(scope, CleanupScope):
            run_id, node_id = scope.run_id, scope.node_id
        else:
            run_id = scope
        values = (
            value for key, value in self._records.items()
            if value.run_id == run_id and (node_id is None or value.node_id == node_id)
            and not self._is_retired(key)
        )
        return tuple(sorted(values, key=lambda value: (value.created_at, value.kind.value, value.resource_id)))

    def record_disposition(self, value: ResourceDisposition) -> ResourceDisposition:
        return self._apply_disposition(value, persist=True)

    def _apply_disposition(self, value: ResourceDisposition, *, persist: bool) -> ResourceDisposition:
        key = (value.kind, value.resource_id)
        record = self._records.get(key)
        if record is None:
            raise invalid_policy("unknown_resource")
        if (value.run_id, value.node_id, value.lifecycle) != (record.run_id, record.node_id, record.lifecycle):
            raise invalid_policy("resource_disposition_owner_conflict")
        terminal = next((item for item in self._attempts.get(key, ()) if item.disposition in TERMINAL_DISPOSITIONS), None)
        sanitized = _sanitize_disposition(value)
        if terminal is not None:
            if terminal == sanitized:
                return terminal
            raise invalid_policy("terminal_resource_disposition_immutable")
        if persist:
            self._append({"event": "disposition", "disposition": _disposition_json(sanitized)})
        self._attempts.setdefault(key, []).append(sanitized)
        return sanitized

    def disposition_for(self, kind: ResourceKind, resource_id: str) -> Optional[ResourceDisposition]:
        history = self._attempts.get((ResourceKind(kind), resource_id), ())
        return history[-1] if history else None

    def disposition_history(self, kind: ResourceKind, resource_id: str) -> Tuple[ResourceDisposition, ...]:
        return tuple(self._attempts.get((ResourceKind(kind), resource_id), ()))

    def _is_retired(self, key: tuple[ResourceKind, str]) -> bool:
        return any(value.disposition in TERMINAL_DISPOSITIONS for value in self._attempts.get(key, ()))


class OwnedResourceLifecycle:
    """Coordinates pure cleanup planning at mandatory lifecycle boundaries."""

    def __init__(self, docker_adapter: object):
        self.docker_adapter = docker_adapter

    def after_chunk(
        self, registry: ResourceRegistry, inventory: object, run_id: str, node_id: str,
        validated: bool, reviewed: bool, evidence_captured: bool, merge_disposed: bool,
    ) -> CleanupPlan:
        if not all((validated, reviewed, evidence_captured, merge_disposed)):
            raise invalid_policy("chunk_cleanup_before_boundary_complete")
        return self.docker_adapter.plan_chunk_cleanup(registry, inventory, run_id, node_id)

    def at_terminal(
        self, registry: ResourceRegistry, inventory: object, run_id: str, status: RunStatus,
        *, active_node_ids: Sequence[str] = (),
    ) -> CleanupPlan:
        try:
            normalized = RunStatus(status)
        except Exception:
            raise invalid_policy("invalid_terminal_status") from None
        if normalized not in {
            RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BLOCKED,
            RunStatus.CANCELLED, RunStatus.INTERRUPTED,
        }:
            raise invalid_policy("cleanup_requires_terminal_status")
        return self.docker_adapter.plan_reconcile_run(
            registry, inventory, run_id, active_node_ids=active_node_ids, terminal=True,
        )


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError
    return parsed


def _resource_json(value: ResourceRecord) -> dict[str, object]:
    return {
        "resource_id": value.resource_id, "kind": value.kind.value,
        "run_id": value.run_id, "node_id": value.node_id,
        "lifecycle": value.lifecycle, "cleanup_policy": value.cleanup_policy,
        "created_at": _timestamp(value.created_at),
        "dependent_node_ids": list(value.dependent_node_ids), "labels": dict(value.labels),
    }


def _record_from_json(value: Mapping[str, object]) -> ResourceRecord:
    return ResourceRecord(
        resource_id=value["resource_id"], kind=ResourceKind(value["kind"]),
        run_id=value["run_id"], node_id=value["node_id"],
        lifecycle=value["lifecycle"], cleanup_policy=value["cleanup_policy"],
        created_at=_parse_timestamp(value["created_at"]),
        dependent_node_ids=tuple(value.get("dependent_node_ids", ())),
        labels=value.get("labels", {}),
    )


def _disposition_json(value: ResourceDisposition) -> dict[str, object]:
    result = {
        "resource_id": value.resource_id, "kind": value.kind.value,
        "run_id": value.run_id, "node_id": value.node_id, "lifecycle": value.lifecycle,
        "disposition": value.disposition.value, "action": value.action, "reason": value.reason,
        "command": list(value.command), "evidence": list(value.evidence),
    }
    if value.follow_up is not None:
        result["follow_up"] = value.follow_up
    return result


def _disposition_from_json(value: Mapping[str, object]) -> ResourceDisposition:
    return ResourceDisposition(
        resource_id=value["resource_id"], kind=ResourceKind(value["kind"]),
        run_id=value["run_id"], node_id=value["node_id"], lifecycle=value["lifecycle"],
        disposition=CleanupDisposition(value["disposition"]), action=value["action"],
        reason=value["reason"], evidence=tuple(value.get("evidence", ())),
        command=tuple(value.get("command", ())), follow_up=value.get("follow_up"),
    )


def _receipt_disposition(value: ResourceDisposition) -> dict[str, object]:
    sanitized = _sanitize_disposition(value)
    result = {
        "resource_id": sanitized.resource_id,
        "kind": sanitized.kind.value,
        "owner": {"run_id": sanitized.run_id, "node_id": sanitized.node_id},
        "lifecycle": sanitized.lifecycle,
        "disposition": sanitized.disposition.value,
        "action": sanitized.action,
        "reason": sanitized.reason,
        "command_evidence": list(sanitized.command),
        "evidence": list(sanitized.evidence),
    }
    if sanitized.follow_up is not None:
        result["follow_up"] = sanitized.follow_up
    return result


def _sanitize_disposition(value: ResourceDisposition) -> ResourceDisposition:
    return replace(
        value,
        evidence=tuple(_redact(item) for item in value.evidence[:_MAX_RECEIPT_ITEMS]),
        command=tuple(_redact(item) for item in value.command[:_MAX_RECEIPT_ITEMS]),
        follow_up=None if value.follow_up is None else _redact(value.follow_up),
    )


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return "value-sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _redact(value: object, *, key: Optional[str] = None, depth: int = 0) -> object:
    if key is not None and _SENSITIVE.search(key):
        return _digest(value)
    if depth >= _MAX_RECEIPT_DEPTH:
        return _digest(value)
    if type(value) is str:
        if len(value) > _MAX_RECEIPT_STRING or _SENSITIVE.search(value):
            return _digest(value)
        return value
    if type(value) is dict:
        items = list(value.items())
        result = {
            _redact_key(name): _redact(item, key=str(name), depth=depth + 1)
            for name, item in items[:_MAX_RECEIPT_ITEMS]
        }
        if len(items) > _MAX_RECEIPT_ITEMS:
            result["truncated"] = _digest(items[_MAX_RECEIPT_ITEMS:])
        return result
    if type(value) in (list, tuple):
        values = list(value)
        result = [_redact(item, depth=depth + 1) for item in values[:_MAX_RECEIPT_ITEMS]]
        if len(values) > _MAX_RECEIPT_ITEMS:
            result.append(_digest(values[_MAX_RECEIPT_ITEMS:]))
        return result
    if type(value) in (int, bool) or value is None:
        return value
    return _digest(value)


def _redact_key(value: object) -> str:
    key = str(value)
    if len(key) > _MAX_RECEIPT_STRING or _SENSITIVE.search(key):
        return "key-sha256:" + hashlib.sha256(key.encode("utf-8")).hexdigest()
    return key
