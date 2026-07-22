"""Deterministic, proposal-only Upstream Improvement Scout records."""

from __future__ import annotations

import hashlib
import json
import math
import re

from .redaction import contains_high_confidence_secret, normalize_evidence_reference


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}\Z")
_CANDIDATE_ID = re.compile(r"improvement-v1:sha256:[0-9a-f]{64}\Z")
_CATEGORIES = frozenset({
    "new_deterministic_check", "existing_check_repair", "plugin_contract",
    "telemetry_gap", "depot_architecture", "documentation_or_runbook",
})
_STATUSES = frozenset({
    "one-off", "recurring", "standing", "completed", "superseded", "rejected",
})
_PROMPT_STATUSES = frozenset({"one-off", "recurring", "standing"})
_BENEFIT_OUTCOMES = frozenset({
    "reduced_manual_friction", "reduced_cycle_time", "improved_correctness",
    "improved_observability", "improved_maintainability",
    "improved_compatibility",
})
_REQUIRED_METRICS = frozenset({
    "duration_seconds", "wait_seconds", "attempt_count",
    "provider_attempt_count", "finding_contribution_count", "usage_count",
})


def _fail(message):
    raise ValueError(message)


def _text(value, name, *, nullable=False):
    if nullable and value is None:
        return None
    if (type(value) is not str or not value or len(value.encode("utf-8")) > 4096
            or contains_high_confidence_secret(value)):
        _fail("invalid " + name)
    return value


def _identity(value, name):
    value = _text(value, name)
    if _ID.fullmatch(value) is None:
        _fail("invalid " + name)
    return value


def _reference(value, name):
    value = _text(value, name)
    try:
        normalized = normalize_evidence_reference(value)
    except ValueError:
        _fail("unsafe " + name)
    if normalized != value:
        _fail("noncanonical " + name)
    return value


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


def candidate_id(dedupe_key):
    key = _text(dedupe_key, "dedupe key")
    return "improvement-v1:" + _digest({"dedupe_key": key})


_INPUT_FIELDS = frozenset({
    "evidence_id", "artifact_ref", "artifact_digest", "source_run",
    "source_stage", "source_chunk", "observation_category", "observed_at",
    "classification_rule", "availability", "redaction_status",
})
_INDEX_FIELDS = frozenset({
    "schema_version", "record_kind", "run_id", "feature_slug", "sealed_at",
    "inputs", "inspected_count", "index_digest",
})
_CANDIDATE_FIELDS = frozenset({
    "candidate_id", "category", "observed_problem", "evidence_refs",
    "source_runs", "source_stages", "source_chunks", "recurrence_count",
    "status", "dedupe_key", "dedupe_reason", "existing_control_refs",
    "owner_plugin", "target_surfaces", "mechanical_work",
    "judgment_boundary", "acceptance_tests", "confidence", "safety_boundary",
    "compatibility_notes", "benefit_basis", "expected_benefit", "benefit_rationale",
    "benefit_measurement", "merge_release_authority",
})
_REPORT_FIELDS = frozenset({
    "schema_version", "record_kind", "run_id", "feature_slug",
    "input_index_digest", "finalized_at", "cleanup_outcomes",
    "shadow_outcome", "metrics", "candidates", "inspected_input_count",
    "deduped_candidate_count", "empty_reason", "report_digest",
})
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")


def _timestamp(value, name):
    value = _text(value, name)
    if _TIMESTAMP.fullmatch(value) is None:
        _fail("invalid " + name)
    return value


def _digest_value(value, name):
    value = _text(value, name)
    if _DIGEST.fullmatch(value) is None:
        _fail("invalid " + name)
    return value


def _validate_input(value):
    if type(value) is not dict or set(value) != _INPUT_FIELDS:
        _fail("invalid improvement input fields")
    result = {
        "evidence_id": _identity(value["evidence_id"], "evidence id"),
        "artifact_ref": _reference(value["artifact_ref"], "artifact reference"),
        "artifact_digest": _digest_value(value["artifact_digest"], "artifact digest"),
        "source_run": _identity(value["source_run"], "source run"),
        "source_stage": _identity(value["source_stage"], "source stage"),
        "source_chunk": None if value["source_chunk"] is None else _identity(
            value["source_chunk"], "source chunk",
        ),
        "observation_category": _identity(
            value["observation_category"], "observation category",
        ),
        "observed_at": _timestamp(value["observed_at"], "observed at"),
        "classification_rule": _identity(
            value["classification_rule"], "classification rule",
        ),
        "availability": value["availability"],
        "redaction_status": value["redaction_status"],
    }
    if result["availability"] not in {"available", "unavailable"}:
        _fail("invalid input availability")
    if result["redaction_status"] != "approved_safe_reference_only":
        _fail("unsafe improvement input")
    return result


