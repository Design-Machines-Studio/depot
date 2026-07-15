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


def _require_spec_receipt_context(spec, events):
    if not events:
        raise ValueError("receipt context missing")
    expected = (
        spec.run_id, spec.workflow_class.value,
        spec.workflow_class_defaulted, spec.execution_mode,
    )
    for event in events:
        actual = (
            event.run_id, event.payload.get("workflow_class"),
            event.payload.get("workflow_class_defaulted"),
            event.payload.get("execution_mode"),
        )
        if actual != expected:
            raise ValueError("run spec receipt context mismatch")


def command_observe_pipeline(args):
    from .pipeline_adapter import translate_manifest, translate_pipeline_receipts

    manifest = _load_json(args.manifest)
    receipts = _load_json(args.receipts)
    if not isinstance(manifest, dict) or not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    spec = translate_manifest(manifest, _profile_from_receipts(receipts))
    events = translate_pipeline_receipts(receipts)
    _require_spec_receipt_context(spec, events)
    artifact = {
        "observation_type": "pipeline",
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
    _require_spec_receipt_context(spec, events)
    artifact = {
        "observation_type": "review",
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
    from .shadow import ParityReport, ReceiptSet, ShadowComparator

    state_dir = Path(args.state_dir)
    observation = state_dir / "pipeline-shadow-observation.json"
    if not observation.is_file():
        observation = state_dir / "review-shadow-observation.json"
    document = _load_json(observation)
    receipts = _load_json(args.authoritative_receipts)
    if not isinstance(document, dict) or not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    observation_type = document.get("observation_type")
    if observation_type == "pipeline":
        from .pipeline_adapter import translate_pipeline_receipts
        events = translate_pipeline_receipts(receipts)
    elif observation_type == "review":
        from .dm_review_adapter import translate_review_receipts
        events = translate_review_receipts(receipts)
    else:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    raw_events = document.get("events")
    if type(raw_events) is not list:
        report = ParityReport(
            "semantic_receipts_required", False, False,
            ("observation_events_missing",),
        )
        _write_json(args.output, report.to_dict())
        return EXIT_PARITY_GAP
    run_spec = document.get("run_spec")
    if type(run_spec) is not dict or not events:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    first = events[0]
    expected_context = (
        first.run_id, first.payload.get("workflow_class"),
        first.payload.get("workflow_class_defaulted"),
        first.payload.get("execution_mode"),
    )
    observed_context = (
        run_spec.get("run_id"), run_spec.get("workflow_class"),
        run_spec.get("workflow_class_defaulted"),
        run_spec.get("execution_mode"),
    )
    if observed_context != expected_context:
        report = ParityReport(
            "run_spec_receipt_context_mismatch", False, False,
            ("run_class_or_mode_drift",),
        )
        _write_json(args.output, report.to_dict())
        return EXIT_PARITY_GAP
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
            candidates = []
            for candidate in cache.iterdir():
                match = re.fullmatch(r"0\.1\.([0-9]+)", candidate.name)
                if match:
                    candidates.append((int(match.group(1)), candidate))
            roots.extend(
                (candidate, cache.resolve(strict=True))
                for _patch, candidate in sorted(candidates, reverse=True)
            )
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
            if document.get("name") != "workflow-kernel" or type(version) is not str or not re.fullmatch(r"0\.1\.[0-9]+", version):
                continue
            references = resolved / "skills" / "workflow-kernel" / "references"
            lexical_references = candidate / "skills" / "workflow-kernel" / "references"
            package = references / "workflow_kernel"
            if package.is_dir() and (package / "__main__.py").is_file() and package.resolve(strict=True).is_relative_to(resolved):
                return references.resolve(strict=True)
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


def _exact_object(value, fields, name):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("invalid " + name)
    return value


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
    _exact_object(value, {
        "schema_version", "argv", "labels", "lifecycle",
        "registration_intents", "compose_override", "compose_override_content",
        "project_name", "environment", "managed", "reason",
    }, "creation plan")
    if value["schema_version"] != 1 or type(value["registration_intents"]) is not list:
        raise ValueError("invalid creation plan")
    intent_fields = {
        "kind", "expected_name", "run_id", "node_id", "lifecycle",
        "cleanup_policy", "labels", "dependent_node_ids",
    }
    if any(type(item) is not dict or set(item) != intent_fields
           for item in value["registration_intents"]):
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
        value["environment"], value["managed"], value["reason"],
    )


def _command_result(value):
    from .resources import CommandResult
    _exact_object(value, {
        "schema_version", "argv", "exit_code", "stdout", "stderr",
    }, "command result")
    if value["schema_version"] != 1:
        raise ValueError("invalid command result")
    return CommandResult(
        tuple(value["argv"]), value["exit_code"],
        value["stdout"], value["stderr"],
    )


def _command_result_dict(value):
    return {
        "schema_version": 1, "argv": list(value.argv),
        "exit_code": value.exit_code, "stdout": value.stdout,
        "stderr": value.stderr,
    }


def _inventory(value):
    from .adapters.docker import DockerInventory, DockerResource
    from .resources import ResourceKind
    _exact_object(value, {
        "schema_version", "kind", "resources", "queried", "absent", "source",
        "evidence",
    }, "Docker inventory")
    if (
        value["schema_version"] != 1 or value["kind"] != "docker-inventory"
        or any(type(value[field]) is not list for field in (
            "resources", "queried", "absent", "evidence",
        ))
        or any(
            type(row) is not list or len(row) != 2
            for field in ("queried", "absent") for row in value[field]
        )
    ):
        raise ValueError("invalid Docker inventory")
    resource_fields = {
        "resource_id", "kind", "labels", "created_at", "running", "in_use",
        "system", "inspect_ok", "name", "use_known",
    }
    if any(type(item) is not dict or set(item) != resource_fields
           for item in value["resources"]):
        raise ValueError("invalid Docker inventory")
    resources = tuple(DockerResource(
        item["resource_id"], ResourceKind(item["kind"]), dict(item["labels"]),
        datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
        item["running"], item["in_use"], item["system"], item["inspect_ok"],
        item["name"], item["use_known"],
    ) for item in value["resources"])
    return DockerInventory(
        resources,
        tuple((ResourceKind(row[0]), row[1]) for row in value["queried"]),
        tuple((ResourceKind(row[0]), row[1]) for row in value["absent"]),
        value["source"], tuple(_command_result(item) for item in value["evidence"]),
    )


def _inventory_dict(value):
    return {
        "schema_version": 1, "kind": "docker-inventory",
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
        "evidence": [_command_result_dict(item) for item in value.evidence],
    }


def _cleanup_plan(value):
    from .resources import (
        CleanupAction, CleanupDisposition, CleanupPlan, CleanupScope,
        ResourceDisposition, ResourceKind,
    )
    _exact_object(value, {
        "schema_version", "scope", "before", "actions", "dispositions",
    }, "cleanup plan")
    if value["schema_version"] != 1:
        raise ValueError("invalid cleanup plan")
    if any(type(value[field]) is not list for field in (
        "before", "actions", "dispositions",
    )):
        raise ValueError("invalid cleanup plan")
    scope = value["scope"]
    if type(scope) is not dict or set(scope) not in (
        {"run_id", "terminal", "stale_sweep"},
        {"run_id", "node_id", "terminal", "stale_sweep"},
    ):
        raise ValueError("invalid cleanup plan")
    action_fields = {
        "resource_id", "kind", "action", "argv", "requires_success_of",
        "owner", "lifecycle", "proof_digest", "preconditions", "environment",
        "predecessor_result_id", "evidence_digest",
    }
    disposition_fields = {
        "resource_id", "kind", "owner", "lifecycle", "disposition", "action",
        "reason", "command_evidence", "evidence",
    }
    if any(type(item) is not dict or set(item) != action_fields or
           type(item.get("owner")) is not dict or set(item["owner"]) != {"run_id", "node_id"}
           for item in value["actions"]):
        raise ValueError("invalid cleanup plan")
    if any(type(item) is not dict or set(item) not in (
        disposition_fields, disposition_fields | {"follow_up"},
    ) or type(item.get("owner")) is not dict or set(item["owner"]) != {"run_id", "node_id"}
           for item in value["dispositions"]):
        raise ValueError("invalid cleanup plan")
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


def _cleanup_artifact_document(plan, inventory):
    return {
        "schema_version": 1, "kind": "cleanup-plan-artifact",
        "plan": plan.to_dict(), "inventory": _inventory_dict(inventory),
    }


def _cleanup_artifact(value):
    _exact_object(value, {"schema_version", "kind", "plan", "inventory"}, "cleanup artifact")
    if value["schema_version"] != 1 or value["kind"] != "cleanup-plan-artifact":
        raise ValueError("invalid cleanup artifact")
    return _cleanup_plan(value["plan"]), _inventory(value["inventory"])


def _cleanup_document(value):
    if type(value) is dict and value.get("kind") == "cleanup-plan-artifact":
        return _cleanup_artifact(value)
    expected = {"schema_version", "scope", "before", "actions", "dispositions", "_inventory"}
    _exact_object(value, expected, "cleanup document")
    plan_value = {key: value[key] for key in expected if key != "_inventory"}
    return _cleanup_plan(plan_value), _inventory(value["_inventory"])


def _direct_cleanup_document(plan, inventory):
    document = plan.to_dict()
    document["_inventory"] = _inventory_dict(inventory)
    return document


def _incomplete_node_proof(state_dir, run_id, records, witness_path=None):
    from .adapters.docker import IncompleteNodeProof
    dependencies = tuple(sorted({
        node_id for record in records for node_id in record.dependent_node_ids
    }))
    if not dependencies and witness_path is None:
        return None
    try:
        state = StateStore(Path(state_dir) / "run-state.json").load()
    except FileNotFoundError:
        if witness_path is not None:
            raise ValueError("node status witness has no verified state") from None
        return None
    if state.run_id != run_id:
        raise ValueError("run state proof identity mismatch")
    if witness_path is not None:
        witness = _load_json(witness_path)
        _exact_object(witness, {
            "schema_version", "run_id", "revision", "updated_at",
            "node_statuses",
        }, "node status witness")
        expected_statuses = {
            node_id: node.status.value for node_id, node in state.nodes.items()
        }
        if (
            witness["schema_version"] != 1
            or witness["run_id"] != state.run_id
            or witness["revision"] != state.revision
            or witness["updated_at"] != state.updated_at
            or witness["node_statuses"] != expected_statuses
        ):
            raise ValueError("node status witness mismatch")
    if not dependencies:
        return None
    statuses = tuple(
        (node_id, state.nodes[node_id].status)
        for node_id in dependencies if node_id in state.nodes
    )
    return IncompleteNodeProof(
        run_id, statuses, True,
        datetime.fromisoformat(state.updated_at.replace("Z", "+00:00")),
    )


class StateDirectoryLeaseReader:
    """Read a fixed, verified run-state location; caller paths never confer proof."""

    _RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}")

    def __init__(self, root, *, now=None):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("invalid state directory")
        self.now = now or (lambda: datetime.now(timezone.utc))

    def read(self, run_id):
        from .adapters.docker import LeaseProof
        from .schema import RunStatus
        if type(run_id) is not str or self._RUN_ID.fullmatch(run_id) is None:
            raise ValueError("invalid lease run id")
        run_dir = self.root / "runs" / run_id
        if not run_dir.is_dir():
            return None
        try:
            state = StateStore(run_dir / "run-state.json").load()
        except FileNotFoundError:
            return None
        if state.run_id != run_id:
            raise ValueError("lease state identity mismatch")
        terminal = {
            RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BLOCKED,
            RunStatus.CANCELLED, RunStatus.INTERRUPTED,
        }
        observed_at = self.now()
        if (
            type(observed_at) is not datetime or observed_at.tzinfo is None
            or observed_at.utcoffset() is None
        ):
            raise ValueError("invalid lease reader clock")
        return LeaseProof(run_id, state.status not in terminal, True, observed_at)


