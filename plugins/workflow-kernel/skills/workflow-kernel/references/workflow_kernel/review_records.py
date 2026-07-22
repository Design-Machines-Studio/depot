"""Immutable review records, deterministic projections, and read-only checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

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
})
_FINDING_FIELDS = frozenset({
    "schema_version", "record_kind", "run_id", "source_finding_id",
    "canonical_finding_id", "rule_id", "category", "severity", "path",
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
    "build_binding_ref", "browser_bundle_refs", "record_digest",
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
        "canonical_finding_id": _text(value["canonical_finding_id"], "canonical finding id", limit=96),
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


def _ensure_directory(path):
    path.mkdir(parents=True, exist_ok=True)
    entry = os.lstat(path)
    if not stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode):
        _fail("unsafe review record directory")


def _read_regular(path):
    entry = os.lstat(path)
    if not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1:
        _fail("unsafe review record")
    with path.open("rb") as handle:
        return handle.read()


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
        record = validate_finding_record(record); identity_field = "source_finding_id"
    elif record.get("record_kind") == "lane":
        record = validate_lane_record(record); identity_field = "lane_id"
    else:
        _fail("unknown review record kind")
    run_id = _identity(run_id, "run id")
    if record["run_id"] != run_id:
        _fail("review record run mismatch")
    root = Path(artifact_root)
    _ensure_directory(root)
    records_root = root / "records" / (record["record_kind"] + "s")
    _ensure_directory(records_root)
    encoded = _canonical_bytes(record) + b"\n"
    name = record["record_digest"].replace(":", "-") + ".json"
    path = records_root / name
    reference = path.relative_to(root).as_posix()
    for existing_path in sorted(records_root.glob("sha256-*.json")):
        existing = json.loads(_read_regular(existing_path))
        if existing.get(identity_field) == record[identity_field] and existing != record:
            _fail("conflicting review record identity")
    if path.exists():
        if _read_regular(path) != encoded:
            _fail("conflicting content address")
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            view = memoryview(encoded)
            while view:
                view = view[os.write(descriptor, view):]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    digest = record["record_digest"]
    identity = record[identity_field]
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
    try:
        event_store.append(WorkflowEvent(
            1, expected_sequence, run_id, None, "evidence.recorded",
            _text(occurred_at, "occurred at"), payload,
        ), expected_sequence, lease=lease)
    except SequenceConflictError:
        if not _already_recorded(event_store, record["record_kind"], identity_field, identity, digest, reference):
            raise
    return result


def project_review_markdown(findings, lanes):
    findings = sorted((validate_finding_record(dict(item)) for item in findings),
                      key=lambda item: (item["severity"], item["canonical_finding_id"], item["source_finding_id"]))
    lanes = sorted((validate_lane_record(dict(item)) for item in lanes), key=lambda item: item["lane_id"])
    lines = ["# Structured Review", "", "## Findings", ""]
    if not findings:
        lines.append("No findings recorded.")
    for item in findings:
        lines.extend((f"### [{item['severity']}] {item['category']}",
                      f"- ID: `{item['canonical_finding_id']}`",
                      f"- Rule: `{item['rule_id']}`",
                      f"- Where: `{item['path']}#{item['anchor']}`",
                      f"- Evidence: {item['observed_evidence']}",
                      f"- Proposed fix: {item['proposed_fix']}",
                      f"- Disposition: {item['finding_disposition']} ({item['agreement']})", ""))
    lines.extend(("## Coverage", ""))
    if not lanes:
        lines.append("No lanes recorded.")
    for lane in lanes:
        gap = "" if lane["coverage_gap_reason"] is None else f" — {lane['coverage_gap_reason']}"
        lines.append(f"- `{lane['lane_id']}`: {lane['state']}{gap}")
    return "\n".join(lines).rstrip() + "\n"


def project_todo_rows(findings):
    """Return a deterministic editing view; callers must never replay it as truth."""
    rows = []
    for item in sorted((validate_finding_record(dict(value)) for value in findings),
                       key=lambda value: value["canonical_finding_id"]):
        if item["finding_disposition"] != "retained":
            continue
        rows.append({
            "finding_id": item["canonical_finding_id"], "priority": item["severity"].lower(),
            "title": item["category"], "where": item["path"] + "#" + item["anchor"],
            "problem": item["observed_evidence"], "fix": item["proposed_fix"],
            "record_digest": item["record_digest"],
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
        if any(value == artifact_relative or value.startswith(artifact_relative + "/") for value in paths):
            continue
        rows.append([status, *paths])
    return _canonical_bytes(sorted(rows))


def capture_review_boundary(repository_root, artifact_root, provider_receipts=()):
    root = Path(repository_root).resolve()
    artifact = Path(artifact_root).resolve()
    if artifact != root and root not in artifact.parents:
        _fail("artifact root outside repository")
    relative = artifact.relative_to(root).as_posix()
    providers = _list(provider_receipts, "provider mutation receipt", _reference)
    return {
        "head": _git(root, "rev-parse", "HEAD").strip(),
        "index_digest": "sha256:" + hashlib.sha256(_git(root, "ls-files", "--stage").encode()).hexdigest(),
        "refs_digest": "sha256:" + hashlib.sha256(_git(root, "for-each-ref", "--format=%(refname) %(objectname)").encode()).hexdigest(),
        "product_status_digest": "sha256:" + hashlib.sha256(_product_status(root, relative)).hexdigest(),
        "provider_receipts_digest": _digest(providers),
    }


def compare_review_boundary(before, after):
    keys = ("head", "index_digest", "refs_digest", "product_status_digest", "provider_receipts_digest")
    changed = [key for key in keys if before.get(key) != after.get(key)]
    return {"read_only": not changed, "changed": changed}