def validate_input_index(value):
    if type(value) is not dict or set(value) != _INDEX_FIELDS:
        _fail("invalid improvement input index fields")
    inputs = [_validate_input(item) for item in value["inputs"]]
    if inputs != sorted(inputs, key=lambda item: item["evidence_id"]):
        _fail("improvement inputs are not canonical")
    if len({item["evidence_id"] for item in inputs}) != len(inputs):
        _fail("duplicate evidence id")
    body = {
        "schema_version": value["schema_version"],
        "record_kind": value["record_kind"],
        "run_id": _identity(value["run_id"], "run id"),
        "feature_slug": _identity(value["feature_slug"], "feature slug"),
        "sealed_at": _timestamp(value["sealed_at"], "sealed at"),
        "inputs": inputs,
        "inspected_count": value["inspected_count"],
    }
    if body["schema_version"] != 1 or body["record_kind"] != "improvement-input-index":
        _fail("invalid improvement input index envelope")
    if type(body["inspected_count"]) is not int or body["inspected_count"] != len(inputs):
        _fail("invalid inspected input count")
    if value["index_digest"] != _digest(body):
        _fail("improvement input index digest mismatch")
    body["index_digest"] = value["index_digest"]
    return body


def build_input_index(*, run_id, feature_slug, sealed_at, inputs):
    normalized = sorted((_validate_input(dict(item)) for item in inputs),
                        key=lambda item: item["evidence_id"])
    body = {
        "schema_version": 1, "record_kind": "improvement-input-index",
        "run_id": run_id, "feature_slug": feature_slug, "sealed_at": sealed_at,
        "inputs": normalized, "inspected_count": len(normalized),
    }
    body["index_digest"] = _digest(body)
    return validate_input_index(body)


def _benefit_measurement(value):
    if type(value) is not dict or set(value) != {
        "metric", "unit", "baseline", "expected", "evidence_refs",
    }:
        _fail("invalid benefit measurement")
    baseline, expected = value["baseline"], value["expected"]
    if any(
        type(number) not in {int, float}
        or type(number) is float and not math.isfinite(number)
        for number in (baseline, expected)
    ):
        _fail("invalid benefit measurement value")
    evidence = _list(
        value["evidence_refs"], "benefit evidence reference", _reference,
    )
    if not evidence:
        _fail("measured benefit lacks evidence")
    return {
        "metric": _identity(value["metric"], "benefit metric"),
        "unit": _identity(value["unit"], "benefit unit"),
        "baseline": baseline, "expected": expected,
        "evidence_refs": evidence,
    }


