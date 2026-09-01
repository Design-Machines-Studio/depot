"""Repo-local argparse interface for workflow-kernel ledgers."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ._files import PinnedDirectory, _OwnedResourceScope, bind_durable_path
from .events import EventStore
from .inspection import InspectionError
from .repository_scope import repository_scope as _repository_scope
from .runtime_resolution import (
    KERNEL_VERSION, KERNEL_VERSION_FLOOR, compatible_kernel_version,
    resolve_plugin_bundle, resolve_trusted_plugin_asset,
    resolve_workflow_kernel_runtime, semantic_version,
)
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
                        expected_sequence, expected_revision, lease,
                        authoritative_initialization=False):
    prepared = (
        _prepare_replay_state(states, next_state, expected_revision)
        if authoritative_initialization else states.prepare(next_state)
    )
    events.append(event, expected_sequence=expected_sequence, lease=lease)
    return states.publish(prepared, expected_revision, lease=lease)


@contextmanager
def _coordinated_run(states):
    """Hold the run lease from mutable observation through publication."""
    with RunLease(states.path) as lease:
        yield lease


def command_init(args):
    root = Path(args.directory)
    scope = _repository_scope(root, create=True)
    expected = scope.lease_root / "runs" / args.run_id
    if root.resolve(strict=False) != expected.resolve(strict=False):
        raise ValueError("run directory does not match canonical repository scope")
    root.mkdir(parents=True, exist_ok=True)
    root, events, states = _paths(root)
    with _coordinated_run(states) as lease:
        events.require_absent()
        states.require_absent()
        event = WorkflowEvent(1, 0, args.run_id, None, "run.initialized", args.occurred_at, {
            "mode": args.mode,
            "repository_scope_id": scope.scope_id,
            "repository_root_device": scope.repo_device,
            "repository_root_inode": scope.repo_inode,
            "lease_root_device": scope.lease_device,
            "lease_root_inode": scope.lease_inode,
        })
        state = TransitionEngine().reconstruct((event,))
        evidence = _append_and_publish(
            events, states, event, state, expected_sequence=0,
            expected_revision=-1, lease=lease,
            authoritative_initialization=True,
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
            authoritative_initialization=materialized is None,
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


def command_decide_validation_retry(args):
    """Atomically decide and record one retry against authoritative run state."""
    from .model import AttemptLedger, FailureReason
    from .policies import RetryPolicy
    from .redaction import contains_secret_shape, normalize_durable_string

    signatures = (() if args.signature is None else (args.signature,))
    try:
        invalid_signature = any(
            len(value) > 4096
            or contains_secret_shape(value)
            or re.match(r"(?i)^(?:sk-|gh[pousr]_|xox[baprs]-|bearer\s)", value)
            or normalize_durable_string(value) != value
            for value in signatures
        )
    except ValueError:
        invalid_signature = True
    if invalid_signature:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_failure_signature",
        })
    _scope, run_id, _root, events, states = _contract_run_context(args.state_dir)
    engine = TransitionEngine()
    with _coordinated_run(states) as lease:
        replayed, _notes, reconstructed, materialized = _observe_consistent_run(
            events, states, engine, recovery=False,
            empty_error=InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_UNINITIALIZED),
        )
        counts = {}
        histories = {}
        for event in replayed:
            if event.kind != "evidence.recorded":
                continue
            payload = event.to_dict()["payload"]
            if payload.get("stage") != "validation_retry_decided":
                continue
            reason = payload.get("failure_reason")
            signature = payload.get("failure_signature")
            if reason not in FailureReason._value2member_map_:
                raise ValueError("invalid authoritative retry event")
            counts[reason] = counts.get(reason, 0) + 1
            if signature is not None:
                histories.setdefault(reason, []).append(signature)
        ledger = AttemptLedger(counts, histories)
        decision = RetryPolicy().decide(
            FailureReason(args.reason), ledger, args.signature,
        )
        receipt = {
            "allowed": decision.allowed,
            "reason_code": decision.reason_code,
            "budget": decision.budget,
            "attempt_count": decision.attempt_count,
            "prior_signature": decision.prior_signature,
        }
        payload = {
            "stage": "validation_retry_decided",
            "failure_reason": args.reason,
            "failure_signature": args.signature,
            **receipt,
            "evidence": ["events.jsonl"],
        }
        current = datetime.now(timezone.utc)
        prior = datetime.fromisoformat(reconstructed.updated_at.replace("Z", "+00:00"))
        occurred_at = max(current, prior + timedelta(microseconds=1)).isoformat().replace(
            "+00:00", "Z",
        )
        event = WorkflowEvent(
            1, len(replayed), run_id, None, "evidence.recorded", occurred_at, payload,
        )
        next_state = engine.apply(reconstructed, event)
        expected_revision = materialized.revision if materialized is not None else -1
        _append_and_publish(
            events, states, event, next_state, expected_sequence=len(replayed),
            expected_revision=expected_revision, lease=lease,
            authoritative_initialization=materialized is None,
        )
    _emit(receipt)
    return 0


def _load_json(path, *, strict=False):
    def reject_duplicate_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON member")
            value[key] = item
        return value

    def reject_constant(_value):
        raise ValueError("non-finite JSON constant")

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
            raw = b"".join(chunks).decode("utf-8")
            if strict:
                return json.loads(
                    raw,
                    object_pairs_hook=reject_duplicate_object,
                    parse_constant=reject_constant,
                )
            return json.loads(raw)
    except (
        OSError, UnicodeError, ValueError, json.JSONDecodeError, RecursionError,
    ):
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


def _write_text(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = value.encode("utf-8")
    binding = bind_durable_path(destination)
    with _OwnedResourceScope() as owned:
        directory = owned.pin(binding)
        directory.revalidate()
        directory.regular_exists(binding.path.name)
        descriptor, temporary = directory.create_temporary(
            binding.path.name + ".tmp-", ".md",
        )
        owned.own_temporary(descriptor, temporary)
        pending = encoded
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("text write made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
        directory.require_identity(descriptor, temporary)
        directory.replace(temporary, binding.path.name)
        owned.disown_temporary()
        directory.fsync()


def _write_json_once(path, value):
    """Atomically claim an immutable artifact pathname without replacement."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ) + "\n").encode("utf-8")
    binding = bind_durable_path(destination)
    with _OwnedResourceScope() as owned:
        directory = owned.pin(binding)
        directory.revalidate()
        descriptor = owned.own(directory.open_regular(
            binding.path.name, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        ))
        pending = encoded
        try:
            while pending:
                count = os.write(descriptor, pending)
                if count <= 0:
                    raise OSError("json write made no progress")
                pending = pending[count:]
            os.fsync(descriptor)
            directory.require_identity(descriptor, binding.path.name)
            directory.fsync()
        except BaseException:
            try:
                directory.unlink(binding.path.name)
                directory.fsync()
            except OSError:
                pass
            raise


@contextmanager
def _contribution_artifact_directory(state_dir, *, create=False):
    """Pin the contribution directory without following either directory name."""
    root_path = Path(os.path.abspath(str(state_dir)))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    root_descriptor = os.open(str(root_path), flags)
    root = None
    child = None
    try:
        opened = os.fstat(root_descriptor)
        entry = os.lstat(str(root_path))
        identity = (opened.st_dev, opened.st_ino)
        if (
            not stat.S_ISDIR(opened.st_mode) or not stat.S_ISDIR(entry.st_mode)
            or identity != (entry.st_dev, entry.st_ino)
        ):
            raise OSError("unsafe contribution state directory")
        root = PinnedDirectory(root_path, root_descriptor, identity)
        root_descriptor = None
        name = "contribution-inputs"
        try:
            child_entry = os.stat(name, dir_fd=root.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            if not create:
                raise
            os.mkdir(name, mode=0o700, dir_fd=root.descriptor)
            root.fsync()
            child_entry = os.stat(name, dir_fd=root.descriptor, follow_symlinks=False)
        if not stat.S_ISDIR(child_entry.st_mode):
            raise OSError("unsafe contribution artifact directory")
        child_descriptor = os.open(name, flags, dir_fd=root.descriptor)
        opened_child = os.fstat(child_descriptor)
        current_child = os.stat(name, dir_fd=root.descriptor, follow_symlinks=False)
        child_identity = (opened_child.st_dev, opened_child.st_ino)
        if (
            not stat.S_ISDIR(opened_child.st_mode)
            or child_identity != (current_child.st_dev, current_child.st_ino)
            or child_identity != (child_entry.st_dev, child_entry.st_ino)
        ):
            os.close(child_descriptor)
            raise OSError("unsafe contribution artifact directory")
        child = PinnedDirectory(root_path / name, child_descriptor, child_identity)
        root.revalidate()
        try:
            yield child
        finally:
            child.revalidate()
            root.revalidate()
    finally:
        if child is not None:
            child.close()
        if root is not None:
            root.close()
        if root_descriptor is not None:
            os.close(root_descriptor)


def _contribution_artifact_name(reference):
    prefix = "contribution-inputs/"
    if (
        type(reference) is not str or not reference.startswith(prefix)
        or "/" in reference[len(prefix):] or not reference[len(prefix):]
    ):
        raise ValueError("invalid contribution artifact reference")
    return reference[len(prefix):]


def _read_contribution_artifact(directory, reference):
    name = _contribution_artifact_name(reference)
    descriptor = directory.open_regular(name, os.O_RDONLY)
    try:
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, MAX_JSON_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_JSON_BYTES:
                raise ValueError("json input too large")
        directory.require_identity(descriptor, name)
        return json.loads(b"".join(chunks).decode("utf-8"))
    finally:
        os.close(descriptor)


def _load_contribution_artifacts(state_dir, references):
    with _contribution_artifact_directory(state_dir) as directory:
        return {
            key: _read_contribution_artifact(directory, reference)
            for key, reference in references.items()
        }


def _seal_contribution_artifacts(state_dir, artifacts):
    """Create immutable contribution artifacts relative to one pinned directory."""
    with _contribution_artifact_directory(state_dir, create=True) as directory:
        pending = []
        for reference, value in artifacts.items():
            name = _contribution_artifact_name(reference)
            if directory.regular_exists(name):
                if _read_contribution_artifact(directory, reference) != value:
                    raise ValueError("conflicting sealed contribution input")
            else:
                pending.append((name, value))
        for name, value in pending:
            encoded = (json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ) + "\n").encode("utf-8")
            descriptor = directory.open_regular(
                name, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
            try:
                offset = 0
                while offset < len(encoded):
                    count = os.write(descriptor, encoded[offset:])
                    if count <= 0:
                        raise OSError("json write made no progress")
                    offset += count
                os.fsync(descriptor)
                directory.require_identity(descriptor, name)
            except BaseException:
                try:
                    directory.unlink(name)
                    directory.fsync()
                except OSError:
                    pass
                raise
            finally:
                os.close(descriptor)
        directory.fsync()
        try:
            directory.revalidate()
        except OSError:
            for name, _value in pending:
                try:
                    directory.unlink(name)
                except FileNotFoundError:
                    pass
            directory.fsync()
            raise


def _profile_from_receipts(receipts):
    from .model import HostCapabilities

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
        None if spec.decision_profile is None else dict(spec.decision_profile),
        spec.decision_profile_defaulted,
    )
    for event in events:
        event_profile = event.payload.get("decision_profile")
        actual = (
            event.run_id, event.payload.get("workflow_class"),
            event.payload.get("workflow_class_defaulted"),
            event.payload.get("execution_mode"),
            None if event_profile is None else dict(event_profile),
            event.payload.get("decision_profile_defaulted"),
        )
        if actual != expected:
            raise ValueError("run spec receipt context mismatch")


def _document_digest(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


_CONTRACT_BINDING_FIELDS = frozenset({
    "stage", "contract_id", "schema_version", "revision", "contract_digest",
    "contract_ref", "previous_contract_digest", "reason_code",
    "verification_profile_id", "verification_profile_digest",
    "verification_profile_ref", "evidence",
})
_CONTRACT_STAGES = frozenset({"verification_contract_bound"})


def _contract_run_context(state_dir):
    scope = _repository_scope(state_dir)
    requested = Path(os.path.abspath(str(state_dir)))
    run_id = requested.name
    expected = scope.lease_root / "runs" / run_id
    if requested.resolve(strict=True) != expected.resolve(strict=True):
        raise ValueError("state directory is not a canonical run directory")
    root, events, states = _paths(requested)
    if root != expected.resolve(strict=True):
        raise ValueError("run directory scope mismatch")
    return scope, run_id, root, events, states


@contextmanager
def _contract_artifact_directory(run_root, name="verification-contracts"):
    with PinnedDirectory.open(Path(run_root)) as run_directory:
        try:
            entry = os.stat(
                name, dir_fd=run_directory.descriptor, follow_symlinks=False,
            )
        except FileNotFoundError:
            os.mkdir(name, mode=0o700, dir_fd=run_directory.descriptor)
            run_directory.fsync()
            entry = os.stat(
                name, dir_fd=run_directory.descriptor, follow_symlinks=False,
            )
        if not stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode):
            raise ValueError("verification contract directory is unsafe")
        run_directory.revalidate()
        directory = PinnedDirectory.open(Path(run_root) / name)
        try:
            yield directory
        finally:
            directory.close()


def _contract_artifact_name(digest):
    if re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid contract digest")
    return "sha256-" + digest.removeprefix("sha256:") + ".json"


def _contract_artifact_ref(digest):
    return "verification-contracts/" + _contract_artifact_name(digest)


def _profile_artifact_ref(digest):
    return "verification-profiles/" + _contract_artifact_name(digest)