def _reconcile_output_paths(output):
    descriptor = Path(output)
    stem = descriptor.name[:-5] if descriptor.name.endswith(".json") else descriptor.name
    current = descriptor.with_name(stem + ".current-run.json")
    stale = descriptor.with_name(stem + ".stale-sweep.json")
    return descriptor, current, stale


def _plan_status(plan):
    from .resources import CleanupDisposition
    unsafe = {CleanupDisposition.BLOCKED, CleanupDisposition.RETAINED_FOR_DEPENDENCY}
    return EXIT_UNSAFE_PLAN if any(item.disposition in unsafe for item in plan.dispositions) else 0


def _cleanup_receipt_status(receipt):
    from .resources import CleanupDisposition
    unsafe = {
        CleanupDisposition.BLOCKED,
        CleanupDisposition.RETAINED_FOR_DEPENDENCY,
    }
    return EXIT_UNSAFE_PLAN if any(
        item.disposition in unsafe for item in receipt.dispositions
    ) else 0


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
    records = registry.resources_for(args.run_id, args.node_id)
    inventory = adapter.inventory_registered(records)
    proof = _incomplete_node_proof(
        args.state_dir, args.run_id, records, args.node_statuses,
    )
    if args.node_id is None:
        plan = adapter.plan_reconcile_run(
            registry, inventory, args.run_id,
            incomplete_node_proof=proof, terminal=False,
        )
    else:
        plan = adapter.plan_chunk_cleanup(
            registry, inventory, args.run_id, args.node_id,
            incomplete_node_proof=proof,
        )
    _write_json(args.output, _direct_cleanup_document(plan, inventory))
    return _plan_status(plan)


