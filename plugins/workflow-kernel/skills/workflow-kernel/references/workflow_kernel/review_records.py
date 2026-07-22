"""Immutable review records, deterministic projections, and read-only checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

from ._files import _OwnedResourceScope, bind_durable_path
from .events import EventStore
from .redaction import (
    contains_high_confidence_secret, normalize_evidence_reference,
)
from .schema import SequenceConflictError, WorkflowEvent
from .state import RunLease


SCHEMA_VERSION = 1
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_FINDING_ID = re.compile(r"finding-v1:sha256:[0-9a-f]{64}\Z")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}\Z")
_SEVERITIES = frozenset({"P1", "P2", "P3"})
_AGREEMENTS = frozenset({"unique", "corroborated", "disputed"})
_DISPOSITIONS = frozenset({"retained", "merged", "discarded"})
_REASON_DISPOSITION = {
    "retained-unique": "retained", "retained-corroborated": "retained",
    "retained-disagreement": "retained", "exact-duplicate": "merged",
    "same-root-cause-merge": "merged",
    "superseded-by-stronger-evidence": "discarded",
    "out-of-scope": "discarded", "not-reproducible": "discarded",
    "agent-findings-cap": "discarded",
}
_LANE_STATES = frozenset({
    "requested", "completed", "failed", "degraded", "unavailable",
    "missing", "unknown",
})
_FINDING_FIELDS = frozenset({
    "schema_version", "record_kind", "run_id", "source_finding_id",
    "lane_id", "canonical_finding_id", "cross_id_links", "rule_id",
    "category", "severity", "path",
    "anchor", "root_cause", "observed_evidence", "proposed_fix",
    "evidence_refs", "raw_ref", "source_agents", "requested_provider",
    "attempted_provider", "implemented_by", "model", "attempt",
    "agreement", "finding_disposition", "decision_reason_code",
    "build_binding_ref", "browser_bundle_refs", "record_digest",
})
_LANE_FIELDS = frozenset({
    "schema_version", "record_kind", "run_id", "lane_id", "state",
    "expected_coverage", "missing_case_ids", "partial_output", "output_ref",
    "source_agents", "requested_provider", "attempted_provider",
    "implemented_by", "model", "attempt", "coverage_gap_reason",
    "build_binding_ref", "browser_bundle_refs", "finding_refs",
    "record_digest",
})


def _fail(reason: str):
    raise ValueError(reason)


def _text(value, name, *, nullable=False, limit=4096):
    if nullable and value is None:
        return None
    if (type(value) is not str or not value
            or len(value.encode("utf-8")) > limit
            or any(ord(char) < 0x20 for char in value)
            or contains_high_confidence_secret(value)):
        _fail("invalid " + name)
    return value


def _identity(value, name):
    value = _text(value, name, limit=256)
    if _IDENTITY.fullmatch(value) is None:
        _fail("invalid " + name)
    return value


def _relative_path(value, name):
    value = _text(value, name, limit=2048).replace("\\", "/")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("./"):
        _fail("unsafe " + name)
    return value


def _reference(value, name, *, nullable=False):
    if nullable and value is None:
        return None
    value = _text(value, name)
    try:
        normalized = normalize_evidence_reference(value)
    except ValueError:
        _fail("unsafe " + name)
    if normalized != value:
        _fail("noncanonical " + name)
    return value


def _raw_reference(value):
    value = _text(value, "raw reference")
    path, marker, anchor = value.partition("#")
    path = _relative_path(path, "raw reference")
    if marker:
        anchor = _text(anchor, "raw reference anchor", limit=512)
        return path + "#" + anchor
    return path


def _list(value, name, validator, *, maximum=256):
    if type(value) not in {list, tuple} or len(value) > maximum:
        _fail("invalid " + name)
    result = [validator(item, name) for item in value]
    if len(result) != len(set(result)):
        _fail("duplicate " + name)
    return result


def _canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def canonical_finding_id(path, anchor, category, root_cause):
    path = _relative_path(path, "path").lower()
    normalized = []
    for value, name in ((anchor, "anchor"), (category, "category"),
                        (root_cause, "root cause")):
        normalized.append(" ".join(_text(value, name).strip().lower().split()))
    key = (f"path={path}\nanchor={normalized[0]}\ncategory={normalized[1]}"
           f"\nroot_cause={normalized[2]}")
    return "finding-v1:sha256:" + hashlib.sha256(key.encode()).hexdigest()


def _finding_id(value, name):
    value = _text(value, name, limit=96)
    if _FINDING_ID.fullmatch(value) is None:
        _fail("invalid " + name)
    return value


def source_scope_digest(record):
    """Scope an agent-local finding ID to its lane, raw artifact, and attempt."""
    return _digest({
        "lane_id": record["lane_id"],
        "raw_artifact": record["raw_ref"].partition("#")[0],
        "requested_provider": record["requested_provider"],
        "attempted_provider": record["attempted_provider"],
        "implemented_by": record["implemented_by"],
        "model": record["model"], "attempt": record["attempt"],
        "source_finding_id": record["source_finding_id"],
    })


def validate_finding_record(value):
    if type(value) is not dict or set(value) != _FINDING_FIELDS:
        _fail("finding record fields mismatch")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        _fail("unsupported finding schema version")
    if value["record_kind"] != "finding":
        _fail("invalid finding record kind")
    body = {
        "schema_version": 1, "record_kind": "finding",
        "run_id": _identity(value["run_id"], "run id"),
        "source_finding_id": _identity(value["source_finding_id"], "source finding id"),
        "lane_id": _identity(value["lane_id"], "lane id"),
        "canonical_finding_id": _finding_id(value["canonical_finding_id"], "canonical finding id"),
        "cross_id_links": _list(value["cross_id_links"], "cross id link", _finding_id),
        "rule_id": _identity(value["rule_id"], "rule id"),
        "category": _text(value["category"], "category", limit=256),
        "severity": value["severity"],
        "path": _relative_path(value["path"], "path"),
        "anchor": _text(value["anchor"], "anchor", limit=2048),
        "root_cause": _text(value["root_cause"], "root cause"),
        "observed_evidence": _text(value["observed_evidence"], "observed evidence"),
        "proposed_fix": _text(value["proposed_fix"], "proposed fix"),
        "evidence_refs": _list(value["evidence_refs"], "evidence reference", _reference),
        "raw_ref": _raw_reference(value["raw_ref"]),
        "source_agents": _list(value["source_agents"], "source agent", _identity, maximum=64),
        "requested_provider": _text(value["requested_provider"], "requested provider", nullable=True, limit=256),
        "attempted_provider": _text(value["attempted_provider"], "attempted provider", nullable=True, limit=256),
        "implemented_by": _text(value["implemented_by"], "implemented by", nullable=True, limit=256),
        "model": _text(value["model"], "model", nullable=True, limit=256),
        "attempt": value["attempt"], "agreement": value["agreement"],
        "finding_disposition": value["finding_disposition"],
        "decision_reason_code": value["decision_reason_code"],
        "build_binding_ref": _reference(value["build_binding_ref"], "build binding reference"),
        "browser_bundle_refs": _list(value["browser_bundle_refs"], "browser bundle reference", _reference),
    }
    if body["severity"] not in _SEVERITIES:
        _fail("invalid severity")
    if type(body["attempt"]) is not int or body["attempt"] < 1:
        _fail("invalid attempt")
    if body["agreement"] not in _AGREEMENTS:
        _fail("invalid agreement")
    if body["finding_disposition"] not in _DISPOSITIONS:
        _fail("invalid finding disposition")
    if _REASON_DISPOSITION.get(body["decision_reason_code"]) != body["finding_disposition"]:
        _fail("invalid finding decision reason")
    expected_id = canonical_finding_id(body["path"], body["anchor"], body["category"], body["root_cause"])
    if _FINDING_ID.fullmatch(body["canonical_finding_id"]) is None or body["canonical_finding_id"] != expected_id:
        _fail("canonical finding id mismatch")
    if body["canonical_finding_id"] in body["cross_id_links"]:
        _fail("self-referential cross id link")
    if value["record_digest"] != _digest(body):
        _fail("finding record digest mismatch")
    body["record_digest"] = value["record_digest"]
    return body


def build_finding_record(**fields):
    fields = dict(fields)
    fields.update(schema_version=1, record_kind="finding")
    fields.setdefault("canonical_finding_id", canonical_finding_id(
        fields["path"], fields["anchor"], fields["category"], fields["root_cause"],
    ))
    fields["record_digest"] = _digest(fields)
    return validate_finding_record(fields)


def validate_lane_record(value):
    if type(value) is not dict or set(value) != _LANE_FIELDS:
        _fail("lane record fields mismatch")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        _fail("unsupported lane schema version")
    if value["record_kind"] != "lane":
        _fail("invalid lane record kind")
    body = {
        "schema_version": 1, "record_kind": "lane",
        "run_id": _identity(value["run_id"], "run id"),
        "lane_id": _identity(value["lane_id"], "lane id"), "state": value["state"],
        "expected_coverage": _list(value["expected_coverage"], "expected coverage", _identity),
        "missing_case_ids": _list(value["missing_case_ids"], "missing case id", _identity),
        "partial_output": value["partial_output"],
        "output_ref": _reference(value["output_ref"], "output reference", nullable=True),
        "source_agents": _list(value["source_agents"], "source agent", _identity, maximum=64),
        "requested_provider": _text(value["requested_provider"], "requested provider", nullable=True, limit=256),
        "attempted_provider": _text(value["attempted_provider"], "attempted provider", nullable=True, limit=256),
        "implemented_by": _text(value["implemented_by"], "implemented by", nullable=True, limit=256),
        "model": _text(value["model"], "model", nullable=True, limit=256),
        "attempt": value["attempt"],
        "coverage_gap_reason": _text(value["coverage_gap_reason"], "coverage gap reason", nullable=True),
        "build_binding_ref": _reference(value["build_binding_ref"], "build binding reference"),
        "browser_bundle_refs": _list(value["browser_bundle_refs"], "browser bundle reference", _reference),
        "finding_refs": _list(value["finding_refs"], "finding reference", _reference),
    }
    if body["state"] not in _LANE_STATES or type(body["partial_output"]) is not bool:
        _fail("invalid lane state")
    if type(body["attempt"]) is not int or body["attempt"] < 1:
        _fail("invalid attempt")
    if body["state"] == "completed":
        if body["missing_case_ids"] or body["partial_output"] or body["coverage_gap_reason"] is not None:
            _fail("completed lane contains coverage gap")
    elif body["coverage_gap_reason"] is None:
        _fail("incomplete lane lacks coverage gap reason")
    if body["partial_output"] and body["output_ref"] is None:
        _fail("partial lane lacks output reference")
    if value["record_digest"] != _digest(body):
        _fail("lane record digest mismatch")
    body["record_digest"] = value["record_digest"]
    return body


def build_lane_record(**fields):
    fields = dict(fields)
    fields.update(schema_version=1, record_kind="lane")
    fields["record_digest"] = _digest(fields)
    return validate_lane_record(fields)


def _ensure_owned_artifact_root(artifact_root, event_store):
    event_root = Path(os.path.abspath(event_store.root))
    root = Path(os.path.abspath(artifact_root))
    try:
        relative = root.relative_to(event_root)
    except ValueError:
        _fail("artifact root outside owned run root")
    if not relative.parts:
        _fail("artifact root must be beneath owned run root")
    event_physical = Path(os.path.realpath(event_root))
    current = event_root
    for part in relative.parts:
        current /= part
        try:
            entry = os.lstat(current)
        except FileNotFoundError:
            os.mkdir(current, 0o700)
            _fsync_directory(current.parent)
            entry = os.lstat(current)
        if not stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode):
            _fail("unsafe review record directory")
        physical = Path(os.path.realpath(current))
        if physical != event_physical and event_physical not in physical.parents:
            _fail("artifact root escaped owned run root")
    return root


def _ensure_directory(path):
    created = False
    try:
        os.mkdir(path, 0o700)
        created = True
    except FileExistsError:
        pass
    entry = os.lstat(path)
    if not stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode):
        _fail("unsafe review record directory")
    if created:
        _fsync_directory(Path(path).parent)


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_regular(path):
    entry = os.lstat(path)
    if not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1:
        _fail("unsafe review record")
    with path.open("rb") as handle:
        return handle.read()


def _read_descriptor(descriptor):
    chunks = []
    while True:
        chunk = os.read(descriptor, 65_536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _event_match(event, kind, identity_field, identity, digest, reference):
    payload = event.payload
    if payload.get("stage") != kind + "_record" or payload.get(identity_field) != identity:
        return None
    if payload.get("record_digest") != digest or payload.get("record_ref") != reference:
        _fail("conflicting review record identity")
    return True


def _already_recorded(event_store, kind, identity_field, identity, digest, reference):
    return any(_event_match(event, kind, identity_field, identity, digest, reference)
               for event in event_store.replay())


def persist_review_record(record, artifact_root, event_store: EventStore,
                          lease: RunLease, expected_sequence: int, *, run_id: str,
                          occurred_at: str):
    """Write a content-addressed document, then append its bounded EventStore ref."""
    if record.get("record_kind") == "finding":
        record = validate_finding_record(record)
        identity_field = "source_scope_digest"
        identity = source_scope_digest(record)
    elif record.get("record_kind") == "lane":
        record = validate_lane_record(record); identity_field = "lane_id"
        identity = record[identity_field]
    else:
        _fail("unknown review record kind")
    run_id = _identity(run_id, "run id")
    if record["run_id"] != run_id:
        _fail("review record run mismatch")
    root = _ensure_owned_artifact_root(artifact_root, event_store)
    _ensure_directory(root / "records")
    records_root = root / "records" / (record["record_kind"] + "s")
    _ensure_directory(records_root)
    encoded = _canonical_bytes(record) + b"\n"
    name = record["record_digest"].replace(":", "-") + ".json"
    path = records_root / name
    reference = path.relative_to(root).as_posix()
    binding = bind_durable_path(path)
    event_physical = Path(os.path.realpath(event_store.root))
    if binding.path.parent != event_physical and event_physical not in binding.path.parent.parents:
        _fail("record path escaped owned run root")
    with _OwnedResourceScope() as scope:
        directory = scope.pin(binding)
        for existing_name in sorted(os.listdir(directory.descriptor)):
            if not existing_name.startswith("sha256-") or not existing_name.endswith(".json"):
                continue
            descriptor = scope.own(directory.open_regular(existing_name, os.O_RDONLY))
            existing = json.loads(_read_descriptor(descriptor))
            existing = (
                validate_finding_record(existing) if record["record_kind"] == "finding"
                else validate_lane_record(existing)
            )
            existing_identity = (
                source_scope_digest(existing) if record["record_kind"] == "finding"
                else existing.get("lane_id")
            )
            if existing_identity == identity and existing != record:
                _fail("conflicting review record identity")
        try:
            descriptor = scope.own(directory.open_regular(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            ))
        except FileExistsError:
            descriptor = scope.own(directory.open_regular(name, os.O_RDONLY))
            if _read_descriptor(descriptor) != encoded:
                _fail("conflicting content address")
        else:
            view = memoryview(encoded)
            while view:
                view = view[os.write(descriptor, view):]
            os.fsync(descriptor)
            directory.fsync()
    digest = record["record_digest"]
    result = {"record_ref": reference, "record_digest": digest}
    if _already_recorded(event_store, record["record_kind"], identity_field, identity, digest, reference):
        return result
    payload = {
        "stage": record["record_kind"] + "_record", "status": "recorded",
        "record_ref": reference, "record_digest": digest,
        "build_binding_ref": record["build_binding_ref"],
        "browser_bundle_refs": record["browser_bundle_refs"],
        identity_field: identity, "evidence": [reference],
    }
    if record["record_kind"] == "finding":
        payload.update(source_finding_id=record["source_finding_id"],
                       lane_id=record["lane_id"])
    else:
        payload["finding_refs"] = record["finding_refs"]
    try:
        event_store.append(WorkflowEvent(
            1, expected_sequence, run_id, None, "evidence.recorded",
            _text(occurred_at, "occurred at"), payload,
        ), expected_sequence, lease=lease)
    except SequenceConflictError:
        if not _already_recorded(event_store, record["record_kind"], identity_field, identity, digest, reference):
            raise
    return result


def consolidate_findings(findings, lanes=()):
    records = [validate_finding_record(dict(item)) for item in findings]
    lane_records = [validate_lane_record(dict(item)) for item in lanes]
    by_id = {}
    source_scopes = {}
    for item in records:
        scope = source_scope_digest(item)
        previous = source_scopes.setdefault(scope, item["record_digest"])
        if previous != item["record_digest"]:
            _fail("conflicting review record identity")
        by_id.setdefault(item["canonical_finding_id"], []).append(item)
    known = set(by_id)
    links = {}
    for canonical_id, items in by_id.items():
        links[canonical_id] = sorted({link for item in items for link in item["cross_id_links"]})
        if not set(links[canonical_id]) <= known:
            _fail("cross id link targets missing finding")
    for canonical_id, targets in links.items():
        if any(canonical_id not in links[target] for target in targets):
            _fail("cross id links are not reciprocal")
    lane_refs = {}
    for lane in lane_records:
        lane_refs.setdefault(lane["lane_id"], set()).update(lane["finding_refs"])
    severity_rank = {"P1": 0, "P2": 1, "P3": 2}
    result = []
    for canonical_id in sorted(by_id):
        items = sorted(by_id[canonical_id], key=lambda item: (
            source_scope_digest(item), item["record_digest"],
        ))
        active = [item for item in items if item["finding_disposition"] != "discarded"]
        retained = [item for item in active if item["finding_disposition"] == "retained"]
        selected = retained or active
        severities = sorted({item["severity"] for item in active}, key=severity_rank.get)
        source_positions = {
            (item["lane_id"], agent)
            for item in active for agent in item["source_agents"]
        }
        agreement = (
            "disputed" if links[canonical_id] or any(item["agreement"] == "disputed" for item in active)
            else "corroborated" if len(source_positions) > 1 else "unique"
        )
        representative = min(selected or items, key=lambda item: (
            severity_rank[item["severity"]], item["record_digest"],
        ))
        sources = []
        for item in items:
            sources.append({
                "record_digest": item["record_digest"],
                "source_scope_digest": source_scope_digest(item),
                "source_finding_id": item["source_finding_id"],
                "lane_id": item["lane_id"], "raw_ref": item["raw_ref"],
                "source_agents": item["source_agents"], "severity": item["severity"],
                "requested_provider": item["requested_provider"],
                "attempted_provider": item["attempted_provider"],
                "implemented_by": item["implemented_by"], "model": item["model"],
                "attempt": item["attempt"], "agreement": item["agreement"],
                "finding_disposition": item["finding_disposition"],
                "decision_reason_code": item["decision_reason_code"],
                "evidence_refs": item["evidence_refs"],
                "lane_finding_refs": sorted(lane_refs.get(item["lane_id"], ())),
            })
        result.append({
            "canonical_finding_id": canonical_id,
            "severity": severities[0] if severities else None,
            "source_severities": severities, "severity_disputed": len(severities) > 1,
            "agreement": agreement, "cross_id_links": links[canonical_id],
            "rule_id": representative["rule_id"], "category": representative["category"],
            "path": representative["path"], "anchor": representative["anchor"],
            "root_cause": representative["root_cause"],
            "observed_evidence": representative["observed_evidence"],
            "proposed_fix": representative["proposed_fix"], "sources": sources,
            "retained": bool(retained),
        })
    return result


def project_review_markdown(findings, lanes):
    canonical = consolidate_findings(findings, lanes)
    lanes = sorted((validate_lane_record(dict(item)) for item in lanes), key=lambda item: item["lane_id"])
    lines = ["# Structured Review", "", "## Findings", ""]
    if not canonical:
        lines.append("No findings recorded.")
    for item in canonical:
        displayed_severity = item["severity"] or "DISCARDED"
        lines.extend((f"### [{displayed_severity}] {item['category']}",
                      f"- ID: `{item['canonical_finding_id']}`",
                      f"- Rule: `{item['rule_id']}`",
                      f"- Where: `{item['path']}#{item['anchor']}`",
                      f"- Evidence: {item['observed_evidence']}",
                      f"- Proposed fix: {item['proposed_fix']}",
                      f"- Agreement: {item['agreement']}",
                      f"- Source records: {', '.join(source['record_digest'] for source in item['sources'])}",
                      f"- Cross-ID disputes: {', '.join(item['cross_id_links']) or 'none'}", ""))
    lines.extend(("## Coverage", ""))
    if not lanes:
        lines.append("No lanes recorded.")
    for lane in lanes:
        gap = "" if lane["coverage_gap_reason"] is None else f" — {lane['coverage_gap_reason']}"
        lines.append(f"- `{lane['lane_id']}`: {lane['state']}{gap}")
    return "\n".join(lines).rstrip() + "\n"


def project_todo_rows(findings, lanes=()):
    """Return a deterministic editing view; callers must never replay it as truth."""
    rows = []
    for item in consolidate_findings(findings, lanes):
        if not item["retained"]:
            continue
        rows.append({
            "finding_id": item["canonical_finding_id"], "priority": item["severity"].lower(),
            "title": item["category"], "where": item["path"] + "#" + item["anchor"],
            "problem": item["observed_evidence"], "fix": item["proposed_fix"],
            "source_record_digests": sorted(
                source["record_digest"] for source in item["sources"]
            ),
            "source_severities": item["source_severities"],
            "severity_disputed": item["severity_disputed"],
        })
    return rows


def _git(root, *args, text=True):
    return subprocess.run(("git", *args), cwd=root, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=text).stdout


def _product_status(root, artifact_relative):
    data = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", text=False)
    parts = data.split(b"\0"); rows = []; position = 0
    while position < len(parts) and parts[position]:
        row = parts[position].decode("utf-8", "surrogateescape"); position += 1
        status, path = row[:2], row[3:]
        paths = [path]
        if "R" in status or "C" in status:
            paths.append(parts[position].decode("utf-8", "surrogateescape")); position += 1
        if all(value == artifact_relative or value.startswith(artifact_relative + "/") for value in paths):
            continue
        rows.append([status, *paths])
    return _canonical_bytes(sorted(rows))


def _hash_regular(path):
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode):
        _fail("boundary path is not regular")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    after = os.lstat(path)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        _fail("boundary path changed during capture")
    return "sha256:" + digest.hexdigest()


def _repository_content(root, artifact_relative):
    rows = []
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(root).as_posix()
        kept = []
        for name in names:
            relative = name if relative_directory == "." else relative_directory + "/" + name
            if relative == ".git" or relative.startswith(".git/"):
                continue
            if relative == artifact_relative or relative.startswith(artifact_relative + "/"):
                continue
            path = directory_path / name
            entry = os.lstat(path)
            if stat.S_ISLNK(entry.st_mode):
                rows.append([relative, "symlink", os.readlink(path)])
            elif stat.S_ISDIR(entry.st_mode):
                kept.append(name)
            else:
                rows.append([relative, "special", entry.st_mode, entry.st_size])
        names[:] = kept
        for name in files:
            path = directory_path / name
            relative = name if relative_directory == "." else relative_directory + "/" + name
            if relative == artifact_relative or relative.startswith(artifact_relative + "/"):
                continue
            entry = os.lstat(path)
            if stat.S_ISLNK(entry.st_mode):
                rows.append([relative, "symlink", os.readlink(path)])
            elif stat.S_ISREG(entry.st_mode):
                rows.append([relative, "file", _hash_regular(path)])
            else:
                rows.append([relative, "special", entry.st_mode, entry.st_size])
    return _canonical_bytes(sorted(rows))


def _provider_path(root, artifact, reference):
    artifact_path = artifact / reference
    try:
        os.lstat(artifact_path)
    except FileNotFoundError:
        return root / reference
    return artifact_path


def _provider_state(root, artifact, references):
    rows = []
    for reference in references:
        path = _provider_path(root, artifact, reference)
        try:
            path.relative_to(root)
        except ValueError:
            _fail("provider receipt outside repository")
        try:
            entry = os.lstat(path)
        except FileNotFoundError:
            rows.append([reference, "missing"])
        else:
            if stat.S_ISREG(entry.st_mode):
                rows.append([reference, "file", _hash_regular(path)])
            elif stat.S_ISLNK(entry.st_mode):
                rows.append([reference, "symlink", os.readlink(path)])
            else:
                rows.append([reference, "other", entry.st_mode])
    return _canonical_bytes(rows)


def _provider_snapshot(root, artifact, reference, supplied_receipts):
    if reference is None:
        return _canonical_bytes([["provider-snapshot", "missing"]]), False
    reference = _reference(reference, "provider snapshot reference")
    path = _provider_path(root, artifact, reference)
    try:
        path.relative_to(root)
    except ValueError:
        _fail("provider snapshot outside repository")
    try:
        entry = os.lstat(path)
    except FileNotFoundError:
        return _canonical_bytes([[reference, "missing"]]), False
    if not stat.S_ISREG(entry.st_mode):
        state = "symlink" if stat.S_ISLNK(entry.st_mode) else "other"
        return _canonical_bytes([[reference, state]]), False
    marker_digest = _hash_regular(path)
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
        if (type(marker) is not dict or set(marker) != {
                "schema_version", "authority", "provider_receipts"}
                or marker.get("schema_version") != 1
                or marker.get("authority") != "complete-provider-snapshot"):
            raise ValueError("invalid provider snapshot marker")
        receipts = _list(
            marker.get("provider_receipts"), "provider mutation receipt", _reference,
        )
        supplied = _list(
            supplied_receipts, "provider mutation receipt", _reference,
        )
        if supplied and supplied != receipts:
            raise ValueError("provider receipt list disagrees with snapshot")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return _canonical_bytes([[reference, "invalid", marker_digest]]), False
    state = json.loads(_provider_state(root, artifact, receipts))
    return _canonical_bytes([[reference, "file", marker_digest], *state]), True


def capture_review_boundary(repository_root, artifact_root, provider_receipts=(), *,
                            provider_snapshot_ref=None):
    root = Path(repository_root).resolve()
    artifact = Path(artifact_root).resolve()
    if artifact != root and root not in artifact.parents:
        _fail("artifact root outside repository")
    relative = artifact.relative_to(root).as_posix()
    provider_state, provider_complete = _provider_snapshot(
        root, artifact, provider_snapshot_ref, provider_receipts,
    )
    return {
        "head": _git(root, "rev-parse", "HEAD").strip(),
        "index_digest": "sha256:" + hashlib.sha256(_git(root, "ls-files", "--stage").encode()).hexdigest(),
        "refs_digest": "sha256:" + hashlib.sha256(_git(root, "for-each-ref", "--format=%(refname) %(objectname)").encode()).hexdigest(),
        "product_status_digest": "sha256:" + hashlib.sha256(_product_status(root, relative)).hexdigest(),
        "product_content_digest": "sha256:" + hashlib.sha256(_repository_content(root, relative)).hexdigest(),
        "provider_receipts_digest": "sha256:" + hashlib.sha256(
            provider_state,
        ).hexdigest(),
        "provider_snapshot_complete": provider_complete,
    }


def compare_review_boundary(before, after):
    keys = ("head", "index_digest", "refs_digest", "product_status_digest",
            "product_content_digest", "provider_receipts_digest")
    changed = [key for key in keys if before.get(key) != after.get(key)]
    complete = (before.get("provider_snapshot_complete") is True
                and after.get("provider_snapshot_complete") is True)
    if not complete:
        changed.append("provider_snapshot_incomplete")
    return {"read_only": complete and not changed, "changed": changed,
            "provider_snapshot_complete": complete}