def _store_profile_once(run_root, profile, digest):
    from .behavioral_contract import parse_profile_bytes

    name = _contract_artifact_name(digest)
    encoded = json.dumps(
        profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    with _contract_artifact_directory(run_root, "verification-profiles") as directory:
        if directory.regular_exists(name):
            descriptor = directory.open_regular(name, os.O_RDONLY)
            try:
                existing = os.read(descriptor, len(encoded) + 1)
                if os.read(descriptor, 1) or existing != encoded:
                    raise ValueError("bound profile artifact mismatch")
                parse_profile_bytes(existing)
                directory.require_identity(descriptor, name)
            finally:
                os.close(descriptor)
            return False
        descriptor, temporary = directory.create_temporary(name + ".tmp-", ".json")
        try:
            pending = encoded
            while pending:
                count = os.write(descriptor, pending)
                if count <= 0:
                    raise OSError("profile write made no progress")
                pending = pending[count:]
            os.fsync(descriptor)
            directory.require_identity(descriptor, temporary)
            os.link(
                temporary, name, src_dir_fd=directory.descriptor,
                dst_dir_fd=directory.descriptor, follow_symlinks=False,
            )
            directory.unlink(temporary)
            temporary = None
            directory.require_identity(descriptor, name)
            directory.fsync()
        finally:
            if temporary is not None:
                try:
                    directory.unlink(temporary)
                except OSError:
                    pass
            os.close(descriptor)
    return True


def _load_bound_profile(run_root, reference, digest):
    from .behavioral_contract import parse_profile_bytes, verification_profile_digest

    if reference != _profile_artifact_ref(digest):
        raise ValueError("verification profile reference mismatch")
    with _contract_artifact_directory(run_root, "verification-profiles") as directory:
        descriptor = directory.open_regular(Path(reference).name, os.O_RDONLY)
        try:
            chunks = []
            while True:
                chunk = os.read(descriptor, 65_536)
                if not chunk:
                    break
                chunks.append(chunk)
                if sum(map(len, chunks)) > MAX_JSON_BYTES:
                    raise ValueError("verification profile artifact too large")
            directory.require_identity(descriptor, Path(reference).name)
        finally:
            os.close(descriptor)
    profile = parse_profile_bytes(b"".join(chunks))
    if verification_profile_digest(profile) != digest:
        raise ValueError("verification profile artifact digest mismatch")
    return profile


def _store_contract_once(run_root, contract, digest):
    from .behavioral_contract import canonical_bytes, parse_contract_bytes

    name = _contract_artifact_name(digest)
    encoded = canonical_bytes(contract) + b"\n"
    with _contract_artifact_directory(run_root) as directory:
        if directory.regular_exists(name):
            descriptor = directory.open_regular(name, os.O_RDONLY)
            try:
                existing = os.read(descriptor, len(encoded) + 1)
                if os.read(descriptor, 1) or existing != encoded:
                    raise ValueError("bound contract artifact mismatch")
                if parse_contract_bytes(existing) != contract:
                    raise ValueError("bound contract artifact invalid")
                directory.require_identity(descriptor, name)
            finally:
                os.close(descriptor)
            return False
        descriptor, temporary = directory.create_temporary(
            name + ".tmp-", ".json",
        )
        try:
            pending = encoded
            while pending:
                count = os.write(descriptor, pending)
                if count <= 0:
                    raise OSError("contract write made no progress")
                pending = pending[count:]
            os.fsync(descriptor)
            directory.require_identity(descriptor, temporary)
            os.link(
                temporary, name,
                src_dir_fd=directory.descriptor,
                dst_dir_fd=directory.descriptor,
                follow_symlinks=False,
            )
            directory.unlink(temporary)
            temporary = None
            directory.require_identity(descriptor, name)
            directory.fsync()
        except BaseException:
            if temporary is not None:
                try:
                    directory.unlink(temporary)
                    directory.fsync()
                except OSError:
                    pass
            raise
        finally:
            os.close(descriptor)
    return True


def _load_bound_contract(run_root, binding):
    from .behavioral_contract import contract_digest, parse_contract_bytes

    expected_ref = _contract_artifact_ref(binding["contract_digest"])
    if binding["contract_ref"] != expected_ref:
        raise ValueError("contract binding reference mismatch")
    with _contract_artifact_directory(run_root) as directory:
        descriptor = directory.open_regular(
            _contract_artifact_name(binding["contract_digest"]), os.O_RDONLY,
        )
        try:
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(65_536, MAX_JSON_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_JSON_BYTES:
                    raise ValueError("bound contract artifact too large")
            directory.require_identity(descriptor, Path(expected_ref).name)
        finally:
            os.close(descriptor)
    contract = parse_contract_bytes(b"".join(chunks))
    if (
        contract_digest(contract) != binding["contract_digest"]
        or contract["contract_id"] != binding["contract_id"]
        or contract["schema_version"] != binding["schema_version"]
        or contract["revision"] != binding["revision"]
        or contract["previous_contract_digest"] != binding["previous_contract_digest"]
    ):
        raise ValueError("bound contract artifact does not match ledger")
    return contract


def _contract_binding(replayed):
    binding = None
    for event in replayed:
        if event.kind != "evidence.recorded":
            continue
        payload = event.to_dict()["payload"]
        if payload.get("stage") not in _CONTRACT_STAGES:
            continue
        if type(payload) is not dict or set(payload) != _CONTRACT_BINDING_FIELDS:
            raise ValueError("invalid verification contract binding event")
        revision = payload["revision"]
        profile_ref = payload["verification_profile_ref"]
        if (
            binding is not None
            or type(revision) is not int or revision != 1
            or type(payload["schema_version"]) is not int
            or payload["schema_version"] != 1
            or type(payload["contract_id"]) is not str
            or re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",
                payload["contract_id"],
            ) is None
            or type(payload["reason_code"]) is not str
            or re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",
                payload["reason_code"],
            ) is None
            or payload["verification_profile_id"] is not None and type(payload["verification_profile_id"]) is not str
            or payload["verification_profile_digest"] is not None and type(payload["verification_profile_digest"]) is not str
            or (profile_ref is not None and type(profile_ref) is not str)
            or payload["previous_contract_digest"] is not None
            or payload["stage"] != "verification_contract_bound"
            or payload["contract_ref"] != _contract_artifact_ref(payload["contract_digest"])
            or payload["evidence"] != (
                [payload["contract_ref"]]
                + ([] if profile_ref is None else [profile_ref])
            )
        ):
            raise ValueError("verification contract binding chain mismatch")
        binding = payload
    return binding


def _contract_receipt(binding):
    return {
        name: binding[name] for name in (
            "stage", "contract_id", "schema_version", "revision",
            "contract_digest", "contract_ref", "previous_contract_digest",
            "reason_code", "verification_profile_id",
            "verification_profile_digest", "verification_profile_ref",
        )
    }


def _contract_binding_payload(contract, digest, stage, *, profile_ref=None):
    justification = contract["revision_justification"]
    reference = _contract_artifact_ref(digest)
    return {
        "stage": stage, "contract_id": contract["contract_id"],
        "schema_version": contract["schema_version"],
        "revision": contract["revision"], "contract_digest": digest,
        "contract_ref": reference,
        "previous_contract_digest": contract["previous_contract_digest"],
        "reason_code": justification["reason_code"],
        "verification_profile_id": contract["verification_profile_id"],
        "verification_profile_digest": contract["verification_profile_digest"],
        "verification_profile_ref": profile_ref,
        "evidence": [reference]
        + ([] if profile_ref is None else [profile_ref]),
    }


def _validated_contract_binding(run_root, binding):
    from .behavioral_contract import contract_digest, validate_initial_binding

    if binding is None:
        return None
    contract = validate_initial_binding(_load_bound_contract(run_root, binding))
    expected = _contract_binding_payload(
        contract, contract_digest(contract), binding["stage"],
        profile_ref=binding["verification_profile_ref"],
    )
    if binding != expected:
        raise ValueError("verification contract binding does not match artifact")
    if binding["verification_profile_ref"] is not None:
        from .behavioral_contract import validate_profile_binding
        profile = _load_bound_profile(
            run_root, binding["verification_profile_ref"],
            binding["verification_profile_digest"],
        )
        contract = validate_profile_binding(contract, profile)
    elif contract["verification_profile_id"] is not None:
        raise ValueError("verification profile artifact is missing")
    return contract


def command_bind_verification_contract(args):
    from .behavioral_contract import (
        contract_digest, load_contract, load_profile, validate_initial_binding,
        validate_profile_binding,
    )

    scope, run_id, run_root, events, states = _contract_run_context(args.state_dir)
    contract_scope = _repository_scope(args.contract)
    if contract_scope.scope_id != scope.scope_id:
        raise ValueError("contract input belongs to a foreign repository scope")
    candidate = load_contract(args.contract)
    digest = contract_digest(candidate)
    engine = TransitionEngine()
    with _coordinated_run(states) as lease:
        replayed, _notes = events.validate(recovery=False)
        if not replayed:
            raise InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_UNINITIALIZED)
        reconstructed = engine.reconstruct(replayed)
        if reconstructed.run_id != run_id:
            raise ValueError("run directory identity mismatch")
        materialized = _load_optional_state(states)
        binding = _contract_binding(replayed)
        requested_stage = "verification_contract_bound"
        profile = None
        profile_ref = None
        if candidate["verification_profile_id"] is not None:
            if getattr(args, "verification_profile", None) is None:
                raise ValueError("verification profile artifact is required")
            profile_scope = _repository_scope(args.verification_profile)
            if profile_scope.scope_id != scope.scope_id:
                raise ValueError("profile input belongs to a foreign repository scope")
            profile = load_profile(args.verification_profile)
            candidate = validate_profile_binding(candidate, profile)
            profile_ref = _profile_artifact_ref(candidate["verification_profile_digest"])
        elif getattr(args, "verification_profile", None) is not None:
            raise ValueError("unexpected verification profile artifact")
        payload = _contract_binding_payload(
            candidate, digest, requested_stage, profile_ref=profile_ref,
        )
        idempotent = (
            binding is not None
            and _contract_receipt(binding) == _contract_receipt(payload)
            and binding["stage"] == requested_stage
        )
        _validated_contract_binding(run_root, binding)

        if idempotent:
            _store_contract_once(run_root, candidate, digest)
            if materialized != reconstructed:
                expected_revision = materialized.revision if materialized is not None else -1
                states.publish(
                    _prepare_replay_state(states, reconstructed, expected_revision),
                    expected_revision, lease=lease,
                )
            receipt = _contract_receipt(binding)
        else:
            _require_materialized_matches_ledger(materialized, reconstructed)
            if binding is not None:
                raise ValueError("verification contract already bound")
            candidate = validate_initial_binding(candidate)
            digest = contract_digest(candidate)
            payload = _contract_binding_payload(
                candidate, digest, requested_stage, profile_ref=profile_ref,
            )
            _store_contract_once(run_root, candidate, digest)
            if profile is not None:
                _store_profile_once(
                    run_root, profile, candidate["verification_profile_digest"],
                )
            current = datetime.now(timezone.utc)
            prior = datetime.fromisoformat(
                reconstructed.updated_at.replace("Z", "+00:00"),
            )
            occurred_at = max(
                current, prior + timedelta(microseconds=1),
            ).isoformat().replace("+00:00", "Z")
            event = WorkflowEvent(
                1, len(replayed), run_id, None, "evidence.recorded", occurred_at,
                payload,
            )
            next_state = engine.apply(reconstructed, event)
            expected_revision = materialized.revision if materialized is not None else -1
            _append_and_publish(
                events, states, event, next_state,
                expected_sequence=len(replayed), expected_revision=expected_revision,
                lease=lease, authoritative_initialization=materialized is None,
            )
            receipt = _contract_receipt(payload)
    _emit(receipt)
    return 0
def _prediction_binding_payload(scope, observation_type, spec, event_digest, source_digest):
    return {
        "stage": "independent_prediction_bound",
        "observation_type": observation_type,
        "run_spec_digest": _document_digest(spec.to_dict()),
        "event_digest": event_digest,
        "source_digest": source_digest,
        "repository_scope_id": scope.scope_id,
        "evidence": [f"{observation_type}-shadow-prediction.json"],
    }


def _prediction_lifecycle(scope, spec):
    return scope.lease_root / "runs" / spec.run_id


def _prediction_binding_matches(event, expected_payload):
    return (
        type(event) is WorkflowEvent and event.kind == "evidence.recorded"
        and event.to_dict().get("payload") == expected_payload
    )


def _load_prediction_lifecycle(scope, spec, *, allow_reconciliation=False):
    directory = _prediction_lifecycle(scope, spec)
    _, events, states = _paths(directory)
    with _coordinated_run(states):
        replayed, _notes = events.validate(recovery=False)
        if not replayed:
            raise InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_UNINITIALIZED)
        reconstructed = TransitionEngine().reconstruct(replayed)
        materialized = _load_optional_state(states)
        if not allow_reconciliation:
            _require_materialized_matches_ledger(materialized, reconstructed)
    return replayed, reconstructed


def _append_prediction_binding(scope, observation_type, spec, document):
    directory = _prediction_lifecycle(scope, spec)
    _, events, states = _paths(directory)
    engine = TransitionEngine()
    expected_payload = _prediction_binding_payload(
        scope, observation_type, spec,
        document["event_digest"], document["source_digest"],
    )
    with _coordinated_run(states) as lease:
        replayed, _notes = events.validate(recovery=False)
        if not replayed:
            raise InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_UNINITIALIZED)
        reconstructed = engine.reconstruct(replayed)
        materialized = _load_optional_state(states)
        if len(replayed) == 2 and replayed[1].kind == "evidence.recorded":
            if not _prediction_binding_matches(replayed[1], expected_payload):
                raise ValueError("prediction lifecycle binding mismatch")
            if materialized != reconstructed:
                expected_revision = (
                    materialized.revision if materialized is not None else -1
                )
                states.publish(
                    _prepare_replay_state(
                        states, reconstructed, expected_revision,
                    ),
                    expected_revision, lease=lease,
                )
            return False
        if (
            len(replayed) != 1 or replayed[0].kind != "run.initialized"
            or reconstructed.status.value != "planned"
        ):
            raise ValueError("prediction must be bound before run start")
        _require_materialized_matches_ledger(materialized, reconstructed)
        current = datetime.now(timezone.utc)
        prior = datetime.fromisoformat(
            reconstructed.updated_at.replace("Z", "+00:00"),
        )
        occurred_at = max(current, prior + timedelta(microseconds=1)).isoformat().replace(
            "+00:00", "Z",
        )
        event = WorkflowEvent(
            1, 1, spec.run_id, None, "evidence.recorded", occurred_at,
            expected_payload,
        )
        next_state = engine.apply(reconstructed, event)
        expected_revision = materialized.revision if materialized is not None else -1
        _append_and_publish(
            events, states, event, next_state, expected_sequence=1,
            expected_revision=expected_revision, lease=lease,
            authoritative_initialization=materialized is None,
        )
    return True


def _bind_prediction(path, observation_type, spec, events, source, scope):
    event_documents = [event.to_dict() for event in events]
    event_digest = _document_digest(event_documents)
    source_digest = _document_digest(source)
    document = {
        "schema_version": 1, "artifact_role": "independent_prediction",
        "observation_type": observation_type,
        "run_spec": spec.to_dict(),
        "run_spec_digest": _document_digest(spec.to_dict()),
        "event_count": len(events),
        "events": event_documents,
        "event_digest": event_digest,
        "source_digest": source_digest,
        "lifecycle_binding": _prediction_binding_payload(
            scope, observation_type, spec, event_digest, source_digest,
        ),
        "observation_only": True,
    }
    try:
        _write_json_once(path, document)
        return True
    except FileExistsError:
        existing = _load_json(path)
        if (
            type(existing) is not dict
            or existing.get("artifact_role") != "independent_prediction"
            or existing.get("observation_type") != observation_type
            or existing.get("run_spec") != spec.to_dict()
            or existing.get("run_spec_digest") != _document_digest(spec.to_dict())
            or existing.get("events") != event_documents
            or existing.get("event_digest") != _document_digest(event_documents)
            or existing.get("source_digest") != _document_digest(source)
            or existing.get("lifecycle_binding") != document["lifecycle_binding"]
        ):
            raise ValueError("invalid bound prediction artifact") from None
        return False


def _require_bound_prediction(state_dir, observation_type, spec):
    from .repository_scope import repository_scope

    scope = repository_scope(state_dir)
    path = Path(state_dir) / f"{observation_type}-shadow-prediction.json"
    prediction = _load_json(path)
    run_spec = spec.to_dict()
    events = prediction.get("events") if type(prediction) is dict else None
    if (
        type(prediction) is not dict
        or prediction.get("artifact_role") != "independent_prediction"
        or prediction.get("observation_type") != observation_type
        or prediction.get("run_spec") != run_spec
        or prediction.get("run_spec_digest") != _document_digest(run_spec)
        or type(events) is not list
        or prediction.get("event_digest") != _document_digest(events)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", prediction.get("source_digest", ""))
        or prediction.get("lifecycle_binding") != _prediction_binding_payload(
            scope, observation_type, spec,
            prediction.get("event_digest"), prediction.get("source_digest"),
        )
    ):
        raise ValueError("bound prediction artifact mismatch")
    replayed, _state = _load_prediction_lifecycle(scope, spec)
    if (
        len(replayed) < 3
        or replayed[0].kind != "run.initialized"
        or not _prediction_binding_matches(
            replayed[1], prediction["lifecycle_binding"],
        )
        or replayed[2].kind != "run.started"
    ):
        raise ValueError("prediction lifecycle authority missing or reordered")
    return prediction


