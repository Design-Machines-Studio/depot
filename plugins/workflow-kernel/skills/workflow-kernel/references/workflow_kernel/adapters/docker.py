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
    ResourceRegistrationIntent, ResourceRegistry, disposition_for,
)


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

    def __post_init__(self) -> None:
        resources = tuple(self.resources)
        keys = [(value.kind, value.resource_id) for value in resources if type(value) is DockerResource]
        if len(keys) != len(resources) or len(set(keys)) != len(keys):
            raise invalid_policy("invalid_docker_inventory")
        object.__setattr__(self, "resources", resources)


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
        creation_time_skew: timedelta = timedelta(minutes=5),
        stop_timeout_seconds: int = 10,
    ):
        if type(stop_timeout_seconds) is not int or not 1 <= stop_timeout_seconds <= 60:
            raise invalid_policy("invalid_docker_stop_timeout")
        if lease_max_age.total_seconds() < 0 or creation_time_skew.total_seconds() < 0:
            raise invalid_policy("invalid_docker_proof_window")
        self.runner = runner
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.lease_reader = lease_reader
        self.lease_max_age = lease_max_age
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
        expected_name = _explicit_name(command) if kind is ResourceKind.CONTAINER else _last_positional(command, insert_at)
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
        list_commands = (
            (ResourceKind.CONTAINER, ("docker", "ps", "-a", "--filter", "label=" + MANAGED_LABEL + "=true", "--format", "{{.ID}}")),
            (ResourceKind.NETWORK, ("docker", "network", "ls", "--filter", "label=" + MANAGED_LABEL + "=true", "--format", "{{.ID}}")),
            (ResourceKind.VOLUME, ("docker", "volume", "ls", "--filter", "label=" + MANAGED_LABEL + "=true", "--format", "{{.Name}}")),
        )
        for kind, argv in list_commands:
            listed = self.runner.run(argv)
            if listed.exit_code != 0:
                raise invalid_policy("docker_inventory_failed")
            for resource_id in filter(None, (line.strip() for line in listed.stdout.splitlines())):
                inspected = self.runner.run(_inspect_argv(kind, resource_id))
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
                    resource = replace(
                        resource, use_known=use.exit_code == 0,
                        in_use=use.exit_code == 0 and bool(use.stdout.strip()),
                    )
                resources.append(resource)
        return DockerInventory(tuple(sorted(resources, key=_resource_key)))

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
    ) -> CleanupPlan:
        records = [value for value in registry.resources_for(run_id, node_id) if value.lifecycle == "chunk" and value.kind in KIND_ORDER]
        return self._plan_registered(inventory, records, CleanupScope(run_id, node_id))

    def plan_reconcile_run(
        self, registry: ResourceRegistry, inventory: DockerInventory, run_id: str,
        *, active_node_ids: Sequence[str] = (), terminal: bool = False,
    ) -> CleanupPlan:
        records = [value for value in registry.resources_for(run_id) if value.kind in KIND_ORDER]
        return self._plan_registered(
            inventory, records, CleanupScope(run_id, terminal=terminal),
            active_node_ids=set(active_node_ids),
        )

    def _plan_registered(
        self, inventory: DockerInventory, records: Sequence[ResourceRecord], scope: CleanupScope,
        *, active_node_ids: Optional[set[str]] = None,
    ) -> CleanupPlan:
        by_key = {(value.kind, value.resource_id): value for value in inventory.resources}
        actions = []
        dispositions = []
        active = active_node_ids or set()
        for record in sorted(records, key=lambda value: (KIND_ORDER[value.kind], value.resource_id)):
            resource = by_key.get((record.kind, record.resource_id))
            if resource is None:
                dispositions.append(disposition_for(record, CleanupDisposition.MISSING, "none", "resource_absent_before_cleanup"))
                continue
            if not resource.inspect_ok:
                dispositions.append(disposition_for(record, CleanupDisposition.BLOCKED, "none", "docker_inspect_failed"))
                continue
            if not _registry_labels_agree(record, resource, self.creation_time_skew):
                dispositions.append(disposition_for(record, CleanupDisposition.FOREIGN, "none", "registry_label_disagreement"))
                continue
            dependent_ids = tuple(sorted(node for node in record.dependent_node_ids if node in active))
            if dependent_ids:
                dispositions.append(disposition_for(
                    record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "active_dependent_node",
                    evidence=("dependent_node=" + node for node in dependent_ids),
                ))
                continue
            planned, disposition = self._plan_one(
                record, resource, allow_stop=record.lifecycle == "chunk" or scope.terminal,
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
            planned, disposition = self._plan_one(record, resource, allow_stop=False)
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
        if resource.kind is ResourceKind.CONTAINER:
            if resource.running:
                if not allow_stop or record.cleanup_policy != "stop-remove":
                    reason = "stale_running_container_never_stopped" if not allow_stop else "running_container_policy_forbids_stop"
                    return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", reason)
                actions.append(CleanupAction(
                    resource.resource_id, resource.kind, "stop",
                    ("docker", "stop", "--time", str(self.stop_timeout_seconds), resource.resource_id),
                    run_id=record.run_id, node_id=record.node_id, lifecycle=record.lifecycle,
                ))
            actions.append(CleanupAction(
                resource.resource_id, resource.kind, "remove", ("docker", "rm", resource.resource_id),
                0 if actions else None, record.run_id, record.node_id, record.lifecycle,
            ))
        elif resource.kind is ResourceKind.NETWORK:
            actions.append(CleanupAction(
                resource.resource_id, resource.kind, "remove", ("docker", "network", "rm", resource.resource_id),
                None, record.run_id, record.node_id, record.lifecycle,
            ))
        elif resource.kind is ResourceKind.VOLUME:
            actions.append(CleanupAction(
                resource.resource_id, resource.kind, "remove", ("docker", "volume", "rm", resource.resource_id),
                None, record.run_id, record.node_id, record.lifecycle,
            ))
        return tuple(actions), None

    def record_results(
        self, plan: CleanupPlan, results: Sequence[CommandResult], after: DockerInventory,
    ) -> CleanupReceipt:
        by_argv = {result.argv: result for result in results}
        after_keys = {(value.kind, value.resource_id) for value in after.resources}
        groups: dict[tuple[ResourceKind, str], list[CleanupAction]] = {}
        for action in plan.actions:
            groups.setdefault((action.kind, action.resource_id), []).append(action)
        dispositions = list(plan.dispositions)
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
            elif (kind, resource_id) not in after_keys:
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
        return CleanupReceipt(
            plan.scope, plan.before,
            tuple(sorted(_resource_identity(value) for value in after.resources)),
            tuple(dispositions),
        )


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


def _last_positional(argv: Tuple[str, ...], start: int) -> Optional[str]:
    values = [value for value in argv[start:] if not value.startswith("-")]
    return values[-1] if values else None


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
    if not labels.get(RUN_LABEL) or not labels.get(NODE_LABEL):
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
    return ResourceDisposition(
        resource.resource_id, resource.kind, labels.get(RUN_LABEL, "unknown"),
        labels.get(NODE_LABEL, "unknown"), lifecycle,
        disposition, action, reason,
    )


def _resource_key(value: DockerResource):
    return (KIND_ORDER.get(value.kind, 9), value.resource_id)


def _resource_identity(value: DockerResource) -> str:
    return value.kind.value + ":" + value.resource_id


def _offset_dependencies(actions: Sequence[CleanupAction], offset: int) -> Tuple[CleanupAction, ...]:
    return tuple(replace(
        value,
        requires_success_of=None if value.requires_success_of is None else value.requires_success_of + offset,
    ) for value in actions)


def _inspect_argv(kind: ResourceKind, resource_id: str) -> Tuple[str, ...]:
    if kind is ResourceKind.CONTAINER:
        return ("docker", "container", "inspect", resource_id)
    return ("docker", kind.value, "inspect", resource_id)


def _resource_from_inspect(kind: ResourceKind, resource_id: str, value: Mapping[str, object]) -> DockerResource:
    config = value.get("Config", {}) if isinstance(value, dict) else {}
    labels = value.get("Labels", {}) or (config.get("Labels", {}) if isinstance(config, dict) else {})
    created_raw = value.get("Created") or value.get("CreatedAt") or labels.get(CREATED_LABEL)
    state = value.get("State", {}) if isinstance(value.get("State", {}), dict) else {}
    containers = value.get("Containers", {}) if isinstance(value.get("Containers", {}), dict) else {}
    return DockerResource(
        resource_id, kind, labels, _parse_timestamp(created_raw),
        running=bool(state.get("Running")),
        in_use=bool(containers),
        system=kind is ResourceKind.NETWORK and value.get("Name") in {"bridge", "host", "none"},
        name=value.get("Name"),
        use_known=kind is not ResourceKind.VOLUME,
    )
