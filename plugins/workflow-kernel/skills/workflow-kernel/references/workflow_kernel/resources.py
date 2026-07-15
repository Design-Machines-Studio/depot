"""Durable ownership records and side-effect-free cleanup plans."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Mapping, Optional, Sequence, Tuple, Union

from workflow_kernel._files import LockHandle, PinnedDirectory, bind_durable_path
from workflow_kernel.adapters.base import invalid_policy
from workflow_kernel.redaction import (
    contains_secret_shape, digest_error_detail_string, is_secret_key,
    sanitize_durable_payload,
)
from workflow_kernel.schema import InvalidSchemaError, RunStatus

if TYPE_CHECKING:
    from workflow_kernel.adapters.docker import IncompleteNodeProof


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
_MAX_RECEIPT_DEPTH = 5
_MAX_RECEIPT_ITEMS = 32
_MAX_RECEIPT_STRING = 256
_MAX_IDENTIFIER = 256
_MAX_RESOURCE_ID = 4096
_VALID_DISPOSITION_ACTIONS = {"none", "remove_exact_id"}
_VALID_CLEANUP_ACTIONS = {"stop", "remove"}
_VALID_CLEANUP_STEP_TYPES = {"command_action", "terminal_observation"}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _valid_text(value: object, *, maximum: int) -> bool:
    return (
        type(value) is str and bool(value) and value == value.strip()
        and len(value) <= maximum and _CONTROL.search(value) is None
    )


def _valid_timestamp(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class CommandResult:
    argv: Tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str

    def __post_init__(self) -> None:
        if type(self.argv) is not tuple:
            raise invalid_policy("invalid_command_result")
        argv = self.argv
        if not argv or any(not _valid_text(value, maximum=_MAX_RESOURCE_ID) for value in argv):
            raise invalid_policy("invalid_command_result")
        if type(self.exit_code) is not int or type(self.stdout) is not str or type(self.stderr) is not str:
            raise invalid_policy("invalid_command_result")
        object.__setattr__(self, "argv", argv)


@dataclass(frozen=True)
class CleanupStepIdentity:
    """One immutable authority-bearing position in a canonical cleanup plan."""

    plan_digest: str
    step_index: int
    step_type: str

    def __post_init__(self) -> None:
        if (
            type(self.plan_digest) is not str
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.plan_digest)
            or type(self.step_index) is not int or self.step_index < 0
            or type(self.step_type) is not str
            or self.step_type not in _VALID_CLEANUP_STEP_TYPES
        ):
            raise invalid_policy("invalid_cleanup_step_identity")


@dataclass(frozen=True)
class GuardedCommandResult:
    """One exact command result authorized under its resource execution guard."""

    result: CommandResult
    kind: ResourceKind
    resource_id: str
    run_id: str
    node_id: str
    action_digest: str
    state_generation: str
    issued_at: datetime
    expires_at: datetime
    authority_id: str
    step_identity: CleanupStepIdentity

    def __post_init__(self) -> None:
        try:
            kind = ResourceKind(self.kind)
        except Exception:
            raise invalid_policy("invalid_guarded_command_result") from None
        if (
            type(self.result) is not CommandResult
            or not _valid_text(self.resource_id, maximum=_MAX_RESOURCE_ID)
            or not all(_valid_text(value, maximum=_MAX_IDENTIFIER) for value in (
                self.run_id, self.node_id,
            ))
            or not all(re.fullmatch(r"sha256:[0-9a-f]{64}", value or "") for value in (
                self.action_digest, self.state_generation, self.authority_id,
            ))
            or not _valid_timestamp(self.issued_at)
            or not _valid_timestamp(self.expires_at)
            or self.expires_at <= self.issued_at
            or type(self.step_identity) is not CleanupStepIdentity
            or self.step_identity.step_type != "command_action"
        ):
            raise invalid_policy("invalid_guarded_command_result")
        object.__setattr__(self, "kind", kind)


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
        if not _valid_text(self.resource_id, maximum=_MAX_RESOURCE_ID) or not all(
            _valid_text(value, maximum=_MAX_IDENTIFIER) for value in (self.run_id, self.node_id)
        ):
            raise invalid_policy("invalid_resource_identity")
        try:
            kind = ResourceKind(self.kind)
        except Exception:
            raise invalid_policy("invalid_resource_kind") from None
        if self.lifecycle not in VALID_LIFECYCLES:
            raise invalid_policy("invalid_resource_lifecycle")
        if self.cleanup_policy not in VALID_CLEANUP_POLICIES:
            raise invalid_policy("invalid_cleanup_policy")
        if not _valid_timestamp(self.created_at):
            raise invalid_policy("resource_created_at_requires_timezone")
        if type(self.dependent_node_ids) is not tuple or type(self.labels) is not dict:
            raise invalid_policy("invalid_resource_record_collections")
        dependencies = self.dependent_node_ids
        if any(not _valid_text(value, maximum=_MAX_IDENTIFIER) for value in dependencies) or len(set(dependencies)) != len(dependencies):
            raise invalid_policy("invalid_resource_dependency")
        try:
            labels = dict(self.labels)
        except Exception:
            raise invalid_policy("invalid_resource_labels") from None
        if any(
            not _valid_text(key, maximum=_MAX_IDENTIFIER)
            or type(value) is not str or len(value) > _MAX_RESOURCE_ID or _CONTROL.search(value)
            for key, value in labels.items()
        ):
            raise invalid_policy("invalid_resource_labels")
        if any(is_secret_key(key) or contains_secret_shape(value) for key, value in labels.items()):
            raise invalid_policy("secret_shaped_resource_label")
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
        if (
            not _valid_text(self.resource_id, maximum=_MAX_RESOURCE_ID)
            or not all(_valid_text(value, maximum=_MAX_IDENTIFIER) for value in (self.run_id, self.node_id))
            or self.lifecycle not in VALID_LIFECYCLES
            or self.action not in _VALID_DISPOSITION_ACTIONS
            or not _valid_text(self.reason, maximum=_MAX_RESOURCE_ID)
        ):
            raise invalid_policy("invalid_resource_disposition")
        if type(self.evidence) is not tuple or type(self.command) is not tuple:
            raise invalid_policy("invalid_resource_disposition_collections")
        command = self.command
        if len(command) > _MAX_RECEIPT_ITEMS or any(not _valid_text(value, maximum=_MAX_RESOURCE_ID) for value in command):
            raise invalid_policy("invalid_cleanup_command")
        if self.follow_up is not None and not _valid_text(self.follow_up, maximum=_MAX_RESOURCE_ID):
            raise invalid_policy("invalid_resource_disposition")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "disposition", state)
        object.__setattr__(self, "evidence", self.evidence)
        object.__setattr__(self, "command", command)


@dataclass(frozen=True)
class GuardedTerminalObservation:
    """Fresh exact-ID terminal observation issued under its resource guard."""

    disposition: ResourceDisposition
    result: CommandResult
    evidence_digest: str
    state_generation: str
    issued_at: datetime
    expires_at: datetime
    authority_id: str
    step_identity: CleanupStepIdentity

    def __post_init__(self) -> None:
        if (
            type(self.disposition) is not ResourceDisposition
            or self.disposition.disposition is not CleanupDisposition.MISSING
            or self.disposition.action != "none"
            or type(self.result) is not CommandResult
            or not all(re.fullmatch(r"sha256:[0-9a-f]{64}", value or "") for value in (
                self.evidence_digest, self.state_generation, self.authority_id,
            ))
            or not _valid_timestamp(self.issued_at)
            or not _valid_timestamp(self.expires_at)
            or self.expires_at <= self.issued_at
            or type(self.step_identity) is not CleanupStepIdentity
            or self.step_identity.step_type != "terminal_observation"
        ):
            raise invalid_policy("invalid_guarded_terminal_observation")


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

    def __post_init__(self) -> None:
        try:
            kind = ResourceKind(self.kind)
            if type(self.labels) is not dict or type(self.dependent_node_ids) is not tuple:
                raise TypeError
            labels = dict(self.labels)
            dependencies = self.dependent_node_ids
        except Exception:
            raise invalid_policy("invalid_resource_registration_intent") from None
        if (
            (self.expected_name is not None and not _valid_text(self.expected_name, maximum=_MAX_RESOURCE_ID))
            or not all(_valid_text(value, maximum=_MAX_IDENTIFIER) for value in (self.run_id, self.node_id))
            or self.lifecycle not in VALID_LIFECYCLES
            or self.cleanup_policy not in VALID_CLEANUP_POLICIES
            or len(set(dependencies)) != len(dependencies)
            or any(not _valid_text(value, maximum=_MAX_IDENTIFIER) for value in dependencies)
            or any(not _valid_text(key, maximum=_MAX_IDENTIFIER) or type(value) is not str for key, value in labels.items())
        ):
            raise invalid_policy("invalid_resource_registration_intent")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "dependent_node_ids", dependencies)


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
    proof_digest: str = ""
    preconditions: Tuple[str, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)
    predecessor_result_id: Optional[str] = None
    evidence_digest: str = ""

    def __post_init__(self) -> None:
        try:
            kind = ResourceKind(self.kind)
            if (
                type(self.argv) is not tuple or type(self.preconditions) is not tuple
                or type(self.environment) is not dict
            ):
                raise TypeError
            argv = self.argv
            environment = dict(self.environment)
        except Exception:
            raise invalid_policy("invalid_cleanup_action") from None
        if (
            not _valid_text(self.resource_id, maximum=_MAX_RESOURCE_ID)
            or self.action not in _VALID_CLEANUP_ACTIONS
            or not argv or any(not _valid_text(value, maximum=_MAX_RESOURCE_ID) for value in argv)
            or (self.requires_success_of is not None and (
                type(self.requires_success_of) is not int or self.requires_success_of < 0
            ))
            or not all(_valid_text(value, maximum=_MAX_IDENTIFIER) for value in (self.run_id, self.node_id))
            or self.lifecycle not in VALID_LIFECYCLES
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.proof_digest)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.evidence_digest)
            or not self.preconditions
            or len(set(self.preconditions)) != len(self.preconditions)
            or any(not _valid_text(value, maximum=_MAX_RESOURCE_ID) for value in self.preconditions)
            or any(
                not _valid_text(key, maximum=_MAX_IDENTIFIER) or type(value) is not str
                or len(value) > _MAX_RESOURCE_ID or _CONTROL.search(value)
                or is_secret_key(key) or contains_secret_shape(value)
                for key, value in environment.items()
            )
            or (self.predecessor_result_id is not None and not re.fullmatch(
                r"sha256:[0-9a-f]{64}", self.predecessor_result_id,
            ))
        ):
            raise invalid_policy("invalid_cleanup_action")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "argv", argv)
        object.__setattr__(self, "preconditions", self.preconditions)
        object.__setattr__(self, "environment", environment)

    def to_dict(self) -> dict[str, object]:
        return {
            "resource_id": self.resource_id, "kind": self.kind.value,
            "action": self.action, "argv": list(self.argv),
            "requires_success_of": self.requires_success_of,
            "owner": {"run_id": self.run_id, "node_id": self.node_id},
            "lifecycle": self.lifecycle, "proof_digest": self.proof_digest,
            "preconditions": list(self.preconditions),
            "environment": dict(self.environment),
            "predecessor_result_id": self.predecessor_result_id,
            "evidence_digest": self.evidence_digest,
        }


@dataclass(frozen=True)
class CleanupScope:
    run_id: str
    node_id: Optional[str] = None
    terminal: bool = False
    stale_sweep: bool = False
    repository_scope_id: str = "0" * 64

    def __post_init__(self) -> None:
        if (
            not _valid_text(self.run_id, maximum=_MAX_IDENTIFIER)
            or (self.node_id is not None and not _valid_text(self.node_id, maximum=_MAX_IDENTIFIER))
            or type(self.terminal) is not bool or type(self.stale_sweep) is not bool
            or re.fullmatch(r"[0-9a-f]{64}", self.repository_scope_id) is None
        ):
            raise invalid_policy("invalid_cleanup_scope")


@dataclass(frozen=True)
class CleanupPlan:
    scope: CleanupScope
    before: Tuple[str, ...]
    actions: Tuple[CleanupAction, ...]
    dispositions: Tuple[ResourceDisposition, ...]

    def __post_init__(self) -> None:
        if not all(type(value) is tuple for value in (self.before, self.actions, self.dispositions)):
            raise invalid_policy("invalid_cleanup_plan_collections")
        before, actions, dispositions = self.before, self.actions, self.dispositions
        if (
            type(self.scope) is not CleanupScope
            or any(not _valid_text(value, maximum=_MAX_RESOURCE_ID) for value in before)
            or len(set(before)) != len(before)
            or any(type(value) is not CleanupAction for value in actions)
            or any(type(value) is not ResourceDisposition for value in dispositions)
        ):
            raise invalid_policy("invalid_cleanup_plan")
        if any(
            action.requires_success_of is not None
            and action.requires_success_of >= index
            for index, action in enumerate(actions)
        ):
            raise invalid_policy("cleanup_dependency_not_earlier_action")
        object.__setattr__(self, "before", before)
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "dispositions", dispositions)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "scope": {
                "run_id": self.scope.run_id,
                **({"node_id": self.scope.node_id} if self.scope.node_id is not None else {}),
                "terminal": self.scope.terminal, "stale_sweep": self.scope.stale_sweep,
                "repository_scope_id": self.scope.repository_scope_id,
            },
            "before": list(self.before),
            "actions": [value.to_dict() for value in self.actions],
            "dispositions": [_raw_receipt_disposition(value) for value in self.dispositions],
        }


def _snapshot_cleanup_plan(plan: CleanupPlan) -> CleanupPlan:
    """Defensively copy every field that contributes to cleanup authority."""
    if type(plan) is not CleanupPlan:
        raise invalid_policy("invalid_cleanup_plan")
    try:
        return CleanupPlan(
            CleanupScope(
                plan.scope.run_id, plan.scope.node_id,
                plan.scope.terminal, plan.scope.stale_sweep,
                plan.scope.repository_scope_id,
            ),
            tuple(plan.before),
            tuple(CleanupAction(
                item.resource_id, item.kind, item.action, tuple(item.argv),
                item.requires_success_of, item.run_id, item.node_id,
                item.lifecycle, item.proof_digest, tuple(item.preconditions),
                dict(item.environment), item.predecessor_result_id,
                item.evidence_digest,
            ) for item in plan.actions),
            tuple(_sanitize_disposition(
                _disposition_from_json(_disposition_json(item))
            ) for item in plan.dispositions),
        )
    except InvalidSchemaError:
        raise
    except Exception:
        raise invalid_policy("invalid_cleanup_plan") from None


def cleanup_plan_digest(plan: CleanupPlan) -> str:
    """Digest one immutable snapshot of every plan field and ordered step."""
    snapshot = _snapshot_cleanup_plan(plan)
    return cleanup_proof_digest({"cleanup_plan": snapshot.to_dict()})


def _cleanup_step_entries(
    plan: CleanupPlan,
) -> tuple[CleanupPlan, Tuple[tuple[CleanupStepIdentity, object], ...]]:
    snapshot = _snapshot_cleanup_plan(plan)
    digest = cleanup_proof_digest({"cleanup_plan": snapshot.to_dict()})
    action_fingerprints = tuple(
        cleanup_proof_digest({"command_action": value.to_dict()})
        for value in snapshot.actions
    )
    action_argv = tuple(value.argv for value in snapshot.actions)
    if (
        len(set(action_fingerprints)) != len(action_fingerprints)
        or len(set(action_argv)) != len(action_argv)
    ):
        raise invalid_policy("duplicate_cleanup_plan_step")
    terminal = tuple(
        value for value in snapshot.dispositions
        if value.disposition is CleanupDisposition.MISSING
    )
    terminal_keys = tuple((value.kind, value.resource_id) for value in terminal)
    action_keys = {(value.kind, value.resource_id) for value in snapshot.actions}
    if (
        len(set(terminal_keys)) != len(terminal_keys)
        or bool(action_keys.intersection(terminal_keys))
    ):
        raise invalid_policy("duplicate_cleanup_plan_step")
    entries: list[tuple[CleanupStepIdentity, object]] = []
    for action in snapshot.actions:
        entries.append((CleanupStepIdentity(
            digest, len(entries), "command_action",
        ), action))
    for disposition in terminal:
        entries.append((CleanupStepIdentity(
            digest, len(entries), "terminal_observation",
        ), disposition))
    return snapshot, tuple(entries)


def cleanup_step_identities(plan: CleanupPlan) -> Tuple[CleanupStepIdentity, ...]:
    """Return action steps followed by actionless terminal observations."""
    _snapshot, entries = _cleanup_step_entries(plan)
    return tuple(identity for identity, _value in entries)


@dataclass(frozen=True)
class CleanupReceipt:
    scope: CleanupScope
    before: Tuple[str, ...]
    after: Tuple[str, ...]
    dispositions: Tuple[ResourceDisposition, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not all(type(value) is tuple for value in (self.before, self.after, self.dispositions)):
            raise invalid_policy("invalid_cleanup_receipt_collections")
        before, after, dispositions = self.before, self.after, self.dispositions
        if (
            type(self.scope) is not CleanupScope or type(self.schema_version) is not int or self.schema_version != 1
            or any(not _valid_text(value, maximum=_MAX_RESOURCE_ID) for value in before + after)
            or len(set(before)) != len(before) or len(set(after)) != len(after)
            or any(type(value) is not ResourceDisposition for value in dispositions)
        ):
            raise invalid_policy("invalid_cleanup_receipt")
        object.__setattr__(self, "before", before)
        object.__setattr__(self, "after", after)
        object.__setattr__(self, "dispositions", dispositions)

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema_version": self.schema_version,
            "scope": {
                "run_id": self.scope.run_id,
                **({"node_id": self.scope.node_id} if self.scope.node_id is not None else {}),
                "terminal": self.scope.terminal,
                "stale_sweep": self.scope.stale_sweep,
                "repository_scope_id": self.scope.repository_scope_id,
            },
            "before": list(self.before),
            "after": list(self.after),
            "dispositions": [_raw_receipt_disposition(value) for value in self.dispositions],
        }
        return sanitize_durable_payload(
            payload,
            public_string_length=_MAX_RECEIPT_STRING,
            max_depth=_MAX_RECEIPT_DEPTH + 4,
            allowed_opaque_schemes=tuple(value.value for value in ResourceKind),
        )


@dataclass(frozen=True)
class CreationReceipt:
    command_succeeded: bool
    before: Tuple[str, ...]
    after: Tuple[str, ...]
    registered: Tuple[ResourceRecord, ...]
    dispositions: Tuple[ResourceDisposition, ...]

    def __post_init__(self) -> None:
        before, after = tuple(self.before), tuple(self.after)
        registered, dispositions = tuple(self.registered), tuple(self.dispositions)
        if (
            type(self.command_succeeded) is not bool
            or any(not _valid_text(value, maximum=_MAX_RESOURCE_ID) for value in before + after)
            or len(set(before)) != len(before) or len(set(after)) != len(after)
            or any(type(value) is not ResourceRecord for value in registered)
            or any(type(value) is not ResourceDisposition for value in dispositions)
        ):
            raise invalid_policy("invalid_creation_receipt")
        object.__setattr__(self, "before", before)
        object.__setattr__(self, "after", after)
        object.__setattr__(self, "registered", registered)
        object.__setattr__(self, "dispositions", dispositions)


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


def cleanup_proof_digest(payload: Mapping[str, object]) -> str:
    """Bind a cleanup capability to one canonical, secret-free proof snapshot."""
    if type(payload) is not dict:
        raise invalid_policy("invalid_cleanup_proof")
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError):
        raise invalid_policy("invalid_cleanup_proof") from None
    if contains_secret_shape(encoded):
        raise invalid_policy("secret_shaped_cleanup_proof")
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def cleanup_result_id(argv: Tuple[str, ...], exit_code: int) -> str:
    if type(argv) is not tuple or type(exit_code) is not int:
        raise invalid_policy("invalid_cleanup_result_identity")
    return cleanup_proof_digest({"argv": list(argv), "exit_code": exit_code})


GuardedAuthority = Union[GuardedCommandResult, GuardedTerminalObservation]


def terminal_observation_evidence_digest(
    disposition: ResourceDisposition, result: CommandResult,
) -> str:
    if type(disposition) is not ResourceDisposition or type(result) is not CommandResult:
        raise invalid_policy("invalid_terminal_observation_evidence")
    return cleanup_proof_digest({
        "disposition": _disposition_json(disposition),
        "result_id": cleanup_result_id(result.argv, result.exit_code),
    })


def _authority_json(value: GuardedAuthority) -> dict[str, object]:
    if type(value) is GuardedCommandResult:
        kind, resource_id = value.kind, value.resource_id
        run_id, node_id = value.run_id, value.node_id
        capability_digest = value.action_digest
        result = value.result
    elif type(value) is GuardedTerminalObservation:
        disposition = value.disposition
        kind, resource_id = disposition.kind, disposition.resource_id
        run_id, node_id = disposition.run_id, disposition.node_id
        capability_digest = value.evidence_digest
        result = value.result
    else:
        raise invalid_policy("invalid_execution_authority")
    return {
        "authority_id": value.authority_id,
        "plan_digest": value.step_identity.plan_digest,
        "step_index": value.step_identity.step_index,
        "step_type": value.step_identity.step_type,
        "kind": kind.value, "resource_id": resource_id,
        "run_id": run_id, "node_id": node_id,
        "capability_digest": capability_digest,
        "state_generation": value.state_generation,
        "result_id": cleanup_result_id(result.argv, result.exit_code),
        "issued_at": _timestamp(value.issued_at),
        "expires_at": _timestamp(value.expires_at),
    }


def _snapshot_guarded_authority(value: GuardedAuthority) -> GuardedAuthority:
    try:
        result = CommandResult(
            tuple(value.result.argv), value.result.exit_code,
            value.result.stdout, value.result.stderr,
        )
        identity = CleanupStepIdentity(
            value.step_identity.plan_digest, value.step_identity.step_index,
            value.step_identity.step_type,
        )
        if type(value) is GuardedCommandResult:
            return GuardedCommandResult(
                result, value.kind, value.resource_id, value.run_id,
                value.node_id, value.action_digest, value.state_generation,
                value.issued_at, value.expires_at, value.authority_id, identity,
            )
        if type(value) is GuardedTerminalObservation:
            return GuardedTerminalObservation(
                _disposition_from_json(_disposition_json(value.disposition)),
                result, value.evidence_digest, value.state_generation,
                value.issued_at, value.expires_at, value.authority_id, identity,
            )
    except InvalidSchemaError:
        raise
    except Exception:
        pass
    raise invalid_policy("invalid_guarded_cleanup_results")


def _validated_authority_json(value: object) -> dict[str, object]:
    required = {
        "authority_id", "plan_digest", "step_index", "step_type",
        "kind", "resource_id", "run_id",
        "node_id", "capability_digest", "state_generation", "result_id",
        "issued_at", "expires_at",
    }
    if type(value) is not dict or set(value) != required:
        raise invalid_policy("invalid_execution_authority_issuance")
    try:
        ResourceKind(value["kind"])
        issued_at = _parse_timestamp(value["issued_at"])
        expires_at = _parse_timestamp(value["expires_at"])
    except Exception:
        raise invalid_policy("invalid_execution_authority_issuance") from None
    if (
        type(value["step_index"]) is not int or value["step_index"] < 0
        or type(value["step_type"]) is not str
        or value["step_type"] not in _VALID_CLEANUP_STEP_TYPES
        or not _valid_text(value["resource_id"], maximum=_MAX_RESOURCE_ID)
        or not all(_valid_text(value[key], maximum=_MAX_IDENTIFIER) for key in (
            "run_id", "node_id",
        ))
        or not all(
            type(value[key]) is str
            and re.fullmatch(r"sha256:[0-9a-f]{64}", value[key])
            for key in (
                "authority_id", "plan_digest", "capability_digest",
                "state_generation", "result_id",
            )
        )
        or expires_at <= issued_at
    ):
        raise invalid_policy("invalid_execution_authority_issuance")
    return dict(value)


def cleanup_action_digest(
    *, evidence_digest: str, resource_id: str, kind: ResourceKind,
    action: str, argv: Tuple[str, ...], requires_success_of: Optional[int],
    run_id: str, node_id: str, lifecycle: str, preconditions: Tuple[str, ...],
    environment: Mapping[str, str], predecessor_result_id: Optional[str],
) -> str:
    return cleanup_proof_digest({
        "evidence_digest": evidence_digest,
        "capability": {
            "resource_id": resource_id, "kind": ResourceKind(kind).value,
            "action": action, "argv": list(argv),
            "requires_success_of": requires_success_of,
            "owner": {"run_id": run_id, "node_id": node_id},
            "lifecycle": lifecycle, "preconditions": list(preconditions),
            "environment": dict(sorted(environment.items())),
            "predecessor_result_id": predecessor_result_id,
        },
    })


def build_cleanup_action(
    *, evidence: Mapping[str, object], resource_id: str, kind: ResourceKind,
    action: str, argv: Tuple[str, ...], requires_success_of: Optional[int],
    run_id: str, node_id: str, lifecycle: str, preconditions: Tuple[str, ...],
    environment: Optional[Mapping[str, str]] = None,
    predecessor_result_id: Optional[str] = None,
) -> CleanupAction:
    environment = {} if environment is None else dict(environment)
    evidence_digest = cleanup_proof_digest(dict(evidence))
    proof_digest = cleanup_action_digest(
        evidence_digest=evidence_digest, resource_id=resource_id, kind=kind,
        action=action, argv=argv, requires_success_of=requires_success_of,
        run_id=run_id, node_id=node_id, lifecycle=lifecycle,
        preconditions=preconditions, environment=environment,
        predecessor_result_id=predecessor_result_id,
    )
    return CleanupAction(
        resource_id, kind, action, argv, requires_success_of,
        run_id, node_id, lifecycle, proof_digest, preconditions,
        environment, predecessor_result_id, evidence_digest,
    )


def reseal_cleanup_action(
    value: CleanupAction, *, requires_success_of: Optional[int],
) -> CleanupAction:
    if type(value) is not CleanupAction:
        raise invalid_policy("invalid_cleanup_action")
    proof_digest = cleanup_action_digest(
        evidence_digest=value.evidence_digest, resource_id=value.resource_id,
        kind=value.kind, action=value.action, argv=value.argv,
        requires_success_of=requires_success_of, run_id=value.run_id,
        node_id=value.node_id, lifecycle=value.lifecycle,
        preconditions=value.preconditions, environment=value.environment,
        predecessor_result_id=value.predecessor_result_id,
    )
    return replace(value, requires_success_of=requires_success_of, proof_digest=proof_digest)


class _RegistryTransaction:
    """Pinned lock and journal descriptors for one registry transaction."""

    __slots__ = ("lock", "directory", "descriptor", "path")

    def __init__(
        self, lock: LockHandle, directory: PinnedDirectory,
        descriptor: int, path: Path,
    ):
        self.lock = lock
        self.directory = directory
        self.descriptor = descriptor
        self.path = path

    def revalidate(self) -> None:
        self.lock.revalidate()
        self.directory.revalidate()
        self.directory.require_identity(self.descriptor, self.path.name)

    def read(self) -> bytes:
        self.revalidate()
        size = os.fstat(self.descriptor).st_size
        chunks = []
        offset = 0
        while offset < size:
            chunk = os.pread(self.descriptor, min(65_536, size - offset), offset)
            if not chunk:
                raise OSError("resource registry read made no progress")
            chunks.append(chunk)
            offset += len(chunk)
        self.revalidate()
        return b"".join(chunks)

    def append(self, encoded: bytes) -> None:
        self.revalidate()
        pending = memoryview(encoded)
        while pending:
            written = os.write(self.descriptor, pending)
            if written <= 0:
                raise OSError("resource registry write made no progress")
            pending = pending[written:]
        os.fsync(self.descriptor)
        self.revalidate()
        self.directory.fsync()

    def repair_incomplete_tail(self) -> None:
        """Remove only a crash-torn final frame while holding the bound lock."""
        raw = self.read()
        if not raw or raw.endswith(b"\n"):
            return
        self.revalidate()
        os.ftruncate(self.descriptor, raw.rfind(b"\n") + 1)
        os.fsync(self.descriptor)
        self.revalidate()
        self.directory.fsync()


class ResourceRegistry:
    """Append-only kind+ID registry with immutable successful outcomes."""

    def __init__(
        self, path: Path | str, *, now: Optional[Callable[[], datetime]] = None,
        authority_ttl: timedelta = timedelta(minutes=1),
    ):
        if not isinstance(authority_ttl, timedelta) or authority_ttl.total_seconds() <= 0:
            raise invalid_policy("invalid_execution_authority_ttl")
        lexical = Path(path)
        lexical.parent.mkdir(parents=True, exist_ok=True)
        self._binding = bind_durable_path(lexical)
        self.path = self._binding.path
        self._lock_binding = bind_durable_path(self.path.with_name(self.path.name + ".lock"))
        self._records: dict[tuple[ResourceKind, str], ResourceRecord] = {}
        self._attempts: dict[tuple[ResourceKind, str], list[ResourceDisposition]] = {}
        self._transactions: set[str] = set()
        self._issued_authorities: dict[str, dict[str, object]] = {}
        self._consumed_authorities: set[str] = set()
        self._current_transaction: Optional[_RegistryTransaction] = None
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.authority_ttl = authority_ttl
        with self._exclusive_lock():
            self._reload_unlocked()

    @contextmanager
    def _exclusive_lock(self):
        handle = None
        directory = None
        descriptor = None
        primary = None
        try:
            self._binding.revalidate_parent()
            self._lock_binding.revalidate_parent()
            handle = LockHandle.acquire_bound(self._lock_binding)
            directory = self._binding.pin_parent()
            descriptor = directory.open_regular(
                self.path.name, os.O_APPEND | os.O_CREAT | os.O_RDWR,
            )
            transaction = _RegistryTransaction(handle, directory, descriptor, self.path)
            transaction.revalidate()
            self._current_transaction = transaction
            yield transaction
            transaction.revalidate()
        except InvalidSchemaError:
            primary = True
            raise
        except OSError:
            primary = True
            raise invalid_policy("resource_registry_path_or_lock_unsafe") from None
        finally:
            self._current_transaction = None
            cleanup_failed = False
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    cleanup_failed = True
            if directory is not None:
                try:
                    directory.close()
                except OSError:
                    cleanup_failed = True
            if handle is not None:
                try:
                    handle.release()
                except OSError:
                    cleanup_failed = True
            if primary is None and cleanup_failed:
                raise invalid_policy("resource_registry_transaction_close_failed") from None

    @contextmanager
    def _exclusive_key_locks(
        self, keys: Iterable[tuple[ResourceKind, str]],
    ):
        normalized = tuple(sorted(set(
            (ResourceKind(kind), resource_id) for kind, resource_id in keys
        ), key=lambda item: (item[0].value, item[1])))
        handles = []
        primary = None
        try:
            for kind, resource_id in normalized:
                if not _valid_text(resource_id, maximum=_MAX_RESOURCE_ID):
                    raise invalid_policy("invalid_resource_identity")
                digest = hashlib.sha256(
                    (kind.value + "\0" + resource_id).encode("utf-8")
                ).hexdigest()
                binding = bind_durable_path(self.path.with_name(
                    self.path.name + ".key-" + digest + ".lock"
                ))
                handles.append(LockHandle.acquire_bound(binding))
            yield
        except InvalidSchemaError:
            primary = True
            raise
        except OSError:
            primary = True
            raise invalid_policy("resource_execution_guard_busy") from None
        finally:
            cleanup_failed = False
            for handle in reversed(handles):
                try:
                    handle.release()
                except OSError:
                    cleanup_failed = True
            if primary is None and cleanup_failed:
                raise invalid_policy("resource_execution_guard_release_failed") from None

    def _reload_unlocked(self) -> None:
        self._records = {}
        self._attempts = {}
        self._transactions = set()
        self._issued_authorities = {}
        self._consumed_authorities = set()
        try:
            transaction = self._require_transaction()
            raw = transaction.read()
            complete_lines = raw.split(b"\n")
            if raw and not raw.endswith(b"\n"):
                complete_lines = complete_lines[:-1]
            for encoded_line in complete_lines:
                if not encoded_line:
                    continue
                event = json.loads(encoded_line.decode("utf-8"))
                self._apply_registry_event(event)
        except InvalidSchemaError:
            raise
        except Exception:
            raise invalid_policy("invalid_resource_registry") from None

    def _append_unlocked(self, event: Mapping[str, object]) -> None:
        self._append_events_unlocked((event,))

    def _append_events_unlocked(self, events: Sequence[Mapping[str, object]]) -> None:
        encoded = "".join(
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            for event in events
        )
        transaction = self._require_transaction()
        transaction.repair_incomplete_tail()
        transaction.append(encoded.encode("utf-8"))

    def _require_transaction(self) -> _RegistryTransaction:
        if self._current_transaction is None:
            raise invalid_policy("resource_registry_transaction_required")
        return self._current_transaction

    def _apply_registry_event(self, event: object, *, in_transaction: bool = False) -> None:
        if type(event) is not dict:
            raise invalid_policy("invalid_resource_registry_event")
        if set(event) == {"event", "resource"} and event["event"] == "registered":
            self._apply_registration(_record_from_json(event["resource"]), persist=False)
            return
        if set(event) == {"event", "disposition"} and event["event"] == "disposition":
            disposition = _disposition_from_json(event["disposition"])
            if disposition.disposition in TERMINAL_DISPOSITIONS and not in_transaction:
                raise invalid_policy("terminal_disposition_requires_cleanup_transaction")
            self._apply_disposition(disposition, persist=False)
            return
        if set(event) == {"event", "authority"} and event["event"] == "authority_issued":
            if in_transaction:
                raise invalid_policy("invalid_execution_authority_issuance")
            authority = _validated_authority_json(event["authority"])
            authority_id = authority["authority_id"]
            if authority_id in self._issued_authorities:
                raise invalid_policy("invalid_execution_authority_issuance")
            self._issued_authorities[authority_id] = authority
            return
        if set(event) == {"event", "authority_id"} and event["event"] == "authority_consumed":
            authority_id = event["authority_id"]
            if (
                not in_transaction or type(authority_id) is not str
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", authority_id)
                or authority_id not in self._issued_authorities
                or authority_id in self._consumed_authorities
            ):
                raise invalid_policy("invalid_execution_authority_consumption")
            self._consumed_authorities.add(authority_id)
            return
        if set(event) == {"event", "transaction_id", "events"} and event["event"] == "transaction":
            transaction_id = event["transaction_id"]
            nested = event["events"]
            if (
                type(transaction_id) is not str
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", transaction_id)
                or type(nested) is not list or not nested or transaction_id in self._transactions
            ):
                raise invalid_policy("invalid_resource_registry_transaction")
            saved_records = dict(self._records)
            saved_attempts = {key: list(values) for key, values in self._attempts.items()}
            saved_issued = dict(self._issued_authorities)
            saved_authorities = set(self._consumed_authorities)
            try:
                for item in nested:
                    if type(item) is not dict or item.get("event") == "transaction":
                        raise invalid_policy("invalid_resource_registry_transaction")
                    self._apply_registry_event(item, in_transaction=True)
            except Exception:
                self._records = saved_records
                self._attempts = saved_attempts
                self._issued_authorities = saved_issued
                self._consumed_authorities = saved_authorities
                raise
            self._transactions.add(transaction_id)
            return
        raise invalid_policy("invalid_resource_registry_event")

    def register(self, resource: ResourceRecord) -> None:
        if type(resource) is not ResourceRecord:
            raise invalid_policy("invalid_resource_record")
        resource = _record_from_json(_resource_json(resource))
        with self._exclusive_key_locks(((resource.kind, resource.resource_id),)):
            with self._exclusive_lock():
                self._reload_unlocked()
                self._apply_registration(resource, persist=True)

    def _apply_registration(self, resource: ResourceRecord, *, persist: bool) -> None:
        key = (resource.kind, resource.resource_id)
        existing = self._records.get(key)
        if existing is not None:
            if existing == resource:
                return
            raise invalid_policy("resource_registration_conflict")
        if persist:
            self._append_unlocked({"event": "registered", "resource": _resource_json(resource)})
        self._records[key] = resource

    def resources_for(self, scope: CleanupScope | str, node_id: Optional[str] = None) -> Tuple[ResourceRecord, ...]:
        with self._exclusive_lock():
            self._reload_unlocked()
            if isinstance(scope, CleanupScope):
                run_id, node_id = scope.run_id, scope.node_id
            else:
                run_id = scope
            values = (
                value for key, value in self._records.items()
                if value.run_id == run_id and (node_id is None or value.node_id == node_id)
                and not self._is_retired(key)
            )
            return tuple(sorted(
                values,
                key=lambda value: (value.created_at, value.kind.value, value.resource_id),
            ))

    def resource_state_for_exact(
        self, kind: ResourceKind, resource_id: str,
    ) -> Tuple[Optional[ResourceRecord], bool]:
        """Reload one global identity and return its record plus active state."""
        if type(kind) is not ResourceKind or not _valid_text(
            resource_id, maximum=_MAX_RESOURCE_ID,
        ):
            raise invalid_policy("invalid_resource_identity")
        with self._exclusive_lock():
            self._reload_unlocked()
            key = (kind, resource_id)
            record = self._records.get(key)
            return record, record is not None and not self._is_retired(key)

    def _state_generation_unlocked(
        self, key: tuple[ResourceKind, str],
    ) -> str:
        record = self._records.get(key)
        return cleanup_proof_digest({
            "record": None if record is None else _resource_json(record),
            "attempts": [
                _disposition_json(value) for value in self._attempts.get(key, ())
            ],
        })

    def _new_authority_id_unlocked(self) -> str:
        for _attempt in range(8):
            authority_id = "sha256:" + secrets.token_hex(32)
            if authority_id not in self._issued_authorities:
                return authority_id
        raise invalid_policy("execution_authority_id_exhausted")

    def _issue_authority_unlocked(self, value: GuardedAuthority) -> None:
        authority = _authority_json(value)
        frame = {"event": "authority_issued", "authority": authority}
        self._apply_registry_event(frame)
        self._append_unlocked(frame)

    def execute_guarded_action(
        self, adapter: object, plan: CleanupPlan, step_index: int,
        resource: object,
        executor: Callable[[Tuple[str, ...]], CommandResult],
        lease_proof: object = None, predecessor_result: object = None, *,
        incomplete_node_proof: object = None, orphan_mode: bool = False,
        authority_prefix: object = None,
    ) -> GuardedCommandResult:
        """Execute the exact command step sealed into one immutable plan."""
        from workflow_kernel.adapters.docker import DockerAdapter

        if (
            type(adapter) is not DockerAdapter
            or type(step_index) is not int or not callable(executor)
        ):
            raise invalid_policy("invalid_guarded_cleanup_execution")
        plan, steps = _cleanup_step_entries(plan)
        if (
            step_index < 0 or step_index >= len(steps)
            or steps[step_index][0].step_type != "command_action"
        ):
            raise invalid_policy("invalid_guarded_cleanup_step")
        step_identity, action = steps[step_index]
        if type(action) is not CleanupAction:
            raise invalid_policy("invalid_guarded_cleanup_step")
        key = (action.kind, action.resource_id)
        with self._exclusive_key_locks((key,)):
            if authority_prefix is not None:
                with self._exclusive_lock():
                    self._reload_unlocked()
                    validated_prefix = self._validate_authority_prefix_unlocked(
                        plan, authority_prefix,
                    )
                if len(validated_prefix) != step_index:
                    raise invalid_policy("guarded_cleanup_authority_conflict")
                predecessor_index = action.requires_success_of
                if predecessor_index is None:
                    if validated_prefix:
                        predecessor_result = None
                else:
                    predecessor = validated_prefix[predecessor_index]
                    if type(predecessor) is not GuardedCommandResult:
                        raise invalid_policy("guarded_cleanup_authority_conflict")
                    predecessor_result = predecessor.result
            adapter.revalidate_action(
                action, resource, lease_proof=lease_proof,
                predecessor_result=predecessor_result,
                action_index=step_index, registry=self,
                incomplete_node_proof=incomplete_node_proof,
                orphan_mode=orphan_mode,
            )
            with self._exclusive_lock():
                self._reload_unlocked()
                generation = self._state_generation_unlocked(key)
            result = executor(action.argv)
            if type(result) is not CommandResult:
                raise invalid_policy("invalid_guarded_cleanup_result")
            result = CommandResult(
                tuple(result.argv), result.exit_code, result.stdout, result.stderr,
            )
            if result.argv != action.argv:
                raise invalid_policy("guarded_cleanup_argv_changed")
            issued_at = self._now()
            if not _valid_timestamp(issued_at):
                raise invalid_policy("resource_registry_clock_invalid")
            expires_at = issued_at + self.authority_ttl
            with self._exclusive_lock():
                self._reload_unlocked()
                if generation != self._state_generation_unlocked(key):
                    raise invalid_policy("guarded_cleanup_authority_changed")
                guarded = GuardedCommandResult(
                    result, action.kind, action.resource_id, action.run_id,
                    action.node_id, action.proof_digest, generation, issued_at,
                    expires_at, self._new_authority_id_unlocked(), step_identity,
                )
                self._issue_authority_unlocked(guarded)
            return guarded

    def observe_guarded_absence(
        self, adapter: object, plan: CleanupPlan, step_index: int,
        executor: Callable[[Tuple[str, ...]], CommandResult],
        *, authority_prefix: object = None,
    ) -> GuardedTerminalObservation:
        """Issue one exact-ID absence observation while its resource key is locked."""
        from workflow_kernel.adapters.docker import (
            DockerAdapter, _inspect_argv, _is_exact_not_found,
        )

        if (
            type(adapter) is not DockerAdapter
            or type(step_index) is not int or not callable(executor)
        ):
            raise invalid_policy("invalid_guarded_terminal_observation")
        plan, steps = _cleanup_step_entries(plan)
        if (
            step_index < 0 or step_index >= len(steps)
            or steps[step_index][0].step_type != "terminal_observation"
        ):
            raise invalid_policy("invalid_guarded_cleanup_step")
        step_identity, disposition = steps[step_index]
        if (
            type(disposition) is not ResourceDisposition
            or disposition.disposition is not CleanupDisposition.MISSING
            or disposition.kind not in {
                ResourceKind.CONTAINER, ResourceKind.NETWORK, ResourceKind.VOLUME,
            }
        ):
            raise invalid_policy("invalid_guarded_terminal_observation")
        disposition = _disposition_from_json(_disposition_json(disposition))
        key = (disposition.kind, disposition.resource_id)
        with self._exclusive_key_locks((key,)):
            with self._exclusive_lock():
                self._reload_unlocked()
                if authority_prefix is not None:
                    validated_prefix = self._validate_authority_prefix_unlocked(
                        plan, authority_prefix,
                    )
                    if len(validated_prefix) != step_index:
                        raise invalid_policy("guarded_cleanup_authority_conflict")
                record = self._records.get(key)
                if (
                    record is None or self._is_retired(key)
                    or (record.run_id, record.node_id, record.lifecycle)
                    != (disposition.run_id, disposition.node_id, disposition.lifecycle)
                ):
                    raise invalid_policy("guarded_terminal_observation_changed")
                generation = self._state_generation_unlocked(key)
            argv = _inspect_argv(disposition.kind, disposition.resource_id)
            result = executor(argv)
            if type(result) is not CommandResult:
                raise invalid_policy("invalid_guarded_terminal_observation_result")
            result = CommandResult(
                tuple(result.argv), result.exit_code, result.stdout, result.stderr,
            )
            if not _is_exact_not_found(
                disposition.kind, disposition.resource_id, result,
            ):
                raise invalid_policy("guarded_terminal_observation_not_absent")
            issued_at = self._now()
            if not _valid_timestamp(issued_at):
                raise invalid_policy("resource_registry_clock_invalid")
            expires_at = issued_at + self.authority_ttl
            evidence_digest = terminal_observation_evidence_digest(
                disposition, result,
            )
            with self._exclusive_lock():
                self._reload_unlocked()
                if generation != self._state_generation_unlocked(key):
                    raise invalid_policy("guarded_terminal_observation_changed")
                guarded = GuardedTerminalObservation(
                    disposition, result, evidence_digest, generation,
                    issued_at, expires_at, self._new_authority_id_unlocked(),
                    step_identity,
                )
                self._issue_authority_unlocked(guarded)
            return guarded

    def record_disposition(self, value: ResourceDisposition) -> ResourceDisposition:
        if type(value) is not ResourceDisposition:
            raise invalid_policy("invalid_resource_disposition")
        if value.disposition in TERMINAL_DISPOSITIONS:
            raise invalid_policy("terminal_disposition_requires_cleanup_receipt")
        value = _disposition_from_json(_disposition_json(value))
        with self._exclusive_key_locks(((value.kind, value.resource_id),)):
            with self._exclusive_lock():
                self._reload_unlocked()
                return self._apply_disposition(value, persist=True)

    def record_receipt(self, receipt: CleanupReceipt) -> Tuple[ResourceDisposition, ...]:
        """Detached receipts are evidence only and never authorize persistence."""
        raise invalid_policy("cleanup_receipt_not_authoritative")

    def record_results(
        self, adapter: object, plan: CleanupPlan, results: Tuple[CommandResult, ...],
        before: object, after: object,
    ) -> CleanupReceipt:
        """Reject result persistence without guarded execution authority."""
        raise invalid_policy("guarded_cleanup_authority_required")

    def record_guarded_results(
        self, adapter: object, plan: CleanupPlan,
        guarded_results: Tuple[GuardedAuthority, ...],
        before: object, after: object,
    ) -> CleanupReceipt:
        """Persist results only with fresh, generation-bound execution authority."""
        if not guarded_results or type(guarded_results) is not tuple or any(
            type(value) not in {GuardedCommandResult, GuardedTerminalObservation}
            for value in guarded_results
        ):
            raise invalid_policy("invalid_guarded_cleanup_results")
        guarded_results = tuple(
            _snapshot_guarded_authority(value) for value in guarded_results
        )
        return self._record_results(
            adapter, plan, tuple(
                value.result for value in guarded_results
                if type(value) is GuardedCommandResult
            ),
            before, after, guarded_results,
        )

    def validate_authority_prefix(
        self, plan: CleanupPlan, authorities: Tuple[GuardedAuthority, ...],
    ) -> Tuple[GuardedAuthority, ...]:
        """Resolve a gap-free, live prefix against registry-issued authority."""
        if type(plan) is not CleanupPlan or type(authorities) is not tuple:
            raise invalid_policy("guarded_cleanup_authority_conflict")
        with self._exclusive_lock():
            self._reload_unlocked()
            return self._validate_authority_prefix_unlocked(plan, authorities)

    def _validate_authority_prefix_unlocked(
        self, plan: CleanupPlan, authorities: object,
    ) -> Tuple[GuardedAuthority, ...]:
        if type(authorities) is not tuple or any(
            type(value) not in {GuardedCommandResult, GuardedTerminalObservation}
            for value in authorities
        ):
            raise invalid_policy("guarded_cleanup_authority_conflict")
        normalized = tuple(_snapshot_guarded_authority(value) for value in authorities)
        identities = cleanup_step_identities(plan)
        if (
            len(normalized) > len(identities)
            or tuple(value.step_identity for value in normalized)
            != identities[:len(normalized)]
            or len({value.authority_id for value in normalized}) != len(normalized)
        ):
            raise invalid_policy("guarded_cleanup_authority_conflict")
        try:
            self._validate_execution_authorities(
                plan,
                tuple(value.result for value in normalized
                      if type(value) is GuardedCommandResult),
                normalized,
            )
        except InvalidSchemaError:
            raise invalid_policy("guarded_cleanup_authority_conflict") from None
        return normalized

    def _record_results(
        self, adapter: object, plan: CleanupPlan, results: Tuple[CommandResult, ...],
        before: object, after: object,
        authorities: Tuple[GuardedAuthority, ...],
    ) -> CleanupReceipt:
        from workflow_kernel.adapters.docker import DockerAdapter

        if type(adapter) is not DockerAdapter or type(plan) is not CleanupPlan:
            raise invalid_policy("invalid_cleanup_result_adapter")
        plan, step_entries = _cleanup_step_entries(plan)
        if len({value.authority_id for value in authorities}) != len(authorities):
            raise invalid_policy("guarded_cleanup_authority_bijection_failed")
        keys = tuple(
            (value.kind, value.resource_id)
            for value in plan.actions + plan.dispositions
        )
        with self._exclusive_key_locks(keys):
            receipt, observed = adapter._reconcile_results(
                plan, results, before, after,
            )
            terminal_receipt_keys = {
                (value.kind, value.resource_id)
                for value in receipt.dispositions
                if value.disposition is CleanupDisposition.MISSING
            }
            if terminal_receipt_keys and len(results) != len(plan.actions):
                raise invalid_policy("guarded_cleanup_authority_step_gap")
            expected_step_identities = tuple(
                identity for identity, value in step_entries
                if (
                    identity.step_type == "command_action"
                    and identity.step_index < len(results)
                ) or (
                    identity.step_type == "terminal_observation"
                    and type(value) is ResourceDisposition
                    and (value.kind, value.resource_id) in terminal_receipt_keys
                )
            )
            if tuple(
                value.step_index for value in expected_step_identities
            ) != tuple(range(len(expected_step_identities))):
                raise invalid_policy("guarded_cleanup_authority_step_gap")
            supplied_step_identities = tuple(
                value.step_identity for value in authorities
            )
            if (
                supplied_step_identities != expected_step_identities
            ):
                raise invalid_policy("guarded_cleanup_authority_bijection_failed")
            transaction_id = adapter._result_transaction_id(
                plan, results, before, after,
            )
            if authorities:
                transaction_id = cleanup_proof_digest({
                    "result_transaction_id": transaction_id,
                    "authority_ids": [value.authority_id for value in authorities],
                })
            with self._exclusive_lock():
                self._reload_unlocked()
                if transaction_id in self._transactions:
                    raise invalid_policy("cleanup_result_transaction_already_recorded")
                if authorities:
                    self._validate_execution_authorities(
                        plan, results, authorities,
                    )
                nested = [
                    {"event": "authority_consumed", "authority_id": value.authority_id}
                    for value in authorities
                ]
                for resource in observed:
                    key = (resource.kind, resource.resource_id)
                    if key not in self._records:
                        nested.append({"event": "registered", "resource": _resource_json(resource)})
                nested.extend(
                    {"event": "disposition", "disposition": _disposition_json(value)}
                    for value in receipt.dispositions
                )
                if not nested:
                    raise invalid_policy("empty_cleanup_result_transaction")
                frame = {
                    "event": "transaction", "transaction_id": transaction_id,
                    "events": nested,
                }
                self._apply_registry_event(frame)
                self._append_unlocked(frame)
            return receipt

    def _validate_execution_authorities(
        self, plan: CleanupPlan, results: Tuple[CommandResult, ...],
        authorities: Tuple[GuardedAuthority, ...],
    ) -> None:
        command_authorities = tuple(
            value for value in authorities if type(value) is GuardedCommandResult
        )
        if len(command_authorities) != len(results):
            raise invalid_policy("guarded_cleanup_authority_missing")
        by_argv = {value.argv: value for value in plan.actions}
        current = self._now()
        if not _valid_timestamp(current):
            raise invalid_policy("resource_registry_clock_invalid")
        for authority in authorities:
            payload = _authority_json(authority)
            key = (ResourceKind(payload["kind"]), payload["resource_id"])
            if (
                self._issued_authorities.get(authority.authority_id) != payload
                or authority.authority_id in self._consumed_authorities
                or not authority.issued_at <= current <= authority.expires_at
                or authority.state_generation != self._state_generation_unlocked(key)
            ):
                raise invalid_policy("guarded_cleanup_authority_changed")
        for result, authority in zip(results, command_authorities):
            action = by_argv.get(result.argv)
            key = (authority.kind, authority.resource_id)
            if (
                action is None or authority.result != result
                or authority.action_digest != action.proof_digest
                or key != (action.kind, action.resource_id)
                or (authority.run_id, authority.node_id)
                != (action.run_id, action.node_id)
            ):
                raise invalid_policy("guarded_cleanup_authority_changed")
        from workflow_kernel.adapters.docker import _is_exact_not_found
        for authority in authorities:
            if type(authority) is not GuardedTerminalObservation:
                continue
            disposition = authority.disposition
            if (
                disposition not in plan.dispositions
                or disposition.disposition is not CleanupDisposition.MISSING
                or authority.evidence_digest != terminal_observation_evidence_digest(
                    disposition, authority.result,
                )
                or not _is_exact_not_found(
                    disposition.kind, disposition.resource_id, authority.result,
                )
            ):
                raise invalid_policy("guarded_cleanup_authority_changed")

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
            self._append_unlocked({"event": "disposition", "disposition": _disposition_json(sanitized)})
        self._attempts.setdefault(key, []).append(sanitized)
        return sanitized

    def disposition_for(self, kind: ResourceKind, resource_id: str) -> Optional[ResourceDisposition]:
        with self._exclusive_lock():
            self._reload_unlocked()
            history = self._attempts.get((ResourceKind(kind), resource_id), ())
            return history[-1] if history else None

    def disposition_history(self, kind: ResourceKind, resource_id: str) -> Tuple[ResourceDisposition, ...]:
        with self._exclusive_lock():
            self._reload_unlocked()
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
        *, incomplete_node_proof: Optional[IncompleteNodeProof] = None,
    ) -> CleanupPlan:
        if not all((validated, reviewed, evidence_captured, merge_disposed)):
            raise invalid_policy("chunk_cleanup_before_boundary_complete")
        return self.docker_adapter.plan_chunk_cleanup(
            registry, inventory, run_id, node_id,
            incomplete_node_proof=incomplete_node_proof,
        )

    def at_terminal(
        self, registry: ResourceRegistry, inventory: object, run_id: str, status: RunStatus,
        *, incomplete_node_proof: Optional[IncompleteNodeProof] = None,
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
            registry, inventory, run_id,
            incomplete_node_proof=incomplete_node_proof, terminal=True,
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
    required = {
        "resource_id", "kind", "run_id", "node_id", "lifecycle", "cleanup_policy",
        "created_at", "dependent_node_ids", "labels",
    }
    if type(value) is not dict or set(value) != required:
        raise invalid_policy("invalid_resource_registry_resource")
    if type(value["dependent_node_ids"]) is not list or type(value["labels"]) is not dict:
        raise invalid_policy("invalid_resource_registry_resource")
    return ResourceRecord(
        resource_id=value["resource_id"], kind=ResourceKind(value["kind"]),
        run_id=value["run_id"], node_id=value["node_id"],
        lifecycle=value["lifecycle"], cleanup_policy=value["cleanup_policy"],
        created_at=_parse_timestamp(value["created_at"]),
        dependent_node_ids=tuple(value["dependent_node_ids"]), labels=dict(value["labels"]),
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
    required = {
        "resource_id", "kind", "run_id", "node_id", "lifecycle", "disposition",
        "action", "reason", "command", "evidence",
    }
    if type(value) is not dict or set(value) not in (required, required | {"follow_up"}):
        raise invalid_policy("invalid_resource_registry_disposition")
    if type(value["command"]) is not list or type(value["evidence"]) is not list:
        raise invalid_policy("invalid_resource_registry_disposition")
    return ResourceDisposition(
        resource_id=value["resource_id"], kind=ResourceKind(value["kind"]),
        run_id=value["run_id"], node_id=value["node_id"], lifecycle=value["lifecycle"],
        disposition=CleanupDisposition(value["disposition"]), action=value["action"],
        reason=value["reason"], evidence=tuple(value["evidence"]),
        command=tuple(value["command"]), follow_up=value.get("follow_up"),
    )


def _raw_receipt_disposition(value: ResourceDisposition) -> dict[str, object]:
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
        reason=_sanitize_receipt_value(value.reason),
        evidence=tuple(
            _sanitize_receipt_value(item)
            for item in value.evidence[:_MAX_RECEIPT_ITEMS]
        ),
        command=tuple(
            _sanitize_receipt_value(item)
            for item in value.command[:_MAX_RECEIPT_ITEMS]
        ),
        follow_up=(
            None if value.follow_up is None
            else _sanitize_receipt_value(value.follow_up)
        ),
    )


def _sanitize_receipt_value(value: object) -> object:
    try:
        return sanitize_durable_payload(
            value,
            public_string_length=_MAX_RECEIPT_STRING,
            max_depth=_MAX_RECEIPT_DEPTH,
            max_items=_MAX_RECEIPT_ITEMS * _MAX_RECEIPT_ITEMS,
        )
    except Exception:
        return digest_error_detail_string("unsafe-receipt-value")