def command_bind_prediction(args):
    from .repository_scope import repository_scope

    source = _load_json(args.prediction_receipts, strict=True)
    if type(source) is not list:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    if args.type == "pipeline":
        from .pipeline_adapter import translate_manifest, translate_pipeline_receipts
        if args.manifest is None or args.request is not None:
            raise ValueError("pipeline prediction requires manifest only")
        spec = translate_manifest(
            _load_json(args.manifest), _profile_from_receipts(source),
        )
        events = translate_pipeline_receipts(source)
        name = "pipeline-shadow-prediction.json"
    else:
        from .dm_review_adapter import ReviewRequest, translate_review, translate_review_receipts
        if args.request is None or args.manifest is not None:
            raise ValueError("review prediction requires request only")
        request = ReviewRequest.from_mapping(_load_json(args.request))
        spec = translate_review(request, _profile_from_receipts(source))
        events = translate_review_receipts(source)
        name = "review-shadow-prediction.json"
    _require_spec_receipt_context(spec, events)
    scope = repository_scope(args.state_dir)
    replayed, state = _load_prediction_lifecycle(
        scope, spec, allow_reconciliation=True,
    )
    if (
        len(replayed) not in {1, 2} or state.status.value != "planned"
        or replayed[0].kind != "run.initialized"
        or (len(replayed) == 2 and replayed[1].kind != "evidence.recorded")
    ):
        raise ValueError("prediction must be bound before run start")
    output = Path(args.state_dir) / name
    artifact_bound = _bind_prediction(output, args.type, spec, events, source, scope)
    lifecycle_bound = _append_prediction_binding(
        scope, args.type, spec, _load_json(output),
    )
    bound = artifact_bound or lifecycle_bound
    _emit({"prediction_bound": bound, "event_count": len(events), "output": str(output)})
    return 0


def command_observe_pipeline(args):
    from .pipeline_adapter import translate_manifest, translate_pipeline_receipts

    manifest = _load_json(args.manifest)
    receipts = _load_json(args.receipts, strict=True)
    if not isinstance(manifest, dict) or not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    spec = translate_manifest(manifest, _profile_from_receipts(receipts))
    events = translate_pipeline_receipts(receipts)
    _require_spec_receipt_context(spec, events)
    _require_bound_prediction(args.state_dir, "pipeline", spec)
    artifact = {
        "schema_version": 1,
        "artifact_role": "authoritative_observation",
        "observation_type": "pipeline",
        "run_spec": spec.to_dict(), "event_count": len(events),
        "events": [event.to_dict() for event in events],
        "run_state": _observed_state(spec.run_id, events),
        "observation_only": True,
    }
    output = Path(args.state_dir) / "pipeline-shadow-observation.json"
    _write_json(output, artifact)
    _emit({
        "observed": True, "event_count": len(events), "output": str(output),
        "prediction_bound": False,
    })
    return 0


def command_reconcile_legacy_browser(args):
    """Atomically append Pipeline's one closed legacy-browser supersession."""
    from .pipeline_adapter import build_legacy_browser_reconciliation

    _reject_symlinked_components(args.events)
    lock_descriptor = _open_receipt_stream_lock(args.events)
    try:
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        receipts = _load_json(args.events, strict=True)
        candidate = build_legacy_browser_reconciliation(
            receipts,
            target_sequence=args.target_sequence,
            occurred_at=args.occurred_at,
            authoritative_receipt=args.authoritative_receipt,
        )
        _write_json(args.events, list(candidate))
    finally:
        os.close(lock_descriptor)
    receipt = candidate[-1]
    _emit({
        "reconciled": True,
        "sequence": receipt["sequence"],
        "target_sequence": receipt["target_sequence"],
        "target_receipt_digest": receipt["target_receipt_digest"],
    })
    return 0


def command_observe_review(args):
    from .dm_review_adapter import (
        export_finding_contributions,
        ReviewRequest, require_browser_recovery_profile_binding,
        require_complete_contribution_coverage,
        require_secret_safe_contribution_inputs,
        translate_review, translate_review_receipts,
    )

    request = ReviewRequest.from_mapping(_load_json(args.request))
    receipts = _load_json(args.receipts, strict=True)
    if not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    # Validate every receipt field, including the sealed references, before
    # using any receipt-supplied value as a filesystem path.
    events = translate_review_receipts(receipts)
    require_complete_contribution_coverage(receipts)
    coverage_index = next(
        index for index, receipt in enumerate(receipts)
        if receipt.get("stage") == "finding_contribution_coverage"
    )
    first_contribution = next((
        index for index, receipt in enumerate(receipts[:coverage_index])
        if receipt.get("stage") == "finding_contribution"
    ), coverage_index)
    coverage = receipts[coverage_index]
    references = {
        "decisions": coverage["synthesis_decisions_ref"],
        "raw_findings": coverage["raw_finding_inventory_ref"],
        "lane_receipts": coverage["lane_receipts_ref"],
        "raw_lane_outputs": coverage["raw_lane_outputs_ref"],
    }
    sealed = _load_contribution_artifacts(args.state_dir, references)
    require_secret_safe_contribution_inputs(*sealed.values())
    sealed_lane_outputs = {}
    for output in sealed["raw_lane_outputs"].get("outputs", ()):
        digest = _document_digest(output).removeprefix("sha256:")
        reference = "contribution-inputs/raw-lane-output-sha256-" + digest + ".json"
        sealed_lane_outputs[reference] = _load_contribution_artifacts(
            args.state_dir, {"output": reference},
        )["output"]
    expected_receipts = export_finding_contributions(
        request, sealed["decisions"], sealed["raw_findings"],
        sealed["lane_receipts"], sealed["raw_lane_outputs"],
        receipts[:first_contribution], references, sealed_lane_outputs,
    )
    if tuple(receipts[:coverage_index + 1]) != expected_receipts:
        raise ValueError("finding contribution coverage does not bind sealed inputs")
    spec = translate_review(request, _profile_from_receipts(receipts))
    _require_spec_receipt_context(spec, events)
    if any(receipt.get("stage") == "browser_recovery" for receipt in receipts):
        contract_events = [
            event for event in events
            if event.payload.get("stage") == "verification_contract_bound"
        ]
        if not contract_events:
            raise ValueError("browser recovery lacks contract binding")
        claimed = contract_events[-1].payload
        if claimed.get("verification_profile_ref") is None:
            raise ValueError("browser recovery lacks contract profile")
        scope = _repository_scope(args.state_dir)
        run_root = _prediction_lifecycle(scope, spec)
        replayed, _state = _load_prediction_lifecycle(scope, spec)
        binding = _contract_binding(replayed)
        if binding is None:
            raise ValueError("browser recovery lacks lifecycle contract binding")
        binding_fields = _CONTRACT_BINDING_FIELDS - frozenset({"evidence"})
        if any(claimed.get(field) != binding[field] for field in binding_fields):
            raise ValueError("browser recovery contract receipt is not current")
        contract = _validated_contract_binding(run_root, binding)
        profile_document = _load_bound_profile(
            run_root, binding["verification_profile_ref"],
            binding["verification_profile_digest"],
        )
        from .verification import VerificationProfile
        profile = VerificationProfile.from_dict(profile_document)
        require_browser_recovery_profile_binding(receipts, contract, profile)
    _require_bound_prediction(args.state_dir, "review", spec)
    artifact = {
        "schema_version": 1,
        "artifact_role": "authoritative_observation",
        "observation_type": "review",
        "run_spec": spec.to_dict(), "event_count": len(events),
        "events": [event.to_dict() for event in events],
        "run_state": _observed_state(spec.run_id, events),
        "observation_only": True,
    }
    output = Path(args.state_dir) / "review-shadow-observation.json"
    _write_json(output, artifact)
    _emit({
        "observed": True, "event_count": len(events), "output": str(output),
        "prediction_bound": False,
    })
    return 0


def command_export_review_contributions(args):
    from .dm_review_adapter import (
        ReviewRequest, export_finding_contributions,
        require_secret_safe_contribution_inputs,
    )

    request = ReviewRequest.from_mapping(_load_json(args.request))
    decisions = _load_json(args.decisions)
    raw_findings = _load_json(args.raw_findings)
    lane_receipts = _load_json(args.lane_receipts)
    raw_lane_outputs = _load_json(args.raw_lane_outputs)
    receipts = _load_json(args.receipts, strict=True)
    if (
        type(decisions) is not dict or type(raw_findings) is not dict
        or type(lane_receipts) is not dict or type(raw_lane_outputs) is not dict
        or type(receipts) is not list
    ):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    require_secret_safe_contribution_inputs(
        decisions, raw_findings, lane_receipts, raw_lane_outputs,
    )
    documents = {
        "decisions": ("synthesis-decisions", decisions),
        "raw_findings": ("raw-finding-inventory", raw_findings),
        "lane_receipts": ("lane-receipts", lane_receipts),
        "raw_lane_outputs": ("raw-lane-outputs", raw_lane_outputs),
    }
    references = {}
    for key, (role, document) in documents.items():
        digest = _document_digest(document).removeprefix("sha256:")
        name = role + "-sha256-" + digest + ".json"
        references[key] = "contribution-inputs/" + name
    exported = export_finding_contributions(
        request, decisions, raw_findings, lane_receipts, raw_lane_outputs,
        receipts, references,
    )
    artifacts = {
        references[key]: document
        for key, (_role, document) in documents.items()
    }
    lane_output_references = {}
    for output in raw_lane_outputs["outputs"]:
        digest = _document_digest(output).removeprefix("sha256:")
        reference = "contribution-inputs/raw-lane-output-sha256-" + digest + ".json"
        artifacts[reference] = output
        lane_output_references[reference] = output
    _seal_contribution_artifacts(args.state_dir, artifacts)
    loaded = _load_contribution_artifacts(args.state_dir, {
        key: reference for key, reference in references.items()
    })
    loaded_lane_outputs = _load_contribution_artifacts(
        args.state_dir, {reference: reference for reference in lane_output_references},
    )
    exported = export_finding_contributions(
        request, loaded["decisions"], loaded["raw_findings"],
        loaded["lane_receipts"], loaded["raw_lane_outputs"], receipts,
        references, loaded_lane_outputs,
    )
    _write_json(args.output, list(exported))
    _emit({
        "exported": len(exported) - len(receipts),
        "receipt_count": len(exported), "output": str(Path(args.output)),
    })
    return 0


def command_compare(args):
    from .shadow import ParityReport, ReceiptSet, ShadowComparator
    from .pipeline_adapter import RunSpec

    state_dir = Path(args.state_dir)
    observation = state_dir / "pipeline-shadow-observation.json"
    if not observation.is_file():
        observation = state_dir / "review-shadow-observation.json"
    document = _load_json(observation)
    receipts = _load_json(args.authoritative_receipts, strict=True)
    if not isinstance(document, dict) or not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    if document.get("artifact_role") != "authoritative_observation":
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    observation_type = document.get("observation_type")
    if observation_type == "pipeline":
        from .pipeline_adapter import translate_pipeline_receipts
        events = translate_pipeline_receipts(receipts)
        prediction_path = state_dir / "pipeline-shadow-prediction.json"
    elif observation_type == "review":
        from .dm_review_adapter import translate_review_receipts
        events = translate_review_receipts(receipts)
        prediction_path = state_dir / "review-shadow-prediction.json"
    else:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    if not prediction_path.is_file():
        report = ParityReport(
            "missing_authoritative_evidence", False, False,
            ("missing_independent_prediction",),
        )
        _write_json(args.output, report.to_dict())
        return EXIT_PARITY_GAP
    prediction = _load_json(prediction_path)
    if (
        type(prediction) is not dict
        or prediction.get("artifact_role") != "independent_prediction"
        or prediction.get("observation_type") != observation_type
    ):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    raw_events = prediction.get("events")
    if (
        type(raw_events) is not list
        or prediction.get("event_digest") != _document_digest(raw_events)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", prediction.get("source_digest", ""))
    ):
        report = ParityReport(
            "missing_authoritative_evidence", False, False,
            ("semantic_receipts_required", "observation_events_missing"),
        )
        _write_json(args.output, report.to_dict())
        return EXIT_PARITY_GAP
    run_spec = document.get("run_spec")
    prediction_spec = prediction.get("run_spec")
    if (
        type(prediction_spec) is not dict
        or prediction.get("run_spec_digest") != _document_digest(prediction_spec)
        or prediction_spec != run_spec
    ):
        report = ParityReport(
            "kernel_prediction_gap", False, False,
            ("run_spec_receipt_context_mismatch", "prediction_context_or_digest_drift"),
        )
        _write_json(args.output, report.to_dict())
        return EXIT_PARITY_GAP
    try:
        spec = RunSpec.from_dict(run_spec)
        prediction = _require_bound_prediction(
            args.state_dir, observation_type, spec,
        )
    except (KernelError, OSError, TypeError, ValueError):
        report = ParityReport(
            "missing_authoritative_evidence", False, False,
            ("prediction_lifecycle_authority_invalid",),
        )
        _write_json(args.output, report.to_dict())
        return EXIT_PARITY_GAP
    raw_events = prediction.get("events")
    if (
        type(raw_events) is not list
        or prediction.get("event_digest") != _document_digest(raw_events)
    ):
        report = ParityReport(
            "missing_authoritative_evidence", False, False,
            ("semantic_receipts_required", "observation_events_missing"),
        )
        _write_json(args.output, report.to_dict())
        return EXIT_PARITY_GAP
    if not events:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    first = events[0]
    expected_context = (
        first.run_id, first.payload.get("workflow_class"),
        first.payload.get("workflow_class_defaulted"),
        first.payload.get("execution_mode"),
    )
    observed_context = (
        spec.run_id, spec.workflow_class.value,
        spec.workflow_class_defaulted, spec.execution_mode,
    )
    if observed_context != expected_context:
        report = ParityReport(
            "kernel_prediction_gap", False, False,
            ("run_spec_receipt_context_mismatch", "run_class_or_mode_drift"),
        )
        _write_json(args.output, report.to_dict())
        return EXIT_PARITY_GAP
    predicted = ReceiptSet.from_events(
        WorkflowEvent.from_dict(value) for value in raw_events
    )
    report = ShadowComparator().compare_receipt_sets(
        predicted, ReceiptSet.from_events(events),
    )
    if report.reason == "semantic_receipts_required":
        report = ParityReport(
            "missing_authoritative_evidence", False, False,
            ("semantic_receipts_required", *report.differences),
        )
    elif report.reason == "run_spec_receipt_context_mismatch":
        report = ParityReport(
            "kernel_prediction_gap", False, False,
            ("run_spec_receipt_context_mismatch", *report.differences),
        )
    _write_json(args.output, report.to_dict())
    return 0 if report.semantic_match else EXIT_PARITY_GAP


def command_metrics(args):
    from .dm_review_adapter import translate_review_receipts
    from .metrics import MetricsAggregator
    from .pipeline_adapter import translate_pipeline_receipts

    receipts = _load_json(args.events, strict=True)
    if not isinstance(receipts, list):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    try:
        events = translate_pipeline_receipts(receipts)
    except ValueError:
        events = translate_review_receipts(receipts)
    report = MetricsAggregator().aggregate(events)
    _write_json(args.output, report.to_dict())
    return 0


def command_emit_observation_index(args):
    """Validate and atomically claim one observation-index-v1 sidecar."""
    from .observation_index import compose_observation_index

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)
    same_file = input_path == output_path
    if not same_file:
        try:
            same_file = os.path.samefile(input_path, output_path)
        except OSError:
            pass
    if same_file:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "observation_input_output_conflict",
        })
    document = _load_json(args.input, strict=True)
    index = compose_observation_index(document)
    _write_json_once(args.output, index)
    _emit({
        "emitted": True, "output": str(Path(args.output)),
        "digest": index["digest"],
    })
    return 0


