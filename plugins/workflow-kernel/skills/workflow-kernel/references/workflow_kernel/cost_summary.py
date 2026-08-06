"""Schema-bound run-cost-summary artifact shaping.

This module owns the consumer-facing run-cost-summary artifact: schema
constants, validation, deterministic shaping, and digest computation.  It
reuses :class:`workflow_kernel.metrics.MetricsAggregator` for all
aggregation and adds only a thin shaping layer that produces per-phase rows
(from event stages), per-lane rows (from attempt economics), totals with
provenance, and measurement coverage.

The artifact is **observation only** -- it never gates, waives, selects, or
alters any lane, phase, or review outcome.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable, Mapping, Optional

from .metrics import MetricsAggregator, USAGE_FIELDS, _number
from .schema import WorkflowEvent


COST_SUMMARY_SCHEMA_VERSION = 1
VOLATILE_FIELDS = ("invocation.emitted_at",)

_REQUIRED_TOP_LEVEL = frozenset({
    "schema_version", "run_identity", "versions", "invocation",
    "phases", "lanes", "totals", "measurement_coverage",
    "volatile_fields", "digest",
})
_REQUIRED_RUN_IDENTITY = frozenset({
    "run_id", "workflow_class", "repository_commit", "dirty_state",
})
_REQUIRED_VERSIONS = frozenset({"kernel_version", "plugin_versions"})
_REQUIRED_INVOCATION = frozenset({"emitted_at", "first_event_at", "last_event_at"})
_REQUIRED_TOTALS = frozenset({
    "usage_count", "input_usage_count", "output_usage_count",
    "cache_read_usage_count", "cache_write_usage_count",
    "reasoning_usage_count", "cost_usd",
    "usage_provenance", "cost_provenance",
})
_REQUIRED_USAGE_PROVENANCE = frozenset(USAGE_FIELDS)
_REQUIRED_COVERAGE_SECTION = frozenset({
    "expected", "measured", "estimated", "missing", "overlap", "unassigned",
})
_ROW_FIELDS = frozenset({
    "requested_provider", "attempted_provider", "implemented_by",
    "provider", "model", "host", "duration_seconds", "wait_category",
    *USAGE_FIELDS, "cost_usd", "measurement_source", "usage_estimated",
})
_PHASE_ROW_KEYS = _ROW_FIELDS | {"phase"}
_LANE_ROW_KEYS = _ROW_FIELDS | {"lane", "chunk_id", "attempt"}

_NULLABLE_STR = (type(None), str)
_NULLABLE_INT = (type(None), int)
_NULLABLE_NUM = (type(None), int, float)


def validate_run_cost_summary(summary: Mapping) -> None:
    """Validate a run-cost-summary dict against the schema contract.

    Raises ValueError on any structural violation, including an unknown
    schema version.  This is the fail-closed gate for consumers that read
    a run-cost-summary.json artifact.  It mirrors
    ``run-cost-summary-schema.json`` (schema v1): exact key sets,
    ``additionalProperties: false`` everywhere, required nullable fields,
    integer coverage counters, and the kernel-declared volatile-field set.
    """
    if type(summary) is not dict:
        raise ValueError("run-cost-summary is not an object")
    if summary.get("schema_version") != COST_SUMMARY_SCHEMA_VERSION:
        raise ValueError("unsupported run-cost-summary schema version")
    if set(summary) != _REQUIRED_TOP_LEVEL:
        raise ValueError("run-cost-summary top-level fields mismatch")
    _validate_run_identity(summary["run_identity"])
    _validate_versions(summary["versions"])
    _validate_invocation(summary["invocation"])
    if type(summary["phases"]) is not list:
        raise ValueError("phases is not a list")
    for row in summary["phases"]:
        _validate_row(row, "phase", _PHASE_ROW_KEYS)
    if type(summary["lanes"]) is not list:
        raise ValueError("lanes is not a list")
    for row in summary["lanes"]:
        _validate_row(row, "lane", _LANE_ROW_KEYS)
        _validate_lane_identity(row)
    _validate_totals(summary["totals"])
    _validate_coverage(summary["measurement_coverage"])
    if summary["volatile_fields"] != list(VOLATILE_FIELDS):
        raise ValueError("volatile_fields must equal the kernel-declared set")
    if type(summary["digest"]) not in (type(None), str):
        raise ValueError("digest must be a string or null")


def _validate_run_identity(identity: Mapping) -> None:
    if type(identity) is not dict:
        raise ValueError("run_identity is not an object")
    if set(identity) != _REQUIRED_RUN_IDENTITY:
        raise ValueError("run_identity fields mismatch")
    if type(identity["run_id"]) is not str or not identity["run_id"]:
        raise ValueError("run_id is invalid")
    if type(identity["workflow_class"]) not in _NULLABLE_STR:
        raise ValueError("workflow_class must be a string or null")
    if type(identity["repository_commit"]) not in _NULLABLE_STR:
        raise ValueError("repository_commit must be a string or null")
    if type(identity["dirty_state"]) is not bool:
        raise ValueError("dirty_state is not boolean")


def _validate_versions(versions: Mapping) -> None:
    if type(versions) is not dict:
        raise ValueError("versions is not an object")
    allowed = _REQUIRED_VERSIONS
    if set(versions) - allowed:
        raise ValueError("versions has unexpected fields")
    if "kernel_version" not in versions:
        raise ValueError("versions missing kernel_version")
    if type(versions["kernel_version"]) is not str or not versions["kernel_version"]:
        raise ValueError("kernel_version is invalid")
    if "plugin_versions" in versions:
        if type(versions["plugin_versions"]) is not dict:
            raise ValueError("plugin_versions is not an object")
        for value in versions["plugin_versions"].values():
            if type(value) is not str:
                raise ValueError("plugin_versions values must be strings")


def _validate_invocation(invocation: Mapping) -> None:
    if type(invocation) is not dict:
        raise ValueError("invocation is not an object")
    if set(invocation) != _REQUIRED_INVOCATION:
        raise ValueError("invocation fields mismatch")
    for field in ("emitted_at", "first_event_at", "last_event_at"):
        if type(invocation[field]) not in _NULLABLE_STR or invocation[field] == "":
            if field == "emitted_at":
                raise ValueError("emitted_at must be a non-empty string")
            elif invocation[field] is not None:
                raise ValueError(field + " must be a string or null")


def _validate_row(row: Mapping, id_field: str, expected_keys: frozenset) -> None:
    if type(row) is not dict:
        raise ValueError("row is not an object")
    if set(row) != expected_keys:
        raise ValueError("row fields mismatch for " + id_field)
    if type(row[id_field]) is not str or not row[id_field]:
        raise ValueError("row %s is invalid" % id_field)
    if type(row.get("measurement_source")) is not str or not row["measurement_source"]:
        raise ValueError("measurement_source is invalid")
    if type(row.get("usage_estimated")) is not bool:
        raise ValueError("usage_estimated is not boolean")
    for field in ("requested_provider", "attempted_provider", "implemented_by",
                  "provider", "model", "host", "wait_category"):
        if type(row[field]) not in _NULLABLE_STR:
            raise ValueError(field + " must be a string or null")
    if type(row["duration_seconds"]) not in _NULLABLE_NUM:
        raise ValueError("duration_seconds must be a number or null")
    for field in USAGE_FIELDS:
        if type(row[field]) not in _NULLABLE_INT:
            raise ValueError(field + " must be an integer or null")
    if type(row["cost_usd"]) not in _NULLABLE_NUM:
        raise ValueError("cost_usd must be a number or null")


def _validate_lane_identity(row: Mapping) -> None:
    if type(row["chunk_id"]) not in _NULLABLE_STR:
        raise ValueError("chunk_id must be a string or null")
    if type(row["attempt"]) not in _NULLABLE_INT:
        raise ValueError("attempt must be an integer or null")


def _validate_totals(totals: Mapping) -> None:
    if type(totals) is not dict:
        raise ValueError("totals is not an object")
    if set(totals) != _REQUIRED_TOTALS:
        raise ValueError("totals fields mismatch")
    for field in USAGE_FIELDS:
        if type(totals[field]) not in _NULLABLE_INT:
            raise ValueError("totals." + field + " must be an integer or null")
    if type(totals["cost_usd"]) not in _NULLABLE_NUM:
        raise ValueError("totals.cost_usd must be a number or null")
    usage_provenance = totals["usage_provenance"]
    if type(usage_provenance) is not dict:
        raise ValueError("totals.usage_provenance is not an object")
    if set(usage_provenance) != _REQUIRED_USAGE_PROVENANCE:
        raise ValueError("totals.usage_provenance fields mismatch")
    for field in USAGE_FIELDS:
        if type(usage_provenance[field]) not in _NULLABLE_STR:
            raise ValueError(
                "totals.usage_provenance." + field + " must be a string or null",
            )
    if type(totals["cost_provenance"]) not in _NULLABLE_STR:
        raise ValueError("totals.cost_provenance must be a string or null")


def _validate_coverage(coverage: Mapping) -> None:
    if type(coverage) is not dict or set(coverage) != {"usage", "cost"}:
        raise ValueError("measurement_coverage is invalid")
    for key in ("usage", "cost"):
        section = coverage[key]
        if type(section) is not dict:
            raise ValueError("measurement_coverage.%s is not an object" % key)
        if set(section) != _REQUIRED_COVERAGE_SECTION:
            raise ValueError("measurement_coverage.%s fields mismatch" % key)
        for field in _REQUIRED_COVERAGE_SECTION:
            value = section[field]
            if type(value) is bool or type(value) is not int:
                raise ValueError(
                    "measurement_coverage.%s.%s must be an integer" % (key, field),
                )


def _kernel_version_string() -> str:
    from .runtime_resolution import KERNEL_VERSION
    return ".".join(str(part) for part in KERNEL_VERSION)


def _remove_volatile(summary: dict) -> dict:
    """Return a shallow copy with volatile fields and digest removed."""
    result = dict(summary)
    result.pop("digest", None)
    for path in VOLATILE_FIELDS:
        parts = path.split(".")
        target = result
        for part in parts[:-1]:
            if not isinstance(target, dict) or part not in target:
                target = None
                break
            if not isinstance(target[part], dict):
                target = None
                break
            target[part] = dict(target[part])
            target = target[part]
        if isinstance(target, dict):
            target.pop(parts[-1], None)
    return result


def compute_cost_summary_digest(summary: Mapping) -> str:
    """Compute a stable SHA-256 digest over non-volatile content.

    Excludes the kernel-declared ``VOLATILE_FIELDS`` paths and the digest
    field itself.  Two emissions from the same event log produce identical
    bytes after excluding the declared volatile fields, and therefore
    identical digests.
    """
    non_volatile = _remove_volatile(dict(summary))
    content = json.dumps(non_volatile, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def _empty_phase_row(stage: str) -> dict:
    return {
        "phase": stage,
        "requested_provider": None,
        "attempted_provider": None,
        "implemented_by": None,
        "provider": None,
        "model": None,
        "host": None,
        "duration_seconds": 0.0,
        "wait_category": None,
        "_has_usage": False,
        "usage_count": None,
        "input_usage_count": None,
        "output_usage_count": None,
        "cache_read_usage_count": None,
        "cache_write_usage_count": None,
        "reasoning_usage_count": None,
        "cost_usd": None,
        "measurement_source": None,
        "usage_estimated": False,
    }


def _phase_row_final(row: dict) -> dict:
    has_usage = row.pop("_has_usage")
    if not has_usage:
        for field in USAGE_FIELDS:
            row[field] = None
    duration = row.pop("duration_seconds")
    # 'unavailable' = no usage telemetry at all; 'unknown' = usage data
    # present but no explicit measurement_source in the event log.
    if row["measurement_source"] is None:
        row["measurement_source"] = "unknown" if has_usage else "unavailable"
    return {
        "phase": row["phase"],
        "requested_provider": row["requested_provider"],
        "attempted_provider": row["attempted_provider"],
        "implemented_by": row["implemented_by"],
        "provider": row["provider"],
        "model": row["model"],
        "host": row["host"],
        "duration_seconds": duration if duration else None,
        "wait_category": row["wait_category"],
        "usage_count": row["usage_count"],
        "input_usage_count": row["input_usage_count"],
        "output_usage_count": row["output_usage_count"],
        "cache_read_usage_count": row["cache_read_usage_count"],
        "cache_write_usage_count": row["cache_write_usage_count"],
        "reasoning_usage_count": row["reasoning_usage_count"],
        "cost_usd": row["cost_usd"],
        "measurement_source": row["measurement_source"],
        "usage_estimated": row["usage_estimated"],
    }


def _build_phase_rows(values: tuple) -> list:
    """Aggregate per-phase rows from event stages."""
    phase_data: dict = {}
    for event in values:
        stage = event.payload.get("stage")
        if type(stage) is not str or not stage:
            continue
        if stage not in phase_data:
            phase_data[stage] = _empty_phase_row(stage)
        row = phase_data[stage]
        payload = event.payload
        for field in (
            "requested_provider", "attempted_provider", "implemented_by",
            "provider", "model", "host", "wait_category",
        ):
            if row[field] is None and payload.get(field) is not None:
                row[field] = payload[field]
        if "duration_seconds" in payload:
            row["duration_seconds"] += _number(payload, "duration_seconds", float)
        for field in USAGE_FIELDS:
            if field in payload:
                row["_has_usage"] = True
                if row[field] is None:
                    row[field] = 0
                row[field] += _number(payload, field, int)
        if "cost_usd" in payload:
            if row["cost_usd"] is None:
                row["cost_usd"] = 0.0
            row["cost_usd"] += _number(payload, "cost_usd", float)
        if payload.get("measurement_source") is not None:
            if row["measurement_source"] is None:
                row["measurement_source"] = payload["measurement_source"]
        if payload.get("usage_estimated") is True:
            row["usage_estimated"] = True
    return [_phase_row_final(phase_data[stage]) for stage in sorted(phase_data)]


def _build_lane_rows(report: MetricsAggregator) -> list:
    """Per-lane rows from attempt economics, deterministically sorted."""
    lanes = []
    for econ in report.attempt_economics:
        lane = (
            econ.get("lane") or econ.get("reviewer")
            or econ.get("node_id") or "unknown"
        )
        lanes.append({
            "lane": lane,
            "chunk_id": econ.get("chunk_id"),
            "attempt": econ.get("attempt"),
            "requested_provider": econ.get("requested_provider"),
            "attempted_provider": econ.get("attempted_provider"),
            "implemented_by": econ.get("implemented_by"),
            "provider": econ.get("provider"),
            "model": econ.get("model"),
            "host": econ.get("host"),
            "duration_seconds": econ.get("duration_seconds"),
            "wait_category": econ.get("wait_category"),
            "usage_count": econ.get("usage_count"),
            "input_usage_count": econ.get("input_usage_count"),
            "output_usage_count": econ.get("output_usage_count"),
            "cache_read_usage_count": econ.get("cache_read_usage_count"),
            "cache_write_usage_count": econ.get("cache_write_usage_count"),
            "reasoning_usage_count": econ.get("reasoning_usage_count"),
            "cost_usd": econ.get("cost_usd"),
            "measurement_source": econ.get("measurement_source") or "unavailable",
            "usage_estimated": bool(econ.get("usage_estimated", False)),
        })
    lanes.sort(key=lambda r: (r["lane"] or "", r["chunk_id"] or "", r["attempt"] or 0))
    return lanes


def _build_totals(report: MetricsAggregator) -> dict:
    usage_provenance = {
        field: report.usage_total_provenance.get(field) for field in USAGE_FIELDS
    }
    return {
        "usage_count": report.usage_totals.get("usage_count"),
        "input_usage_count": report.usage_totals.get("input_usage_count"),
        "output_usage_count": report.usage_totals.get("output_usage_count"),
        "cache_read_usage_count": report.usage_totals.get("cache_read_usage_count"),
        "cache_write_usage_count": report.usage_totals.get("cache_write_usage_count"),
        "reasoning_usage_count": report.usage_totals.get("reasoning_usage_count"),
        "cost_usd": report.cost_usd,
        "usage_provenance": usage_provenance,
        "cost_provenance": report.cost_total_provenance,
    }


def _build_measurement_coverage(report: MetricsAggregator) -> dict:
    fields = ("expected", "measured", "estimated", "missing", "overlap", "unassigned")
    return {
        "usage": {
            field: report.usage_measurement_coverage.get(field, 0) for field in fields
        },
        "cost": {
            field: report.cost_measurement_coverage.get(field, 0) for field in fields
        },
    }


def _build_summary_identity(
    values: tuple, report: MetricsAggregator, *,
    repository_commit: Optional[str], dirty_state: bool,
) -> dict:
    run_id = values[0].run_id if values else "unknown"
    workflow_class = None
    if report.workflow_classes:
        workflow_class = max(
            report.workflow_classes, key=report.workflow_classes.get,
        )
    return {
        "run_id": run_id,
        "workflow_class": workflow_class,
        "repository_commit": repository_commit,
        "dirty_state": dirty_state,
    }


def build_run_cost_summary(
    events: Iterable[WorkflowEvent], *,
    repository_commit: Optional[str] = None,
    dirty_state: bool = False,
) -> dict:
    """Build a schema-bound run-cost-summary dict from workflow events.

    Reuses :class:`workflow_kernel.metrics.MetricsAggregator` for all
    aggregation; adds a thin shaping layer that produces per-phase rows
    (from event stages), per-lane rows (from attempt economics), totals
    with provenance, and measurement coverage.

    The ``digest`` field is left ``None``; the CLI command
    :func:`workflow_kernel.cli.command_run_cost_summary` is the sole place
    that finalizes the digest after redaction, so a stale pre-redaction
    digest can never be emitted or trusted.

    Missing-data honesty: phases/lanes without usage telemetry report
    ``measurement_source`` ``"unavailable"`` and null usage fields, never
    zeros.
    """
    values = tuple(events)
    report = MetricsAggregator().aggregate(values)

    summary = {
        "schema_version": COST_SUMMARY_SCHEMA_VERSION,
        "run_identity": _build_summary_identity(
            values, report,
            repository_commit=repository_commit, dirty_state=dirty_state,
        ),
        "versions": {
            "kernel_version": _kernel_version_string(),
        },
        "invocation": {
            "emitted_at": datetime.now(timezone.utc).isoformat(),
            "first_event_at": values[0].occurred_at if values else None,
            "last_event_at": values[-1].occurred_at if values else None,
        },
        "phases": _build_phase_rows(values),
        "lanes": _build_lane_rows(report),
        "totals": _build_totals(report),
        "measurement_coverage": _build_measurement_coverage(report),
        "volatile_fields": list(VOLATILE_FIELDS),
        "digest": None,
    }
    return summary
