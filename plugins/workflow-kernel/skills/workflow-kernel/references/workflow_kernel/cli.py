"""Repo-local argparse interface for workflow-kernel ledgers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from ._files import bind_durable_path
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
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_json_input",
        }) from None


def _write_json(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


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
    predicted = RunState.from_dict(document["run_state"])
    try:
        events = translate_pipeline_receipts(receipts)
    except ValueError:
        from .dm_review_adapter import translate_review_receipts
        events = translate_review_receipts(receipts)
    report = ShadowComparator().compare(predicted, ReceiptSet.from_events(events))
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
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        return args.handler(args)
    except KernelError as exc:
        _emit(serialize_kernel_error(exc), sys.stderr)
        return 2
    except (OSError, ValueError, TypeError) as exc:
        error = UnsafePayloadError(ErrorMessage.OPERATION_FAILED, {
            ErrorDetailKey.EXCEPTION_TYPE.value: type(exc).__name__,
        })
        _emit(serialize_kernel_error(error), sys.stderr)
        return EXIT_INVALID