def _reject_symlinked_components(path):
    """Refuse a path whose directory chain or final name is a symlink.

    ``O_NOFOLLOW`` guards only the final component. Receipt and artifact paths
    are predictable and live in the workspace, so a symlinked `.claude/`,
    `ux-review/`, or `plans/<feature>/` would redirect both the write and the
    delete outside the run directory while the final-component check passed.

    This narrows the window; it does not close it. An attacker who can swap a
    directory in the working tree between this check and the open can still
    win the race -- but that attacker can already edit the scripts being run,
    so the realistic threat this addresses is an accidental or leftover
    symlink, not a live adversary inside the workspace. Say so rather than
    imply a guarantee the check cannot provide.
    """
    absolute = os.path.abspath(path)
    judged_final = False
    for lexical, is_final in _workspace_components(absolute):
        judged_final = judged_final or is_final
        if os.path.islink(lexical):
            raise ValueError("symlinked path component: " + lexical)
    # Outside the workspace there is no trusted root to walk from, so judge
    # only what this command will actually open.
    if not judged_final and os.path.islink(absolute):
        raise ValueError("symlinked path: " + absolute)


def _workspace_components(absolute):
    """Yield ``(path_as_written, is_final)`` for components inside the workspace.

    Only components INSIDE the workspace are ours to judge. The path above it
    belongs to the operating system and is legitimately symlinked on the
    platforms this runs on -- macOS resolves /var to /private/var and every
    temporary directory sits under it. Walking from the filesystem root and
    refusing every symlink would reject nearly every real path while proving
    nothing about the workspace.

    "Inside the workspace" cannot be decided by comparing whole path strings.
    An earlier version tested a realpath base against a lexical candidate, so a
    workspace reached through a symlink -- `/tmp` -> `/private/tmp` is the
    everyday case -- never matched, fell through to the final-component check,
    and was weakest in exactly the situation the guard exists for. Comparing
    both sides lexically does not fix it either: `os.getcwd()` always answers
    with the resolved path, so the workspace's symlinked spelling is not
    recoverable from it.

    So decide per component instead. Walk the path as written, carrying the
    resolved parent alongside. A component is ours to judge once its resolved
    parent is the workspace or below it; above that line the operating system's
    own symlinks pass untouched. Walking as written is the point -- resolving
    the candidate first would erase the very symlinks being looked for.
    """
    base = os.path.realpath(os.getcwd())
    lexical = os.sep if os.path.isabs(absolute) else ""
    resolved_parent = os.path.realpath(lexical or os.curdir)
    parts = [p for p in absolute.split(os.sep) if p not in ("", os.curdir)]
    for index, part in enumerate(parts):
        lexical = os.path.join(lexical, part)
        try:
            inside = os.path.commonpath([resolved_parent, base]) == base
        except ValueError:  # different drives / no common prefix
            inside = False
        if inside:
            yield lexical, index == len(parts) - 1
        resolved_parent = os.path.realpath(lexical)


def _coverage_suffix(output_path):
    """Name the measured-lane count on the inventory line.

    Nothing enforces that an orchestrator calls `openrouter-usage` or
    `lane-input-bytes` after each attempt -- it is prose in eleven consumer
    files, so an unwired run still emits a structurally valid artifact with
    `lanes: []`. The artifact says so in `measurement_coverage`, but nobody
    reads the artifact to find out whether reading the artifact is worthwhile.
    The run receipt is where an operator looks, so the count goes there too.

    This reports; it does not gate. An unmeasured run is still a successful
    emission.
    """
    try:
        # Explicit UTF-8: `_write_json` writes it, and a C or cp1252 default
        # locale would otherwise fail to decode a non-ASCII provider or lane
        # name and silently drop the count off the receipt line.
        with open(output_path, encoding="utf-8") as handle:
            coverage = json.load(handle)["measurement_coverage"]["usage"]
        return " (usage measured %s/%s)" % (
            coverage["measured"], coverage["expected"],
        )
    except (OSError, ValueError, KeyError, TypeError):
        # The line must still be written. A missing count is not worth losing
        # the inventory entry over.
        return ""


def _read_receipt_events(events_path):
    """Translate a receipt array with whichever adapter accepts it.

    Pipeline first, review second. Both entry points and every other reader of
    a receipt stream in this file do exactly this; the one place that did not
    is what made the dm-review measurement boundary unusable.
    """
    from .dm_review_adapter import translate_review_receipts
    from .pipeline_adapter import translate_pipeline_receipts

    receipts = _load_json(events_path, strict=True)
    if not isinstance(receipts, list):
        # `InvalidSchemaError` rather than `ValueError`, because that is what the
        # legacy entry point raised for this exact input and both entry points
        # now share this function. `emit-cost-summary` catches everything and
        # records `summary-failed` either way, so only the legacy path can tell
        # the difference -- and it should not start telling a different story
        # because the two builders were merged.
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    try:
        return translate_pipeline_receipts(receipts)
    except ValueError:
        # A stream neither adapter accepts still raises ValueError out of here,
        # exactly as before the merge.
        return translate_review_receipts(receipts)


def _build_and_write_cost_summary(args):
    """Build the artifact and write it. The only path that produces one.

    Both entry points funnel through here. They used to carry their own copies
    of the adapter selection, summary construction, redaction, digest, and
    write -- five steps that had to stay identical while the artifact format
    moved under them, with nothing enforcing that they did.
    """
    from .cost_summary import build_run_cost_summary, compute_cost_summary_digest
    from .redaction import sanitize_durable_payload

    matrix = _load_cost_imputation_matrix(getattr(args, "matrix", None))
    summary = build_run_cost_summary(
        _read_receipt_events(args.events),
        repository_commit=getattr(args, "repository_commit", None),
        dirty_state=bool(getattr(args, "dirty_state", False)),
        matrix=matrix,
    )
    sanitized = sanitize_durable_payload(summary)
    sanitized["digest"] = compute_cost_summary_digest(sanitized)
    _write_json(args.output, sanitized)


def _runtime_home():
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def _load_cost_imputation_matrix(selector):
    """Load a caller-selected matrix only from a coherent installed bundle."""
    if selector is None or selector == "":
        return None
    try:
        asset = resolve_trusted_plugin_asset(selector, home=_runtime_home())
        matrix = _load_json(asset)
        from .imputed_cost import validate_model_matrix
        validate_model_matrix(matrix)
        return matrix
    except Exception:  # noqa: BLE001 -- optional observation must not gate
        sys.stderr.write(
            "run-cost-summary: trusted matrix unavailable or invalid; "
            "skipping imputation\n"
        )
        return None


def command_emit_cost_summary(args):
    """Clear, build, write, and record the cost summary in one command.

    The emission obligation used to be an eight-line shell block duplicated
    into eleven consumer files: remove the stale artifact, run the summary,
    then branch on the exit code to append either the artifact path or a skip
    line. Six independent review lanes found defects in that block -- an
    unchecked `rm -f` that let a stale artifact be attributed to the current
    run, a `test -L` preflight that a later `>>` redirection raced, an
    `&& ... || ...` chain that could append a skip line after successfully
    appending the artifact line, and a validator that could only check the
    prose beside it, never the behavior.

    None of those are shell bugs to be patched. They are what happens when a
    transaction is expressed as a sequence of independent commands. This
    command is the transaction: it owns the artifact path, writes the artifact,
    and records exactly one inventory line naming what actually happened.

    Measurement outcomes always exit 0. Invalid invocation or ambiguous JSON
    input exits 2 before the transaction mutates either output path. The
    artifact is observation-only, so a later measurement failure never becomes
    a workflow failure and records its own skip line.
    """
    if not _emit_paths_are_distinct(args):
        return EXIT_INVALID
    # The transaction owns deletion of a stale artifact and appending its run
    # receipt line. Reject ambiguous JSON before either mutation; the later
    # reader still owns adapter translation and all semantic validation.
    if os.path.exists(args.events):
        _load_json(args.events, strict=True)
    outcome = _prepare_emit_artifact_path(args)
    if outcome.reason is None:
        outcome = _EmitOutcome(_run_emit_summary(args), recordable=True)
    return _record_emit_outcome(args, outcome)


class _EmitOutcome:
    """What happened, and whether the run receipt can be told about it.

    Two loose values -- a reason string and a boolean -- could spell states that
    cannot occur, such as a successful build whose receipt was refused. Pairing
    them here means `recordable=False` only ever accompanies the refusal that
    produced it.
    """

    __slots__ = ("reason", "recordable")

    def __init__(self, reason, *, recordable):
        self.reason = reason
        self.recordable = recordable


def _emit_stderr(message):
    sys.stderr.write("emit-cost-summary: " + message + "\n")


def _emit_paths_are_distinct(args):
    """Refuse one path used for more than one transaction role.

    The command reads `--events`, unlinks and replaces `--output`, then appends
    a text line to `--receipt`. Reusing any file for two of those roles either
    destroys the authoritative stream or leaves JSON followed by Markdown.
    Compare both normalized spellings and existing-file identities so a
    relative alias or hard link cannot bypass the preflight.
    """
    paths = (
        ("--events", args.events),
        ("--output", args.output),
        ("--receipt", args.receipt),
    )
    for index, (left_name, left_path) in enumerate(paths):
        left = os.path.abspath(left_path)
        for right_name, right_path in paths[index + 1:]:
            right = os.path.abspath(right_path)
            same_file = left == right
            if not same_file:
                try:
                    same_file = os.path.samefile(left, right)
                except OSError:
                    pass
            if same_file:
                _emit_stderr(
                    f"{left_name} and {right_name} are the same path: {left}"
                )
                return False
    return True


def _prepare_emit_artifact_path(args):
    """Validate both paths and take ownership of the artifact path.

    Returns an :class:`_EmitOutcome`. ``recordable`` is False only when the
    *receipt* path itself was refused, because a bad `--output` still leaves a
    writable receipt to record the skip in and a bad `--receipt` does not:
    appending the skip line anyway would write through the symlink just refused,
    since `_append_receipt_line` guards only the final component with
    `O_NOFOLLOW`. Refusing a path and then writing to it is not a guard.
    """
    try:
        _reject_symlinked_components(args.receipt)
    except ValueError as error:
        _emit_stderr(str(error))
        return _EmitOutcome("unsafe-path", recordable=False)
    try:
        _reject_symlinked_components(args.output)
    except ValueError as error:
        _emit_stderr(str(error))
        return _EmitOutcome("unsafe-path", recordable=True)
    try:
        # Own the artifact path. A stale file left by an earlier run must not
        # survive to be recorded as this run's measurement.
        if os.path.lexists(args.output):
            os.unlink(args.output)
    except OSError as error:
        _emit_stderr(str(error))
        return _EmitOutcome("stale-artifact-not-removable", recordable=True)
    return _EmitOutcome(None, recordable=True)


def _run_emit_summary(args):
    """Build and write the artifact. Returns a skip reason, or ``None``."""
    try:
        _build_and_write_cost_summary(args)
    # Catch everything. A narrower tuple made "always exits 0" true only for the
    # failures already thought of: any other defect escaped, exited non-zero,
    # and -- if it happened after the artifact was written -- let the caller's
    # `||` fallback append `skipped (kernel-unresolvable)` next to a present,
    # current measurement. A false skip reason is worse than an honest one.
    except Exception as error:  # noqa: BLE001 -- see comment above
        _emit_stderr(str(error))
        return "summary-failed"
    return None


def _record_emit_outcome(args, outcome):
    """Append exactly one inventory line naming what actually happened."""
    line = (
        "run-cost-summary: " + str(args.output) + _coverage_suffix(args.output)
        if outcome.reason is None
        else "run-cost-summary: skipped (" + outcome.reason + ")"
    )
    if not outcome.recordable:
        # Nothing to append to: the receipt path is the thing that was refused.
        # Say so on stderr and stop, rather than writing the refusal through the
        # symlink that caused it.
        #
        # This is the one case that records nothing and still exits 0, and the
        # exemption is deliberate. The caller's fallback is
        # `|| printf 'run-cost-summary: skipped (...)' >> <receipt>`, so exiting
        # non-zero here would append through the very symlink just rejected and
        # undo the refusal. Stderr is the only safe channel left.
        _emit_stderr("could not record '" + line + "': receipt path refused")
        return 0
    try:
        _append_receipt_line(args.receipt, line)
    except (OSError, InvalidSchemaError) as error:
        # The artifact may well have been written, but the run receipt will not
        # say so -- and a receipt that names neither an artifact nor a skip is
        # the silence the failure-modes checklist forbids. Exiting non-zero is
        # the only remaining way to surface it: the observation-only contract
        # protects the *artifact* from failing a review, not this command's
        # ability to report that it could not report.
        _emit_stderr("could not record '" + line + "': " + str(error))
        return EXIT_CONFLICT
    return 0


def command_run_cost_summary(args):
    """The legacy two-step entry point. Kept for callers not yet migrated.

    Unlike `emit-cost-summary` it does not own the artifact path (no stale-file
    clearing) and has no skip line: a failure exits non-zero and records
    nothing. The artifact it produces is byte-identical, because both go
    through :func:`_build_and_write_cost_summary`.
    """
    # Validate the receipt path BEFORE writing the artifact. The preflight used
    # to live inside `_append_receipt_inventory_line`, which runs after the
    # build -- so a symlinked or unwritable receipt left the artifact on disk
    # with nothing pointing at it and an exception escaping uncaught. Order the
    # checks the way `emit-cost-summary` does: refuse first, produce second.
    receipt_line = getattr(args, "receipt_line", None)
    if receipt_line:
        _reject_symlinked_components(receipt_line)
    _build_and_write_cost_summary(args)
    _append_receipt_inventory_line(receipt_line, args.output)
    return 0


def _append_receipt_inventory_line(receipt_path, artifact_path):
    if not receipt_path:
        return
    # Same sink as `emit-cost-summary`, so the same preflight. The caller runs it
    # before building as well -- refusing after the artifact exists would leave
    # an orphan -- but a second check here costs nothing and keeps the guard
    # attached to the write it protects rather than to one caller's ordering.
    _reject_symlinked_components(receipt_path)
    _append_receipt_line(receipt_path, "run-cost-summary: " + str(artifact_path))


def _append_receipt_line(receipt_path, line):
    """Append the required inventory line, atomically, after the artifact.

    The emission obligation was previously prose: a consumer was told to put
    either the artifact path or a skip line into its run receipt, and whether
    that happened depended on a model reading the instruction and acting on it.
    This makes the success half deterministic -- the same command that wrote
    the artifact records that it did, and it records it only after the write
    succeeded, so the receipt can never claim an artifact that is not there.

    The skip half stays with the caller by necessity: the reason to skip is
    that this runtime could not be resolved or could not run, and a process
    that did not start cannot write its own absence. Callers pair this flag
    with a shell fallback that writes the skip line on a non-zero exit.
    """
    if not receipt_path:
        return
    encoded = (line + "\n").encode("utf-8")
    directory = os.path.dirname(os.path.abspath(receipt_path)) or "."
    os.makedirs(directory, exist_ok=True)
    # O_APPEND makes each write land at the current end of file, so a
    # concurrent appender cannot overwrite this one. It does NOT make a
    # multi-byte write indivisible: a short write is still possible, so the
    # loop below drives the line to completion and a residual short write is
    # reported as receipt corruption rather than silently accepted.
    #
    # O_NOFOLLOW rejects a symlinked final component. Receipt paths are
    # predictable and live in the workspace, so without it a pre-created
    # symlink would redirect this append to an arbitrary file under the
    # invoking user's authority.
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(receipt_path, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
                ErrorDetailKey.REASON_CODE.value: "invalid_argument",
            })
        written = 0
        while written < len(encoded):
            count = os.write(descriptor, encoded[written:])
            if count <= 0:
                raise OSError("short write appending the run-cost-summary line")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _invalid_append_argument(error_label, message):
    sys.stderr.write(error_label + ": " + message + "\n")
    raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
        ErrorDetailKey.REASON_CODE.value: "invalid_argument",
    }) from None


