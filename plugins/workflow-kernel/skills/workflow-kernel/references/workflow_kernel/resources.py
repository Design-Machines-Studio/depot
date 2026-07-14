"""Durable owned-resource registry and cleanup planning primitives.

Cleanup plans are data.  In particular, this module never executes Docker
cleanup; the workflow executor consumes the exact argv recorded by a plan.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Tuple

from workflow_kernel.adapters.base import invalid_policy
from workflow_kernel.schema import RunStatus


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
        if not all(type(x) is str and x for x in (self.resource_id, self.run_id, self.node_id)):
            raise invalid_policy("invalid_resource_identity")
        if self.lifecycle not in ("chunk", "run"):
            raise invalid_policy("invalid_resource_lifecycle")
        if self.created_at.tzinfo is None:
            raise invalid_policy("resource_created_at_requires_timezone")
        object.__setattr__(self, "kind", ResourceKind(self.kind))
        object.__setattr__(self, "dependent_node_ids", tuple(self.dependent_node_ids))
        object.__setattr__(self, "labels", dict(self.labels))


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
    evidence: Tuple[str, ...] = ()
    follow_up: Optional[str] = None


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
    before: Tuple[str, ...]
    after: Tuple[str, ...]
    dispositions: Tuple[ResourceDisposition, ...]


def disposition_for(
    record: ResourceRecord,
    disposition: CleanupDisposition,
    action: str,
    reason: str,
    *,
    evidence: Iterable[str] = (),
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
        follow_up=follow_up,
    )


class ResourceRegistry:
    """Append-only JSONL registry replayed on construction."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._records: dict[str, ResourceRecord] = {}
        self._dispositions: dict[str, ResourceDisposition] = {}
        if self.path.exists():
            self._replay()

    def _replay(self) -> None:
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event["event"] == "registered":
                    value = event["resource"]
                    record = ResourceRecord(
                        resource_id=value["resource_id"], kind=ResourceKind(value["kind"]),
                        run_id=value["run_id"], node_id=value["node_id"],
                        lifecycle=value["lifecycle"], cleanup_policy=value["cleanup_policy"],
                        created_at=_parse_timestamp(value["created_at"]),
                        dependent_node_ids=tuple(value.get("dependent_node_ids", ())),
                        labels=value.get("labels", {}),
                    )
                    self._records[record.resource_id] = record
                elif event["event"] == "disposition":
                    value = event["disposition"]
                    self._dispositions[value["resource_id"]] = ResourceDisposition(
                        resource_id=value["resource_id"], kind=ResourceKind(value["kind"]),
                        run_id=value["run_id"], node_id=value["node_id"],
                        lifecycle=value["lifecycle"], disposition=CleanupDisposition(value["disposition"]),
                        action=value["action"], reason=value["reason"],
                        evidence=tuple(value.get("evidence", ())), follow_up=value.get("follow_up"),
                    )
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
        existing = self._records.get(resource.resource_id)
        if existing is not None:
            if existing == resource:
                return
            raise invalid_policy("resource_registration_conflict")
        self._append({"event": "registered", "resource": _resource_json(resource)})
        self._records[resource.resource_id] = resource

    def resources_for(self, scope: CleanupScope | str, node_id: Optional[str] = None) -> Tuple[ResourceRecord, ...]:
        if isinstance(scope, CleanupScope):
            run_id, node_id = scope.run_id, scope.node_id
        else:
            run_id = scope
        values = (
            value for value in self._records.values()
            if value.run_id == run_id and (node_id is None or value.node_id == node_id)
            and self._dispositions.get(value.resource_id, None) is None
        )
        return tuple(sorted(values, key=lambda value: (value.created_at, value.kind.value, value.resource_id)))

    def record_disposition(
        self, resource_id: ResourceDisposition | str,
        disposition: Optional[CleanupDisposition] = None, reason: Optional[str] = None,
        *, action: str = "none", evidence: Iterable[str] = (), follow_up: Optional[str] = None,
    ) -> ResourceDisposition:
        if isinstance(resource_id, ResourceDisposition):
            value = resource_id
            record = self._records.get(value.resource_id)
            if record is None:
                raise invalid_policy("unknown_resource")
            if (value.kind, value.run_id, value.node_id, value.lifecycle) != (
                record.kind, record.run_id, record.node_id, record.lifecycle,
            ):
                raise invalid_policy("resource_disposition_owner_conflict")
        else:
            record = self._records.get(resource_id)
            if record is None:
                raise invalid_policy("unknown_resource")
            if disposition is None or reason is None:
                raise invalid_policy("incomplete_resource_disposition")
            value = disposition_for(record, CleanupDisposition(disposition), action, reason, evidence=evidence, follow_up=follow_up)
        if self._dispositions.get(value.resource_id) == value:
            return value
        self._append({"event": "disposition", "disposition": _disposition_json(value)})
        self._dispositions[value.resource_id] = value
        return value

    def disposition_for(self, resource_id: str) -> Optional[ResourceDisposition]:
        return self._dispositions.get(resource_id)


class OwnedResourceLifecycle:
    """Coordinates cleanup planning at mandatory lifecycle boundaries."""

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
            registry, inventory, run_id, active_node_ids=active_node_ids, terminal=True
        )


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _resource_json(value: ResourceRecord) -> dict[str, object]:
    return {
        "resource_id": value.resource_id, "kind": value.kind.value,
        "run_id": value.run_id, "node_id": value.node_id,
        "lifecycle": value.lifecycle, "cleanup_policy": value.cleanup_policy,
        "created_at": _timestamp(value.created_at),
        "dependent_node_ids": list(value.dependent_node_ids), "labels": dict(value.labels),
    }


def _disposition_json(value: ResourceDisposition) -> dict[str, object]:
    result = {
        "resource_id": value.resource_id, "kind": value.kind.value,
        "run_id": value.run_id, "node_id": value.node_id, "lifecycle": value.lifecycle,
        "disposition": value.disposition.value, "action": value.action, "reason": value.reason,
        "evidence": list(value.evidence),
    }
    if value.follow_up is not None:
        result["follow_up"] = value.follow_up
    return result
