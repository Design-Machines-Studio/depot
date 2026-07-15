"""Repo-local argparse interface for workflow-kernel ledgers."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ._files import _OwnedResourceScope, bind_durable_path
from .events import EventStore
from .schema import (
    CorruptEventError, ErrorDetailKey, ErrorMessage, InvalidSchemaError, KernelError,
    RunMode, UnsafePayloadError, WorkflowEvent, serialize_kernel_error,
)
from .state import RunLease, StateStore, _prepare_replay_state
from .transitions import TransitionEngine


EXIT_INVALID = 2
EXIT_UNSAFE_PLAN = 3
EXIT_RUNTIME_UNAVAILABLE = 4
EXIT_PARITY_GAP = 5
EXIT_CONFLICT = 6
MAX_JSON_BYTES = 16 * 1024 * 1024


class RuntimeUnavailableError(OSError):
    pass


class KernelArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        match = re.search(r"argument ([^:]+)", message)
        option = match.group(1) if match else "command"
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument", ErrorDetailKey.OPTION.value: option,
        })


def _paths(directory):
    root = Path(directory)
    if not root.is_dir():
        raise InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_UNINITIALIZED)
    bound_root = bind_durable_path(root / "run-state.json").path.parent
    states = StateStore(bound_root / "run-state.json")
    return bound_root, EventStore(bound_root), states


def _emit(value, stream=sys.stdout):
    stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _load_optional_state(states):
    """Return verified state or None only for a missing file in a live parent."""
    try:
        return states.load()
    except FileNotFoundError:
        return None


def _require_materialized_matches_ledger(materialized, reconstructed):
    if materialized is not None and materialized != reconstructed:
        raise InvalidSchemaError(ErrorMessage.STATE_LEDGER_MISMATCH, {
            ErrorDetailKey.MATERIALIZED_REVISION.value: materialized.revision,
            ErrorDetailKey.LEDGER_REVISION.value: reconstructed.revision,
        })


def _observe_consistent_run(events, states, engine, *, recovery, empty_error):
    replayed, notes = events.validate(recovery=recovery)
    if not replayed:
        raise empty_error
    reconstructed = engine.reconstruct(replayed)
    materialized = _load_optional_state(states)
    _require_materialized_matches_ledger(materialized, reconstructed)
    return replayed, notes, reconstructed, materialized


def _append_and_publish(events, states, event, next_state, *,
                        expected_sequence, expected_revision, lease):
    prepared = states.prepare(next_state)
    events.append(event, expected_sequence=expected_sequence, lease=lease)
    return states.publish(prepared, expected_revision, lease=lease)


@contextmanager
def _coordinated_run(states):
    """Hold the run lease from mutable observation through publication."""
    with RunLease(states.path) as lease:
        yield lease


def command_init(args):
    root = Path(args.directory)
    root.mkdir(parents=True, exist_ok=True)
    root, events, states = _paths(root)
    with _coordinated_run(states) as lease:
        events.require_absent()
        states.require_absent()
        event = WorkflowEvent(1, 0, args.run_id, None, "run.initialized", args.occurred_at, {"mode": args.mode})
        state = TransitionEngine().reconstruct((event,))
        evidence = _append_and_publish(
            events, states, event, state, expected_sequence=0,
            expected_revision=-1, lease=lease,
        )
    _emit({"run_id": state.run_id, "mode": state.mode.value, "status": state.status.value, "revision": state.revision,
           "durability": evidence})
    return 0


def command_validate(args):
    _, events, states = _paths(args.directory)
    engine = TransitionEngine()
    with _coordinated_run(states):
        replayed, notes, _, _ = _observe_consistent_run(
            events, states, engine, recovery=args.recovery,
            empty_error=CorruptEventError(ErrorMessage.AUTHORITATIVE_LEDGER_MISSING),
        )
    _emit({"valid": True, "event_count": len(replayed), "notes": list(notes)})
    return 0


def command_append(args):
    _, events, states = _paths(args.directory)
    try:
        data = json.loads(args.event)
    except json.JSONDecodeError as exc:
        raise InvalidSchemaError(ErrorMessage.EVENT_INVALID_JSON, {ErrorDetailKey.OFFSET.value: exc.pos}) from None
    except RecursionError:
        raise InvalidSchemaError(ErrorMessage.EVENT_INVALID_JSON, {
            ErrorDetailKey.REASON_CODE.value: "recursion_limit",
        }) from None
    event = WorkflowEvent.from_dict(data)
    engine = TransitionEngine()
    with _coordinated_run(states) as lease:
        existing, _, state, materialized = _observe_consistent_run(
            events, states, engine, recovery=False,
            empty_error=InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_UNINITIALIZED),
        )
        expected = materialized.revision if materialized is not None else -1
        next_state = engine.apply(state, event)
        evidence = _append_and_publish(
            events, states, event, next_state, expected_sequence=len(existing),
            expected_revision=expected, lease=lease,
        )
    _emit({"appended": event.sequence, "revision": next_state.revision, "status": next_state.status.value,
           "durability": evidence})
    return 0


def command_replay(args):
    _, events, states = _paths(args.directory)
    engine = TransitionEngine()
    with _coordinated_run(states) as lease:
        reconstructed = engine.reconstruct(events.replay())
        materialized = _load_optional_state(states)
        expected = materialized.revision if materialized is not None else -1
        prepared = _prepare_replay_state(states, reconstructed, expected)
        evidence = states.publish(prepared, expected, lease=lease)
    _emit({"run_id": reconstructed.run_id, "revision": reconstructed.revision,
           "status": reconstructed.status.value, "durability": evidence})
    return 0


def command_status(args):
    _, _, states = _paths(args.directory)
    _emit(states.load().to_dict())
    return 0


def _load_json(path):
    try:
        binding = bind_durable_path(Path(path))
        with _OwnedResourceScope() as owned:
            directory = owned.pin(binding)
            descriptor = owned.own(directory.open_regular(binding.path.name, os.O_RDONLY))
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(65536, MAX_JSON_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_JSON_BYTES:
                    raise ValueError("json input too large")
            return json.loads(b"".join(chunks).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_json_input",
        }) from None


def _write_json(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ) + "\n").encode("utf-8")
    binding = bind_durable_path(destination)
    with _OwnedResourceScope() as owned:
        directory = owned.pin(binding)
        directory.revalidate()
        directory.regular_exists(binding.path.name)
        descriptor, temporary = directory.create_temporary(
            binding.path.name + ".tmp-", ".json",
        )
        owned.own_temporary(descriptor, temporary)
        pending = encoded
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("json write made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
        directory.require_identity(descriptor, temporary)
        directory.replace(temporary, binding.path.name)
        owned.disown_temporary()
        directory.fsync()


def _profile_from_receipts(receipts):
    from .adapters.base import HostCapabilities

    host = "generic"
    if receipts and isinstance(receipts[0], dict):
        candidate = receipts[0].get("host")
        if type(candidate) is str and candidate:
            host = candidate
    return HostCapabilities(host, frozenset())


def _observed_state(run_id, events):
    refs = [event.payload["authoritative_receipt"] for event in events]
    first = events[0].occurred_at if events else "1970-01-01T00:00:00Z"
    last = events[-1].occurred_at if events else first
    return {
        "schema_version": 1, "revision": len(events), "run_id": run_id,
        "mode": "shadow", "status": "running", "created_at": first,
        "updated_at": last, "nodes": {}, "evidence": refs,
        "cleanup_reconciled": False,
    }


def command_observe_pipeline(args):
    from .pipeline_adapter import translate_manifest, translate_pipeline_receipts

    manifest = _load_json(args.manifest)
    receipts = _load_json(args.receipts)
    if not isinstance(manifest, dict) or not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    spec = translate_manifest(manifest, _profile_from_receipts(receipts))
    events = translate_pipeline_receipts(receipts)
    artifact = {
        "run_spec": spec.to_dict(), "event_count": len(events),
        "events": [event.to_dict() for event in events],
        "run_state": _observed_state(spec.run_id, events),
        "observation_only": True,
    }
    output = Path(args.state_dir) / "pipeline-shadow-observation.json"
    _write_json(output, artifact)
    _emit({"observed": True, "event_count": len(events), "output": str(output)})
    return 0


def command_observe_review(args):
    from .dm_review_adapter import ReviewRequest, translate_review, translate_review_receipts

    request = ReviewRequest.from_mapping(_load_json(args.request))
    receipts = _load_json(args.receipts)
    if not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    spec = translate_review(request, _profile_from_receipts(receipts))
    events = translate_review_receipts(receipts)
    artifact = {
        "run_spec": spec.to_dict(), "event_count": len(events),
        "events": [event.to_dict() for event in events],
        "run_state": _observed_state(spec.run_id, events),
        "observation_only": True,
    }
    output = Path(args.state_dir) / "review-shadow-observation.json"
    _write_json(output, artifact)
    _emit({"observed": True, "event_count": len(events), "output": str(output)})
    return 0


def command_compare(args):
    from .pipeline_adapter import translate_pipeline_receipts
    from .schema import RunState
    from .shadow import ReceiptSet, ShadowComparator

    state_dir = Path(args.state_dir)
    observation = state_dir / "pipeline-shadow-observation.json"
    if not observation.is_file():
        observation = state_dir / "review-shadow-observation.json"
    document = _load_json(observation)
    receipts = _load_json(args.authoritative_receipts)
    if not isinstance(document, dict) or not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    try:
        events = translate_pipeline_receipts(receipts)
    except ValueError:
        from .dm_review_adapter import translate_review_receipts
        events = translate_review_receipts(receipts)
    raw_events = document.get("events")
    if type(raw_events) is not list:
        report = ShadowComparator().compare(
            RunState.from_dict(document["run_state"]),
            ReceiptSet.from_events(events),
        )
        _write_json(args.output, report.to_dict())
        return 0 if report.semantic_match else EXIT_PARITY_GAP
    predicted = ReceiptSet.from_events(
        WorkflowEvent.from_dict(value) for value in raw_events
    )
    report = ShadowComparator().compare_receipt_sets(
        predicted, ReceiptSet.from_events(events),
    )
    _write_json(args.output, report.to_dict())
    return 0 if report.semantic_match else EXIT_PARITY_GAP


def command_metrics(args):
    from .dm_review_adapter import translate_review_receipts
    from .metrics import MetricsAggregator
    from .pipeline_adapter import translate_pipeline_receipts

    receipts = _load_json(args.events)
    if not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    try:
        events = translate_pipeline_receipts(receipts)
    except ValueError:
        events = translate_review_receipts(receipts)
    report = MetricsAggregator().aggregate(events)
    _write_json(args.output, report.to_dict())
    return 0


def resolve_workflow_kernel_runtime(canonical_plugin_root, *, home=None):
    """Resolve only the canonical Depot sibling, then named versioned caches."""
    source = Path(canonical_plugin_root).resolve(strict=True)
    if source.name not in {"pipeline", "dm-review"} or source.parent.name != "plugins":
        raise ValueError("invalid canonical plugin root")
    depot = source.parent.parent.resolve(strict=True)
    lexical_depot = Path(os.path.abspath(str(canonical_plugin_root))).parent.parent
    home = Path.home() if home is None else Path(home)
    roots = [(lexical_depot / "plugins" / "workflow-kernel", depot)]
    for cache_name in (".claude", ".codex"):
        cache = home / cache_name / "plugins" / "cache" / "depot" / "workflow-kernel"
        if cache.is_dir():
            roots.extend((candidate, cache.resolve(strict=True)) for candidate in sorted(cache.iterdir(), reverse=True))
    for candidate, boundary in roots:
        try:
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(boundary):
                continue
            manifest = resolved / ".claude-plugin" / "plugin.json"
            if not manifest.is_file():
                manifest = resolved / ".codex-plugin" / "plugin.json"
            document = _load_json(manifest)
            version = document.get("version") if type(document) is dict else None
            if document.get("name") != "workflow-kernel" or type(version) is not str or not re.fullmatch(r"(?:0\.1|1\.0)(?:\.[0-9]+)?", version):
                continue
            references = resolved / "skills" / "workflow-kernel" / "references"
            lexical_references = candidate / "skills" / "workflow-kernel" / "references"
            package = references / "workflow_kernel"
            if package.is_dir() and (package / "__main__.py").is_file() and package.resolve(strict=True).is_relative_to(resolved):
                return lexical_references
        except (OSError, ValueError, InvalidSchemaError):
            continue
    raise FileNotFoundError("compatible workflow-kernel runtime unavailable")


class _SubprocessRunner:
    def run(self, argv):
        from .resources import CommandResult
        try:
            result = subprocess.run(
                tuple(argv), text=True, capture_output=True, check=False,
            )
        except FileNotFoundError:
            raise RuntimeUnavailableError("docker runtime unavailable") from None
        return CommandResult(tuple(argv), result.returncode, result.stdout, result.stderr)


def _registry(state_dir):
    from .resources import ResourceRegistry
    return ResourceRegistry(Path(state_dir) / "resources.jsonl")


def _creation_plan_dict(plan):
    return {
        "schema_version": 1, "argv": list(plan.argv), "labels": dict(plan.labels),
        "lifecycle": plan.lifecycle,
        "registration_intents": [{
            "kind": value.kind.value, "expected_name": value.expected_name,
            "run_id": value.run_id, "node_id": value.node_id,
            "lifecycle": value.lifecycle, "cleanup_policy": value.cleanup_policy,
            "labels": dict(value.labels),
            "dependent_node_ids": list(value.dependent_node_ids),
        } for value in plan.registration_intents],
        "compose_override": None if plan.compose_override is None else str(plan.compose_override),
        "compose_override_content": plan.compose_override_content,
        "project_name": plan.project_name,
        "environment": None if plan.environment is None else dict(plan.environment),
        "managed": plan.managed, "reason": plan.reason,
    }


def _creation_plan(value):
    from .adapters.docker import DockerCreationPlan
    from .resources import ResourceKind, ResourceRegistrationIntent
    if type(value) is not dict or type(value.get("registration_intents")) is not list:
        raise ValueError("invalid creation plan")
    intents = tuple(ResourceRegistrationIntent(
        ResourceKind(item["kind"]), item.get("expected_name"), item["run_id"],
        item["node_id"], item["lifecycle"], item["cleanup_policy"],
        dict(item["labels"]), tuple(item.get("dependent_node_ids", ())),
    ) for item in value["registration_intents"] if type(item) is dict)
    if len(intents) != len(value["registration_intents"]):
        raise ValueError("invalid creation plan")
    override = value.get("compose_override")
    return DockerCreationPlan(
        tuple(value["argv"]), dict(value["labels"]), value["lifecycle"], intents,
        None if override is None else Path(override),
        value.get("compose_override_content"), value.get("project_name"),
        value.get("environment"), value.get("managed", True), value.get("reason"),
    )


def _command_result(value):
    from .resources import CommandResult
    if type(value) is not dict:
        raise ValueError("invalid command result")
    return CommandResult(
        tuple(value["argv"]), value["exit_code"],
        value.get("stdout", ""), value.get("stderr", ""),
    )


def _inventory(value):
    from .adapters.docker import DockerInventory, DockerResource
    from .resources import ResourceKind
    if type(value) is not dict or type(value.get("resources")) is not list:
        raise ValueError("invalid Docker inventory")
    resources = tuple(DockerResource(
        item["resource_id"], ResourceKind(item["kind"]), dict(item["labels"]),
        datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
        item.get("running", False), item.get("in_use", False),
        item.get("system", False), item.get("inspect_ok", True),
        item.get("name"), item.get("use_known", True),
    ) for item in value["resources"] if type(item) is dict)
    if len(resources) != len(value["resources"]):
        raise ValueError("invalid Docker inventory")
    return DockerInventory(
        resources,
        tuple((ResourceKind(row[0]), row[1]) for row in value.get("queried", ())),
        tuple((ResourceKind(row[0]), row[1]) for row in value.get("absent", ())),
        value.get("source", "provided"), (),
    )


def _inventory_dict(value):
    return {
        "resources": [{
            "resource_id": item.resource_id, "kind": item.kind.value,
            "labels": dict(item.labels),
            "created_at": item.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "running": item.running, "in_use": item.in_use,
            "system": item.system, "inspect_ok": item.inspect_ok,
            "name": item.name, "use_known": item.use_known,
        } for item in value.resources],
        "queried": [[kind.value, resource_id] for kind, resource_id in value.queried],
        "absent": [[kind.value, resource_id] for kind, resource_id in value.absent],
        "source": value.source,
    }


def _cleanup_plan(value):
    from .resources import (
        CleanupAction, CleanupDisposition, CleanupPlan, CleanupScope,
        ResourceDisposition, ResourceKind,
    )
    if type(value) is not dict:
        raise ValueError("invalid cleanup plan")
    scope = value["scope"]
    actions = tuple(CleanupAction(
        item["resource_id"], ResourceKind(item["kind"]), item["action"],
        tuple(item["argv"]), item.get("requires_success_of"),
        item["owner"]["run_id"], item["owner"]["node_id"], item["lifecycle"],
        item["proof_digest"], tuple(item["preconditions"]),
        dict(item.get("environment", {})), item.get("predecessor_result_id"),
        item["evidence_digest"],
    ) for item in value["actions"])
    dispositions = tuple(ResourceDisposition(
        item["resource_id"], ResourceKind(item["kind"]),
        item["owner"]["run_id"], item["owner"]["node_id"], item["lifecycle"],
        CleanupDisposition(item["disposition"]), item["action"], item["reason"],
        tuple(item.get("evidence", ())), tuple(item.get("command_evidence", ())),
        item.get("follow_up"),
    ) for item in value["dispositions"])
    return CleanupPlan(
        CleanupScope(scope["run_id"], scope.get("node_id"),
                     scope.get("terminal", False), scope.get("stale_sweep", False)),
        tuple(value["before"]), actions, dispositions,
    )


def _proof(args, run_id=None):
    from .adapters.docker import IncompleteNodeProof
    from .schema import NodeStatus
    path = getattr(args, "node_statuses", None)
    if path is None:
        return None
    value = _load_json(path)
    if type(value) is not dict or type(value.get("node_statuses")) is not dict:
        raise ValueError("invalid node status proof")
    return IncompleteNodeProof(
        run_id or args.run_id,
        tuple((key, NodeStatus(status)) for key, status in sorted(value["node_statuses"].items())),
        value.get("readable", True),
        datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00")),
    )


def _plan_status(plan):
    from .resources import CleanupDisposition
    unsafe = {CleanupDisposition.BLOCKED, CleanupDisposition.RETAINED_FOR_DEPENDENCY}
    return EXIT_UNSAFE_PLAN if any(item.disposition in unsafe for item in plan.dispositions) else 0


def command_plan_create(args):
    from .adapters.docker import DockerAdapter
    argv = _load_json(args.argv_json)
    dependencies = ()
    if args.dependent_node_ids_json:
        dependencies = _load_json(args.dependent_node_ids_json)
    if type(argv) is not list or type(dependencies) not in {list, tuple}:
        raise ValueError("invalid Docker argv")
    plan = DockerAdapter(_SubprocessRunner()).plan_create(
        argv, args.run_id, args.node_id, args.lifecycle, args.cleanup_policy,
        dependent_node_ids=tuple(dependencies),
    )
    _write_json(args.output, _creation_plan_dict(plan))
    return 0 if plan.managed else EXIT_UNSAFE_PLAN


def command_plan_compose(args):
    from .adapters.docker import DockerAdapter
    argv = _load_json(args.argv_json)
    dependencies = () if not args.dependent_node_ids_json else _load_json(args.dependent_node_ids_json)
    if type(argv) is not list or type(dependencies) not in {list, tuple}:
        raise ValueError("invalid Docker argv")
    plan = DockerAdapter(_SubprocessRunner()).plan_compose(
        argv, args.run_id, args.node_id, args.lifecycle, args.cleanup_policy,
        dependent_node_ids=tuple(dependencies),
    )
    _write_json(args.output, _creation_plan_dict(plan))
    return 0 if plan.managed else EXIT_UNSAFE_PLAN


def command_record_create(args):
    from .adapters.docker import DockerAdapter
    from .resources import _disposition_json, _resource_json
    receipt = DockerAdapter(_SubprocessRunner()).record_creation(
        _registry(args.state_dir), _creation_plan(_load_json(args.plan)),
        _command_result(_load_json(args.result)),
        _inventory(_load_json(args.before_inventory)),
        _inventory(_load_json(args.after_inventory)),
    )
    _emit({
        "command_succeeded": receipt.command_succeeded,
        "before": list(receipt.before), "after": list(receipt.after),
        "registered": [_resource_json(item) for item in receipt.registered],
        "dispositions": [_disposition_json(item) for item in receipt.dispositions],
    })
    return 0 if receipt.command_succeeded else EXIT_UNSAFE_PLAN


def _registered_inventory(adapter, registry, run_id, node_id=None):
    return adapter.inventory_registered(registry.resources_for(run_id, node_id))


def command_plan_cleanup(args):
    from .adapters.docker import DockerAdapter
    adapter = DockerAdapter(_SubprocessRunner())
    registry = _registry(args.state_dir)
    inventory = _registered_inventory(adapter, registry, args.run_id, args.node_id)
    if args.node_id is None:
        plan = adapter.plan_reconcile_run(
            registry, inventory, args.run_id,
            incomplete_node_proof=_proof(args), terminal=False,
        )
    else:
        plan = adapter.plan_chunk_cleanup(
            registry, inventory, args.run_id, args.node_id,
            incomplete_node_proof=_proof(args),
        )
    document = plan.to_dict(); document["_inventory"] = _inventory_dict(inventory)
    _write_json(args.output, document)
    return _plan_status(plan)


def command_plan_reconcile(args):
    from .adapters.docker import DockerAdapter
    adapter = DockerAdapter(_SubprocessRunner())
    registry = _registry(args.state_dir)
    inventory = _registered_inventory(adapter, registry, args.run_id)
    plan = adapter.plan_reconcile_run(
        registry, inventory, args.run_id,
        incomplete_node_proof=_proof(args), terminal=True,
    )
    stale_inventory = adapter.inventory()
    stale_plan = _stale_cleanup_plan(adapter, stale_inventory, args.ttl_hours)
    document = plan.to_dict(); document["_inventory"] = _inventory_dict(inventory)
    document["ttl_hours"] = args.ttl_hours
    document["stale_sweep"] = stale_plan.to_dict()
    document["_stale_inventory"] = _inventory_dict(stale_inventory)
    _write_json(args.output, document)
    return max(_plan_status(plan), _plan_status(stale_plan))


def _stale_cleanup_plan(adapter, inventory, ttl_hours):
    if type(ttl_hours) not in {int, float} or ttl_hours < 0:
        raise ValueError("invalid stale cleanup TTL")
    return adapter.plan_stale_sweep(inventory, timedelta(hours=float(ttl_hours)))


def command_next_cleanup_step(args):
    from .resources import cleanup_step_identities
    document = _load_json(args.plan); plan = _cleanup_plan(document)
    prior = _load_json(args.outcomes)
    if type(prior) is not list or len(prior) > len(cleanup_step_identities(plan)):
        raise ValueError("invalid cleanup results")
    identities = cleanup_step_identities(plan)
    authorities = tuple(_authority(item) for item in prior)
    if any(value.step_identity != identities[position]
           for position, value in enumerate(authorities)):
        raise ValueError("non-contiguous cleanup outcomes")
    output = {"complete": len(prior) == len(identities)}
    if len(prior) < len(identities):
        step = identities[len(prior)]
        output.update({"step_index": step.step_index, "step_type": step.step_type,
                       "plan_digest": step.plan_digest})
    _write_json(args.output, output)
    return 0


def _authority_dict(value):
    from .resources import GuardedCommandResult, _disposition_json
    result = {
        "type": "command" if type(value) is GuardedCommandResult else "terminal",
        "result": {"argv": list(value.result.argv), "exit_code": value.result.exit_code,
                   "stdout": value.result.stdout, "stderr": value.result.stderr},
        "state_generation": value.state_generation,
        "issued_at": value.issued_at.isoformat(), "expires_at": value.expires_at.isoformat(),
        "authority_id": value.authority_id,
        "step_identity": {"plan_digest": value.step_identity.plan_digest,
                          "step_index": value.step_identity.step_index,
                          "step_type": value.step_identity.step_type},
    }
    if type(value) is GuardedCommandResult:
        result.update({"kind": value.kind.value, "resource_id": value.resource_id,
                       "run_id": value.run_id, "node_id": value.node_id,
                       "action_digest": value.action_digest})
    else:
        result.update({"disposition": _disposition_json(value.disposition),
                       "evidence_digest": value.evidence_digest})
    return result


def _authority(value):
    from .resources import (
        CleanupStepIdentity, GuardedCommandResult, GuardedTerminalObservation,
        ResourceKind, _disposition_from_json,
    )
    if type(value) is not dict or type(value.get("step_identity")) is not dict:
        raise ValueError("invalid guarded authority")
    step = value["step_identity"]
    identity = CleanupStepIdentity(
        step["plan_digest"], step["step_index"], step["step_type"],
    )
    result = _command_result(value["result"])
    issued = datetime.fromisoformat(value["issued_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(value["expires_at"].replace("Z", "+00:00"))
    if value.get("type") == "command":
        return GuardedCommandResult(
            result, ResourceKind(value["kind"]), value["resource_id"],
            value["run_id"], value["node_id"], value["action_digest"],
            value["state_generation"], issued, expires, value["authority_id"], identity,
        )
    if value.get("type") == "terminal":
        return GuardedTerminalObservation(
            _disposition_from_json(value["disposition"]), result,
            value["evidence_digest"], value["state_generation"], issued,
            expires, value["authority_id"], identity,
        )
    raise ValueError("invalid guarded authority")


def command_execute_cleanup_step(args):
    from .adapters.docker import DockerAdapter
    from .resources import cleanup_step_identities
    document = _load_json(args.plan); plan = _cleanup_plan(document)
    identities = cleanup_step_identities(plan)
    if args.step_index < 0 or args.step_index >= len(identities):
        raise ValueError("invalid cleanup step")
    adapter = DockerAdapter(_SubprocessRunner())
    registry = _registry(args.state_dir)
    proof = _proof(args, plan.scope.run_id)
    prior = _load_json(args.outcomes)
    if type(prior) is not list:
        raise ValueError("invalid prior cleanup results")
    authorities = tuple(_authority(item) for item in prior)
    if len(authorities) != args.step_index or any(
        value.step_identity != identities[position]
        for position, value in enumerate(authorities)
    ):
        raise ValueError("non-contiguous cleanup outcomes")
    predecessor = authorities[-1].result if authorities else None
    identity = identities[args.step_index]
    if identity.step_type == "terminal_observation":
        guarded = registry.observe_guarded_absence(
            adapter, plan, args.step_index, adapter.runner.run,
        )
    else:
        action = plan.actions[args.step_index]
        record, active = registry.resource_state_for_exact(action.kind, action.resource_id)
        if not active or record is None:
            raise ValueError("cleanup resource is not active")
        supplied = _inventory(_load_json(args.inventory))
        current = adapter.inventory_registered((record,))
        resource = next((item for item in current.resources
                         if item.kind is action.kind and item.resource_id == action.resource_id), None)
        supplied_resource = next((item for item in supplied.resources
                                  if item.kind is action.kind and item.resource_id == action.resource_id), None)
        if resource is None or supplied_resource is None:
            raise ValueError("cleanup resource unavailable")
        guarded = registry.execute_guarded_action(
            adapter, plan, args.step_index, resource, adapter.runner.run,
            predecessor_result=predecessor, incomplete_node_proof=proof,
        )
    _write_json(args.output, _authority_dict(guarded))
    return 0


def command_record_cleanup(args):
    from .adapters.docker import DockerAdapter
    document = _load_json(args.plan); plan = _cleanup_plan(document)
    raw_results = _load_json(args.outcomes)
    if type(raw_results) is not list:
        raise ValueError("invalid guarded cleanup results")
    results = tuple(_authority(item) for item in raw_results)
    adapter = DockerAdapter(_SubprocessRunner())
    registry = _registry(args.state_dir)
    before = _inventory(document.get("_inventory", {"resources": []}))
    after = adapter.inventory_registered(registry.resources_for(plan.scope))
    receipt = registry.record_guarded_results(
        adapter, plan, results, before, after,
    )
    _emit(receipt.to_dict())
    return 0


def parser():
    result = KernelArgumentParser(prog="workflow_kernel", description="Durable workflow state kernel")
    commands = result.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="initialize a shadow-mode run")
    init.add_argument("directory")
    init.add_argument("--run-id", required=True)
    init.add_argument("--mode", choices=[item.value for item in RunMode], default=RunMode.SHADOW.value)
    init.add_argument("--occurred-at", required=True, help="timezone-aware ISO-8601 timestamp")
    init.set_defaults(handler=command_init)

    validate = commands.add_parser("validate", help="validate a ledger and materialized state")
    validate.add_argument("directory")
    validate.add_argument("--recovery", action="store_true", help="report and ignore only a truncated final record")
    validate.set_defaults(handler=command_validate)

    append = commands.add_parser("append", help="validate and append one event JSON object")
    append.add_argument("directory")
    append.add_argument("--event", required=True)
    append.set_defaults(handler=command_append)

    replay = commands.add_parser("replay", help="reconstruct run-state.json from events.jsonl")
    replay.add_argument("directory")
    replay.set_defaults(handler=command_replay)

    status = commands.add_parser("status", help="print materialized state")
    status.add_argument("directory")
    status.set_defaults(handler=command_status)

    observe_pipeline = commands.add_parser("observe-pipeline", help="observe authoritative pipeline receipts")
    observe_pipeline.add_argument("--manifest", required=True)
    observe_pipeline.add_argument("--receipts", required=True)
    observe_pipeline.add_argument("--state-dir", required=True)
    observe_pipeline.set_defaults(handler=command_observe_pipeline)

    observe_review = commands.add_parser("observe-review", help="observe authoritative review receipts")
    observe_review.add_argument("--request", required=True)
    observe_review.add_argument("--receipts", required=True)
    observe_review.add_argument("--state-dir", required=True)
    observe_review.set_defaults(handler=command_observe_review)

    compare = commands.add_parser("compare", help="compare shadow state with authoritative receipts")
    compare.add_argument("--state-dir", required=True)
    compare.add_argument("--authoritative-receipts", required=True)
    compare.add_argument("--output", required=True)
    compare.set_defaults(handler=command_compare)

    metrics = commands.add_parser("metrics", help="aggregate receipt reliability metrics")
    metrics.add_argument("--events", required=True)
    metrics.add_argument("--output", required=True)
    metrics.set_defaults(handler=command_metrics)

    def creation_command(name, handler):
        command = commands.add_parser(name, help="plan one managed Docker creation")
        command.add_argument("--state-dir", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--node-id", required=True)
        command.add_argument("--lifecycle", choices=("chunk", "run"), required=True)
        command.add_argument("--cleanup-policy", choices=("stop-remove", "remove-when-stopped", "retain"), required=True)
        command.add_argument("--argv-json", required=True)
        command.add_argument("--dependent-node-ids-json")
        command.add_argument("--output", required=True)
        command.set_defaults(handler=handler)

    creation_command("plan-create", command_plan_create)
    creation_command("plan-compose", command_plan_compose)

    record_create = commands.add_parser("record-create", help="record an observed managed Docker creation")
    record_create.add_argument("--state-dir", required=True)
    record_create.add_argument("--plan", required=True)
    record_create.add_argument("--result", required=True)
    record_create.add_argument("--before-inventory", required=True)
    record_create.add_argument("--after-inventory", required=True)
    record_create.set_defaults(handler=command_record_create)

    plan_cleanup = commands.add_parser("plan-cleanup", help="plan registered resource cleanup")
    plan_cleanup.add_argument("--state-dir", required=True)
    plan_cleanup.add_argument("--run-id", required=True)
    plan_cleanup.add_argument("--node-id")
    plan_cleanup.add_argument("--node-statuses")
    plan_cleanup.add_argument("--output", required=True)
    plan_cleanup.set_defaults(handler=command_plan_cleanup)

    next_step = commands.add_parser("next-cleanup-step", help="select the next sealed cleanup-plan step")
    next_step.add_argument("--state-dir", required=True)
    next_step.add_argument("--plan", required=True)
    next_step.add_argument("--outcomes", "--results", dest="outcomes", required=True)
    next_step.add_argument("--output", required=True)
    next_step.set_defaults(handler=command_next_cleanup_step)

    execute_step = commands.add_parser("execute-cleanup-step", help="execute one sealed cleanup step under registry guard")
    execute_step.add_argument("--state-dir", required=True)
    execute_step.add_argument("--plan", required=True)
    execute_step.add_argument("--step-index", type=int, required=True)
    execute_step.add_argument("--inventory", required=True)
    execute_step.add_argument("--node-statuses", required=True)
    execute_step.add_argument("--outcomes", "--prior-results", dest="outcomes", required=True)
    execute_step.add_argument("--output", required=True)
    execute_step.set_defaults(handler=command_execute_cleanup_step)

    record_cleanup = commands.add_parser("record-cleanup", help="persist guarded cleanup results")
    record_cleanup.add_argument("--state-dir", required=True)
    record_cleanup.add_argument("--plan", required=True)
    record_cleanup.add_argument("--outcomes", "--results", dest="outcomes", required=True)
    record_cleanup.set_defaults(handler=command_record_cleanup)

    reconcile = commands.add_parser("plan-reconcile", help="plan terminal registered-resource reconciliation")
    reconcile.add_argument("--state-dir", required=True)
    reconcile.add_argument("--run-id", required=True)
    reconcile.add_argument("--ttl-hours", type=float, default=24.0)
    reconcile.add_argument("--node-statuses")
    reconcile.add_argument("--output", required=True)
    reconcile.set_defaults(handler=command_plan_reconcile)
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        return args.handler(args)
    except KernelError as exc:
        _emit(serialize_kernel_error(exc), sys.stderr)
        if exc.code in {"sequence_conflict", "revision_conflict", "lease_conflict"}:
            return EXIT_CONFLICT
        reason = exc.details.get(ErrorDetailKey.REASON_CODE.value)
        if reason in {
            "resource_registration_conflict", "cleanup_result_transaction_already_recorded",
            "resource_execution_guard_busy", "execution_authority_already_consumed",
        }:
            return EXIT_CONFLICT
        return EXIT_INVALID
    except RuntimeUnavailableError as exc:
        error = UnsafePayloadError(ErrorMessage.OPERATION_FAILED, {
            ErrorDetailKey.EXCEPTION_TYPE.value: type(exc).__name__,
        })
        _emit(serialize_kernel_error(error), sys.stderr)
        return EXIT_RUNTIME_UNAVAILABLE
    except (OSError, ValueError, TypeError) as exc:
        error = UnsafePayloadError(ErrorMessage.OPERATION_FAILED, {
            ErrorDetailKey.EXCEPTION_TYPE.value: type(exc).__name__,
        })
        _emit(serialize_kernel_error(error), sys.stderr)
        return EXIT_INVALID