def _validate_append_envelope(args, error_label):
    """Require the envelope flags, and require the timestamp to be a timestamp."""
    for flag, value in (
        ("--run-id", args.run_id),
        ("--occurred-at", args.occurred_at),
        ("--authoritative-receipt", args.authoritative_receipt),
    ):
        if not value:
            _invalid_append_argument(
                error_label, flag + " is required with --append-to",
            )
    # The contract says `--occurred-at <ISO-8601>` and nothing enforced it, so
    # any non-empty string became durable evidence verbatim. A timestamp that
    # cannot be ordered against its neighbours is not a timestamp.
    try:
        parsed = datetime.fromisoformat(
            str(args.occurred_at).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            raise ValueError("missing UTC offset")
    except ValueError as error:
        _invalid_append_argument(
            error_label,
            "--occurred-at must be a timezone-aware ISO-8601 timestamp: "
            + str(error),
        )


def _reject_symlinked_receipt_stream(receipts_path, error_label):
    """Preflight the ledger path, as `emit-cost-summary` does for its own.

    The receipt stream is the authoritative evidence ledger, written after every
    lane attempt. Without this, the same leftover `.claude/ux-review/` or
    `plans/<feature>/` symlink that the emission command refuses would redirect
    the ledger write -- and the lock file beside it -- out of the run directory.
    `O_NOFOLLOW` on the lock guards only its final component.
    """
    try:
        _reject_symlinked_components(receipts_path)
    except ValueError as error:
        _invalid_append_argument(error_label, str(error))


def _open_receipt_stream_lock(receipts_path):
    """Open the exclusive lock guarding one receipt-stream read-modify-write.

    Lane attempts finish concurrently by design, so appending is a
    read-modify-write race unless it is serialized. Atomic replacement protects
    against a truncated file, not against a lost update: two appenders could
    both read length n, both claim sequence n, and the later replacement would
    silently discard the earlier attempt -- a measurement backbone losing
    exactly the measurements it exists to keep.
    """
    lock_path = str(receipts_path) + ".lock"
    lock_directory = os.path.dirname(os.path.abspath(lock_path)) or "."
    os.makedirs(lock_directory, exist_ok=True)
    lock_flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    return os.open(lock_path, lock_flags, 0o600)


def _open_openrouter_consumption_lock(state_dir, run_id):
    scope = _repository_scope(state_dir)
    requested = Path(os.path.abspath(str(state_dir)))
    expected = scope.lease_root / "runs" / run_id
    if requested.resolve(strict=True) != expected.resolve(strict=True):
        raise ValueError(
            "OpenRouter state directory is not the canonical run directory"
        )
    ledger_path = str(scope.lease_root / "openrouter-consumptions.json")
    _reject_symlinked_components(ledger_path)
    return ledger_path, _open_receipt_stream_lock(ledger_path)


def _reserve_openrouter_invocation(
    ledger_path, receipts_path, run_id, lane, usage, error_label,
):
    if os.path.exists(ledger_path):
        ledger = _load_json(ledger_path)
        if (
            type(ledger) is not dict
            or set(ledger) != {"schema_version", "consumptions"}
            or ledger["schema_version"] != 1
            or type(ledger["consumptions"]) is not list
        ):
            _invalid_append_argument(
                error_label, "invalid OpenRouter consumption ledger",
            )
    else:
        ledger = {"schema_version": 1, "consumptions": []}
    consumptions = ledger["consumptions"]
    if (
        type(consumptions) is not list
        or any(type(item) is not dict for item in consumptions)
    ):
        _invalid_append_argument(error_label, "invalid OpenRouter consumption ledger")
    invocation_id = usage["source_invocation_id"]
    receipt_digest = usage["source_receipt_digest"]
    duplicates = [
        item for item in consumptions if (
        item.get("invocation_id") == invocation_id
        or item.get("receipt_digest") == receipt_digest
        )
    ]
    reconciled = False
    blocking_duplicates = []
    for item in duplicates:
        if item.get("status") != "pending":
            blocking_duplicates.append(item)
            continue
        receipt_stream = item.get("receipt_stream")
        if type(receipt_stream) is not str or not receipt_stream:
            blocking_duplicates.append(item)
            continue
        if not os.path.exists(receipt_stream):
            consumptions.remove(item)
            reconciled = True
            continue
        try:
            bound_receipts = _load_json(receipt_stream, strict=True)
        except (InvalidSchemaError, OSError, TypeError, ValueError):
            blocking_duplicates.append(item)
            continue
        if type(bound_receipts) is not list:
            blocking_duplicates.append(item)
            continue
        if any(
            type(receipt) is dict
            and receipt.get("source_receipt_digest") == item.get("receipt_digest")
            for receipt in bound_receipts
        ):
            item["status"] = "committed"
            blocking_duplicates.append(item)
            reconciled = True
        else:
            consumptions.remove(item)
            reconciled = True
    if reconciled:
        _write_json(ledger_path, ledger)
    if blocking_duplicates:
        _invalid_append_argument(
            error_label, "OpenRouter source receipt was already recorded",
        )
    reservation = {
        "invocation_id": invocation_id,
        "receipt_digest": receipt_digest,
        "request_digest": usage["source_request_digest"],
        "run_id": run_id,
        "lane": lane,
        "receipt_stream": os.path.abspath(receipts_path),
        "status": "pending",
    }
    consumptions.append(reservation)
    _write_json(ledger_path, ledger)
    return ledger, reservation


def _finish_openrouter_reservation(
    ledger_path, ledger, reservation, *, committed,
):
    if committed:
        reservation["status"] = "committed"
    else:
        ledger["consumptions"].remove(reservation)
    _write_json(ledger_path, ledger)


def _append_attempt_usage_receipt(receipts_path, payload, args, error_label):
    """Wrap one measurement payload as an attempt_usage receipt and append it.

    This is the executable half of the emission boundary. Documenting "wrap the
    payload in an envelope and append it to the run's receipt stream" left the
    step to whoever read the prose, and a step nobody performs produces a cost
    summary with `lanes: []` -- structurally valid and informationally empty,
    which is the exact failure the measurement backbone exists to end.

    `sequence` is derived from the existing array rather than supplied, so a
    caller cannot collide two receipts or leave a gap. The array is rewritten
    through `_write_json`, which is atomic, so a crash mid-append leaves the
    prior receipt stream intact rather than a truncated one.
    """
    _validate_append_envelope(args, error_label)
    _reject_symlinked_receipt_stream(receipts_path, error_label)
    lock_descriptor = _open_receipt_stream_lock(receipts_path)
    try:
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        _append_attempt_usage_locked(receipts_path, payload, args, error_label)
    finally:
        os.close(lock_descriptor)


def _append_attempt_usage_locked(receipts_path, payload, args, error_label):
    """The critical section of :func:`_append_attempt_usage_receipt`."""
    _append_receipts_locked(receipts_path, error_label, [
        {
            "stage": "attempt_usage",
            "status": "observed",
            "authoritative_receipt": args.authoritative_receipt,
            **payload,
        },
    ], args.run_id, args.occurred_at)


def _append_receipts_locked(receipts_path, error_label, bodies, run_id,
                            occurred_at):
    """Append one or more receipts to the stream as a single unit.

    Callers pass receipt bodies without `run_id`, `sequence`, or `occurred_at`.
    `sequence` must equal each receipt's zero-based position in the array and
    `_translation` rejects any other value, so deriving it from the array length
    here -- rather than accepting it as a flag -- is what makes a collision or a
    gap unrepresentable.

    Appending several receipts in one call is what lets `record-attempt` put a
    lane's outcome and its measurement into the stream together: either both
    land or neither does, so a recorded lane cannot be missing its usage row.
    """
    if os.path.exists(receipts_path):
        receipts = _load_json(receipts_path, strict=True)
        if not isinstance(receipts, list):
            sys.stderr.write(
                error_label + ": receipt target is not a receipt array\n"
            )
            raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
                ErrorDetailKey.REASON_CODE.value: "invalid_argument",
            })
    else:
        receipts = []
    source_receipt_digests = {
        receipt.get("source_receipt_digest")
        for receipt in receipts
        if type(receipt) is dict and "source_receipt_digest" in receipt
    }
    for body in bodies:
        source_receipt_digest = body.get("source_receipt_digest")
        if source_receipt_digest is not None:
            if source_receipt_digest in source_receipt_digests:
                sys.stderr.write(
                    error_label + ": OpenRouter source receipt was already recorded\n"
                )
                raise InvalidSchemaError(
                    ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
                        ErrorDetailKey.REASON_CODE.value: "invalid_argument",
                    },
                )
            source_receipt_digests.add(source_receipt_digest)
        receipt = {
            "run_id": run_id,
            "sequence": len(receipts),
            "occurred_at": occurred_at,
        }
        receipt.update(body)
        receipts.append(receipt)
    # Prove the appended stream still translates before it replaces the old
    # one. A receipt stream that no longer parses is worse than no append.
    #
    # Try both adapters, exactly as every other reader of a receipt stream in
    # this file does. Validating with the pipeline adapter alone rejected every
    # dm-review stream -- which is to say, the documented `--append-to` wiring
    # for seven of the eleven consumers could never have worked.
    from .dm_review_adapter import translate_review_receipts
    from .pipeline_adapter import translate_pipeline_receipts
    try:
        translate_pipeline_receipts(receipts)
    except ValueError:
        try:
            translate_review_receipts(receipts)
        except ValueError as error:
            sys.stderr.write(
                error_label + ": appended receipt would break the stream: "
                + str(error) + "\n"
            )
            raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
                ErrorDetailKey.REASON_CODE.value: "invalid_argument",
            }) from None
    _write_json(receipts_path, receipts)


def _emit_measurement_payload(produce, output, error_label, args=None):
    """Run one measurement translator and write its payload.

    The two measurement commands differ only in how they obtain a payload.
    Everything after that -- the ValueError-to-invalid-argument mapping, the
    canonical JSON serialization, and the stdout-or-file branch -- is one
    contract, defined here so the handlers cannot drift apart.

    ``produce`` is a zero-argument callable returning the payload dict.
    ``error_label`` names the command in the stderr diagnostic, so a caller
    reading a failed run knows which translator rejected its input.
    """
    try:
        payload = produce()
    except ValueError as error:
        sys.stderr.write(error_label + ": " + str(error) + "\n")
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        }) from None
    append_to = getattr(args, "append_to", None) if args is not None else None
    if append_to and output:
        # Appending is a durable ledger mutation; writing --output is not. If
        # the output write failed after a successful append, the command would
        # report failure over an attempt that is already recorded, and a retry
        # would append it twice. Refuse the combination instead of documenting
        # a commit order nobody will remember.
        sys.stderr.write(
            error_label + ": --append-to and --output are mutually exclusive\n"
        )
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        })
    if append_to:
        _append_attempt_usage_receipt(append_to, payload, args, error_label)
    if output:
        _write_json(output, payload)
    elif not append_to:
        sys.stdout.write(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ) + "\n")
    return 0


def _attempt_context(args):
    """Collect the attempt coordinates both measurement commands share.

    The six arrive as identical flags on both commands, so reading them into
    the shared carrier here keeps one spelling of the mapping rather than two
    that can drift.
    """
    from ._usage_identity import AttemptContext

    return AttemptContext(
        lane=args.lane,
        chunk_id=args.chunk_id,
        node_id=args.node_id,
        attempt=args.attempt,
        host=args.host,
        duration_seconds=args.duration_seconds,
    )


def command_openrouter_usage(args):
    from .openrouter_usage import translate_openrouter_receipt

    receipt = _validated_openrouter_receipt(args.receipt, "openrouter-usage")
    return _emit_measurement_payload(
        lambda: translate_openrouter_receipt(
            receipt, context=_attempt_context(args),
        ),
        args.output,
        "openrouter-usage",
        args,
    )


def _validated_openrouter_receipt(path, error_label):
    """Load the closed wrapper envelope shared by both usage entry points."""
    receipt = _load_json(path)
    if not isinstance(receipt, dict):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS)
    schema_version = receipt.get("schemaVersion")
    if type(schema_version) is not int or schema_version != 2:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        })
    # `outcome` is required, not optional-with-a-default. The translator
    # treats a missing outcome as a failure, which is the safe reading for a
    # library, but at the CLI boundary a schemaVersion-2 receipt that omits it
    # is malformed rather than failed -- and silently reclassifying a legacy
    # success as a failure would corrupt the cost picture in the direction of
    # inventing failures. Reject it and say so.
    if type(receipt.get("outcome")) is not str or not receipt.get("outcome"):
        sys.stderr.write(
            error_label + ": receipt has no 'outcome'; a schemaVersion-2 "
            "receipt must state its outcome\n"
        )
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        })
    invocation_id = receipt.get("invocationId")
    if (
        type(invocation_id) is not str
        or re.fullmatch(r"[0-9a-f]{64}", invocation_id) is None
    ):
        sys.stderr.write(
            error_label + ": receipt has no valid wrapper invocation identity\n"
        )
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        })
    return receipt


def command_lane_input_bytes(args):
    from ._usage_identity import ProviderAttribution
    from .lane_bytes import measure_lane_inputs

    return _emit_measurement_payload(
        lambda: measure_lane_inputs(
            args.agent_definition,
            args.diff,
            args.boilerplate,
            context=_attempt_context(args),
            attribution=ProviderAttribution(
                requested_provider=args.requested_provider,
                attempted_provider=args.attempted_provider,
                implemented_by=args.implemented_by,
                provider=args.provider,
                model=args.model,
            ),
        ),
        args.output,
        "lane-input-bytes",
        args,
    )