def _candidate(value):
    if type(value) is not dict or set(value) != _CANDIDATE_FIELDS:
        _fail("invalid improvement candidate fields")
    result = {
        "candidate_id": value["candidate_id"],
        "category": value["category"],
        "observed_problem": _text(value["observed_problem"], "observed problem"),
        "evidence_refs": _list(value["evidence_refs"], "evidence reference", _reference),
        "source_runs": _list(value["source_runs"], "source run", _identity),
        "source_stages": _list(value["source_stages"], "source stage", _identity),
        "source_chunks": _list(value["source_chunks"], "source chunk", _identity),
        "recurrence_count": value["recurrence_count"], "status": value["status"],
        "dedupe_key": _text(value["dedupe_key"], "dedupe key"),
        "dedupe_reason": _text(value["dedupe_reason"], "dedupe reason"),
        "existing_control_refs": _list(
            value["existing_control_refs"], "existing control reference", _reference,
        ),
        "owner_plugin": _identity(value["owner_plugin"], "owner plugin"),
        "target_surfaces": _list(value["target_surfaces"], "target surface", _reference),
        "mechanical_work": _text(value["mechanical_work"], "mechanical work"),
        "judgment_boundary": _text(value["judgment_boundary"], "judgment boundary"),
        "acceptance_tests": _list(value["acceptance_tests"], "acceptance test", _text),
        "confidence": value["confidence"],
        "safety_boundary": _text(value["safety_boundary"], "safety boundary"),
        "compatibility_notes": _text(value["compatibility_notes"], "compatibility notes"),
        "benefit_basis": value["benefit_basis"],
        "expected_benefit": value["expected_benefit"],
        "benefit_rationale": _text(value["benefit_rationale"], "benefit rationale"),
        "benefit_measurement": (
            None if value["benefit_measurement"] is None
            else _benefit_measurement(value["benefit_measurement"])
        ),
        "merge_release_authority": value["merge_release_authority"],
    }
    if result["category"] not in _CATEGORIES or result["status"] not in _STATUSES:
        _fail("invalid candidate category or status")
    if (type(result["recurrence_count"]) is not int
            or result["recurrence_count"] < 1):
        _fail("invalid recurrence count")
    if ((result["status"] == "one-off" and result["recurrence_count"] != 1)
            or (result["status"] == "recurring" and result["recurrence_count"] < 2)
            or (result["status"] == "standing" and result["recurrence_count"] < 3)):
        _fail("candidate status disagrees with recurrence")
    if not result["evidence_refs"] or not result["source_runs"] or not result["source_stages"]:
        _fail("candidate lacks direct provenance")
    if not result["target_surfaces"] or not result["acceptance_tests"]:
        _fail("candidate lacks implementation boundary")
    if result["confidence"] not in {"low", "medium", "high", "unavailable"}:
        _fail("invalid candidate confidence")
    if result["benefit_basis"] not in {"qualitative", "measured"}:
        _fail("invalid benefit basis")
    if result["expected_benefit"] not in _BENEFIT_OUTCOMES:
        _fail("invalid benefit outcome category")
    if result["benefit_basis"] == "measured" and result["benefit_measurement"] is None:
        _fail("measured benefit lacks evidence")
    if result["benefit_basis"] == "qualitative" and result["benefit_measurement"] is not None:
        _fail("qualitative benefit claims measured evidence")
    if result["merge_release_authority"] is not False:
        _fail("Scout candidate claims merge or release authority")
    expected_id = candidate_id(result["dedupe_key"])
    if result["candidate_id"] != expected_id or _CANDIDATE_ID.fullmatch(expected_id) is None:
        _fail("candidate id mismatch")
    return result


def build_candidate(**fields):
    fields = dict(fields)
    if fields.get("merge_release_authority", False) is not False:
        _fail("Scout candidate claims merge or release authority")
    fields["candidate_id"] = candidate_id(fields.get("dedupe_key"))
    fields["merge_release_authority"] = False
    return _candidate(fields)


def _cleanup_outcome(value):
    fields = {"domain", "disposition", "count", "tier", "sensitivity", "evidence_ref"}
    if type(value) is not dict or set(value) != fields:
        _fail("invalid cleanup outcome")
    result = {
        "domain": value["domain"], "disposition": value["disposition"],
        "count": value["count"],
        "tier": _text(value["tier"], "cleanup tier", nullable=True),
        "sensitivity": _text(value["sensitivity"], "cleanup sensitivity", nullable=True),
        "evidence_ref": _reference(value["evidence_ref"], "cleanup evidence reference"),
    }
    if result["domain"] not in {"docker", "artifact", "git"}:
        _fail("invalid cleanup domain")
    if result["disposition"] not in {
            "created", "removed", "missing", "retained", "blocked", "uninspectable"}:
        _fail("invalid cleanup disposition")
    if type(result["count"]) is not int or result["count"] < 0:
        _fail("invalid cleanup count")
    return result


def _shadow_outcome(value):
    fields = {"availability", "category", "reasons", "missing_authority", "evidence_refs"}
    if type(value) is not dict or set(value) != fields:
        _fail("invalid shadow outcome")
    result = {
        "availability": value["availability"],
        "category": _text(value["category"], "shadow category", nullable=True),
        "reasons": _list(value["reasons"], "shadow reason", _text),
        "missing_authority": _list(value["missing_authority"], "missing authority", _text),
        "evidence_refs": _list(value["evidence_refs"], "shadow evidence reference", _reference),
    }
    if result["availability"] not in {"available", "unavailable"}:
        _fail("invalid shadow availability")
    if result["availability"] == "available" and result["category"] is None:
        _fail("available shadow outcome lacks category")
    if result["availability"] == "unavailable" and not result["reasons"]:
        _fail("unavailable shadow outcome lacks reason")
    if not result["evidence_refs"]:
        _fail("shadow outcome lacks evidence")
    return result


def _metric(value):
    fields = {"name", "availability", "value", "unit", "evidence_ref"}
    if type(value) is not dict or set(value) != fields:
        _fail("invalid Scout metric")
    result = {
        "name": _identity(value["name"], "metric name"),
        "availability": value["availability"], "value": value["value"],
        "unit": _text(value["unit"], "metric unit", nullable=True),
        "evidence_ref": _reference(value["evidence_ref"], "metric evidence reference"),
    }
    if result["availability"] == "measured":
        if type(result["value"]) not in {int, float} or result["unit"] is None:
            _fail("invalid measured metric")
    elif result["availability"] == "unavailable":
        if result["value"] is not None or result["unit"] is not None:
            _fail("unavailable metric has substituted value")
    else:
        _fail("invalid metric availability")
    return result


