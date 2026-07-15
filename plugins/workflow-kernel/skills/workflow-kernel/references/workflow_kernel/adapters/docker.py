"""Label-first Docker creation and pure, positive-ownership cleanup planning."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol, Sequence, Tuple

from workflow_kernel.adapters.base import invalid_policy
from workflow_kernel.resources import (
    VALID_CLEANUP_POLICIES, VALID_LIFECYCLES,
    CleanupAction, CleanupDisposition, CleanupPlan, CleanupReceipt, CleanupScope,
    CommandResult, CreationReceipt, ResourceDisposition, ResourceKind, ResourceRecord,
    ResourceRegistrationIntent, ResourceRegistry, build_cleanup_action,
    cleanup_proof_digest, cleanup_result_id, disposition_for,
    reseal_cleanup_action,
)
from workflow_kernel.schema import NodeStatus


LABEL_PREFIX = "com.designmachines.depot."
MANAGED_LABEL = LABEL_PREFIX + "managed"
RUN_LABEL = LABEL_PREFIX + "run-id"
NODE_LABEL = LABEL_PREFIX + "node-id"
CREATED_LABEL = LABEL_PREFIX + "created-at"
LIFECYCLE_LABEL = LABEL_PREFIX + "lifecycle"
POLICY_LABEL = LABEL_PREFIX + "cleanup-policy"
REQUIRED_LABELS = (MANAGED_LABEL, RUN_LABEL, NODE_LABEL, CREATED_LABEL, LIFECYCLE_LABEL, POLICY_LABEL)
KIND_ORDER = {ResourceKind.CONTAINER: 0, ResourceKind.NETWORK: 1, ResourceKind.VOLUME: 2}
COMPOSE_MATCH_LABEL = {
    ResourceKind.CONTAINER: "com.docker.compose.service",
    ResourceKind.NETWORK: "com.docker.compose.network",
    ResourceKind.VOLUME: "com.docker.compose.volume",
}
_CREATE_VALUE_OPTIONS = {
    ResourceKind.NETWORK: frozenset({
        "--aux-address", "--config-from", "--driver", "-d", "--gateway",
        "--ip-range", "--ipam-driver", "--ipam-opt", "--label", "--opt",
        "-o", "--scope", "--subnet",
    }),
    ResourceKind.VOLUME: frozenset({
        "--availability", "--driver", "-d", "--group", "--label",
        "--limit-bytes", "--opt", "-o", "--required-bytes", "--scope",
        "--sharing",
    }),
}
_CREATE_FLAG_OPTIONS = {
    ResourceKind.NETWORK: frozenset({
        "--attachable", "--config-only", "--ingress", "--internal",
        "--ipv4", "--ipv6",
    }),
    ResourceKind.VOLUME: frozenset(),
}


def _normalized_docker_text(value: object, maximum: int) -> bool:
    return (
        type(value) is str and bool(value) and value == value.strip()
        and len(value) <= maximum
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


class CommandRunner(Protocol):
    def run(self, argv: Tuple[str, ...]) -> CommandResult: ...


@dataclass(frozen=True)
class LeaseProof:
    run_id: str
    active: bool
    readable: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        if not _valid_lease_proof(self):
            raise invalid_policy("invalid_lease_proof")


def _valid_lease_proof(proof: object) -> bool:
    return (
        type(proof) is LeaseProof
        and _normalized_docker_text(proof.run_id, 256)
        and type(proof.active) is bool and type(proof.readable) is bool
        and type(proof.observed_at) is datetime
        and proof.observed_at.tzinfo is not None and proof.observed_at.utcoffset() is not None
    )


class LeaseReader(Protocol):
    def read(self, run_id: str) -> Optional[LeaseProof]: ...


TERMINAL_NODE_STATUSES = frozenset({
    NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.BLOCKED,
    NodeStatus.SKIPPED,
})


@dataclass(frozen=True)
class IncompleteNodeProof:
    """Authoritative status snapshot used to retain every nonterminal dependent."""

    run_id: str
    node_statuses: Tuple[Tuple[str, NodeStatus], ...]
    readable: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        if not _valid_incomplete_node_proof(self):
            raise invalid_policy("invalid_incomplete_node_proof")

    @property
    def incomplete_node_ids(self) -> Tuple[str, ...]:
        return tuple(
            node_id for node_id, status in self.node_statuses
            if status not in TERMINAL_NODE_STATUSES
        )


def _valid_incomplete_node_proof(proof: object) -> bool:
    if (
        type(proof) is not IncompleteNodeProof
        or not _normalized_docker_text(proof.run_id, 256)
        or type(proof.node_statuses) is not tuple
        or type(proof.readable) is not bool
        or type(proof.observed_at) is not datetime
        or proof.observed_at.tzinfo is None
        or proof.observed_at.utcoffset() is None
    ):
        return False
    seen = set()
    for row in proof.node_statuses:
        if type(row) is not tuple or len(row) != 2:
            return False
        node_id, status = row
        if (
            not _normalized_docker_text(node_id, 256)
            or type(status) is not NodeStatus or node_id in seen
        ):
            return False
        seen.add(node_id)
    return True


def _snapshot_incomplete_node_proof(proof: object) -> IncompleteNodeProof:
    if type(proof) is not IncompleteNodeProof:
        raise invalid_policy("invalid_incomplete_node_proof")
    try:
        rows = proof.node_statuses
        snapshot = IncompleteNodeProof(
            proof.run_id,
            tuple((row[0], row[1]) for row in rows),
            proof.readable,
            proof.observed_at,
        )
    except Exception:
        raise invalid_policy("invalid_incomplete_node_proof") from None
    return snapshot


@dataclass(frozen=True)
class DockerResource:
    resource_id: str
    kind: ResourceKind
    labels: Mapping[str, str]
    created_at: datetime
    running: bool = False
    in_use: bool = False
    system: bool = False
    inspect_ok: bool = True
    name: Optional[str] = None
    use_known: bool = True

    def __post_init__(self) -> None:
        try:
            kind = ResourceKind(self.kind)
            if type(self.labels) is not dict:
                raise TypeError
            labels = dict(self.labels)
        except Exception:
            raise invalid_policy("invalid_docker_resource") from None
        if (
            not _normalized_docker_text(self.resource_id, 4096)
            or kind not in KIND_ORDER
            or any(
                not _normalized_docker_text(key, 256)
                or type(value) is not str or len(value) > 4096
                or any(ord(character) < 32 or ord(character) == 127 for character in value)
                for key, value in labels.items()
            )
            or type(self.created_at) is not datetime
            or self.created_at.tzinfo is None or self.created_at.utcoffset() is None
            or not all(type(value) is bool for value in (
                self.running, self.in_use, self.system, self.inspect_ok, self.use_known,
            ))
            or (self.name is not None and not _normalized_docker_text(self.name, 4096))
        ):
            raise invalid_policy("invalid_docker_resource")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "labels", labels)


@dataclass(frozen=True)
class DockerInventory:
    resources: Tuple[DockerResource, ...]
    queried: Tuple[Tuple[ResourceKind, str], ...] = ()
    absent: Tuple[Tuple[ResourceKind, str], ...] = ()
    source: str = "provided"
    evidence: Tuple[CommandResult, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.resources) is not tuple or type(self.queried) is not tuple
            or type(self.absent) is not tuple or type(self.evidence) is not tuple
        ):
            raise invalid_policy("invalid_docker_inventory")
        resources = self.resources
        keys = [(value.kind, value.resource_id) for value in resources if type(value) is DockerResource]
        try:
            queried = tuple((ResourceKind(kind), resource_id) for kind, resource_id in self.queried)
            absent = tuple((ResourceKind(kind), resource_id) for kind, resource_id in self.absent)
        except Exception:
            raise invalid_policy("invalid_docker_inventory") from None
        if (
            len(keys) != len(resources) or len(set(keys)) != len(keys)
            or any(type(value) is not tuple or len(value) != 2 for value in self.queried + self.absent)
            or len(set(queried)) != len(queried) or len(set(absent)) != len(absent)
            or not set(absent).issubset(set(queried)) or set(keys) & set(absent)
            or self.source not in {"provided", "registered_exact", "managed_orphan_sweep"}
            or any(type(value) is not CommandResult for value in self.evidence)
            or len({value.argv for value in self.evidence}) != len(self.evidence)
        ):
            raise invalid_policy("invalid_docker_inventory")
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "queried", queried)
        object.__setattr__(self, "absent", absent)
        object.__setattr__(self, "evidence", self.evidence)


@dataclass(frozen=True)
class DockerCreationPlan:
    argv: Tuple[str, ...]
    labels: Mapping[str, str]
    lifecycle: str
    registration_intents: Tuple[ResourceRegistrationIntent, ...]
    compose_override: Optional[Path] = None
    compose_override_content: Optional[str] = None
    project_name: Optional[str] = None
    environment: Optional[Mapping[str, str]] = None
    managed: bool = True
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        try:
            argv = tuple(self.argv)
            labels = dict(self.labels)
            intents = tuple(self.registration_intents)
            environment = None if self.environment is None else dict(self.environment)
        except Exception:
            raise invalid_policy("invalid_docker_creation_plan") from None
        if (
            not argv or any(not _normalized_docker_text(value, 4096) for value in argv)
            or any(not _normalized_docker_text(key, 256) or type(value) is not str for key, value in labels.items())
            or self.lifecycle not in VALID_LIFECYCLES
            or any(type(value) is not ResourceRegistrationIntent for value in intents)
            or (self.compose_override is not None and not isinstance(self.compose_override, Path))
            or (self.compose_override_content is not None and type(self.compose_override_content) is not str)
            or (self.project_name is not None and not _normalized_docker_text(self.project_name, 256))
            or (environment is not None and any(
                not _normalized_docker_text(key, 256) or type(value) is not str
                for key, value in environment.items()
            ))
            or type(self.managed) is not bool
            or (self.reason is not None and not _normalized_docker_text(self.reason, 4096))
        ):
            raise invalid_policy("invalid_docker_creation_plan")
        object.__setattr__(self, "argv", argv)
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "registration_intents", intents)
        object.__setattr__(self, "environment", environment)


class DockerAdapter:
    def __init__(
        self, runner: CommandRunner, *, now: Optional[Callable[[], datetime]] = None,
        lease_reader: Optional[LeaseReader] = None,
        lease_max_age: timedelta = timedelta(minutes=1),
        incomplete_node_max_age: timedelta = timedelta(minutes=1),
        creation_time_skew: timedelta = timedelta(minutes=5),
        stop_timeout_seconds: int = 10,
    ):
        if type(stop_timeout_seconds) is not int or not 1 <= stop_timeout_seconds <= 60:
            raise invalid_policy("invalid_docker_stop_timeout")
        if (
            lease_max_age.total_seconds() < 0
            or incomplete_node_max_age.total_seconds() < 0
            or creation_time_skew.total_seconds() < 0
        ):
            raise invalid_policy("invalid_docker_proof_window")
        self.runner = runner
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.lease_reader = lease_reader
        self.lease_max_age = lease_max_age
        self.incomplete_node_max_age = incomplete_node_max_age
        self.creation_time_skew = creation_time_skew
        self.stop_timeout_seconds = stop_timeout_seconds

    def labels_for(self, run_id: str, node_id: str, lifecycle: str, cleanup_policy: str) -> dict[str, str]:
        if not all(type(value) is str and value for value in (run_id, node_id)):
            raise invalid_policy("invalid_docker_owner")
        if lifecycle not in VALID_LIFECYCLES:
            raise invalid_policy("invalid_resource_lifecycle")
        if cleanup_policy not in VALID_CLEANUP_POLICIES:
            raise invalid_policy("invalid_cleanup_policy")
        created = self.now()
        if not isinstance(created, datetime) or created.tzinfo is None:
            raise invalid_policy("docker_clock_requires_timezone")
        return {
            MANAGED_LABEL: "true", RUN_LABEL: run_id, NODE_LABEL: node_id,
            CREATED_LABEL: _timestamp(created), LIFECYCLE_LABEL: lifecycle,
            POLICY_LABEL: cleanup_policy,
        }

    def plan_create(
        self, argv: Sequence[str], run_id: str, node_id: str, lifecycle: str,
        cleanup_policy: str, *, dependent_node_ids: Sequence[str] = (),
    ) -> DockerCreationPlan:
        command = tuple(argv)
        forms = {
            ("docker", "run"): (2, ResourceKind.CONTAINER),
            ("docker", "container", "create"): (3, ResourceKind.CONTAINER),
            ("docker", "network", "create"): (3, ResourceKind.NETWORK),
            ("docker", "volume", "create"): (3, ResourceKind.VOLUME),
        }
        match = next(((prefix, value) for prefix, value in forms.items() if command[:len(prefix)] == prefix), None)
        if match is None:
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="unsupported_docker_create_form")
        _, (insert_at, kind) = match
        if len(command) <= insert_at:
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="ambiguous_docker_create_form")
        labels = self.labels_for(run_id, node_id, lifecycle, cleanup_policy)
        label_argv = tuple(part for key in REQUIRED_LABELS for part in ("--label", key + "=" + labels[key]))
        planned = command[:insert_at] + label_argv + command[insert_at:]
        expected_name = (
            _explicit_name(command)
            if kind is ResourceKind.CONTAINER else
            _create_resource_name(command, insert_at, kind)
        )
        if kind is not ResourceKind.CONTAINER and expected_name is None:
            return DockerCreationPlan(
                command, {}, lifecycle, (), managed=False,
                reason="ambiguous_docker_create_form",
            )
        intent = ResourceRegistrationIntent(
            kind, expected_name, run_id, node_id, lifecycle, cleanup_policy,
            labels, tuple(dependent_node_ids),
        )
        return DockerCreationPlan(planned, labels, lifecycle, (intent,))

    def plan_compose(
        self, argv: Sequence[str], run_id: str, node_id: str, lifecycle: str,
        cleanup_policy: str, *, dependent_node_ids: Sequence[str] = (),
    ) -> DockerCreationPlan:
        command = tuple(argv)
        if command[:2] != ("docker", "compose"):
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="unsupported_compose_form")
        action_index = next((index for index, value in enumerate(command[2:], 2) if value in {"up", "create", "run", "start"}), None)
        if action_index is None:
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="unsupported_compose_form")
        compose_files = []
        index = 2
        while index < action_index:
            value = command[index]
            if (
                value in {"-p", "--project-name"}
                or (value.startswith("-p") and not value.startswith("--") and len(value) > 2)
                or value.startswith("--project-name=")
            ):
                return DockerCreationPlan(
                    command, {}, lifecycle, (), managed=False,
                    reason="caller_project_name_forbidden",
                )
            if value in {"-f", "--file"}:
                if index + 1 >= action_index or not _normalized_docker_text(command[index + 1], 4096):
                    return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_file_invalid")
                compose_files.append(command[index + 1])
                index += 2
                continue
            if (
                (value.startswith("-f") and not value.startswith("--") and len(value) > 2)
                or value.startswith("--file=")
            ):
                compose_file = (
                    value[2:].removeprefix("=")
                    if not value.startswith("--") else value.split("=", 1)[1]
                )
                if not _normalized_docker_text(compose_file, 4096):
                    return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_file_invalid")
                compose_files.append(compose_file)
            index += 1
        if not compose_files:
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_file_required")
        inspected = self.runner.run(command[:action_index] + ("config", "--format", "json"))
        if inspected.exit_code != 0:
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_config_failed")
        try:
            config = json.loads(inspected.stdout)
            services = config.get("services", {})
            networks = config.get("networks", {})
            volumes = config.get("volumes", {})
            if not isinstance(services, dict) or not services or not isinstance(networks, dict) or not isinstance(volumes, dict):
                raise ValueError
        except Exception:
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_config_invalid")
        if any(isinstance(value, dict) and value.get("external") for collection in (networks, volumes) for value in collection.values()):
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_external_resource")
        if _has_anonymous_volume(services):
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_anonymous_volume")
        labels = self.labels_for(run_id, node_id, lifecycle, cleanup_policy)
        project = _project_name(run_id, node_id)
        override_networks = {name: {"labels": labels} for name in networks}
        override_networks.setdefault("default", {"labels": labels})
        override = {
            "services": {name: {"labels": labels} for name in services},
            "networks": override_networks,
            "volumes": {name: {"labels": labels} for name in volumes},
        }
        dependencies = tuple(dependent_node_ids)
        intents = [
            ResourceRegistrationIntent(ResourceKind.CONTAINER, name, run_id, node_id, lifecycle, cleanup_policy, labels, dependencies)
            for name in services
        ]
        intents.extend(
            ResourceRegistrationIntent(ResourceKind.NETWORK, name, run_id, node_id, lifecycle, cleanup_policy, labels, dependencies)
            for name in override_networks
        )
        intents.extend(
            ResourceRegistrationIntent(ResourceKind.VOLUME, name, run_id, node_id, lifecycle, cleanup_policy, labels, dependencies)
            for name in volumes
        )
        override_path = Path(".workflow-kernel") / "docker-overrides" / (project + ".json")
        planned = (
            command[:2] + ("--project-name", project) + command[2:action_index]
            + ("-f", str(override_path)) + command[action_index:]
        )
        return DockerCreationPlan(
            planned, labels, lifecycle, tuple(intents), override_path,
            json.dumps(override, sort_keys=True), project, {"COMPOSE_PROJECT_NAME": project},
        )

    def inventory(self) -> DockerInventory:
        resources = []
        evidence = []
        list_commands = (
            (ResourceKind.CONTAINER, ("docker", "ps", "-a", "--filter", "label=" + MANAGED_LABEL + "=true", "--format", "{{.ID}}")),
            (ResourceKind.NETWORK, ("docker", "network", "ls", "--filter", "label=" + MANAGED_LABEL + "=true", "--format", "{{.ID}}")),
            (ResourceKind.VOLUME, ("docker", "volume", "ls", "--filter", "label=" + MANAGED_LABEL + "=true", "--format", "{{.Name}}")),
        )
        for kind, argv in list_commands:
            listed = self.runner.run(argv)
            evidence.append(listed)
            if listed.exit_code != 0:
                raise invalid_policy("docker_inventory_failed")
            for resource_id in filter(None, (line.strip() for line in listed.stdout.splitlines())):
                inspected = self.runner.run(_inspect_argv(kind, resource_id))
                evidence.append(inspected)
                if inspected.exit_code != 0:
                    resources.append(DockerResource(
                        resource_id, kind, {MANAGED_LABEL: "true"}, self.now(),
                        inspect_ok=False, use_known=False,
                    ))
                    continue
                try:
                    value = json.loads(inspected.stdout)
                    if isinstance(value, list):
                        value = value[0]
                    resource = _resource_from_inspect(kind, resource_id, value)
                except Exception:
                    resources.append(DockerResource(
                        resource_id, kind, {MANAGED_LABEL: "true"}, self.now(),
                        inspect_ok=False, use_known=False,
                    ))
                    continue
                if kind is ResourceKind.VOLUME:
                    use_argv = ("docker", "ps", "-a", "--filter", "volume=" + resource_id, "--format", "{{.ID}}")
                    use = self.runner.run(use_argv)
                    evidence.append(use)
                    resource = replace(
                        resource, use_known=use.exit_code == 0,
                        in_use=use.exit_code == 0 and bool(use.stdout.strip()),
                    )
                resources.append(resource)
        return DockerInventory(
            tuple(sorted(resources, key=_resource_key)), source="managed_orphan_sweep",
            evidence=tuple(evidence),
        )

    def inventory_registered(self, records: Sequence[ResourceRecord]) -> DockerInventory:
        """Inspect every registered Docker kind+ID directly; never discover by label."""
        if type(records) is not tuple or any(type(value) is not ResourceRecord for value in records):
            raise invalid_policy("invalid_registered_docker_inventory_request")
        queried = tuple((value.kind, value.resource_id) for value in records if value.kind in KIND_ORDER)
        if len(set(queried)) != len(queried):
            raise invalid_policy("invalid_registered_docker_inventory_request")
        resources = []
        absent = []
        evidence = []
        for kind, resource_id in queried:
            inspected = self.runner.run(_inspect_argv(kind, resource_id))
            evidence.append(inspected)
            if inspected.exit_code != 0:
                if _is_exact_not_found(kind, resource_id, inspected):
                    absent.append((kind, resource_id))
                else:
                    resources.append(DockerResource(
                        resource_id, kind, {}, self.now(), inspect_ok=False, use_known=False,
                    ))
                continue
            try:
                value = json.loads(inspected.stdout)
                if type(value) is not list or len(value) != 1:
                    raise ValueError
                resource = _resource_from_inspect(kind, resource_id, value[0])
            except Exception:
                resource = DockerResource(
                    resource_id, kind, {}, self.now(), inspect_ok=False, use_known=False,
                )
            if kind is ResourceKind.VOLUME and resource.inspect_ok:
                use = self.runner.run((
                    "docker", "ps", "-a", "--filter", "volume=" + resource_id,
                    "--format", "{{.ID}}",
                ))
                evidence.append(use)
                resource = replace(resource, use_known=use.exit_code == 0,
                                   in_use=use.exit_code == 0 and bool(use.stdout.strip()))
            resources.append(resource)
        return DockerInventory(
            tuple(sorted(resources, key=_resource_key)), queried, tuple(absent),
            "registered_exact", tuple(evidence),
        )

    def record_creation(
        self, registry: ResourceRegistry, plan: DockerCreationPlan, result: CommandResult,
        before: DockerInventory, after: DockerInventory,
    ) -> CreationReceipt:
        before_keys = {(value.kind, value.resource_id) for value in before.resources}
        added = [value for value in after.resources if (value.kind, value.resource_id) not in before_keys]
        unmatched = list(plan.registration_intents)
        registered = []
        dispositions = []
        result_matches = result.argv == plan.argv
        for resource in sorted(added, key=_resource_key):
            intent = next((
                value for value in unmatched
                if _intent_matches(resource, value, unmatched)
                and _result_identity_matches(plan, resource, result)
            ), None)
            if not plan.managed or not result_matches or intent is None:
                dispositions.append(_docker_disposition(
                    resource, CleanupDisposition.FOREIGN, "none", "creation_result_or_intent_mismatch",
                ))
                continue
            unmatched.remove(intent)
            record = ResourceRecord(
                resource.resource_id, resource.kind, intent.run_id, intent.node_id,
                intent.lifecycle, intent.cleanup_policy, resource.created_at,
                intent.dependent_node_ids, _ownership_labels(resource.labels),
            )
            registry.register(record)
            registered.append(record)
        for intent in unmatched:
            placeholder = ResourceRecord(
                "missing:" + intent.kind.value + ":" + (intent.expected_name or "unnamed"),
                intent.kind, intent.run_id, intent.node_id, intent.lifecycle,
                intent.cleanup_policy, self.now(), intent.dependent_node_ids, dict(intent.labels),
            )
            dispositions.append(disposition_for(
                placeholder, CleanupDisposition.MISSING, "none",
                "creation_not_observed" if result.exit_code == 0 and result_matches else "creation_command_failed",
                command=plan.argv,
            ))
        return CreationReceipt(
            command_succeeded=result.exit_code == 0 and result_matches,
            before=tuple(sorted(_resource_identity(value) for value in before.resources)),
            after=tuple(sorted(_resource_identity(value) for value in after.resources)),
            registered=tuple(registered), dispositions=tuple(dispositions),
        )

    def plan_chunk_cleanup(
        self, registry: ResourceRegistry, inventory: DockerInventory, run_id: str, node_id: str,
        *, incomplete_node_proof: Optional[IncompleteNodeProof] = None,
    ) -> CleanupPlan:
        records = [value for value in registry.resources_for(run_id, node_id) if value.lifecycle == "chunk" and value.kind in KIND_ORDER]
        return self._plan_registered(
            inventory, records, CleanupScope(run_id, node_id),
            incomplete_node_proof=incomplete_node_proof,
        )

    def plan_reconcile_run(
        self, registry: ResourceRegistry, inventory: DockerInventory, run_id: str,
        *, incomplete_node_proof: Optional[IncompleteNodeProof] = None,
        terminal: bool = False,
    ) -> CleanupPlan:
        records = [value for value in registry.resources_for(run_id) if value.kind in KIND_ORDER]
        return self._plan_registered(
            inventory, records, CleanupScope(run_id, terminal=terminal),
            incomplete_node_proof=incomplete_node_proof,
        )

    def _plan_registered(
        self, inventory: DockerInventory, records: Sequence[ResourceRecord], scope: CleanupScope,
        *, incomplete_node_proof: Optional[IncompleteNodeProof],
    ) -> CleanupPlan:
        by_key = {(value.kind, value.resource_id): value for value in inventory.resources}
        exact_absent = _authoritative_absent_keys(inventory)
        actions = []
        dispositions = []
        if incomplete_node_proof is not None:
            incomplete_node_proof = _snapshot_incomplete_node_proof(
                incomplete_node_proof,
            )
            if (
                incomplete_node_proof.run_id != scope.run_id
                or not incomplete_node_proof.readable
                or not self._incomplete_node_proof_is_fresh(incomplete_node_proof)
            ):
                raise invalid_policy("invalid_incomplete_node_proof")
            statuses = dict(incomplete_node_proof.node_statuses)
            incomplete = set(incomplete_node_proof.incomplete_node_ids)
        else:
            statuses = {}
            incomplete = set()
        for record in sorted(records, key=lambda value: (KIND_ORDER[value.kind], value.resource_id)):
            resource = by_key.get((record.kind, record.resource_id))
            if resource is None:
                if (record.kind, record.resource_id) in exact_absent:
                    dispositions.append(disposition_for(record, CleanupDisposition.MISSING, "none", "resource_absent_before_cleanup"))
                else:
                    dispositions.append(disposition_for(record, CleanupDisposition.BLOCKED, "none", "resource_not_exactly_inspected"))
                continue
            if not resource.inspect_ok:
                dispositions.append(disposition_for(record, CleanupDisposition.BLOCKED, "none", "docker_inspect_failed"))
                continue
            if not _registry_labels_agree(record, resource, self.creation_time_skew):
                dispositions.append(disposition_for(record, CleanupDisposition.FOREIGN, "none", "registry_label_disagreement"))
                continue
            if record.dependent_node_ids and incomplete_node_proof is None:
                dispositions.append(disposition_for(
                    record, CleanupDisposition.BLOCKED, "none",
                    "incomplete_node_proof_missing",
                ))
                continue
            missing_statuses = tuple(sorted(
                node for node in record.dependent_node_ids if node not in statuses
            ))
            if missing_statuses:
                dispositions.append(disposition_for(
                    record, CleanupDisposition.BLOCKED, "none",
                    "dependent_node_status_missing",
                    evidence=("dependent_node=" + node for node in missing_statuses),
                ))
                continue
            dependent_ids = tuple(sorted(
                node for node in record.dependent_node_ids if node in incomplete
            ))
            if dependent_ids:
                dispositions.append(disposition_for(
                    record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none",
                    "incomplete_dependent_node",
                    evidence=("dependent_node=" + node for node in dependent_ids),
                ))
                continue
            planned, disposition = self._plan_one(
                record, resource, allow_stop=record.lifecycle == "chunk" or scope.terminal,
                incomplete_node_proof=(
                    incomplete_node_proof if record.dependent_node_ids else None
                ),
            )
            base = len(actions)
            actions.extend(_offset_dependencies(planned, base))
            if disposition is not None:
                dispositions.append(disposition)
        registered_keys = {(value.kind, value.resource_id) for value in records}
        if scope.terminal:
            for resource in sorted(inventory.resources, key=_resource_key):
                key = (resource.kind, resource.resource_id)
                if key in registered_keys:
                    continue
                if (
                    not resource.inspect_ok or not _valid_ownership_labels(resource.labels)
                    or resource.labels.get(RUN_LABEL) != scope.run_id
                ):
                    if resource.labels.get(RUN_LABEL) == scope.run_id:
                        dispositions.append(_docker_disposition(
                            resource, CleanupDisposition.FOREIGN, "none",
                            "unregistered_resource_ownership_invalid",
                        ))
                    continue
                record = _record_from_resource(resource)
                lease, lease_error = self._read_lease(record.run_id, self.now())
                if lease_error is not None:
                    dispositions.append(disposition_for(
                        record, CleanupDisposition.BLOCKED, "none", lease_error,
                    ))
                    continue
                if lease.active:
                    dispositions.append(disposition_for(
                        record, CleanupDisposition.RETAINED_FOR_DEPENDENCY,
                        "none", "active_run_lease",
                    ))
                    continue
                planned, disposition = self._plan_one(
                    record, resource, allow_stop=True, lease_proof=lease,
                )
                base = len(actions)
                actions.extend(_offset_dependencies(planned, base))
                if disposition is not None:
                    dispositions.append(disposition)
        return CleanupPlan(
            scope, tuple(sorted(_resource_identity(value) for value in inventory.resources)),
            tuple(actions), tuple(dispositions),
        )

    def plan_stale_sweep(self, inventory: DockerInventory, ttl: timedelta) -> CleanupPlan:
        if not isinstance(ttl, timedelta) or ttl.total_seconds() < 0:
            raise invalid_policy("invalid_resource_ttl")
        now = self.now()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise invalid_policy("docker_clock_requires_timezone")
        actions = []
        dispositions = []
        lease_cache: dict[str, tuple[Optional[LeaseProof], Optional[str]]] = {}
        for resource in sorted(inventory.resources, key=_resource_key):
            if not resource.inspect_ok:
                dispositions.append(_docker_disposition(resource, CleanupDisposition.BLOCKED, "none", "docker_inspect_failed"))
                continue
            labels = resource.labels
            if not _valid_ownership_labels(labels):
                dispositions.append(_docker_disposition(resource, CleanupDisposition.FOREIGN, "none", "invalid_ownership_labels"))
                continue
            created = _parse_timestamp(labels[CREATED_LABEL])
            if resource.created_at.tzinfo is None or abs(resource.created_at - created) > self.creation_time_skew:
                dispositions.append(_docker_disposition(resource, CleanupDisposition.FOREIGN, "none", "created_at_label_disagreement"))
                continue
            record = _record_from_resource(resource)
            run_id = labels[RUN_LABEL]
            if run_id not in lease_cache:
                lease_cache[run_id] = self._read_lease(run_id, now)
            lease, lease_error = lease_cache[run_id]
            if lease_error is not None:
                dispositions.append(disposition_for(record, CleanupDisposition.BLOCKED, "none", lease_error))
                continue
            if lease.active:
                dispositions.append(disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "active_run_lease"))
                continue
            if now - created <= ttl or now - resource.created_at <= ttl:
                dispositions.append(disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "ttl_not_expired"))
                continue
            planned, disposition = self._plan_one(
                record, resource, allow_stop=False, lease_proof=lease,
            )
            base = len(actions)
            actions.extend(_offset_dependencies(planned, base))
            if disposition is not None:
                dispositions.append(disposition)
        return CleanupPlan(
            CleanupScope("stale", stale_sweep=True),
            tuple(sorted(_resource_identity(value) for value in inventory.resources)),
            tuple(actions), tuple(dispositions),
        )

    def _read_lease(self, run_id: str, now: datetime) -> tuple[Optional[LeaseProof], Optional[str]]:
        if self.lease_reader is None:
            return None, "lease_reader_unavailable"
        try:
            proof = self.lease_reader.read(run_id)
        except Exception:
            return None, "lease_read_failed"
        if proof is None:
            return None, "lease_proof_missing"
        if (
            type(proof) is not LeaseProof or not _valid_lease_proof(proof)
            or proof.run_id != run_id or not proof.readable
        ):
            return None, "lease_proof_unreadable"
        age = now - proof.observed_at
        if age < timedelta(0) or age > self.lease_max_age:
            return None, "lease_proof_stale"
        return proof, None

    def _plan_one(
        self, record: ResourceRecord, resource: DockerResource, *, allow_stop: bool,
        lease_proof: Optional[LeaseProof] = None,
        incomplete_node_proof: Optional[IncompleteNodeProof] = None,
    ) -> tuple[Tuple[CleanupAction, ...], Optional[ResourceDisposition]]:
        if resource.kind in (ResourceKind.NETWORK, ResourceKind.VOLUME):
            if not resource.use_known:
                return (), disposition_for(record, CleanupDisposition.BLOCKED, "none", "resource_use_unknown")
            if resource.in_use:
                return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "resource_in_use")
        if resource.system:
            return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "system_resource")
        if record.cleanup_policy == "retain":
            return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "cleanup_policy_retain")
        actions = []
        preconditions = (
            "registered_kind_and_exact_id", "ownership_labels_exact",
            "docker_inspect_exact_id_succeeded", "resource_use_revalidated",
        )
        if lease_proof is not None:
            preconditions += ("inactive_run_lease",)
        if incomplete_node_proof is not None:
            preconditions += ("incomplete_node_snapshot",)
        if resource.kind is ResourceKind.CONTAINER:
            if resource.running:
                if not allow_stop or record.cleanup_policy != "stop-remove":
                    reason = "stale_running_container_never_stopped" if not allow_stop else "running_container_policy_forbids_stop"
                    return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", reason)
                stop_argv = (
                    "docker", "stop", "--time", str(self.stop_timeout_seconds),
                    resource.resource_id,
                )
                actions.append(_docker_action(
                    record, resource, "stop", stop_argv, None,
                    preconditions + ("container_running",), lease_proof,
                    incomplete_node_proof,
                ))
            projected = replace(resource, running=False) if actions else resource
            predecessor_id = cleanup_result_id(actions[0].argv, 0) if actions else None
            actions.append(_docker_action(
                record, projected, "remove", ("docker", "rm", resource.resource_id),
                0 if actions else None,
                preconditions + (("container_stopped_after_predecessor",) if actions else ()),
                lease_proof, incomplete_node_proof, predecessor_id,
            ))
        elif resource.kind is ResourceKind.NETWORK:
            actions.append(_docker_action(
                record, resource, "remove", ("docker", "network", "rm", resource.resource_id),
                None, preconditions + ("network_not_in_use",), lease_proof,
                incomplete_node_proof,
            ))
        elif resource.kind is ResourceKind.VOLUME:
            actions.append(_docker_action(
                record, resource, "remove", ("docker", "volume", "rm", resource.resource_id),
                None, preconditions + ("volume_not_in_use",), lease_proof,
                incomplete_node_proof,
            ))
        return tuple(actions), None

    def revalidate_action(
        self, action: CleanupAction, resource: DockerResource,
        lease_proof: Optional[LeaseProof] = None,
        predecessor_result: Optional[CommandResult] = None,
        *, action_index: Optional[int] = None,
        registry: Optional[ResourceRegistry] = None,
        incomplete_node_proof: Optional[IncompleteNodeProof] = None,
        orphan_mode: bool = False,
    ) -> None:
        """Validate the destructive capability against a fresh exact-ID inspect."""
        if (
            type(action) is not CleanupAction or type(resource) is not DockerResource
            or (action_index is not None and (type(action_index) is not int or action_index < 0))
            or type(orphan_mode) is not bool
        ):
            raise invalid_policy("invalid_docker_cleanup_revalidation")
        try:
            action = CleanupAction(
                action.resource_id, action.kind, action.action, tuple(action.argv),
                action.requires_success_of, action.run_id, action.node_id,
                action.lifecycle, action.proof_digest, tuple(action.preconditions),
                dict(action.environment), action.predecessor_result_id,
                action.evidence_digest,
            )
            resource = DockerResource(
                resource.resource_id, resource.kind, dict(resource.labels),
                resource.created_at, resource.running, resource.in_use,
                resource.system, resource.inspect_ok, resource.name,
                resource.use_known,
            )
        except Exception:
            raise invalid_policy("invalid_docker_cleanup_revalidation") from None
        if (action.kind, action.resource_id) != (resource.kind, resource.resource_id):
            raise invalid_policy("docker_cleanup_precondition_changed")

        if type(registry) is not ResourceRegistry:
            raise invalid_policy("docker_cleanup_precondition_changed")
        record, record_active = registry.resource_state_for_exact(
            action.kind, action.resource_id,
        )
        if orphan_mode:
            if (
                record is not None or incomplete_node_proof is not None
                or not _valid_ownership_labels(resource.labels)
            ):
                raise invalid_policy("docker_cleanup_precondition_changed")
            record = _record_from_resource(resource)
        else:
            if lease_proof is not None:
                raise invalid_policy("docker_cleanup_precondition_changed")
            if not record_active or record is None or (record.run_id, record.node_id) != (
                action.run_id, action.node_id,
            ):
                raise invalid_policy("docker_cleanup_precondition_changed")

        requires_incomplete_nodes = bool(record.dependent_node_ids)
        if requires_incomplete_nodes:
            incomplete_node_proof = _snapshot_incomplete_node_proof(
                incomplete_node_proof,
            )
            if (
                not incomplete_node_proof.readable
                or incomplete_node_proof.run_id != action.run_id
                or not self._incomplete_node_proof_is_fresh(incomplete_node_proof)
                or (record.kind, record.resource_id)
                != (resource.kind, resource.resource_id)
                or (record.run_id, record.node_id, record.lifecycle)
                != (action.run_id, action.node_id, action.lifecycle)
                or not set(record.dependent_node_ids).issubset(
                    {node_id for node_id, _status in incomplete_node_proof.node_statuses}
                )
                or set(record.dependent_node_ids) & set(
                    incomplete_node_proof.incomplete_node_ids
                )
            ):
                raise invalid_policy("docker_cleanup_precondition_changed")
        elif incomplete_node_proof is not None:
            raise invalid_policy("docker_cleanup_precondition_changed")

        requires_lease = orphan_mode
        lease_valid = (
            type(lease_proof) is LeaseProof and _valid_lease_proof(lease_proof)
            and lease_proof.run_id == action.run_id and lease_proof.readable
            and not lease_proof.active
            and timedelta(0) <= self.now() - lease_proof.observed_at <= self.lease_max_age
        ) if requires_lease else lease_proof is None
        if not resource.inspect_ok or not _registry_labels_agree(record, resource, self.creation_time_skew) or not lease_valid:
            raise invalid_policy("docker_cleanup_precondition_changed")
        base_preconditions = (
            "registered_kind_and_exact_id", "ownership_labels_exact",
            "docker_inspect_exact_id_succeeded", "resource_use_revalidated",
        ) + (("inactive_run_lease",) if lease_proof is not None else ()) \
            + (("incomplete_node_snapshot",) if incomplete_node_proof is not None else ())
        expected = None
        if action.action == "stop" and resource.kind is ResourceKind.CONTAINER and resource.running:
            expected = _docker_action(
                record, resource, "stop",
                ("docker", "stop", "--time", str(self.stop_timeout_seconds), resource.resource_id),
                None, base_preconditions + ("container_running",), lease_proof,
                incomplete_node_proof,
            )
        elif action.action == "remove":
            if resource.system or (
                resource.kind in (ResourceKind.NETWORK, ResourceKind.VOLUME)
                and (not resource.use_known or resource.in_use)
            ):
                raise invalid_policy("docker_cleanup_precondition_changed")
            predecessor_id = action.predecessor_result_id
            preconditions = base_preconditions
            requires = None
            if predecessor_id is not None:
                if (
                    action_index is None or action_index == 0
                    or resource.kind is not ResourceKind.CONTAINER or resource.running
                    or type(predecessor_result) is not CommandResult
                    or predecessor_result.exit_code != 0
                    or cleanup_result_id(predecessor_result.argv, predecessor_result.exit_code) != predecessor_id
                ):
                    raise invalid_policy("docker_cleanup_precondition_changed")
                expected_stop = (
                    "docker", "stop", "--time", str(self.stop_timeout_seconds),
                    resource.resource_id,
                )
                if predecessor_result.argv != expected_stop:
                    raise invalid_policy("docker_cleanup_precondition_changed")
                preconditions += ("container_stopped_after_predecessor",)
                requires = action_index - 1
            elif predecessor_result is not None:
                raise invalid_policy("docker_cleanup_precondition_changed")
            argv = (
                ("docker", "rm", resource.resource_id)
                if resource.kind is ResourceKind.CONTAINER else
                ("docker", resource.kind.value, "rm", resource.resource_id)
            )
            if resource.kind is ResourceKind.NETWORK:
                preconditions += ("network_not_in_use",)
            elif resource.kind is ResourceKind.VOLUME:
                preconditions += ("volume_not_in_use",)
            expected = _docker_action(
                record, resource, "remove", argv, requires, preconditions,
                lease_proof, incomplete_node_proof, predecessor_id,
            )
        if expected is None or action != expected:
            raise invalid_policy("docker_cleanup_precondition_changed")

    def _incomplete_node_proof_is_fresh(self, proof: IncompleteNodeProof) -> bool:
        current = self.now()
        if (
            type(current) is not datetime or current.tzinfo is None
            or current.utcoffset() is None
        ):
            return False
        age = current - proof.observed_at
        return timedelta(0) <= age <= self.incomplete_node_max_age

    def record_results(
        self, plan: CleanupPlan, results: Sequence[CommandResult], after: DockerInventory,
    ) -> CleanupReceipt:
        receipt, _ = self._reconcile_results(plan, results, DockerInventory(()), after)
        return receipt

    def _reconcile_results(
        self, plan: CleanupPlan, results: Sequence[CommandResult],
        before: DockerInventory, after: DockerInventory,
    ) -> tuple[CleanupReceipt, Tuple[ResourceRecord, ...]]:
        if (
            type(plan) is not CleanupPlan or type(results) is not tuple
            or type(before) is not DockerInventory or type(after) is not DockerInventory
        ):
            raise invalid_policy("invalid_cleanup_result_models")
        if (
            type(plan.scope) is not CleanupScope
            or type(plan.before) is not tuple or type(plan.actions) is not tuple
            or type(plan.dispositions) is not tuple
            or any(type(value) is not CleanupAction for value in plan.actions)
            or any(type(value) is not ResourceDisposition for value in plan.dispositions)
            or any(type(value) is not CommandResult for value in results)
            or type(after.resources) is not tuple or type(after.queried) is not tuple
            or type(after.absent) is not tuple or type(after.evidence) is not tuple
            or any(type(value) is not DockerResource for value in after.resources)
            or any(type(value) is not CommandResult for value in after.evidence)
            or type(before.resources) is not tuple or type(before.queried) is not tuple
            or type(before.absent) is not tuple or type(before.evidence) is not tuple
            or any(type(value) is not DockerResource for value in before.resources)
            or any(type(value) is not CommandResult for value in before.evidence)
        ):
            raise invalid_policy("invalid_cleanup_result_models")
        # Reconstruct every externally supplied frozen model before trusting it.
        plan = CleanupPlan(
            CleanupScope(plan.scope.run_id, plan.scope.node_id, plan.scope.terminal, plan.scope.stale_sweep),
            tuple(plan.before),
            tuple(CleanupAction(
                item.resource_id, item.kind, item.action, tuple(item.argv), item.requires_success_of,
                item.run_id, item.node_id, item.lifecycle, item.proof_digest, tuple(item.preconditions),
                dict(item.environment), item.predecessor_result_id, item.evidence_digest,
            ) for item in plan.actions),
            tuple(ResourceDisposition(
                item.resource_id, item.kind, item.run_id, item.node_id, item.lifecycle,
                item.disposition, item.action, item.reason, tuple(item.evidence), tuple(item.command),
                item.follow_up,
            ) for item in plan.dispositions),
        )
        normalized_results = tuple(CommandResult(
            tuple(value.argv), value.exit_code, value.stdout, value.stderr,
        ) for value in results)
        after = DockerInventory(
            tuple(DockerResource(
                value.resource_id, value.kind, dict(value.labels), value.created_at,
                value.running, value.in_use, value.system, value.inspect_ok,
                value.name, value.use_known,
            ) for value in after.resources),
            tuple(after.queried), tuple(after.absent), after.source,
            tuple(CommandResult(
                tuple(value.argv), value.exit_code, value.stdout, value.stderr,
            ) for value in after.evidence),
        )
        before = DockerInventory(
            tuple(DockerResource(
                value.resource_id, value.kind, dict(value.labels), value.created_at,
                value.running, value.in_use, value.system, value.inspect_ok,
                value.name, value.use_known,
            ) for value in before.resources),
            tuple(before.queried), tuple(before.absent), before.source,
            tuple(CommandResult(
                tuple(value.argv), value.exit_code, value.stdout, value.stderr,
            ) for value in before.evidence),
        )
        planned_argv = tuple(action.argv for action in plan.actions)
        result_argv = tuple(value.argv for value in normalized_results)
        if len(set(planned_argv)) != len(planned_argv) or len(set(result_argv)) != len(result_argv):
            raise invalid_policy("cleanup_results_not_one_to_one")
        if any(argv not in planned_argv for argv in result_argv):
            raise invalid_policy("cleanup_result_not_planned")
        action_indexes = {argv: index for index, argv in enumerate(planned_argv)}
        result_indexes = tuple(action_indexes[argv] for argv in result_argv)
        if result_indexes != tuple(range(len(result_indexes))):
            raise invalid_policy("cleanup_results_out_of_order")
        results_by_index = {
            index: result for index, result in zip(result_indexes, normalized_results)
        }
        for index, result in zip(result_indexes, normalized_results):
            dependency = plan.actions[index].requires_success_of
            if dependency is not None and (
                dependency not in results_by_index
                or dependency >= index
                or results_by_index[dependency].exit_code != 0
            ):
                raise invalid_policy("cleanup_dependency_result_unsatisfied")
        by_argv = {result.argv: result for result in normalized_results}
        after_keys = {(value.kind, value.resource_id) for value in after.resources}
        exact_absent = _authoritative_absent_keys(after)
        groups: dict[tuple[ResourceKind, str], list[CleanupAction]] = {}
        for action in plan.actions:
            groups.setdefault((action.kind, action.resource_id), []).append(action)
        dispositions = [
            replace(item, disposition=CleanupDisposition.BLOCKED,
                    reason="resource_reappeared_before_result_recording")
            if item.disposition is CleanupDisposition.MISSING
            and (item.kind, item.resource_id) not in exact_absent else item
            for item in plan.dispositions
        ]
        for (kind, resource_id), actions in groups.items():
            missing_results = [action for action in actions if action.argv not in by_argv]
            failures = [(action, by_argv[action.argv]) for action in actions if action.argv in by_argv and by_argv[action.argv].exit_code != 0]
            owner = actions[0]
            if missing_results:
                failed_action = missing_results[0]
                dispositions.append(ResourceDisposition(
                    resource_id, kind, owner.run_id, owner.node_id, owner.lifecycle,
                    CleanupDisposition.BLOCKED, "remove_exact_id", "cleanup_result_missing",
                    command=failed_action.argv, follow_up="execute or record exact planned command",
                ))
            elif failures:
                failed_action, failed_result = failures[0]
                reason = "container_stop_failed" if failed_action.action == "stop" else kind.value + "_remove_failed"
                dispositions.append(ResourceDisposition(
                    resource_id, kind, owner.run_id, owner.node_id, owner.lifecycle,
                    CleanupDisposition.BLOCKED, "remove_exact_id", reason,
                    evidence=("exit=" + str(failed_result.exit_code),), command=failed_action.argv,
                    follow_up="retry exact owned resource cleanup",
                ))
            elif (kind, resource_id) in exact_absent:
                remove_action = actions[-1]
                dispositions.append(ResourceDisposition(
                    resource_id, kind, owner.run_id, owner.node_id, owner.lifecycle,
                    CleanupDisposition.REMOVED, "remove_exact_id", "confirmed_removed",
                    evidence=tuple("exit=0" for _ in actions), command=remove_action.argv,
                ))
            else:
                dispositions.append(ResourceDisposition(
                    resource_id, kind, owner.run_id, owner.node_id, owner.lifecycle,
                    CleanupDisposition.BLOCKED, "remove_exact_id", "resource_still_present",
                    command=actions[-1].argv, follow_up="inspect dependency or retry exact removal",
                ))
        receipt = CleanupReceipt(
            plan.scope, plan.before,
            tuple(sorted(_resource_identity(value) for value in after.resources)),
            tuple(dispositions),
        )
        disposition_keys = {
            (value.kind, value.resource_id) for value in receipt.dispositions
        }
        observed = tuple(
            _record_from_resource(value) for value in before.resources
            if (value.kind, value.resource_id) in disposition_keys
            and _valid_ownership_labels(value.labels)
        )
        return receipt, observed

    def _result_transaction_id(
        self, plan: CleanupPlan, results: Tuple[CommandResult, ...],
        before: DockerInventory, after: DockerInventory,
    ) -> str:
        receipt, observed = self._reconcile_results(plan, results, before, after)
        return cleanup_proof_digest({
            "plan": plan.to_dict(),
            "results": [
                {"argv": list(value.argv), "exit_code": value.exit_code}
                for value in results
            ],
            "before": sorted(_resource_identity(value) for value in before.resources),
            "after": sorted(_resource_identity(value) for value in after.resources),
            "receipt": receipt.to_dict(),
            "observed": sorted(_resource_identity(value) for value in observed),
        })


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError
    return parsed


def _explicit_name(argv: Tuple[str, ...]) -> Optional[str]:
    for index, part in enumerate(argv):
        if part == "--name" and index + 1 < len(argv):
            return argv[index + 1]
        if part.startswith("--name="):
            return part.split("=", 1)[1]
    return None


def _create_resource_name(
    argv: Tuple[str, ...], start: int, kind: ResourceKind,
) -> Optional[str]:
    value_options = _CREATE_VALUE_OPTIONS[kind]
    flag_options = _CREATE_FLAG_OPTIONS[kind]
    positionals = []
    index = start
    while index < len(argv):
        value = argv[index]
        if value in value_options:
            if index + 1 >= len(argv) or not _normalized_docker_text(argv[index + 1], 4096):
                return None
            index += 2
            continue
        if value in flag_options:
            index += 1
            continue
        if value.startswith("--"):
            name, separator, option_value = value.partition("=")
            if name in value_options and separator and _normalized_docker_text(option_value, 4096):
                index += 1
                continue
            return None
        if value.startswith("-"):
            option = value[:2]
            if option in value_options and len(value) > 2:
                if not _normalized_docker_text(value[2:].removeprefix("="), 4096):
                    return None
                index += 1
                continue
            return None
        positionals.append(value)
        index += 1
    if len(positionals) != 1 or not _normalized_docker_text(positionals[0], 4096):
        return None
    return positionals[0]


def _project_name(run_id: str, node_id: str) -> str:
    raw = "depot-" + run_id + "-" + node_id
    normalized = re.sub(r"[^a-z0-9_-]+", "-", raw.lower()).strip("-_")
    if len(normalized) <= 63:
        return normalized
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return normalized[:52].rstrip("-_") + "-" + digest


def _has_anonymous_volume(services: Mapping[str, object]) -> bool:
    for service in services.values():
        if not isinstance(service, dict):
            return True
        for volume in service.get("volumes", ()):
            if isinstance(volume, str) and ":" not in volume:
                return True
            if isinstance(volume, dict) and volume.get("type", "volume") == "volume" and not volume.get("source"):
                return True
    return False


def _intent_matches(
    resource: DockerResource, intent: ResourceRegistrationIntent,
    intents: Sequence[ResourceRegistrationIntent],
) -> bool:
    if resource.kind is not intent.kind or _ownership_labels(resource.labels) != dict(intent.labels):
        return False
    expected = intent.expected_name
    if expected is None:
        return sum(value.kind is intent.kind for value in intents) == 1
    return (
        (resource.name or "").lstrip("/") == expected
        or resource.labels.get(COMPOSE_MATCH_LABEL[intent.kind]) == expected
    )


def _result_identity_matches(
    plan: DockerCreationPlan, resource: DockerResource, result: CommandResult,
) -> bool:
    if plan.compose_override is not None:
        return True
    token = result.stdout.strip().splitlines()[0].strip() if result.stdout.strip() else ""
    if plan.argv[:3] == ("docker", "container", "create"):
        return bool(token) and _ids_correlate(token, resource.resource_id)
    if plan.argv[:3] == ("docker", "network", "create"):
        return bool(token) and _ids_correlate(token, resource.resource_id)
    if plan.argv[:3] == ("docker", "volume", "create"):
        return token == resource.resource_id or token == resource.name
    if plan.argv[:2] == ("docker", "run"):
        detached = "-d" in plan.argv or "--detach" in plan.argv
        return not detached or (bool(token) and _ids_correlate(token, resource.resource_id))
    return False


def _ids_correlate(left: str, right: str) -> bool:
    return left == right or left.startswith(right) or right.startswith(left)


def _ownership_labels(labels: Mapping[str, str]) -> dict[str, str]:
    return {key: labels[key] for key in REQUIRED_LABELS if key in labels}


def _valid_ownership_labels(labels: Mapping[str, str]) -> bool:
    if set(_ownership_labels(labels)) != set(REQUIRED_LABELS):
        return False
    if labels.get(MANAGED_LABEL) != "true":
        return False
    if labels.get(LIFECYCLE_LABEL) not in VALID_LIFECYCLES or labels.get(POLICY_LABEL) not in VALID_CLEANUP_POLICIES:
        return False
    if (
        not _normalized_docker_text(labels.get(RUN_LABEL), 256)
        or not _normalized_docker_text(labels.get(NODE_LABEL), 256)
        or not _normalized_docker_text(labels.get(CREATED_LABEL), 128)
    ):
        return False
    try:
        _parse_timestamp(labels[CREATED_LABEL])
    except Exception:
        return False
    return True


def _registry_labels_agree(
    record: ResourceRecord, resource: DockerResource, creation_time_skew: timedelta,
) -> bool:
    labels = _ownership_labels(resource.labels)
    if not record.labels or set(record.labels) != set(REQUIRED_LABELS):
        return False
    if not _valid_ownership_labels(labels) or dict(record.labels) != labels:
        return False
    if resource.kind is not record.kind:
        return False
    if (
        labels[RUN_LABEL] != record.run_id or labels[NODE_LABEL] != record.node_id
        or labels[LIFECYCLE_LABEL] != record.lifecycle or labels[POLICY_LABEL] != record.cleanup_policy
        or resource.created_at != record.created_at
    ):
        return False
    try:
        return abs(resource.created_at - _parse_timestamp(labels[CREATED_LABEL])) <= creation_time_skew
    except Exception:
        return False


def _record_from_resource(resource: DockerResource) -> ResourceRecord:
    labels = _ownership_labels(resource.labels)
    return ResourceRecord(
        resource.resource_id, resource.kind, labels[RUN_LABEL], labels[NODE_LABEL],
        labels[LIFECYCLE_LABEL], labels[POLICY_LABEL], resource.created_at,
        (), labels,
    )


def _docker_disposition(resource, disposition, action, reason):
    labels = resource.labels
    lifecycle = labels.get(LIFECYCLE_LABEL, "chunk")
    if lifecycle not in VALID_LIFECYCLES:
        lifecycle = "chunk"
    run_id = labels.get(RUN_LABEL)
    node_id = labels.get(NODE_LABEL)
    if not _normalized_docker_text(run_id, 256):
        run_id = "unknown"
    if not _normalized_docker_text(node_id, 256):
        node_id = "unknown"
    return ResourceDisposition(
        resource.resource_id, resource.kind, run_id, node_id, lifecycle,
        disposition, action, reason,
    )


def _resource_key(value: DockerResource):
    return (KIND_ORDER.get(value.kind, 9), value.resource_id)


def _resource_identity(value: DockerResource) -> str:
    return value.kind.value + ":" + value.resource_id


def _docker_cleanup_evidence(
    record: ResourceRecord, resource: DockerResource,
    lease_proof: Optional[LeaseProof] = None,
    incomplete_node_proof: Optional[IncompleteNodeProof] = None,
) -> dict[str, object]:
    payload = {
        "resource_id": resource.resource_id, "kind": resource.kind.value,
        "labels": dict(sorted(resource.labels.items())),
        "created_at": _timestamp(resource.created_at), "running": resource.running,
        "in_use": resource.in_use, "system": resource.system,
        "inspect_ok": resource.inspect_ok, "use_known": resource.use_known,
        "run_id": record.run_id, "node_id": record.node_id,
        "lifecycle": record.lifecycle, "cleanup_policy": record.cleanup_policy,
    }
    if incomplete_node_proof is not None:
        payload["dependencies"] = {
            "dependent_node_ids": list(record.dependent_node_ids),
            "node_statuses": [
                [node_id, status.value]
                for node_id, status in incomplete_node_proof.node_statuses
            ],
            "incomplete_node_ids": list(
                incomplete_node_proof.incomplete_node_ids
            ),
            "run_id": incomplete_node_proof.run_id,
        }
    if lease_proof is not None:
        payload["lease"] = {
            "run_id": lease_proof.run_id, "active": lease_proof.active,
            "readable": lease_proof.readable,
        }
    return payload


def _docker_action(
    record: ResourceRecord, resource: DockerResource, action: str,
    argv: Tuple[str, ...], requires_success_of: Optional[int],
    preconditions: Tuple[str, ...], lease_proof: Optional[LeaseProof],
    incomplete_node_proof: Optional[IncompleteNodeProof] = None,
    predecessor_result_id: Optional[str] = None,
) -> CleanupAction:
    return build_cleanup_action(
        evidence=_docker_cleanup_evidence(
            record, resource, lease_proof, incomplete_node_proof,
        ),
        resource_id=resource.resource_id, kind=resource.kind, action=action,
        argv=argv, requires_success_of=requires_success_of,
        run_id=record.run_id, node_id=record.node_id, lifecycle=record.lifecycle,
        preconditions=preconditions, predecessor_result_id=predecessor_result_id,
    )


def _offset_dependencies(actions: Sequence[CleanupAction], offset: int) -> Tuple[CleanupAction, ...]:
    return tuple(
        value if value.requires_success_of is None else reseal_cleanup_action(
            value, requires_success_of=value.requires_success_of + offset,
        )
        for value in actions
    )


def _inspect_argv(kind: ResourceKind, resource_id: str) -> Tuple[str, ...]:
    if kind is ResourceKind.CONTAINER:
        return ("docker", "container", "inspect", resource_id)
    return ("docker", kind.value, "inspect", resource_id)


def _is_exact_not_found(
    kind: ResourceKind, resource_id: str, result: CommandResult,
) -> bool:
    if result.argv != _inspect_argv(kind, resource_id) or result.exit_code != 1 or result.stdout:
        return False
    noun = "container" if kind is ResourceKind.CONTAINER else kind.value
    messages = {
        "Error: No such object: " + resource_id,
        "Error: No such " + noun + ": " + resource_id,
        "Error response from daemon: No such " + noun + ": " + resource_id,
    }
    return result.stderr.strip() in messages


def _authoritative_absent_keys(inventory: DockerInventory) -> set[tuple[ResourceKind, str]]:
    evidence = {value.argv: value for value in inventory.evidence}
    return {
        (kind, resource_id)
        for kind, resource_id in inventory.absent
        if (kind, resource_id) in set(inventory.queried)
        and (result := evidence.get(_inspect_argv(kind, resource_id))) is not None
        and _is_exact_not_found(kind, resource_id, result)
    }


def _resource_from_inspect(kind: ResourceKind, resource_id: str, value: Mapping[str, object]) -> DockerResource:
    if type(value) is not dict:
        raise ValueError("inspect payload must be an object")
    config = value.get("Config", {})
    if type(config) is not dict:
        raise ValueError("inspect Config must be an object")
    labels = value.get("Labels", {}) or config.get("Labels", {})
    if type(labels) is not dict or any(type(key) is not str or type(item) is not str for key, item in labels.items()):
        raise ValueError("inspect Labels must be a string map")
    created_raw = value.get("Created") or value.get("CreatedAt") or labels.get(CREATED_LABEL)
    state = value.get("State", {})
    containers = value.get("Containers", {})
    if type(state) is not dict or type(containers) is not dict:
        raise ValueError("inspect State and Containers must be objects")
    running = state.get("Running", False)
    if type(running) is not bool:
        raise ValueError("inspect Running must be boolean")
    name = value.get("Name")
    if name is not None and type(name) is not str:
        raise ValueError("inspect Name must be a string")
    return DockerResource(
        resource_id, kind, labels, _parse_timestamp(created_raw),
        running=running,
        in_use=bool(containers),
        system=kind is ResourceKind.NETWORK and name in {"bridge", "host", "none"},
        name=name,
        use_known=kind is not ResourceKind.VOLUME,
    )