def _attempt_usage_payload(args):
    """Build the usage half of a recorded attempt from whatever evidence exists.

    Three sources, in the order the caller can supply them:

    * an OpenRouter wrapper receipt, translated to real provider counters;
    * the lane's input files, measured deterministically as bytes;
    * neither, which becomes an explicit `attempt_unmeasured` row.

    The third case is the point. A lane that ran on a host reporting nothing
    used to produce no row at all, and an absent row is indistinguishable from
    a lane that never ran -- so the spend vanished and the artifact still called
    itself complete. Saying "this ran and nothing measured it" is a claim that
    can be counted, audited, and argued with.
    """
    from ._usage_identity import ProviderAttribution, build_attempt_identity
    from .lane_bytes import measure_lane_inputs
    from .openrouter_usage import translate_openrouter_receipt

    context = _attempt_context(args)
    # The lane outcome is authoritative for routing identity. Earlier versions
    # accepted a second independently supplied requested/attempted provider
    # tuple for the paired usage row, so one atomic append could still contain
    # two contradictory accounts of the same attempt. Retain the legacy flags
    # only as equality assertions, then derive the usage identity once from the
    # executor fields.
    for supplied, executor, flag in (
        (args.requested_provider, args.requested_executor, "--requested-provider"),
        (args.attempted_provider, args.attempted_executor, "--attempted-provider"),
    ):
        if supplied is not None and supplied != executor:
            raise ValueError(
                flag + " must match its paired executor identity"
            )
    if args.openrouter_receipt:
        if (
            args.attempted_executor != "openrouter"
            or args.implemented_by != "openrouter"
        ):
            raise ValueError(
                "an OpenRouter receipt requires attempted and implementing executor openrouter"
            )
        receipt = _validated_openrouter_receipt(
            args.openrouter_receipt, "record-attempt",
        )
        authorization = receipt.get("authorization")
        request_digest = (
            authorization.get("requestEnvelopeSha256")
            if isinstance(authorization, dict) else None
        )
        if (
            not isinstance(authorization, dict)
            or authorization.get("runId") != args.run_id
            or authorization.get("laneId") != args.lane
            or type(request_digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", request_digest) is None
            or type(args.request_envelope_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", args.request_envelope_sha256) is None
            or request_digest != args.request_envelope_sha256
        ):
            raise ValueError(
                "OpenRouter receipt does not match the recorded run, lane, "
                "and request envelope"
            )
        if not args.state_dir:
            raise ValueError("an OpenRouter receipt requires --state-dir")
        payload = translate_openrouter_receipt(receipt, context=context)
        # The request-envelope digest identifies authorized bytes, but retries
        # may legitimately send identical bytes. Bind the provider observation
        # itself so the same wrapper receipt cannot be appended as two attempts.
        # Deduplication happens later under the receipt-stream lock.
        payload["source_receipt_digest"] = _document_digest(receipt)
        payload["source_invocation_id"] = receipt["invocationId"]
        payload["source_request_digest"] = request_digest
        payload.update({
            "requested_provider": args.requested_executor,
            "attempted_provider": args.attempted_executor,
            "implemented_by": args.implemented_by,
        })
        return payload

    attribution = ProviderAttribution(
        requested_provider=args.requested_executor,
        attempted_provider=args.attempted_executor,
        implemented_by=args.implemented_by,
        provider=args.provider,
        model=args.model,
    )
    if bool(args.agent_definition) != bool(args.diff):
        missing = "--diff" if args.agent_definition else "--agent-definition"
        raise ValueError(
            "--agent-definition and --diff must be supplied together; missing "
            + missing
        )
    if args.agent_definition and args.diff:
        return measure_lane_inputs(
            args.agent_definition, args.diff, args.boilerplate,
            context=context, attribution=attribution,
        )
    payload = build_attempt_identity("record-attempt", context, attribution)
    payload["measurement_source"] = "attempt_unmeasured"
    payload["usage_estimated"] = False
    return payload


def command_record_attempt(args):
    """Record a lane's outcome and its measurement as one indivisible append.

    Before this command the two were separate obligations: write the lane
    receipt, then remember to run `openrouter-usage` or `lane-input-bytes`. The
    second half was prose in eleven consumer files, and prose is not a
    mechanism -- every run that forgot it produced a structurally valid
    `run-cost-summary.json` with `lanes: []`, which reads exactly like a run
    that cost nothing.

    Recording the lane now *is* recording its measurement. Both receipts are
    built, then appended together under one lock and validated as one stream:
    either both land or neither does. A recorded lane cannot be missing its
    usage row, because there is no call that writes one without the other.
    """
    error_label = "record-attempt"
    _validate_append_envelope(args, error_label)
    _reject_symlinked_receipt_stream(args.receipts, error_label)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", args.matrix_snapshot_date) is None:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        })
    try:
        datetime.strptime(args.matrix_snapshot_date, "%Y-%m-%d")
    except ValueError:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        }) from None
    scope_fields = (args.diff_scope, args.full_diff_override, args.slice_status)
    if args.stage == "review_dispatch":
        if any(value is None for value in scope_fields):
            raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
                ErrorDetailKey.REASON_CODE.value: "invalid_argument",
            })
        scoped = re.fullmatch(
            r"scoped\(([1-9][0-9]*) files of ([1-9][0-9]*)\)",
            args.diff_scope,
        )
        if args.diff_scope != "full" and scoped is None:
            raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
                ErrorDetailKey.REASON_CODE.value: "invalid_argument",
            })
        if scoped is not None and int(scoped.group(1)) > int(scoped.group(2)):
            raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
                ErrorDetailKey.REASON_CODE.value: "invalid_argument",
            })
        coherent = (
            scoped is not None
            and args.full_diff_override == "false"
            and args.slice_status == "sliced"
        ) or (
            args.diff_scope == "full"
            and (
                args.full_diff_override == "true"
                and args.slice_status == "full_diff_override"
                or args.full_diff_override == "false"
                and args.slice_status in {
                    "not_sliced", "unclassified", "slice_failed",
                }
            )
        )
        if not coherent:
            raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
                ErrorDetailKey.REASON_CODE.value: "invalid_argument",
            })
    elif any(value is not None for value in scope_fields):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        })
    try:
        usage = _attempt_usage_payload(args)
    except ValueError as error:
        sys.stderr.write(error_label + ": " + str(error) + "\n")
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_argument",
        }) from None

    lane_receipt = {
        "stage": args.stage,
        "status": args.status,
        "node_id": args.node_id,
        "authoritative_receipt": args.authoritative_receipt,
        "host": args.host,
        "lane": args.lane,
        "chunk_id": args.chunk_id,
        "attempt": args.attempt,
        "requested_executor": args.requested_executor,
        "attempted_executor": args.attempted_executor,
        "implemented_by": args.implemented_by,
        "matrix_snapshot_date": args.matrix_snapshot_date,
        "rung_rationale": args.rung_rationale,
    }
    if args.stage == "review_dispatch":
        lane_receipt.update({
            "diff_scope": args.diff_scope,
            "full_diff_override": args.full_diff_override == "true",
            "slice_status": args.slice_status,
        })
    if args.fallback_reason:
        lane_receipt["fallback_reason"] = args.fallback_reason
    usage_receipt = {
        "stage": "attempt_usage",
        "status": "observed",
        "authoritative_receipt": args.authoritative_receipt,
        **usage,
    }

    consumption_lock = None
    consumption_path = None
    lock_descriptor = None
    reservation = None
    reservation_ledger = None
    appended = False
    try:
        if "source_invocation_id" in usage:
            consumption_path, consumption_lock = _open_openrouter_consumption_lock(
                args.state_dir, args.run_id,
            )
            fcntl.flock(consumption_lock, fcntl.LOCK_EX)
        lock_descriptor = _open_receipt_stream_lock(args.receipts)
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        if os.path.exists(args.receipts):
            # Reject ambiguous input before the OpenRouter reservation writes
            # its durable consumption ledger. The append helper re-reads under
            # this same lock so its existing schema/translation gate stays the
            # single owner of the candidate stream.
            _load_json(args.receipts, strict=True)
        if consumption_path is not None:
            reservation_ledger, reservation = _reserve_openrouter_invocation(
                consumption_path, args.receipts, args.run_id, args.lane,
                usage, error_label,
            )
        _append_receipts_locked(
            args.receipts, error_label, [lane_receipt, usage_receipt],
            args.run_id, args.occurred_at,
        )
        appended = True
        if reservation is not None:
            _finish_openrouter_reservation(
                consumption_path, reservation_ledger, reservation,
                committed=True,
            )
    except BaseException:
        if reservation is not None and not appended:
            _finish_openrouter_reservation(
                consumption_path, reservation_ledger, reservation,
                committed=False,
            )
        raise
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        if consumption_lock is not None:
            os.close(consumption_lock)
    sys.stdout.write(json.dumps({
        "recorded": 2,
        "lane": args.lane,
        "measurement_source": usage["measurement_source"],
    }, sort_keys=True) + "\n")
    return 0


# Fixed PATH for the one runtime path that shells out; the caller's PATH
# never selects the docker binary that executes destructive stop/rm actions.
_FIXED_SUBPROCESS_PATH = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
_SUBPROCESS_ENV_PASSTHROUGH = (
    "HOME", "TMPDIR", "DOCKER_HOST", "DOCKER_CONFIG", "DOCKER_CONTEXT",
    "DOCKER_CERT_PATH", "DOCKER_TLS_VERIFY", "DOCKER_API_VERSION",
)


class _SubprocessRunner:
    """Executes Docker commands with a fixed PATH and a minimal environment."""

    def run(self, argv):
        from .resources import CommandResult
        argv = tuple(argv)
        if not argv:
            raise RuntimeUnavailableError("docker runtime unavailable")
        executable = argv[0] if os.path.isabs(argv[0]) else shutil.which(
            argv[0], path=_FIXED_SUBPROCESS_PATH,
        )
        if executable is None:
            raise RuntimeUnavailableError("docker runtime unavailable")
        env = {"PATH": _FIXED_SUBPROCESS_PATH}
        for name in _SUBPROCESS_ENV_PASSTHROUGH:
            if name in os.environ:
                env[name] = os.environ[name]
        try:
            result = subprocess.run(
                (executable,) + argv[1:], text=True, capture_output=True,
                check=False, env=env,
            )
        except FileNotFoundError:
            raise RuntimeUnavailableError("docker runtime unavailable") from None
        return CommandResult(argv, result.returncode, result.stdout, result.stderr)


def _registry(state_dir):
    from .resources import ResourceRegistry
    return ResourceRegistry(Path(state_dir) / "resources.jsonl")


def _scoped_docker_adapter(state_dir, *, lease_reader=False):
    from .adapters.docker import DockerAdapter
    scope = _repository_scope(state_dir)
    reader = (
        StateDirectoryLeaseReader(scope.lease_root, scope.scope_id)
        if lease_reader else None
    )
    return scope, DockerAdapter(
        _SubprocessRunner(), repository_scope_id=scope.scope_id,
        lease_reader=reader,
    )


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
        {"run_id", "terminal", "stale_sweep", "repository_scope_id"},
        {"run_id", "node_id", "terminal", "stale_sweep", "repository_scope_id"},
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
                     scope.get("terminal", False), scope.get("stale_sweep", False),
                     scope["repository_scope_id"]),
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

    def __init__(self, root, repository_scope_id, *, now=None):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("invalid state directory")
        if re.fullmatch(r"[0-9a-f]{64}", repository_scope_id) is None:
            raise ValueError("invalid repository scope identity")
        self.repository_scope_id = repository_scope_id
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _state_path(self, run_id):
        if type(run_id) is not str or self._RUN_ID.fullmatch(run_id) is None:
            raise ValueError("invalid lease run id")
        run_dir = self.root / "runs" / run_id
        return None if not run_dir.is_dir() else run_dir / "run-state.json"

    def _proof(self, run_id, state_path):
        from .adapters.docker import LeaseProof
        from .schema import RunStatus
        try:
            state = StateStore(state_path).load()
        except FileNotFoundError:
            return None
        ledger, _notes = EventStore(state_path.parent).validate(recovery=False)
        if (
            not ledger
            or ledger[0].kind != "run.initialized"
            or ledger[0].payload.get("repository_scope_id") != self.repository_scope_id
        ):
            raise ValueError("lease state repository scope mismatch")
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
        return LeaseProof(
            run_id, state.status not in terminal, True, observed_at,
            self.repository_scope_id,
        )

    def read(self, run_id):
        from .adapters.docker import LeaseProof
        from .schema import LeaseConflictError
        state_path = self._state_path(run_id)
        if state_path is None:
            return None
        try:
            with RunLease(state_path):
                return self._proof(run_id, state_path)
        except LeaseConflictError:
            observed_at = self.now()
            if (
                type(observed_at) is not datetime or observed_at.tzinfo is None
                or observed_at.utcoffset() is None
            ):
                raise ValueError("invalid lease reader clock") from None
            return LeaseProof(
                run_id, True, True, observed_at, self.repository_scope_id,
            )

    @contextmanager
    def inactive_guard(self, run_id):
        state_path = self._state_path(run_id)
        if state_path is None:
            raise ValueError("stale cleanup lease proof unavailable")
        with RunLease(state_path):
            proof = self._proof(run_id, state_path)
            if proof is None or proof.active:
                raise ValueError("stale cleanup run is not inactive")
            yield proof


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
    argv = _load_json(args.argv_json)
    dependencies = ()
    if args.dependent_node_ids_json:
        dependencies = _load_json(args.dependent_node_ids_json)
    if type(argv) is not list or type(dependencies) not in {list, tuple}:
        raise ValueError("invalid Docker argv")
    _scope, adapter = _scoped_docker_adapter(args.state_dir)
    plan = adapter.plan_create(
        argv, args.run_id, args.node_id, args.lifecycle, args.cleanup_policy,
        dependent_node_ids=tuple(dependencies),
    )
    _write_json(args.output, _creation_plan_dict(plan))
    return 0 if plan.managed else EXIT_UNSAFE_PLAN


def command_plan_compose(args):
    argv = _load_json(args.argv_json)
    dependencies = () if not args.dependent_node_ids_json else _load_json(args.dependent_node_ids_json)
    if type(argv) is not list or type(dependencies) not in {list, tuple}:
        raise ValueError("invalid Docker argv")
    _scope, adapter = _scoped_docker_adapter(args.state_dir)
    plan = adapter.plan_compose(
        argv, args.run_id, args.node_id, args.lifecycle, args.cleanup_policy,
        dependent_node_ids=tuple(dependencies),
    )
    _write_json(args.output, _creation_plan_dict(plan))
    return 0 if plan.managed else EXIT_UNSAFE_PLAN


