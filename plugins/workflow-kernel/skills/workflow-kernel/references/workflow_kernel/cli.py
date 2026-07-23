"""Repo-local argparse interface for workflow-kernel ledgers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ._files import PinnedDirectory, _OwnedResourceScope, bind_durable_path
from .events import EventStore
from .repository_scope import repository_scope as _repository_scope
from .runtime_resolution import (
    KERNEL_VERSION_FLOOR, compatible_kernel_version,
    resolve_workflow_kernel_runtime,
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
    if (
        event.kind == "evidence.recorded"
        and event.payload.get("stage")
        == "verification_contract_revision_authorized"
    ):
        raise InvalidSchemaError(ErrorMessage.INVALID_COMMAND_ARGUMENTS, {
            ErrorDetailKey.REASON_CODE.value: "reserved_coordinator_event",
        })
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
    "human_approval_evidence_ref", "verification_profile_id",
    "verification_profile_digest", "verification_profile_ref", "evidence",
})
_CONTRACT_STAGES = frozenset({
    "verification_contract_bound", "verification_contract_revised",
})
_CONTRACT_APPROVAL_FIELDS = frozenset({
    "stage", "run_id", "actor", "authority", "decision", "issued_at",
    "expires_at", "nonce",
    "previous_contract_digest", "candidate_contract_digest",
    "approval_ref", "evidence",
})


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


def _approval_artifact_ref(digest):
    return "verification-approvals/" + _contract_artifact_name(digest)


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


def _store_approval_once(run_root, approval, digest, *, previous_digest,
                         candidate_digest, run_id):
    from .behavioral_contract import approval_bytes, parse_approval_bytes

    name = _contract_artifact_name(digest)
    encoded = approval_bytes(
        approval, previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    ) + b"\n"
    with _contract_artifact_directory(run_root, "verification-approvals") as directory:
        if directory.regular_exists(name):
            descriptor = directory.open_regular(name, os.O_RDONLY)
            try:
                existing = os.read(descriptor, len(encoded) + 1)
                if os.read(descriptor, 1) or existing != encoded:
                    raise ValueError("bound approval artifact mismatch")
                parse_approval_bytes(
                    existing, previous_digest=previous_digest,
                    candidate_digest=candidate_digest, run_id=run_id,
                )
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
                    raise OSError("approval write made no progress")
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


def _load_bound_approval(run_root, reference, *, previous_digest,
                         candidate_digest, run_id):
    from .behavioral_contract import approval_digest, parse_approval_bytes

    match = re.fullmatch(
        r"verification-approvals/sha256-([0-9a-f]{64})\.json", reference or "",
    )
    if match is None:
        raise ValueError("invalid approval artifact reference")
    digest = "sha256:" + match.group(1)
    with _contract_artifact_directory(run_root, "verification-approvals") as directory:
        descriptor = directory.open_regular(Path(reference).name, os.O_RDONLY)
        try:
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(8192, 65_537 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > 65_536:
                    raise ValueError("approval artifact too large")
            directory.require_identity(descriptor, Path(reference).name)
        finally:
            os.close(descriptor)
    approval = parse_approval_bytes(
        b"".join(chunks), previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    )
    if approval_digest(
        approval, previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    ) != digest:
        raise ValueError("approval artifact digest mismatch")
    return approval


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


def _contract_bindings(replayed):
    bindings = []
    for event in replayed:
        if event.kind != "evidence.recorded":
            continue
        payload = event.to_dict()["payload"]
        if payload.get("stage") not in _CONTRACT_STAGES:
            continue
        if type(payload) is not dict or set(payload) != _CONTRACT_BINDING_FIELDS:
            raise ValueError("invalid verification contract binding event")
        revision = payload["revision"]
        expected_revision = len(bindings) + 1
        expected_previous = None if not bindings else bindings[-1]["contract_digest"]
        expected_stage = (
            "verification_contract_bound" if revision == 1
            else "verification_contract_revised"
        )
        approval = payload["human_approval_evidence_ref"]
        profile_ref = payload["verification_profile_ref"]
        if (
            type(revision) is not int or revision != expected_revision
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
            or (approval is not None and type(approval) is not str)
            or payload["verification_profile_id"] is not None and type(payload["verification_profile_id"]) is not str
            or payload["verification_profile_digest"] is not None and type(payload["verification_profile_digest"]) is not str
            or (profile_ref is not None and type(profile_ref) is not str)
            or payload["previous_contract_digest"] != expected_previous
            or payload["stage"] != expected_stage
            or payload["contract_ref"] != _contract_artifact_ref(payload["contract_digest"])
            or payload["evidence"] != (
                [payload["contract_ref"]]
                + ([] if profile_ref is None else [profile_ref])
                + ([] if approval is None else [approval])
            )
            or (bindings and payload["contract_id"] != bindings[-1]["contract_id"])
        ):
            raise ValueError("verification contract binding chain mismatch")
        bindings.append(payload)
    return tuple(bindings)


def _contract_authorizations(replayed, run_root, run_id, *, load_artifacts=True):
    authorizations = []
    last_binding_sequence = -1
    used_nonces = set()
    for event in replayed:
        if event.kind != "evidence.recorded":
            continue
        payload = event.to_dict()["payload"]
        if payload.get("stage") in _CONTRACT_STAGES:
            last_binding_sequence = event.sequence
            continue
        if payload.get("stage") != "verification_contract_revision_authorized":
            continue
        if type(payload) is not dict or set(payload) != _CONTRACT_APPROVAL_FIELDS:
            raise ValueError("invalid contract approval authorization event")
        if (
            payload["run_id"] != run_id
            or payload["decision"] != "approved"
            or payload["evidence"] != [payload["approval_ref"]]
            or event.sequence <= last_binding_sequence
            or payload["nonce"] in used_nonces
        ):
            raise ValueError("invalid contract approval authorization order")
        approval = None
        if load_artifacts:
            approval = _load_bound_approval(
                run_root, payload["approval_ref"],
                previous_digest=payload["previous_contract_digest"],
                candidate_digest=payload["candidate_contract_digest"], run_id=run_id,
            )
            if any(approval[name] != payload[name] for name in (
                "actor", "authority", "decision", "issued_at", "expires_at",
                "nonce", "run_id",
                "previous_contract_digest", "candidate_contract_digest",
            )):
                raise ValueError("contract approval authorization mismatch")
        used_nonces.add(payload["nonce"])
        authorizations.append((event.sequence, last_binding_sequence, payload, approval))
    return tuple(authorizations)


def _authorized_contract_revision(replayed, run_root, run_id, *,
                                  previous_digest, candidate_digest,
                                  idempotent=False):
    bindings = [
        event for event in replayed
        if event.kind == "evidence.recorded"
        and event.payload.get("stage") in _CONTRACT_STAGES
    ]
    if idempotent:
        if not bindings:
            raise ValueError("authoritative contract approval is missing")
        prior_sequence = bindings[-2].sequence if len(bindings) > 1 else -1
        ceiling = bindings[-1].sequence
    else:
        prior_sequence = bindings[-1].sequence if bindings else -1
        ceiling = None
    matches = [
        item for item in _contract_authorizations(
            replayed, run_root, run_id, load_artifacts=False,
        )
        if item[0] > prior_sequence
        and (ceiling is None or item[0] < ceiling)
        and item[2]["previous_contract_digest"] == previous_digest
        and item[2]["candidate_contract_digest"] == candidate_digest
    ]
    if len(matches) != 1:
        raise ValueError("authoritative contract approval is missing or ambiguous")
    return matches[0][2]


def _validate_contract_authorization_chain(replayed, run_root, run_id):
    binding_events = [
        event for event in replayed
        if event.kind == "evidence.recorded"
        and event.payload.get("stage") in _CONTRACT_STAGES
    ]
    authorizations = _contract_authorizations(replayed, run_root, run_id)
    for index, binding in enumerate(binding_events[1:], start=1):
        payload = binding.to_dict()["payload"]
        approval_ref = payload["human_approval_evidence_ref"]
        candidates = [
            item for item in authorizations
            if binding_events[index - 1].sequence < item[0] < binding.sequence
            and item[2]["previous_contract_digest"]
            == payload["previous_contract_digest"]
            and item[2]["candidate_contract_digest"] == payload["contract_digest"]
            and item[2]["approval_ref"] == approval_ref
        ]
        if approval_ref is not None and len(candidates) != 1:
            raise ValueError("contract revision lacks lifecycle approval authority")
        if approval_ref is None and candidates:
            raise ValueError("contract revision dropped lifecycle approval authority")


def _contract_receipt(binding):
    return {
        name: binding[name] for name in (
            "stage", "contract_id", "schema_version", "revision",
            "contract_digest", "contract_ref", "previous_contract_digest",
            "reason_code", "human_approval_evidence_ref",
            "verification_profile_id", "verification_profile_digest",
            "verification_profile_ref",
        )
    }


def _contract_binding_payload(contract, digest, stage, *, approval_ref=None,
                              profile_ref=None):
    justification = contract["revision_justification"]
    reference = _contract_artifact_ref(digest)
    return {
        "stage": stage, "contract_id": contract["contract_id"],
        "schema_version": contract["schema_version"],
        "revision": contract["revision"], "contract_digest": digest,
        "contract_ref": reference,
        "previous_contract_digest": contract["previous_contract_digest"],
        "reason_code": justification["reason_code"],
        "human_approval_evidence_ref": approval_ref,
        "verification_profile_id": contract["verification_profile_id"],
        "verification_profile_digest": contract["verification_profile_digest"],
        "verification_profile_ref": profile_ref,
        "evidence": [reference]
        + ([] if profile_ref is None else [profile_ref])
        + ([] if approval_ref is None else [approval_ref]),
    }


def _validated_contract_binding_chain(run_root, bindings, *, run_id,
                                      missing_latest=None, missing_approval=None):
    from .behavioral_contract import (
        contract_digest, validate_initial_binding, validate_revision,
    )

    contracts = []
    previous_digest = None
    for index, binding in enumerate(bindings):
        try:
            contract = _load_bound_contract(run_root, binding)
        except FileNotFoundError:
            if (
                index != len(bindings) - 1
                or binding["revision"] == 1
                or missing_latest is None
            ):
                raise ValueError("verification contract artifact is missing") from None
            contract = missing_latest
        digest = contract_digest(contract)
        expected = _contract_binding_payload(
            contract, digest, binding["stage"],
            approval_ref=binding["human_approval_evidence_ref"],
            profile_ref=binding["verification_profile_ref"],
        )
        if binding != expected:
            raise ValueError("verification contract binding does not match artifact")
        if not contracts:
            contract = validate_initial_binding(contract)
        else:
            approval = None
            if binding["human_approval_evidence_ref"] is not None:
                if missing_approval is not None and index == len(bindings) - 1:
                    approval = missing_approval
                else:
                    approval = _load_bound_approval(
                        run_root, binding["human_approval_evidence_ref"],
                        previous_digest=previous_digest,
                        candidate_digest=digest, run_id=run_id,
                    )
            contract = validate_revision(
                contracts[-1], contract, previous_digest,
                approval_evidence=approval, run_id=run_id,
            )
        if binding["verification_profile_ref"] is not None:
            from .behavioral_contract import validate_profile_binding
            profile = _load_bound_profile(
                run_root, binding["verification_profile_ref"],
                binding["verification_profile_digest"],
            )
            contract = validate_profile_binding(contract, profile)
        elif contract["verification_profile_id"] is not None:
            raise ValueError("verification profile artifact is missing")
        contracts.append(contract)
        previous_digest = digest
    return tuple(contracts)


def command_authorize_verification_contract_revision(args):
    """Verify one externally held host capability before authorization."""
    from .behavioral_contract import (
        approval_digest, load_approval, load_host_approval_capability,
        verify_approval_capability,
    )

    scope, run_id, run_root, events, states = _contract_run_context(args.state_dir)
    approval_scope = _repository_scope(args.approval)
    if approval_scope.scope_id != scope.scope_id:
        raise ValueError("approval input belongs to a foreign repository scope")
    raw = _load_json(args.approval)
    if type(raw) is not dict:
        raise ValueError("invalid approval document")
    try:
        previous_digest = raw["previous_contract_digest"]
        candidate_digest = raw["candidate_contract_digest"]
    except KeyError:
        raise ValueError("invalid approval document") from None
    approval = load_approval(
        args.approval, previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    )
    capability_path = bind_durable_path(Path(args.host_capability)).path
    try:
        capability_path.relative_to(scope.repo_root.resolve(strict=True))
    except ValueError:
        pass
    else:
        raise ValueError("host approval capability must be outside repository scope")
    capability = load_host_approval_capability(capability_path)
    approval = verify_approval_capability(
        approval, capability, previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    )
    digest = approval_digest(
        approval, previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    )
    approval_ref = _approval_artifact_ref(digest)
    engine = TransitionEngine()
    with _coordinated_run(states) as lease:
        replayed, _notes, reconstructed, materialized = _observe_consistent_run(
            events, states, engine, recovery=False,
            empty_error=InvalidSchemaError(ErrorMessage.RUN_DIRECTORY_UNINITIALIZED),
        )
        bindings = _contract_bindings(replayed)
        if not bindings or bindings[-1]["contract_digest"] != previous_digest:
            raise ValueError("approval does not extend current contract binding")
        authorizations = _contract_authorizations(
            replayed, run_root, run_id, load_artifacts=False,
        )
        latest_binding_sequence = max(
            event.sequence for event in replayed
            if event.kind == "evidence.recorded"
            and event.payload.get("stage") in _CONTRACT_STAGES
        )
        if any(
            item[0] > latest_binding_sequence
            or item[2]["nonce"] == approval["nonce"]
            for item in authorizations
        ):
            raise ValueError("contract revision approval already pending or reused")
        _store_approval_once(
            run_root, approval, digest, previous_digest=previous_digest,
            candidate_digest=candidate_digest, run_id=run_id,
        )
        payload = {
            "stage": "verification_contract_revision_authorized",
            "run_id": run_id, "actor": approval["actor"],
            "authority": approval["authority"],
            "decision": approval["decision"],
            "issued_at": approval["issued_at"],
            "expires_at": approval["expires_at"], "nonce": approval["nonce"],
            "previous_contract_digest": previous_digest,
            "candidate_contract_digest": candidate_digest,
            "approval_ref": approval_ref, "evidence": [approval_ref],
        }
        current = datetime.now(timezone.utc)
        prior = datetime.fromisoformat(reconstructed.updated_at.replace("Z", "+00:00"))
        event_time = max(current, prior + timedelta(microseconds=1)).isoformat().replace(
            "+00:00", "Z",
        )
        event = WorkflowEvent(
            1, len(replayed), run_id, None, "evidence.recorded", event_time, payload,
        )
        next_state = engine.apply(reconstructed, event)
        expected_revision = materialized.revision if materialized is not None else -1
        _append_and_publish(
            events, states, event, next_state, expected_sequence=len(replayed),
            expected_revision=expected_revision, lease=lease,
            authoritative_initialization=materialized is None,
        )
    _emit({name: value for name, value in payload.items() if name != "evidence"})
    return 0


def _command_verification_contract(args, *, revise):
    from .behavioral_contract import (
        approval_digest, contract_digest, load_approval, load_contract, load_profile,
        validate_initial_binding, validate_profile_binding, validate_revision,
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
        bindings = _contract_bindings(replayed)
        latest = bindings[-1] if bindings else None
        requested_stage = (
            "verification_contract_revised" if revise
            else "verification_contract_bound"
        )
        source_approval_ref = candidate["revision_justification"][
            "human_approval_evidence_ref"
        ]
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
        approval = None
        approval_ref = None
        candidate_matches_latest = (
            revise and latest is not None
            and latest["stage"] == "verification_contract_revised"
            and latest["contract_digest"] == digest
        )
        if source_approval_ref is not None:
            if not revise:
                raise ValueError("initial binding cannot carry approval evidence")
            authorization = _authorized_contract_revision(
                replayed, run_root, run_id,
                previous_digest=candidate["previous_contract_digest"],
                candidate_digest=digest, idempotent=candidate_matches_latest,
            )
            approval_ref = authorization["approval_ref"]
            try:
                approval = _load_bound_approval(
                    run_root, approval_ref,
                    previous_digest=candidate["previous_contract_digest"],
                    candidate_digest=digest, run_id=run_id,
                )
            except FileNotFoundError:
                if getattr(args, "approval", None) is None:
                    raise ValueError("authorized approval artifact is missing") from None
                approval_scope = _repository_scope(args.approval)
                if approval_scope.scope_id != scope.scope_id:
                    raise ValueError("approval input belongs to a foreign repository scope")
                approval = load_approval(
                    args.approval,
                    previous_digest=candidate["previous_contract_digest"],
                    candidate_digest=digest, run_id=run_id,
                )
                restored_digest = approval_digest(
                    approval, previous_digest=candidate["previous_contract_digest"],
                    candidate_digest=digest, run_id=run_id,
                )
                if _approval_artifact_ref(restored_digest) != approval_ref:
                    raise ValueError("approval recovery artifact mismatch")
                _store_approval_once(
                    run_root, approval, restored_digest,
                    previous_digest=candidate["previous_contract_digest"],
                    candidate_digest=digest, run_id=run_id,
                )
            if any(approval[name] != authorization[name] for name in (
                "actor", "authority", "decision", "issued_at", "expires_at",
                "nonce", "run_id",
                "previous_contract_digest", "candidate_contract_digest",
            )):
                raise ValueError("approval artifact does not match authorization")
        elif getattr(args, "approval", None) is not None:
            raise ValueError("unexpected approval artifact")
        payload = _contract_binding_payload(
            candidate, digest, requested_stage, approval_ref=approval_ref,
            profile_ref=profile_ref,
        )
        idempotent = (
            latest is not None
            and _contract_receipt(latest) == _contract_receipt(payload)
            and latest["stage"] == requested_stage
        )
        _validate_contract_authorization_chain(replayed, run_root, run_id)
        _validated_contract_binding_chain(
            run_root, bindings, run_id=run_id,
            missing_latest=candidate if idempotent and revise else None,
            missing_approval=None,
        )

        if idempotent:
            _store_contract_once(run_root, candidate, digest)
            if materialized != reconstructed:
                expected_revision = materialized.revision if materialized is not None else -1
                states.publish(
                    _prepare_replay_state(states, reconstructed, expected_revision),
                    expected_revision, lease=lease,
                )
            receipt = _contract_receipt(latest)
        else:
            _require_materialized_matches_ledger(materialized, reconstructed)
            if revise:
                if latest is None:
                    raise ValueError("verification contract has no prior binding")
                previous = _load_bound_contract(run_root, latest)
                candidate = validate_revision(
                    previous, candidate, latest["contract_digest"],
                    approval_evidence=approval, run_id=run_id,
                )
            else:
                if latest is not None:
                    raise ValueError("verification contract already bound")
                candidate = validate_initial_binding(candidate)
            digest = contract_digest(candidate)
            payload = _contract_binding_payload(
                candidate, digest, requested_stage, approval_ref=approval_ref,
                profile_ref=profile_ref,
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


def command_bind_verification_contract(args):
    return _command_verification_contract(args, revise=False)


def command_revise_verification_contract(args):
    return _command_verification_contract(args, revise=True)


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

    source = _load_json(args.prediction_receipts)
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
    receipts = _load_json(args.receipts)
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


def command_observe_review(args):
    from .dm_review_adapter import (
        export_finding_contributions,
        ReviewRequest, require_browser_recovery_profile_binding,
        require_complete_contribution_coverage,
        require_secret_safe_contribution_inputs,
        translate_review, translate_review_receipts,
    )

    request = ReviewRequest.from_mapping(_load_json(args.request))
    receipts = _load_json(args.receipts)
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
            if event.payload.get("stage") in {
                "verification_contract_bound", "verification_contract_revised",
            }
        ]
        if not contract_events:
            raise ValueError("browser recovery lacks contract binding")
        claimed = contract_events[-1].payload
        if claimed.get("verification_profile_ref") is None:
            raise ValueError("browser recovery lacks contract profile")
        scope = _repository_scope(args.state_dir)
        run_root = _prediction_lifecycle(scope, spec)
        replayed, _state = _load_prediction_lifecycle(scope, spec)
        bindings = _contract_bindings(replayed)
        if not bindings:
            raise ValueError("browser recovery lacks lifecycle contract authority")
        latest = bindings[-1]
        binding_fields = _CONTRACT_BINDING_FIELDS - frozenset({"evidence"})
        if any(claimed.get(field) != latest[field] for field in binding_fields):
            raise ValueError("browser recovery contract receipt is not current")
        contracts = _validated_contract_binding_chain(
            run_root, bindings, run_id=spec.run_id,
        )
        contract = contracts[-1]
        profile_document = _load_bound_profile(
            run_root, latest["verification_profile_ref"],
            latest["verification_profile_digest"],
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
    receipts = _load_json(args.receipts)
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
    receipts = _load_json(args.authoritative_receipts)
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

    revise_contract = commands.add_parser(
        "revise-verification-contract",
        help="validate and append one behavioral verification contract revision",
    )
    revise_contract.add_argument("--state-dir", required=True)
    revise_contract.add_argument("--contract", required=True)
    revise_contract.add_argument("--verification-profile")
    revise_contract.add_argument("--approval")
    revise_contract.set_defaults(handler=command_revise_verification_contract)

    authorize_contract = commands.add_parser(
        "authorize-verification-contract-revision",
        help="record one coordinator-authorized verification contract revision",
    )
    authorize_contract.add_argument("--state-dir", required=True)
    authorize_contract.add_argument("--approval", required=True)
    authorize_contract.add_argument("--host-capability", required=True)
    authorize_contract.set_defaults(
        handler=command_authorize_verification_contract_revision,
    )

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