def _dedupe(candidates):
    groups = {}
    for raw in candidates:
        item = _candidate(dict(raw))
        groups.setdefault(item["dedupe_key"], []).append(item)
    result = []
    terminal_rank = {
        "completed": 0, "superseded": 1, "rejected": 2,
        "standing": 3, "recurring": 4, "one-off": 5,
    }
    for key in sorted(groups):
        items = groups[key]
        chosen = min(items, key=lambda item: (
            terminal_rank[item["status"]], _canonical_bytes(item),
        ))
        merged = dict(chosen)
        for field in ("evidence_refs", "source_runs", "source_stages", "source_chunks",
                      "existing_control_refs"):
            merged[field] = sorted({entry for item in items for entry in item[field]})
        measurements = [item["benefit_measurement"] for item in items]
        if measurements[0] is not None:
            identity = {
                key: measurements[0][key]
                for key in ("metric", "unit", "baseline", "expected")
            }
            if any(
                measurement is None or any(
                    measurement[key] != expected for key, expected in identity.items()
                )
                for measurement in measurements
            ):
                _fail("conflicting measured benefit claims")
            merged["benefit_measurement"] = {
                **identity,
                "evidence_refs": sorted({
                    reference for measurement in measurements
                    for reference in measurement["evidence_refs"]
                }),
            }
        merged["recurrence_count"] = len(merged["source_runs"])
        if merged["status"] in {"one-off", "recurring", "standing"}:
            merged["status"] = (
                "standing" if merged["recurrence_count"] >= 3
                else "recurring" if merged["recurrence_count"] >= 2 else "one-off"
            )
        result.append(_candidate(merged))
    return result, sum(len(items) - 1 for items in groups.values())


def _bind_candidate_to_index(candidate, index_inputs):
    """Reject claimed provenance that the sealed Stage A index cannot prove."""
    item = _candidate(dict(candidate))
    by_reference = {}
    for record in index_inputs:
        by_reference.setdefault(record["artifact_ref"], []).append(record)
    if any(reference not in by_reference for reference in item["evidence_refs"]):
        _fail("candidate evidence is absent from sealed input index")
    records = [
        record for reference in item["evidence_refs"]
        for record in by_reference[reference]
    ]
    expected = {
        "source_runs": sorted({record["source_run"] for record in records}),
        "source_stages": sorted({record["source_stage"] for record in records}),
        "source_chunks": sorted({
            record["source_chunk"] for record in records
            if record["source_chunk"] is not None
        }),
    }
    for field, values in expected.items():
        if sorted(item[field]) != values:
            _fail("candidate provenance disagrees with sealed input index")
    if item["recurrence_count"] != len(expected["source_runs"]):
        _fail("candidate recurrence disagrees with distinct indexed runs")
    measurement = item["benefit_measurement"]
    for reference in (() if measurement is None else measurement["evidence_refs"]):
        records = by_reference.get(reference)
        if not records or not any(
            record["availability"] == "available" for record in records
        ):
            _fail("measured benefit evidence is absent or unavailable")
    return item


def validate_improvement_report(value):
    if type(value) is not dict or set(value) != _REPORT_FIELDS:
        _fail("invalid improvement report fields")
    candidates = [_candidate(item) for item in value["candidates"]]
    if candidates != sorted(candidates, key=lambda item: item["candidate_id"]):
        _fail("improvement candidates are not canonical")
    body = {
        "schema_version": value["schema_version"], "record_kind": value["record_kind"],
        "run_id": _identity(value["run_id"], "run id"),
        "feature_slug": _identity(value["feature_slug"], "feature slug"),
        "input_index_digest": _digest_value(value["input_index_digest"], "input index digest"),
        "finalized_at": _timestamp(value["finalized_at"], "finalized at"),
        "cleanup_outcomes": [_cleanup_outcome(item) for item in value["cleanup_outcomes"]],
        "shadow_outcome": _shadow_outcome(value["shadow_outcome"]),
        "metrics": [_metric(item) for item in value["metrics"]],
        "candidates": candidates,
        "inspected_input_count": value["inspected_input_count"],
        "deduped_candidate_count": value["deduped_candidate_count"],
        "empty_reason": _text(value["empty_reason"], "empty reason", nullable=True),
    }
    if body["schema_version"] != 1 or body["record_kind"] != "improvement-report":
        _fail("invalid improvement report envelope")
    for field in ("inspected_input_count", "deduped_candidate_count"):
        if type(body[field]) is not int or body[field] < 0:
            _fail("invalid report count")
    if bool(candidates) == (body["empty_reason"] is not None):
        _fail("invalid empty report reason")
    if not candidates and body["empty_reason"] != "no_evidence_backed_improvement":
        _fail("invalid empty report reason")
    if {item["domain"] for item in body["cleanup_outcomes"]} != {
            "docker", "artifact", "git"}:
        _fail("incomplete cleanup outcomes")
    if {item["name"] for item in body["metrics"]} != _REQUIRED_METRICS:
        _fail("incomplete terminal metrics")
    if value["report_digest"] != _digest(body):
        _fail("improvement report digest mismatch")
    body["report_digest"] = value["report_digest"]
    return body