def command_record_create(args):
    from .resources import _disposition_json, _resource_json
    _scope, adapter = _scoped_docker_adapter(args.state_dir)
    receipt = adapter.record_creation(
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
    scope, adapter = _scoped_docker_adapter(args.state_dir)
    registry = _registry(args.state_dir)
    records = registry.resources_for(args.run_id, args.node_id)
    inventory = adapter.inventory_registered(records)
    proof = _incomplete_node_proof(
        scope.lease_root / "runs" / args.run_id,
        args.run_id, records, args.node_statuses,
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
    scope, adapter = _scoped_docker_adapter(args.state_dir, lease_reader=True)
    registry = _registry(args.state_dir)
    records = registry.resources_for(args.run_id)
    inventory = adapter.inventory_registered(records)
    plan = adapter.plan_reconcile_run(
        registry, inventory, args.run_id,
        incomplete_node_proof=_incomplete_node_proof(
            scope.lease_root / "runs" / args.run_id,
            args.run_id, records, args.node_statuses,
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
    if plan.scope.repository_scope_id != _repository_scope(args.state_dir).scope_id:
        raise ValueError("cleanup plan repository scope mismatch")
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
    from .resources import cleanup_step_identities
    scope, adapter = _scoped_docker_adapter(args.state_dir)
    plan, sealed_inventory = _cleanup_document(_load_json(args.plan))
    if plan.scope.repository_scope_id != scope.scope_id:
        raise ValueError("cleanup plan repository scope mismatch")
    identities = cleanup_step_identities(plan)
    if args.step_index < 0 or args.step_index >= len(identities):
        raise ValueError("invalid cleanup step")
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
        orphan_mode = plan.scope.stale_sweep
        lease_context = (
            StateDirectoryLeaseReader(
                scope.lease_root, scope.scope_id,
            ).inactive_guard(action.run_id)
            if orphan_mode else nullcontext(None)
        )
        with lease_context as lease_proof:
            if orphan_mode:
                current = adapter.inventory()
                records = ()
                proof = None
            else:
                record, active = registry.resource_state_for_exact(
                    action.kind, action.resource_id,
                )
                if not active or record is None:
                    raise ValueError("cleanup resource is not active")
                records = (record,)
                current = adapter.inventory_registered(records)
                proof = _incomplete_node_proof(
                    scope.lease_root / "runs" / action.run_id,
                    action.run_id, records,
                    args.node_statuses,
                )
            witness = _inventory(_load_json(args.inventory))
            if _inventory_dict(witness) != _inventory_dict(current):
                raise ValueError("cleanup inventory witness mismatch")
            resource = next((
                item for item in current.resources
                if item.kind is action.kind
                and item.resource_id == action.resource_id
            ), None)
            if resource is None:
                raise ValueError("cleanup resource unavailable")
            guarded = registry.execute_guarded_action(
                adapter, plan, args.step_index, resource,
                adapter.runner.run, lease_proof=lease_proof,
                incomplete_node_proof=proof, orphan_mode=orphan_mode,
                authority_prefix=authorities,
            )
    _write_json(args.output, _authority_dict(guarded))
    return 0


def command_record_cleanup(args):
    scope, adapter = _scoped_docker_adapter(args.state_dir)
    plan, before = _cleanup_document(_load_json(args.plan))
    if plan.scope.repository_scope_id != scope.scope_id:
        raise ValueError("cleanup plan repository scope mismatch")
    raw_results = _load_json(args.outcomes)
    if type(raw_results) is not list:
        raise ValueError("invalid guarded cleanup results")
    results = tuple(_authority(item) for item in raw_results)
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


def _inspection_json(path):
    from .inspection import decode_json_bytes

    try:
        return decode_json_bytes(Path(path).read_bytes())
    except OSError:
        raise InvalidSchemaError(ErrorMessage.OPERATION_FAILED, {
            ErrorDetailKey.REASON_CODE.value: "input_read_failed",
        }) from None


def command_inspection_validate(args):
    from .inspection import load_inspection_profile, load_result_policy

    profile = load_inspection_profile(args.profile, args.repository_root)
    result_policy = load_result_policy(args.result_policy)
    _emit({
        "schema_version": 1, "status": "validated",
        "profile_id": profile.document["profile_id"],
        "profile_version": profile.document["profile_version"],
        "profile_path": profile.profile_path,
        "profile_digest": profile.digest,
        "result_policy_id": result_policy.document["policy_id"],
        "result_policy_version": result_policy.document["policy_version"],
        "result_policy_digest": result_policy.digest,
    })
    return 0


def command_snapshot_files(args):
    from .inspection import snapshot_regular_files

    _emit({
        "schema_version": 1,
        "status": "snapshotted",
        "files": snapshot_regular_files(
            args.source_root,
            args.destination_root,
            args.name,
        ),
    })
    return 0


def command_kernel_info(args):
    version = ".".join(str(item) for item in KERNEL_VERSION)
    requested = (
        semantic_version(args.minimum_version)
        if args.minimum_version
        else KERNEL_VERSION
    )
    if (
        requested is None
        or requested[0] != KERNEL_VERSION[0]
        or KERNEL_VERSION < requested
    ):
        raise InvalidSchemaError(ErrorMessage.OPERATION_FAILED, {
            ErrorDetailKey.REASON_CODE.value: "kernel_version_incompatible",
        })
    _emit({
        "schema_version": 1,
        "kernel_version": version,
        "status": "compatible",
    })
    return 0


def command_inspection_classify(args):
    from .inspection import classify_observations, load_inspection_profile

    profile = load_inspection_profile(args.profile, args.repository_root)
    observations = _inspection_json(args.observations)
    _emit({
        "schema_version": 1,
        "classifications": classify_observations(profile, observations),
    })
    return 0


def command_inspection_trend(args):
    from .inspection import compare_trends, load_host_publication_authority_key

    publication_key = load_host_publication_authority_key(args.repository_root)
    _emit(compare_trends(
        _inspection_json(args.current), _inspection_json(args.baseline),
        publication_authority_key=publication_key,
    ))
    return 0


def command_inspection_finalize(args):
    from .inspection import (
        finalize_authoritative_result, load_host_publication_authority_key,
    )

    baseline = None if args.baseline is None else _inspection_json(args.baseline)
    publication_key = load_host_publication_authority_key(args.repository_root)
    _emit(finalize_authoritative_result(
        _inspection_json(args.input),
        publication_status=args.publication_status,
        baseline=baseline,
        publication_authority_key=publication_key,
    ))
    return 0


def command_inspection_publish(args):
    from .publication import publish_authoritative_result

    _emit(publish_authoritative_result(
        _inspection_json(args.input),
        args.repository_root,
    ))
    return 0


def command_inspection_render(args):
    from .inspection import render_markdown, load_host_publication_authority_key

    publication_key = load_host_publication_authority_key(args.repository_root)
    sys.stdout.write(render_markdown(
        _inspection_json(args.input),
        publication_authority_key=publication_key,
    ))
    return 0


def command_inspection_run(args):
    from .inspection import (
        build_authoritative_result, execute_inspection_lanes,
        load_host_attestation, load_inspection_profile,
        load_host_publication_authority_key, load_result_policy,
    )

    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    profile = load_inspection_profile(args.profile, args.repository_root)
    result_policy = load_result_policy(args.result_policy)
    attestation = load_host_attestation(args.attestation, profile.repository_root)
    publication_key = load_host_publication_authority_key(
        profile.repository_root,
    )
    dirty = args.dirty == "true"
    receipts, observations = execute_inspection_lanes(
        profile, args.lane_id, attestation,
        source=args.source, ref=args.ref, commit=args.commit, dirty=dirty,
        purpose=args.purpose,
        operator_authorization_event_id=args.authorization_event_id,
        return_observations=True,
    )
    finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _emit(build_authoritative_result(
        profile, result_policy,
        source=args.source, ref=args.ref, commit=args.commit, dirty=dirty,
        observations=observations, lane_receipts=receipts,
        invocation={
            "started_at": started_at, "finished_at": finished_at,
            "operator_authorization_event_id": attestation[
                "operator_authorization_event_id"
            ],
            "purpose": args.purpose, "selected_lane_ids": sorted(args.lane_id),
        },
        publication_authority_key=publication_key,
    ))
    return 0


def command_resolve_plugin_bundle(args):
    try:
        bundle = resolve_plugin_bundle(
            args.plugin, args.required_asset,
            active_host=args.active_host, minimum_version=args.minimum_version,
            required_executables=args.required_executable,
        )
    except (FileNotFoundError, ValueError):
        raise InvalidSchemaError(ErrorMessage.OPERATION_FAILED, {
            ErrorDetailKey.REASON_CODE.value: "plugin_bundle_unavailable",
        }) from None
    _emit(bundle.to_dict())
    return 0


def command_resolve_plugin_asset(args):
    """Print one caller-bindable asset path from a coherent plugin bundle."""
    try:
        bundle = resolve_plugin_bundle(
            args.plugin, [args.asset], active_host=args.active_host,
            minimum_version=args.minimum_version,
        )
        asset = (bundle.root / args.asset).resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        raise InvalidSchemaError(ErrorMessage.OPERATION_FAILED, {
            ErrorDetailKey.REASON_CODE.value: "plugin_bundle_unavailable",
        }) from None
    sys.stdout.write(str(asset) + "\n")
    return 0


def _repository_profile_ref(repository_root, profile_path):
    repository = Path(repository_root).resolve(strict=True)
    if Path(profile_path).is_symlink():
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "verification_profile_symlink",
        })
    profile = Path(profile_path).resolve(strict=True)
    try:
        return repository, profile.relative_to(repository).as_posix()
    except ValueError:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "verification_profile_outside_repository",
        }) from None


def _exact_commit(repository, value):
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--verify", f"{value}^{{commit}}"],
        capture_output=True, check=False, text=True,
    )
    commit = result.stdout.strip()
    if (
        result.returncode != 0
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit) is None
    ):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "verification_commit_unresolved",
        })
    return commit


def command_plan_verification(args):
    from .verification_errors import VerificationPlannerError
    from .verification_planning import build_plan

    repository, profile_ref = _repository_profile_ref(
        args.repository_root, args.profile,
    )
    base_commit = _exact_commit(repository, args.base_ref)
    head_commit = _exact_commit(repository, args.candidate_ref)
    try:
        plan = build_plan(
            _load_json(args.profile), repository, profile_ref, None,
            args.boundary, args.risk,
            base_commit=base_commit, head_commit=head_commit,
            include_worktree=args.include_worktree,
        )
    except VerificationPlannerError as exc:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_repository_verification",
        }) from exc
    _write_json(args.output, plan)
    _emit(plan)
    return EXIT_UNSAFE_PLAN if plan["status"] == "blocked" else 0


def command_run_verification(args):
    from .verification_errors import VerificationPlannerError
    from .verification_orchestrator import execute_plan

    repository, profile_ref = _repository_profile_ref(
        args.repository_root, args.profile,
    )
    try:
        plan = _load_json(args.plan)
        if type(plan) is not dict or plan.get("profile_ref") != profile_ref:
            raise VerificationPlannerError(
                "verification plan profile does not match --profile",
            )
        result = execute_plan(
            _load_json(args.profile), repository, plan,
        )
    except VerificationPlannerError as exc:
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "invalid_repository_verification",
        }) from exc
    _emit(result)
    return 0 if result["status"] == "complete" else EXIT_UNSAFE_PLAN


def command_owned_run_start(args):
    from .owned_run import ExactOwnedRun

    run = ExactOwnedRun.start(
        args.workflow, args.run_id,
        base=None if args.base is None else Path(args.base),
    )
    _emit({
        "schema_version": 1, "status": "started", "path": str(run.root),
        "workflow": run.workflow, "run_id": run.run_id,
    })
    return 0


def command_owned_run_create(args):
    from .owned_run import ExactOwnedRun

    run = ExactOwnedRun.open(Path(args.run_root))
    path = run.create_path(args.kind, args.relative_path)
    _emit({
        "schema_version": 1, "status": "created", "path": str(path),
        "kind": args.kind, "run_root": str(run.root),
    })
    return 0


def command_owned_run_finish(args):
    from .owned_run import ExactOwnedRun

    root = Path(os.path.abspath(args.run_root))
    if not os.path.lexists(root):
        _emit({"schema_version": 1, "status": "missing", "path": str(root)})
        return 0
    report = ExactOwnedRun.open(root).finish(
        args.outcome, retain_diagnostics=args.retain_diagnostics,
        reason=args.reason, contains=args.contains,
    )
    _emit({"schema_version": 1, **report.to_dict()})
    return 0


def command_owned_run_exec(args):
    from .owned_run import run_owned_command

    command = tuple(args.argv)
    if command[:1] == ("--",):
        command = command[1:]
    status, report = run_owned_command(
        args.workflow, args.run_id, command,
        base=None if args.base is None else Path(args.base),
        resume_root=None if args.resume_root is None else Path(args.resume_root),
        retain_on_failure=args.retain_on_failure,
        diagnostic_contains=args.contains,
    )
    _emit({"schema_version": 1, **report.to_dict()})
    return status