def command_plan_reconcile(args):
    from .adapters.docker import DockerAdapter
    lease_reader = StateDirectoryLeaseReader(args.state_dir)
    adapter = DockerAdapter(_SubprocessRunner(), lease_reader=lease_reader)
    registry = _registry(args.state_dir)
    records = registry.resources_for(args.run_id)
    inventory = adapter.inventory_registered(records)
    plan = adapter.plan_reconcile_run(
        registry, inventory, args.run_id,
        incomplete_node_proof=_incomplete_node_proof(
            args.state_dir, args.run_id, records, args.node_statuses,
        ), terminal=True,
    )
    stale_inventory = adapter.inventory()
    stale_plan = _stale_cleanup_plan(adapter, stale_inventory, args.ttl_hours)
    descriptor, current_path, stale_path = _reconcile_output_paths(args.output)
    _write_json(current_path, _cleanup_artifact_document(plan, inventory))
    _write_json(stale_path, _cleanup_artifact_document(stale_plan, stale_inventory))
    _write_json(descriptor, {
        "schema_version": 1, "kind": "cleanup-plan-set",
        "current_run_plan": str(current_path),
        "stale_sweep_plan": str(stale_path), "ttl_hours": args.ttl_hours,
    })
    return max(_plan_status(plan), _plan_status(stale_plan))


