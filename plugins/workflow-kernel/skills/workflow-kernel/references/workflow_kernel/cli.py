"""Repo-local argparse interface for workflow-kernel ledgers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .events import EventStore
from .schema import InvalidSchemaError, KernelError, RunMode, RunState, UnsafePayloadError, WorkflowEvent
from .state import RunLease, StateStore
from .transitions import TransitionEngine


class KernelArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidSchemaError("invalid command arguments", {"reason": message})


def _paths(directory):
    root = Path(directory)
    return root, EventStore(root / "events.jsonl"), StateStore(root / "run-state.json")


def _emit(value, stream=sys.stdout):
    stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _write_state(store, state, expected_revision):
    with RunLease(store.path):
        return store.write(state, expected_revision)


def command_init(args):
    root, events, states = _paths(args.directory)
    root.mkdir(parents=True, exist_ok=True)
    if events.path.exists() or states.path.exists():
        raise InvalidSchemaError("run directory is already initialized", {"directory": str(root)})
    event = WorkflowEvent(1, 0, args.run_id, None, "run.initialized", args.occurred_at, {"mode": args.mode})
    state = TransitionEngine().reconstruct((event,))
    with RunLease(states.path):
        events.append(event, 0)
        evidence = states.write(state, -1)
    _emit({"run_id": state.run_id, "mode": state.mode.value, "status": state.status.value, "revision": state.revision,
           "durability": evidence})
    return 0


def command_validate(args):
    _, events, states = _paths(args.directory)
    replayed, notes = events.validate(recovery=args.recovery)
    state = TransitionEngine().reconstruct(replayed) if replayed else None
    if states.path.exists() and state is not None and states.load() != state:
        raise InvalidSchemaError("materialized state does not match event ledger", {
            "materialized_revision": states.load().revision, "ledger_revision": state.revision,
        })
    _emit({"valid": True, "event_count": len(replayed), "notes": list(notes)})
    return 0


def command_append(args):
    _, events, states = _paths(args.directory)
    try:
        data = json.loads(args.event)
    except json.JSONDecodeError as exc:
        raise InvalidSchemaError("event is not valid JSON", {"offset": exc.pos}) from exc
    event = WorkflowEvent.from_dict(data)
    with RunLease(states.path):
        existing = events.replay()
        if not existing:
            raise InvalidSchemaError("run directory is not initialized")
        state = TransitionEngine().reconstruct(existing)
        next_state = TransitionEngine().apply(state, event)
        events.append(event, expected_sequence=len(existing))
        expected = states.load().revision if states.path.exists() else -1
        evidence = states.write(next_state, expected)
    _emit({"appended": event.sequence, "revision": next_state.revision, "status": next_state.status.value,
           "durability": evidence})
    return 0


def command_replay(args):
    _, events, states = _paths(args.directory)
    reconstructed = TransitionEngine().reconstruct(events.replay())
    expected = states.load().revision if states.path.exists() else -1
    evidence = _write_state(states, reconstructed, expected)
    _emit({"run_id": reconstructed.run_id, "revision": reconstructed.revision,
           "status": reconstructed.status.value, "durability": evidence})
    return 0


def command_status(args):
    _, _, states = _paths(args.directory)
    _emit(states.load().to_dict())
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
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        return args.handler(args)
    except KernelError as exc:
        _emit(exc.to_dict(), sys.stderr)
        return 2
    except (OSError, ValueError, TypeError) as exc:
        error = UnsafePayloadError("workflow kernel operation failed", {"exception_type": type(exc).__name__})
        _emit(error.to_dict(), sys.stderr)
        return 1