def parser():
    from .verification_contract import BOUNDARY_CHOICES
    from .verification_repository import RISK_CHOICES

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

    retry = commands.add_parser(
        "decide-validation-retry",
        help="project the canonical validation retry decision",
    )
    retry.add_argument(
        "--reason", choices=(
            "provider_unavailable", "deterministic_validation_failure",
            "reviewer_finding", "browser_recovery", "cleanup", "infrastructure",
        ), required=True,
    )
    retry.add_argument("--state-dir", required=True)
    retry.add_argument("--signature")
    retry.set_defaults(handler=command_decide_validation_retry)

    bind_prediction = commands.add_parser(
        "bind-prediction", help="seal one independent pre-action prediction",
    )
    bind_prediction.add_argument("--type", choices=("pipeline", "review"), required=True)
    bind_prediction.add_argument("--manifest")
    bind_prediction.add_argument("--request")
    bind_prediction.add_argument("--prediction-receipts", required=True)
    bind_prediction.add_argument("--state-dir", required=True)
    bind_prediction.set_defaults(handler=command_bind_prediction)

    bind_contract = commands.add_parser(
        "bind-verification-contract",
        help="validate and bind one initial behavioral verification contract",
    )
    bind_contract.add_argument("--state-dir", required=True)
    bind_contract.add_argument("--contract", required=True)
    bind_contract.add_argument("--verification-profile")
    bind_contract.set_defaults(handler=command_bind_verification_contract)

    observe_pipeline = commands.add_parser("observe-pipeline", help="observe authoritative pipeline receipts")
    observe_pipeline.add_argument("--manifest", required=True)
    observe_pipeline.add_argument("--receipts", required=True)
    observe_pipeline.add_argument("--state-dir", required=True)
    observe_pipeline.set_defaults(handler=command_observe_pipeline)

    reconcile_legacy_browser = commands.add_parser(
        "reconcile-legacy-browser",
        help="append the closed Pipeline legacy browser-recovery reconciliation",
        description=(
            "Derive and atomically append one reconciliation for an exact earlier "
            "blocked browser_recovery row that lacks recovery_receipts. The "
            "original row remains unchanged; all other invalid rows are rejected."
        ),
    )
    reconcile_legacy_browser.add_argument("--events", required=True)
    reconcile_legacy_browser.add_argument(
        "--target-sequence", required=True, type=int,
    )
    reconcile_legacy_browser.add_argument("--occurred-at", required=True)
    reconcile_legacy_browser.add_argument(
        "--authoritative-receipt", required=True,
    )
    reconcile_legacy_browser.set_defaults(
        handler=command_reconcile_legacy_browser,
    )

    observe_review = commands.add_parser("observe-review", help="observe authoritative review receipts")
    observe_review.add_argument("--request", required=True)
    observe_review.add_argument("--receipts", required=True)
    observe_review.add_argument("--state-dir", required=True)
    observe_review.set_defaults(handler=command_observe_review)

    export_contributions = commands.add_parser(
        "export-review-contributions",
        help="append canonical dm-review finding-contribution receipts",
    )
    export_contributions.add_argument("--request", required=True)
    export_contributions.add_argument("--decisions", required=True)
    export_contributions.add_argument("--raw-findings", required=True)
    export_contributions.add_argument("--lane-receipts", required=True)
    export_contributions.add_argument("--raw-lane-outputs", required=True)
    export_contributions.add_argument("--receipts", required=True)
    export_contributions.add_argument("--state-dir", required=True)
    export_contributions.add_argument("--output", required=True)
    export_contributions.set_defaults(
        handler=command_export_review_contributions,
    )

    compare = commands.add_parser("compare", help="compare shadow state with authoritative receipts")
    compare.add_argument("--state-dir", required=True)
    compare.add_argument("--authoritative-receipts", required=True)
    compare.add_argument("--output", required=True)
    compare.set_defaults(handler=command_compare)

    metrics = commands.add_parser("metrics", help="aggregate receipt reliability metrics")
    metrics.add_argument("--events", required=True)
    metrics.add_argument("--output", required=True)
    metrics.set_defaults(handler=command_metrics)

    observation_index = commands.add_parser(
        "emit-observation-index",
        help="validate and emit one bounded observation-index-v1 sidecar",
    )
    observation_index.add_argument("--input", required=True)
    observation_index.add_argument("--output", required=True)
    observation_index.set_defaults(handler=command_emit_observation_index)

    run_cost_summary = commands.add_parser(
        "run-cost-summary",
        help="emit a schema-bound per-run cost summary artifact",
    )
    run_cost_summary.add_argument("--events", required=True)
    run_cost_summary.add_argument("--output", required=True)
    run_cost_summary.add_argument("--repository-commit", default=None)
    run_cost_summary.add_argument(
        "--matrix", default=None,
        help="optional caller-selected installed-plugin matrix asset",
    )
    run_cost_summary.add_argument("--dirty-state", action="store_true", default=False)
    run_cost_summary.add_argument(
        "--receipt-line", default=None,
        help=(
            "append 'run-cost-summary: <artifact path>' to this run-receipt "
            "file after the artifact is written"
        ),
    )
    run_cost_summary.set_defaults(handler=command_run_cost_summary)

    emit_cost_summary = commands.add_parser(
        "emit-cost-summary",
        help="clear, build, write, and record the run cost summary in one step",
    )
    emit_cost_summary.add_argument("--events", required=True)
    emit_cost_summary.add_argument("--output", required=True)
    emit_cost_summary.add_argument("--receipt", required=True)
    emit_cost_summary.add_argument("--repository-commit", default=None)
    emit_cost_summary.add_argument(
        "--matrix", default=None,
        help="optional caller-selected installed-plugin matrix asset",
    )
    emit_cost_summary.add_argument(
        "--dirty-state", action="store_true", default=False,
    )
    emit_cost_summary.set_defaults(handler=command_emit_cost_summary)

    openrouter_usage = commands.add_parser(
        "openrouter-usage",
        help="translate one OpenRouter wrapper receipt into an attempt usage payload",
    )
    openrouter_usage.add_argument("--receipt", required=True)
    openrouter_usage.add_argument("--lane", required=True)
    openrouter_usage.add_argument("--chunk-id", required=True)
    openrouter_usage.add_argument("--node-id", required=True)
    openrouter_usage.add_argument("--attempt", required=True, type=int)
    openrouter_usage.add_argument("--host", required=True)
    openrouter_usage.add_argument("--duration-seconds", required=True, type=float)
    openrouter_usage.add_argument("--output", default=None)
    openrouter_usage.add_argument(
        "--append-to", default=None,
        help=(
            "append the payload to this authoritative receipt array as an "
            "attempt_usage receipt instead of printing it"
        ),
    )
    openrouter_usage.add_argument("--run-id", default=None)
    openrouter_usage.add_argument("--occurred-at", default=None)
    openrouter_usage.add_argument("--authoritative-receipt", default=None)
    openrouter_usage.set_defaults(handler=command_openrouter_usage)

    lane_input_bytes = commands.add_parser(
        "lane-input-bytes",
        help="measure deterministic per-lane input bytes into an attempt usage payload",
    )
    lane_input_bytes.add_argument("--agent-definition", required=True)
    lane_input_bytes.add_argument("--diff", required=True)
    lane_input_bytes.add_argument("--boilerplate", action="append", default=[])
    lane_input_bytes.add_argument("--lane", required=True)
    lane_input_bytes.add_argument("--chunk-id", required=True)
    lane_input_bytes.add_argument("--node-id", required=True)
    lane_input_bytes.add_argument("--attempt", required=True, type=int)
    lane_input_bytes.add_argument("--host", required=True)
    lane_input_bytes.add_argument("--duration-seconds", required=True, type=float)
    lane_input_bytes.add_argument("--requested-provider", required=True)
    lane_input_bytes.add_argument("--attempted-provider", required=True)
    lane_input_bytes.add_argument("--implemented-by", required=True)
    lane_input_bytes.add_argument("--provider", required=True)
    lane_input_bytes.add_argument("--model", required=True)
    lane_input_bytes.add_argument("--output", default=None)
    lane_input_bytes.add_argument(
        "--append-to", default=None,
        help=(
            "append the payload to this authoritative receipt array as an "
            "attempt_usage receipt instead of printing it"
        ),
    )
    lane_input_bytes.add_argument("--run-id", default=None)
    lane_input_bytes.add_argument("--occurred-at", default=None)
    lane_input_bytes.add_argument("--authoritative-receipt", default=None)

    record_attempt = commands.add_parser(
        "record-attempt",
        help="append a lane outcome and its measurement as one unit",
    )
    record_attempt.add_argument("--receipts", required=True)
    record_attempt.add_argument("--run-id", required=True)
    record_attempt.add_argument("--occurred-at", required=True)
    record_attempt.add_argument("--authoritative-receipt", required=True)
    record_attempt.add_argument("--stage", required=True)
    record_attempt.add_argument("--status", required=True)
    record_attempt.add_argument("--lane", required=True)
    record_attempt.add_argument("--chunk-id", required=True)
    record_attempt.add_argument("--node-id", required=True)
    record_attempt.add_argument("--attempt", required=True, type=int)
    record_attempt.add_argument("--host", required=True)
    record_attempt.add_argument("--duration-seconds", required=True, type=float)
    record_attempt.add_argument("--requested-executor", required=True)
    record_attempt.add_argument("--attempted-executor", required=True)
    record_attempt.add_argument("--implemented-by", required=True)
    record_attempt.add_argument("--matrix-snapshot-date", required=True)
    record_attempt.add_argument(
        "--rung-rationale", required=True,
        choices=("cost", "context", "strength", "availability"),
    )
    record_attempt.add_argument("--diff-scope", default=None)
    record_attempt.add_argument(
        "--full-diff-override", choices=("true", "false"), default=None,
    )
    record_attempt.add_argument(
        "--slice-status",
        choices=(
            "sliced", "not_sliced", "unclassified", "slice_failed",
            "full_diff_override",
        ),
        default=None,
    )
    record_attempt.add_argument("--fallback-reason", default=None)
    # Measurement evidence. An OpenRouter receipt wins; otherwise the lane input
    # files are measured; otherwise the row is recorded `attempt_unmeasured`.
    record_attempt.add_argument("--openrouter-receipt", default=None)
    record_attempt.add_argument("--request-envelope-sha256", default=None)
    record_attempt.add_argument("--state-dir", default=None)
    record_attempt.add_argument("--agent-definition", default=None)
    record_attempt.add_argument("--diff", default=None)
    record_attempt.add_argument("--boilerplate", action="append", default=[])
    record_attempt.add_argument("--requested-provider", default=None)
    record_attempt.add_argument("--attempted-provider", default=None)
    record_attempt.add_argument("--provider", default="not_reported")
    record_attempt.add_argument("--model", default="not_reported")
    record_attempt.set_defaults(handler=command_record_attempt)
    lane_input_bytes.set_defaults(handler=command_lane_input_bytes)

    plan_verification = commands.add_parser(
        "plan-verification",
        help="select tiered repository verification lanes for one boundary",
        description=(
            "Validate a repository-owned command-array profile, resolve changed "
            "paths, and select only the lanes scheduled for this boundary."
        ),
    )
    plan_verification.add_argument("--repository-root", required=True)
    plan_verification.add_argument("--profile", required=True)
    plan_verification.add_argument(
        "--boundary", choices=BOUNDARY_CHOICES, required=True,
    )
    plan_verification.add_argument(
        "--risk", choices=RISK_CHOICES, required=True,
    )
    plan_verification.add_argument(
        "--base-ref", required=True,
        help="Git commit or ref used as the exact changed-path base",
    )
    plan_verification.add_argument(
        "--candidate-ref", default="HEAD",
        help="Git commit or ref to verify (default: HEAD)",
    )
    plan_verification.add_argument(
        "--include-worktree", action="store_true",
        help="include staged, unstaged, and untracked changes",
    )
    plan_verification.add_argument("--output", required=True)
    plan_verification.set_defaults(handler=command_plan_verification)

    run_verification = commands.add_parser(
        "run-verification",
        help="execute exact local lanes from a fresh repository verification plan",
        description=(
            "Revalidate the profile, source inputs, commands, and plan identity "
            "before executing local argv arrays without a shell. Remote lanes "
            "remain explicit in the invocation result."
        ),
    )
    run_verification.add_argument("--repository-root", required=True)
    run_verification.add_argument("--profile", required=True)
    run_verification.add_argument("--plan", required=True)
    run_verification.set_defaults(handler=command_run_verification)

    owned_start = commands.add_parser(
        "owned-run-start",
        help="create one unique exact-owned disposable run root",
    )
    owned_start.add_argument("--workflow", required=True)
    owned_start.add_argument("--run-id", required=True)
    owned_start.add_argument("--base")
    owned_start.set_defaults(handler=command_owned_run_start)

    owned_create = commands.add_parser(
        "owned-run-create",
        help="create and record one directory inside an exact-owned run root",
    )
    owned_create.add_argument("--run-root", required=True)
    owned_create.add_argument(
        "--kind", choices=(
            "temporary-directory", "temporary-repository", "cache",
            "raw-output", "diagnostic",
        ), required=True,
    )
    owned_create.add_argument("--relative-path", required=True)
    owned_create.set_defaults(handler=command_owned_run_create)

    owned_finish = commands.add_parser(
        "owned-run-finish",
        help="remove one exact-owned root or retain one bounded diagnostic root",
    )
    owned_finish.add_argument("--run-root", required=True)
    owned_finish.add_argument(
        "--outcome", choices=(
            "succeeded", "failed", "blocked", "cancelled", "interrupted",
            "review-aborted",
        ), required=True,
    )
    owned_finish.add_argument("--retain-diagnostics", action="store_true")
    owned_finish.add_argument("--reason")
    owned_finish.add_argument("--contains")
    owned_finish.set_defaults(handler=command_owned_run_finish)

    owned_exec = commands.add_parser(
        "owned-run-exec",
        help="supervise one argv command with exact INT/TERM cleanup",
    )
    owned_exec.add_argument("--workflow", required=True)
    owned_exec.add_argument("--run-id", required=True)
    owned_location = owned_exec.add_mutually_exclusive_group()
    owned_location.add_argument("--base")
    owned_location.add_argument("--resume-root")
    owned_exec.add_argument("--retain-on-failure", action="store_true")
    owned_exec.add_argument("--contains", default="compact command diagnostics")
    owned_exec.add_argument("argv", nargs=argparse.REMAINDER)
    owned_exec.set_defaults(handler=command_owned_run_exec)

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

    snapshot_files = commands.add_parser(
        "snapshot-files",
        help="copy owned regular files without following links",
        description=(
            "Read source files descriptor-relatively with no-follow identity "
            "checks and create private destination files with exact bytes."
        ),
    )
    snapshot_files.add_argument("--source-root", required=True)
    snapshot_files.add_argument("--destination-root", required=True)
    snapshot_files.add_argument("--name", action="append", required=True)
    snapshot_files.set_defaults(handler=command_snapshot_files)

    kernel_info = commands.add_parser(
        "kernel-info",
        help="report and validate the workflow-kernel runtime version",
        description=(
            "Emit the runtime version and fail non-zero when it is incompatible "
            "with an optional semantic-version floor."
        ),
    )
    kernel_info.add_argument("--minimum-version")
    kernel_info.set_defaults(handler=command_kernel_info)

    inspection_validate = commands.add_parser(
        "inspection-validate",
        help="validate a complete inspection profile and emit its canonical digest",
        description=(
            "Validate one closed inspection profile before lane admission. "
            "Failures are structured JSON on stderr with a non-zero exit."
        ),
    )
    inspection_validate.add_argument("--repository-root", required=True)
    inspection_validate.add_argument("--profile", required=True)
    inspection_validate.add_argument("--result-policy", required=True)
    inspection_validate.set_defaults(handler=command_inspection_validate)

    inspection_classify = commands.add_parser(
        "inspection-classify",
        help="classify observations against closed validated profile IDs",
        description=(
            "Emit deterministic JSON classifications; unknown inputs are actionable "
            "fail-closed results. Invalid inputs exit non-zero."
        ),
    )
    inspection_classify.add_argument("--repository-root", required=True)
    inspection_classify.add_argument("--profile", required=True)
    inspection_classify.add_argument("--observations", required=True)
    inspection_classify.set_defaults(handler=command_inspection_classify)

    inspection_trend = commands.add_parser(
        "inspection-trend",
        help="compare compatible authoritative inspection results",
        description=(
            "Emit JSON deltas or a baseline_discontinuity. Invalid authoritative "
            "JSON exits non-zero."
        ),
    )
    inspection_trend.add_argument("--current", required=True)
    inspection_trend.add_argument("--baseline", required=True)
    inspection_trend.add_argument("--repository-root", required=True)
    inspection_trend.set_defaults(handler=command_inspection_trend)

    inspection_finalize = commands.add_parser(
        "inspection-finalize",
        help="advance authoritative inspection publication and trend lifecycle",
        description=(
            "Validate authoritative JSON, compute an optional baseline trend, "
            "and rebind the ready-state attestation before emitting a re-digested "
            "artifact. Rendered and published transitions are available only "
            "through inspection-publish. Invalid lifecycle input exits non-zero."
        ),
    )
    inspection_finalize.add_argument("--input", required=True)
    inspection_finalize.add_argument("--repository-root", required=True)
    inspection_finalize.add_argument(
        "--publication-status",
        choices=("authoritative_json_ready",),
        required=True,
    )
    inspection_finalize.add_argument(
        "--baseline",
        help=(
            "authoritative baseline JSON; the kernel computes and binds the "
            "trend result rather than accepting caller-supplied deltas"
        ),
    )
    inspection_finalize.set_defaults(handler=command_inspection_finalize)

    inspection_publish = commands.add_parser(
        "inspection-publish",
        help="durably publish profile-declared Markdown and authoritative JSON",
        description=(
            "Render and durably replace the validated profile-declared Markdown "
            "and authoritative JSON outputs, minting lifecycle attestations only "
            "after the corresponding writes. Failures exit non-zero."
        ),
    )
    inspection_publish.add_argument("--input", required=True)
    inspection_publish.add_argument("--repository-root", required=True)
    inspection_publish.set_defaults(handler=command_inspection_publish)

    inspection_render = commands.add_parser(
        "inspection-render",
        help="render Markdown from validated authoritative inspection JSON",
        description=(
            "Accept only validated authoritative JSON and emit Markdown. Prose or "
            "digest-mismatched JSON exits non-zero."
        ),
    )
    inspection_render.add_argument("--input", required=True)
    inspection_render.add_argument("--repository-root", required=True)
    inspection_render.set_defaults(handler=command_inspection_render)

    inspection_run = commands.add_parser(
        "inspection-run",
        help="run attested Docker-backed lanes from an immutable profile snapshot",
        description=(
            "Validate and freeze a profile, verify a host-issued attestation outside "
            "the repository, execute selected declared primary lanes without a "
            "shell, and emit authoritative JSON. Any admission failure exits "
            "non-zero before subprocess execution."
        ),
    )
    inspection_run.add_argument("--repository-root", required=True)
    inspection_run.add_argument("--profile", required=True)
    inspection_run.add_argument(
        "--result-policy",
        required=True,
        help="trusted workflow-owned result-policy JSON",
    )
    inspection_run.add_argument(
        "--lane-id", action="append", required=True,
        help="declared primary lane ID; repeat for multiple lanes",
    )
    inspection_run.add_argument(
        "--attestation", required=True,
        help="host-issued attestation file outside the repository",
    )
    inspection_run.add_argument("--source", choices=("git",), required=True)
    inspection_run.add_argument("--ref", required=True)
    inspection_run.add_argument("--commit", required=True)
    inspection_run.add_argument("--dirty", choices=("true", "false"), required=True)
    inspection_run.add_argument("--purpose", required=True)
    inspection_run.add_argument(
        "--authorization-event-id", required=True,
        help="host-observed operator authorization event bound by the attestation",
    )
    inspection_run.set_defaults(handler=command_inspection_run)

    resolve_bundle = commands.add_parser(
        "resolve-plugin-bundle",
        help="select one coherent installed-plugin bundle across host caches",
        description=(
            "Emit one home-relative selected root, cache class, semantic version, "
            "and selection reason. Malformed, incompatible, or incomplete bundles "
            "exit non-zero."
        ),
    )
    resolve_bundle.add_argument("--plugin", required=True)
    resolve_bundle.add_argument(
        "--required-asset", action="append", default=[],
        help="required path relative to the selected plugin root; repeat as needed",
    )
    resolve_bundle.add_argument(
        "--required-executable", action="append", default=[],
        help=(
            "required readable executable path relative to the selected plugin "
            "root; repeat as needed"
        ),
    )
    resolve_bundle.add_argument("--minimum-version")
    resolve_bundle.add_argument("--active-host", choices=("claude", "codex"))
    resolve_bundle.set_defaults(handler=command_resolve_plugin_bundle)

    resolve_asset = commands.add_parser(
        "resolve-plugin-asset",
        help="resolve one caller-selected asset from a coherent plugin bundle",
    )
    resolve_asset.add_argument("--plugin", required=True)
    resolve_asset.add_argument("--asset", required=True)
    resolve_asset.add_argument("--minimum-version")
    resolve_asset.add_argument("--active-host", choices=("claude", "codex"))
    resolve_asset.set_defaults(handler=command_resolve_plugin_asset)
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        return args.handler(args)
    except InspectionError as exc:
        _emit({
            "error": {
                "code": "inspection_error",
                "message": "inspection input rejected",
                "details": {"reason_code": exc.reason_code},
            },
        }, sys.stderr)
        return EXIT_INVALID
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
            "verification_receipt_conflict",
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