def _stale_cleanup_plan(adapter, inventory, ttl_hours):
    if type(ttl_hours) not in {int, float} or ttl_hours < 0:
        raise ValueError("invalid stale cleanup TTL")
    return adapter.plan_stale_sweep(inventory, timedelta(hours=float(ttl_hours)))


def command_next_cleanup_step(args):
    from .resources import cleanup_step_identities
    plan, _sealed_inventory = _cleanup_document(_load_json(args.plan))
    prior = _load_json(args.outcomes)
    if type(prior) is not list or len(prior) > len(cleanup_step_identities(plan)):
        raise ValueError("invalid cleanup results")
    identities = cleanup_step_identities(plan)
    authorities = tuple(_authority(item) for item in prior)
    _registry(args.state_dir).validate_authority_prefix(plan, authorities)
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
        "schema_version": 1,
        "type": "command" if type(value) is GuardedCommandResult else "terminal",
        "result": _command_result_dict(value.result),
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
    common = {
        "schema_version", "type", "result", "state_generation", "issued_at",
        "expires_at", "authority_id", "step_identity",
    }
    command_fields = common | {
        "kind", "resource_id", "run_id", "node_id", "action_digest",
    }
    terminal_fields = common | {"disposition", "evidence_digest"}
    if type(value) is not dict or value.get("schema_version") != 1:
        raise ValueError("invalid guarded authority")
    if value.get("type") == "command":
        _exact_object(value, command_fields, "guarded command authority")
    elif value.get("type") == "terminal":
        _exact_object(value, terminal_fields, "guarded terminal authority")
    else:
        raise ValueError("invalid guarded authority")
    step = value["step_identity"]
    _exact_object(step, {"plan_digest", "step_index", "step_type"}, "cleanup step identity")
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
    plan, sealed_inventory = _cleanup_document(_load_json(args.plan))
    identities = cleanup_step_identities(plan)
    if args.step_index < 0 or args.step_index >= len(identities):
        raise ValueError("invalid cleanup step")
    adapter = DockerAdapter(_SubprocessRunner())
    registry = _registry(args.state_dir)
    prior = _load_json(args.outcomes)
    if type(prior) is not list:
        raise ValueError("invalid prior cleanup results")
    authorities = tuple(_authority(item) for item in prior)
    if len(authorities) != args.step_index:
        raise ValueError("non-contiguous cleanup outcomes")
    registry.validate_authority_prefix(plan, authorities)
    identity = identities[args.step_index]
    if identity.step_type == "terminal_observation":
        guarded = registry.observe_guarded_absence(
            adapter, plan, args.step_index, adapter.runner.run,
            authority_prefix=authorities,
        )
    else:
        action = plan.actions[args.step_index]
        sealed_resource = next((
            item for item in sealed_inventory.resources
            if item.kind is action.kind and item.resource_id == action.resource_id
        ), None)
        if sealed_resource is None:
            raise ValueError("cleanup resource absent from sealed inventory")
        lease_proof = None
        orphan_mode = plan.scope.stale_sweep
        if orphan_mode:
            current = adapter.inventory()
            lease_proof = StateDirectoryLeaseReader(args.state_dir).read(action.run_id)
            if lease_proof is None:
                raise ValueError("stale cleanup lease proof unavailable")
            records = ()
        else:
            record, active = registry.resource_state_for_exact(
                action.kind, action.resource_id,
            )
            if not active or record is None:
                raise ValueError("cleanup resource is not active")
            records = (record,)
            current = adapter.inventory_registered(records)
        witness = _inventory(_load_json(args.inventory))
        if _inventory_dict(witness) != _inventory_dict(current):
            raise ValueError("cleanup inventory witness mismatch")
        resource = next((item for item in current.resources
                         if item.kind is action.kind and item.resource_id == action.resource_id), None)
        if resource is None:
            raise ValueError("cleanup resource unavailable")
        proof = _incomplete_node_proof(
            args.state_dir, action.run_id, records, args.node_statuses,
        )
        guarded = registry.execute_guarded_action(
            adapter, plan, args.step_index, resource, adapter.runner.run,
            lease_proof=lease_proof, incomplete_node_proof=proof,
            orphan_mode=orphan_mode, authority_prefix=authorities,
        )
    _write_json(args.output, _authority_dict(guarded))
    return 0