def build_improvement_report(*, input_index, finalized_at, cleanup_outcomes,
                             shadow_outcome, metrics, candidates):
    index = validate_input_index(input_index)
    bound = [
        _bind_candidate_to_index(candidate, index["inputs"])
        for candidate in candidates
    ]
    consolidated, deduped_count = _dedupe(bound)
    body = {
        "schema_version": 1, "record_kind": "improvement-report",
        "run_id": index["run_id"], "feature_slug": index["feature_slug"],
        "input_index_digest": index["index_digest"], "finalized_at": finalized_at,
        "cleanup_outcomes": sorted(
            (_cleanup_outcome(item) for item in cleanup_outcomes),
            key=lambda item: (item["domain"], item["disposition"], item["evidence_ref"]),
        ),
        "shadow_outcome": _shadow_outcome(shadow_outcome),
        "metrics": sorted((_metric(item) for item in metrics), key=lambda item: item["name"]),
        "candidates": sorted(consolidated, key=lambda item: item["candidate_id"]),
        "inspected_input_count": index["inspected_count"],
        "deduped_candidate_count": deduped_count,
        "empty_reason": None if consolidated else "no_evidence_backed_improvement",
    }
    body["report_digest"] = _digest(body)
    return validate_improvement_report(body)


def render_upstream_prompt(report):
    report = validate_improvement_report(report)
    eligible = [item for item in report["candidates"] if item["status"] in _PROMPT_STATUSES]
    lines = [
        "# Depot Upstream Improvement Run", "",
        "Run this work through the full `/pipeline` workflow in the Design-Machines/depot repository.",
        "Preserve this prompt as `original-prompt.md` and run a fresh final review.", "",
        "## Authority and compatibility fences", "",
        "- The structured upstream-improvements.json report is authoritative; this Markdown is a projection.",
        "- Do not merge, release, edit marketplace data, or mutate installed plugin caches.",
        "- Preserve Claude/Codex compatibility and do not invent savings or unavailable telemetry.", "",
        "## Evidence-backed candidates", "",
    ]
    if not eligible:
        lines.append("No eligible upstream implementation candidates were produced.")
    for item in eligible:
        measurement = item["benefit_measurement"]
        benefit = (
            f"- Benefit basis: `{item['benefit_basis']}`\n"
            f"- Benefit outcome: `{item['expected_benefit']}`\n"
            f"- Benefit rationale: {item['benefit_rationale']}"
        )
        if measurement is not None:
            benefit += (
                f"\n- Measured quantity: {measurement['metric']} "
                f"{measurement['baseline']} -> {measurement['expected']} "
                f"{measurement['unit']}. Evidence: "
                + ", ".join(measurement["evidence_refs"])
            )
        lines.extend((
            f"### {item['candidate_id']}", "",
            f"- Category: `{item['category']}`", f"- Status: `{item['status']}`",
            f"- Observed problem: {item['observed_problem']}",
            f"- Evidence: {', '.join(item['evidence_refs'])}",
            f"- Owner: `{item['owner_plugin']}`",
            f"- Proposed surfaces: {', '.join(item['target_surfaces'])}",
            f"- Mechanical work: {item['mechanical_work']}",
            f"- Agent/human judgment retained: {item['judgment_boundary']}",
            f"- Acceptance tests: {'; '.join(item['acceptance_tests'])}",
            f"- Safety boundary: {item['safety_boundary']}",
            f"- Compatibility: {item['compatibility_notes']}",
            benefit, "",
        ))
    return "\n".join(lines).rstrip() + "\n"
