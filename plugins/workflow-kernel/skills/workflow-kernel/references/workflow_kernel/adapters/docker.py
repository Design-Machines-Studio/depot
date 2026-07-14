"""Label-first Docker creation and positive-ownership cleanup planning."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol, Sequence, Tuple

from workflow_kernel.adapters.base import invalid_policy
from workflow_kernel.resources import (
    CleanupAction, CleanupDisposition, CleanupPlan, CleanupReceipt, CleanupScope,
    CommandResult, ResourceDisposition, ResourceKind, ResourceRecord,
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


class CommandRunner(Protocol):
    def run(self, argv: Tuple[str, ...]) -> CommandResult: ...


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


@dataclass(frozen=True)
class DockerInventory:
    resources: Tuple[DockerResource, ...]


@dataclass(frozen=True)
class DockerCreationPlan:
    argv: Tuple[str, ...]
    labels: Mapping[str, str]
    lifecycle: str
    registration_intents: Tuple[ResourceRegistrationIntent, ...]
    compose_override: Optional[Path] = None
    compose_override_content: Optional[str] = None
    project_name: Optional[str] = None
    environment: Mapping[str, str] = None
    managed: bool = True
    reason: Optional[str] = None


class DockerAdapter:
    def __init__(
        self, runner: CommandRunner, *, now: Optional[Callable[[], datetime]] = None,
        stop_timeout_seconds: int = 10,
    ):
        if type(stop_timeout_seconds) is not int or not 1 <= stop_timeout_seconds <= 60:
            raise invalid_policy("invalid_docker_stop_timeout")
        self.runner = runner
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.stop_timeout_seconds = stop_timeout_seconds

    def labels_for(self, run_id: str, node_id: str, lifecycle: str, cleanup_policy: str) -> dict[str, str]:
        if not all(type(x) is str and x for x in (run_id, node_id)):
            raise invalid_policy("invalid_docker_owner")
        if lifecycle not in ("chunk", "run"):
            raise invalid_policy("invalid_resource_lifecycle")
        if cleanup_policy not in ("stop-remove", "remove-when-stopped", "retain"):
            raise invalid_policy("invalid_cleanup_policy")
        created = self.now()
        if created.tzinfo is None:
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
        labels = self.labels_for(run_id, node_id, lifecycle, cleanup_policy)
        label_argv = tuple(part for key in REQUIRED_LABELS for part in ("--label", key + "=" + labels[key]))
        planned = command[:insert_at] + label_argv + command[insert_at:]
        expected_name = _explicit_name(command) if kind is ResourceKind.CONTAINER else (command[-1] if len(command) > insert_at else None)
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
        config_argv = _compose_config_argv(command)
        inspected = self.runner.run(config_argv)
        if inspected.exit_code != 0:
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_config_failed")
        try:
            config = json.loads(inspected.stdout)
            services = config.get("services", {})
            networks = config.get("networks", {})
            volumes = config.get("volumes", {})
            if not isinstance(services, dict) or not isinstance(networks, dict) or not isinstance(volumes, dict) or not services:
                raise ValueError
        except Exception:
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_config_invalid")
        for collection in (networks, volumes):
            if any(isinstance(value, dict) and value.get("external") for value in collection.values()):
                return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_external_resource")
        if _has_anonymous_volume(services):
            return DockerCreationPlan(command, {}, lifecycle, (), managed=False, reason="compose_anonymous_volume")

        labels = self.labels_for(run_id, node_id, lifecycle, cleanup_policy)
        project = _project_name(run_id, node_id)
        override_networks = {name: {"labels": labels} for name in networks}
        if "default" not in override_networks:
            override_networks["default"] = {"labels": labels}
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
        action_index = next((i for i, value in enumerate(command[2:], 2) if value in {"up", "create", "run", "start"}), len(command))
        planned_argv = (
            command[:2] + ("--project-name", project) + command[2:action_index]
            + ("-f", str(override_path)) + command[action_index:]
        )
        return DockerCreationPlan(
            planned_argv, labels, lifecycle, tuple(intents), override_path,
            json.dumps(override, sort_keys=True), project, {"COMPOSE_PROJECT_NAME": project},
        )

    def inventory(self) -> DockerInventory:
        """Inspect only resources carrying the positive managed label."""
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
                inspect_argv = _inspect_argv(kind, resource_id)
                result = self.runner.run(inspect_argv)
                if result.exit_code != 0:
                    resources.append(DockerResource(resource_id, kind, {}, self.now(), inspect_ok=False))
                    continue
                try:
                    value = json.loads(result.stdout)
                    if isinstance(value, list):
                        value = value[0]
                    resources.append(_resource_from_inspect(kind, resource_id, value))
                except Exception:
                    resources.append(DockerResource(resource_id, kind, {}, self.now(), inspect_ok=False))
        return DockerInventory(tuple(sorted(resources, key=_resource_key)))

    def record_creation(
        self, registry: ResourceRegistry, before: DockerInventory, after: DockerInventory,
        plan: DockerCreationPlan,
    ) -> CleanupReceipt:
        before_ids = {value.resource_id for value in before.resources}
        added = [value for value in after.resources if value.resource_id not in before_ids]
        dispositions = []
        unmatched = list(plan.registration_intents)
        for resource in sorted(added, key=_resource_key):
            intent = next((value for value in unmatched if value.kind is resource.kind and _labels_equal(resource.labels, value.labels)), None)
            if intent is None:
                dispositions.append(_docker_disposition(resource, CleanupDisposition.FOREIGN, "none", "creation_labels_or_intent_mismatch"))
                continue
            unmatched.remove(intent)
            record = ResourceRecord(
                resource.resource_id, resource.kind, intent.run_id, intent.node_id,
                intent.lifecycle, intent.cleanup_policy, resource.created_at,
                intent.dependent_node_ids, dict(resource.labels),
            )
            registry.register(record)
            dispositions.append(disposition_for(record, CleanupDisposition.REMOVED, "register", "creation_registered"))
        for intent in unmatched:
            placeholder = ResourceRecord(
                "missing:" + intent.kind.value + ":" + (intent.expected_name or "unnamed"),
                intent.kind, intent.run_id, intent.node_id, intent.lifecycle,
                intent.cleanup_policy, self.now(), intent.dependent_node_ids, intent.labels,
            )
            dispositions.append(disposition_for(placeholder, CleanupDisposition.MISSING, "none", "creation_not_observed"))
        return CleanupReceipt(
            tuple(sorted(before_ids)), tuple(sorted(value.resource_id for value in after.resources)),
            tuple(dispositions),
        )

    def plan_chunk_cleanup(
        self, registry: ResourceRegistry, inventory: DockerInventory, run_id: str, node_id: str,
    ) -> CleanupPlan:
        records = [value for value in registry.resources_for(run_id, node_id) if value.lifecycle == "chunk"]
        return self._plan_registered(registry, inventory, records, CleanupScope(run_id, node_id))

    def plan_reconcile_run(
        self, registry: ResourceRegistry, inventory: DockerInventory, run_id: str,
        *, active_node_ids: Sequence[str] = (), terminal: bool = False,
    ) -> CleanupPlan:
        records = list(registry.resources_for(run_id))
        return self._plan_registered(
            registry, inventory, records, CleanupScope(run_id, terminal=terminal),
            active_node_ids=set(active_node_ids),
        )

    def _plan_registered(
        self, registry: ResourceRegistry, inventory: DockerInventory,
        records: Sequence[ResourceRecord], scope: CleanupScope,
        *, active_node_ids: Optional[set[str]] = None,
    ) -> CleanupPlan:
        by_id = {value.resource_id: value for value in inventory.resources}
        actions = []
        dispositions = []
        active = active_node_ids or set()
        for record in sorted(records, key=lambda value: (KIND_ORDER.get(value.kind, 9), value.resource_id)):
            resource = by_id.get(record.resource_id)
            if resource is None:
                dispositions.append(disposition_for(record, CleanupDisposition.MISSING, "none", "resource_already_absent"))
                continue
            if not _registry_labels_agree(record, resource):
                dispositions.append(disposition_for(record, CleanupDisposition.FOREIGN, "none", "registry_label_disagreement"))
                continue
            if any(node in active for node in record.dependent_node_ids):
                dependent_ids = tuple(sorted(node for node in record.dependent_node_ids if node in active))
                dispositions.append(disposition_for(
                    record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none",
                    "active_dependent_node", evidence=("dependent_node=" + node for node in dependent_ids),
                ))
                continue
            planned_actions, disposition = self._plan_one(
                record, resource, allow_stop=record.lifecycle == "chunk" or scope.terminal,
            )
            base = len(actions)
            actions.extend(_offset_dependencies(planned_actions, base))
            dispositions.append(disposition)
        return CleanupPlan(scope, tuple(sorted(by_id)), tuple(actions), tuple(dispositions))

    def plan_stale_sweep(
        self, inventory: DockerInventory, ttl: timedelta, *, active_run_ids: Sequence[str],
    ) -> CleanupPlan:
        if not isinstance(ttl, timedelta) or ttl.total_seconds() < 0:
            raise invalid_policy("invalid_resource_ttl")
        now = self.now()
        active = set(active_run_ids)
        actions = []
        dispositions = []
        for resource in sorted(inventory.resources, key=_resource_key):
            labels = resource.labels
            if not _complete_owned_labels(labels):
                dispositions.append(_docker_disposition(resource, CleanupDisposition.FOREIGN, "none", "incomplete_ownership_labels"))
                continue
            try:
                created = _parse_timestamp(labels[CREATED_LABEL])
            except Exception:
                dispositions.append(_docker_disposition(resource, CleanupDisposition.FOREIGN, "none", "invalid_created_at_label"))
                continue
            record = _record_from_resource(resource)
            if labels[RUN_LABEL] in active:
                dispositions.append(disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "active_run_lease"))
                continue
            if now - created <= ttl:
                dispositions.append(disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "ttl_not_expired"))
                continue
            planned_actions, disposition = self._plan_one(record, resource, allow_stop=False)
            base = len(actions)
            actions.extend(_offset_dependencies(planned_actions, base))
            dispositions.append(disposition)
        return CleanupPlan(CleanupScope("stale", stale_sweep=True), tuple(value.resource_id for value in inventory.resources), tuple(actions), tuple(dispositions))

    def _plan_one(
        self, record: ResourceRecord, resource: DockerResource, *, allow_stop: bool,
    ) -> tuple[Tuple[CleanupAction, ...], ResourceDisposition]:
        if not resource.inspect_ok:
            return (), disposition_for(record, CleanupDisposition.BLOCKED, "none", "docker_inspect_failed")
        if resource.system:
            return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "system_resource")
        if resource.in_use:
            return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "resource_in_use")
        if record.cleanup_policy == "retain":
            return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", "cleanup_policy_retain")
        actions = []
        if resource.kind is ResourceKind.CONTAINER:
            if resource.running:
                if not allow_stop or record.cleanup_policy != "stop-remove":
                    reason = "stale_running_container_never_stopped" if not allow_stop else "running_container_policy_forbids_stop"
                    return (), disposition_for(record, CleanupDisposition.RETAINED_FOR_DEPENDENCY, "none", reason)
                actions.append(CleanupAction(resource.resource_id, resource.kind, "stop", ("docker", "stop", "--time", str(self.stop_timeout_seconds), resource.resource_id)))
            actions.append(CleanupAction(resource.resource_id, resource.kind, "remove", ("docker", "rm", resource.resource_id), 0 if actions else None))
        elif resource.kind is ResourceKind.NETWORK:
            actions.append(CleanupAction(resource.resource_id, resource.kind, "remove", ("docker", "network", "rm", resource.resource_id)))
        elif resource.kind is ResourceKind.VOLUME:
            actions.append(CleanupAction(resource.resource_id, resource.kind, "remove", ("docker", "volume", "rm", resource.resource_id)))
        else:
            return (), disposition_for(record, CleanupDisposition.FOREIGN, "none", "unsupported_docker_resource_kind")
        return tuple(actions), disposition_for(record, CleanupDisposition.REMOVED, "remove_exact_id", "owned_cleanup_planned")

    def record_results(
        self, plan: CleanupPlan, results: Sequence[CommandResult], after: DockerInventory,
    ) -> CleanupReceipt:
        """Record executor results without issuing any command."""
        by_argv = {result.argv: result for result in results}
        after_ids = {value.resource_id for value in after.resources}
        by_resource: dict[str, list[CleanupAction]] = {}
        for action in plan.actions:
            by_resource.setdefault(action.resource_id, []).append(action)
        dispositions = []
        for planned in plan.dispositions:
            if planned.disposition is not CleanupDisposition.REMOVED:
                dispositions.append(planned)
                continue
            if planned.resource_id not in after_ids:
                dispositions.append(ResourceDisposition(
                    planned.resource_id, planned.kind, planned.run_id, planned.node_id,
                    planned.lifecycle, CleanupDisposition.MISSING, "none", "resource_absent_after_cleanup",
                ))
                continue
            resource_actions = by_resource.get(planned.resource_id, ())
            failures = [(action, by_argv[action.argv]) for action in resource_actions if action.argv in by_argv and by_argv[action.argv].exit_code != 0]
            if failures:
                failed_action, failed_result = failures[0]
                reason = {
                    "stop": "container_stop_failed",
                    "remove": planned.kind.value + "_remove_failed",
                }.get(failed_action.action, "cleanup_command_failed")
                dispositions.append(ResourceDisposition(
                    planned.resource_id, planned.kind, planned.run_id, planned.node_id,
                    planned.lifecycle, CleanupDisposition.BLOCKED, "remove_exact_id",
                    reason, ("argv=" + " ".join(failed_action.argv), "exit=" + str(failed_result.exit_code)),
                    "retry exact owned resource cleanup",
                ))
            else:
                dispositions.append(ResourceDisposition(
                    planned.resource_id, planned.kind, planned.run_id, planned.node_id,
                    planned.lifecycle, CleanupDisposition.BLOCKED, "remove_exact_id",
                    "resource_still_present", (), "inspect dependency or retry exact removal",
                ))
        return CleanupReceipt(plan.before, tuple(sorted(after_ids)), tuple(dispositions))


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError
    return parsed


def _explicit_name(argv: Tuple[str, ...]) -> Optional[str]:
    for index, part in enumerate(argv):
        if part in ("--name",) and index + 1 < len(argv):
            return argv[index + 1]
        if part.startswith("--name="):
            return part.split("=", 1)[1]
    return None


def _compose_config_argv(argv: Tuple[str, ...]) -> Tuple[str, ...]:
    actions = {"up", "create", "run", "start"}
    index = next((i for i, value in enumerate(argv[2:], 2) if value in actions), len(argv))
    return argv[:index] + ("config", "--format", "json")


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


def _labels_equal(actual: Mapping[str, str], expected: Mapping[str, str]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items()) and _complete_owned_labels(actual)


def _complete_owned_labels(labels: Mapping[str, str]) -> bool:
    return labels.get(MANAGED_LABEL) == "true" and all(type(labels.get(key)) is str and labels.get(key) for key in REQUIRED_LABELS)


def _registry_labels_agree(record: ResourceRecord, resource: DockerResource) -> bool:
    labels = resource.labels
    return (
        _complete_owned_labels(labels)
        and labels[RUN_LABEL] == record.run_id and labels[NODE_LABEL] == record.node_id
        and labels[LIFECYCLE_LABEL] == record.lifecycle and labels[POLICY_LABEL] == record.cleanup_policy
        and (not record.labels or _labels_equal(labels, record.labels))
    )


def _record_from_resource(resource: DockerResource) -> ResourceRecord:
    labels = resource.labels
    return ResourceRecord(
        resource.resource_id, resource.kind, labels[RUN_LABEL], labels[NODE_LABEL],
        labels[LIFECYCLE_LABEL], labels[POLICY_LABEL], _parse_timestamp(labels[CREATED_LABEL]),
        (), dict(labels),
    )


def _docker_disposition(resource, disposition, action, reason):
    labels = resource.labels
    return ResourceDisposition(
        resource.resource_id, resource.kind, labels.get(RUN_LABEL, "unknown"),
        labels.get(NODE_LABEL, "unknown"), labels.get(LIFECYCLE_LABEL, "unknown"),
        disposition, action, reason,
    )


def _resource_key(value: DockerResource):
    return (KIND_ORDER.get(value.kind, 9), value.resource_id)


def _offset_dependencies(actions: Sequence[CleanupAction], offset: int) -> Tuple[CleanupAction, ...]:
    return tuple(
        CleanupAction(value.resource_id, value.kind, value.action, value.argv,
                      None if value.requires_success_of is None else value.requires_success_of + offset)
        for value in actions
    )


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
    usage = value.get("UsageData", {}) if isinstance(value.get("UsageData", {}), dict) else {}
    return DockerResource(
        resource_id, kind, labels, _parse_timestamp(created_raw),
        running=bool(state.get("Running")),
        in_use=bool(containers) or bool(usage.get("RefCount", 0) > 0),
        system=kind is ResourceKind.NETWORK and value.get("Name") in {"bridge", "host", "none"},
        name=value.get("Name"),
    )
