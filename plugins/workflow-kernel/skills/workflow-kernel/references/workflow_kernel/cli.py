"""Repo-local argparse interface for workflow-kernel ledgers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from .events import EventStore
from .schema import (
    CorruptEventError, ErrorDetailKey, ErrorMessage, InvalidSchemaError, KernelError,
    RunMode, UnsafePayloadError, WorkflowEvent,
)
from .state import RunLease, StateStore
from .transitions import TransitionEngine


class KernelArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        match = re.search(r"argument ([^:]+)", message)
        option = match.group(1) if match else "command"
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument", ErrorDetailKey.OPTION.value: option,
        })


def _paths(directory):
    root = Path(directory)
    return root, EventStore(root / "events.jsonl"), StateStore(root / "run-state.json")


def _emit(value, stream=sys.stdout):
    stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


@contextmanager
def _coordinated_run(states):
    """Hold the run lease from mutable observation through publication."""
    with RunLease(states.path) as lease:
        yield lease


def command_init(args):
    root, events, states = _paths(args.directory)
    root.mkdir(parents=True, exist_ok=True)
    with _coordinated_run(states) as lease:
        if events.path.exists() or states.path.exists():
            raise InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_INITIALIZED, {
                ErrorDetailKey.DIRECTORY.value: str(root),
            })
        event = WorkflowEvent(1, 0, args.run_id, None, "run.initialized", args.occurred_at, {"mode": args.mode})
        state = TransitionEngine().reconstruct((event,))
        events.append(event, 0)
        evidence = states.write(state, -1, lease=lease)
    _emit({"run_id": state.run_id, "mode": state.mode.value, "status": state.status.value, "revision": state.revision,
           "durability": evidence})
    return 0


def command_validate(args):
    _, events, states = _paths(args.directory)
    replayed, notes = events.validate(recovery=args.recovery)
    if not replayed:
        raise CorruptEventError(ErrorMessage.AUTHORITATIVE_LEDGER_MISSING)
    state = TransitionEngine().reconstruct(replayed)
    if states.path.exists():
        materialized = states.load()
        if materialized != state:
            raise InvalidSchemaError(ErrorMessage.STATE_LEDGER_MISMATCH, {
                ErrorDetailKey.MATERIALIZED_REVISION.value: materialized.revision,
                ErrorDetailKey.LEDGER_REVISION.value: state.revision,
            })
    _emit({"valid": True, "event_count": len(replayed), "notes": list(notes)})
    return 0


def command_append(args):
    _, events, states = _paths(args.directory)
    try:
        data = json.loads(args.event)
    except json.JSONDecodeError as exc:
        raise InvalidSchemaError(ErrorMessage.EVENT_INVALID_JSON, {ErrorDetailKey.OFFSET.value: exc.pos}) from exc
    except RecursionError as exc:
        raise InvalidSchemaError(ErrorMessage.EVENT_INVALID_JSON, {
            ErrorDetailKey.REASON_CODE.value: "recursion_limit",
        }) from exc
    event = WorkflowEvent.from_dict(data)
    with _coordinated_run(states) as lease:
        existing = events.replay()
        if not existing:
            raise InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_UNINITIALIZED)
        expected = states.load().revision if states.path.exists() else -1
        state = TransitionEngine().reconstruct(existing)
        next_state = TransitionEngine().apply(state, event)
        prepared = states.prepare(next_state)
        events.append(event, expected_sequence=len(existing))
        evidence = states.publish(prepared, expected, lease=lease)
    _emit({"appended": event.sequence, "revision": next_state.revision, "status": next_state.status.value,
           "durability": evidence})
    return 0


def command_replay(args):
    _, events, states = _paths(args.directory)
    with _coordinated_run(states) as lease:
        reconstructed = TransitionEngine().reconstruct(events.replay())
        expected = states.load().revision if states.path.exists() else -1
        evidence = states.write(reconstructed, expected, lease=lease)
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
        error = UnsafePayloadError(ErrorMessage.OPERATION_FAILED, {
            ErrorDetailKey.EXCEPTION_TYPE.value: type(exc).__name__,
        })
        _emit(error.to_dict(), sys.stderr)
        return 1