def command_record_cleanup(args):
    from .adapters.docker import DockerAdapter
    plan, before = _cleanup_document(_load_json(args.plan))
    raw_results = _load_json(args.outcomes)
    if type(raw_results) is not list:
        raise ValueError("invalid guarded cleanup results")
    results = tuple(_authority(item) for item in raw_results)
    adapter = DockerAdapter(_SubprocessRunner())
    registry = _registry(args.state_dir)
    registry.validate_authority_prefix(plan, results)
    if plan.scope.stale_sweep:
        after = adapter.inventory()
    else:
        after = adapter.inventory_registered(registry.resources_for(plan.scope))
    if not results:
        from .resources import cleanup_step_identities
        if cleanup_step_identities(plan):
            raise ValueError("guarded cleanup results missing")
        receipt, _observed = adapter._reconcile_results(plan, (), before, after)
        _emit(receipt.to_dict())
        return _cleanup_receipt_status(receipt)
    receipt = registry.record_guarded_results(
        adapter, plan, results, before, after,
    )
    _emit(receipt.to_dict())
    return _cleanup_receipt_status(receipt)


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
            "guarded_cleanup_authority_conflict", "guarded_cleanup_authority_changed",
            "guarded_cleanup_authority_bijection_failed",
            "guarded_cleanup_authority_step_gap",
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
