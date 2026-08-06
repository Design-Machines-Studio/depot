"""Read-only reliability aggregation over receipt-bound workflow events."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Iterable, Mapping, Optional, Tuple

from .schema import WorkflowEvent


WAIT_CATEGORIES = (
    "human_gate",
    "external_dependency",
    "capacity",
    "ci",
)
USAGE_FIELDS = (
    "usage_count", "input_usage_count", "output_usage_count",
    "cache_read_usage_count", "cache_write_usage_count",
    "reasoning_usage_count",
)
CONTRIBUTION_BUCKETS = (
    "retained", "merged", "discarded", "unique", "corroborated", "disputed",
)
ATTEMPT_ROW_FIELDS = (
    "chunk_id", "attempt", "reviewer", "lane", "requested_provider",
    "attempted_provider", "implemented_by", "provider", "model", "host",
    "duration_seconds", "wait_category", "usage_scope", *USAGE_FIELDS,
    "cost_usd", "measurement_source", "usage_estimated",
)


@dataclass(frozen=True)
class ReliabilityReport:
    event_count: int
    duration_seconds_by_node: Mapping[str, float]
    attempts_by_node: Mapping[str, int]
    providers: Mapping[str, int]
    models: Mapping[str, int]
    hosts: Mapping[str, int]
    workflow_classes: Mapping[str, int]
    decision_profiles: Mapping[str, int]
    isolation_modes: Mapping[str, int]
    isolation_strategies: Mapping[str, int]
    retry_reasons: Mapping[str, int]
    convergence_signatures: Tuple[str, ...]
    validation_first_pass_rate: float
    findings_per_reviewer: Mapping[str, int]
    unique_reviewer_yield: int
    persona_expected: int
    persona_passed: int
    persona_recovered: int
    persona_missing: int
    browser_expected: int
    browser_passed: int
    browser_recovered: int
    browser_missing: int
    cleanup_removed: int
    cleanup_retained: int
    cleanup_blocked: int
    cleanup_foreign: int
    tokens: Optional[int]
    cost_usd: Optional[float]
    completion_rate: float
    time_to_clean_seconds: Optional[float]
    wall_clock_seconds: Optional[float]
    active_compute_seconds: Optional[float]
    wait_seconds_by_category: Mapping[str, float]
    cost_to_clean: Optional[float]
    fallback_rate: float
    cleanup_reliability: float
    attempt_economics: Tuple[Mapping[str, object], ...]
    usage_totals: Mapping[str, Optional[int]]
    usage_total_provenance: Mapping[str, Optional[str]]
    usage_measurement_coverage: Mapping[str, object]
    cost_total_provenance: Optional[str]
    cost_measurement_coverage: Mapping[str, object]
    canonical_finding_count: int
    finding_contribution_count: int
    finding_contributions_by_reviewer: Mapping[str, Mapping[str, int]]
    finding_contributions_by_provider: Mapping[str, Mapping[str, int]]
    finding_contributions_by_model: Mapping[str, Mapping[str, int]]
    human_intervention_count: int
    human_interventions_by_reason: Mapping[str, int]
    human_intervention_attempts: Tuple[Mapping[str, object], ...]
    proposals: Tuple[Mapping[str, object], ...]

    def to_dict(self) -> dict:
        return {
            "event_count": self.event_count,
            "duration_seconds_by_node": dict(self.duration_seconds_by_node),
            "attempts_by_node": dict(self.attempts_by_node),
            "providers": dict(self.providers), "models": dict(self.models),
            "hosts": dict(self.hosts), "workflow_classes": dict(self.workflow_classes),
            "decision_profiles": dict(self.decision_profiles),
            "isolation_modes": dict(self.isolation_modes),
            "isolation_strategies": dict(self.isolation_strategies),
            "retry_reasons": dict(self.retry_reasons),
            "convergence_signatures": list(self.convergence_signatures),
            "validation_first_pass_rate": self.validation_first_pass_rate,
            "findings_per_reviewer": dict(self.findings_per_reviewer),
            "unique_reviewer_yield": self.unique_reviewer_yield,
            "persona_expected": self.persona_expected, "persona_passed": self.persona_passed,
            "persona_recovered": self.persona_recovered, "persona_missing": self.persona_missing,
            "browser_expected": self.browser_expected, "browser_passed": self.browser_passed,
            "browser_recovered": self.browser_recovered, "browser_missing": self.browser_missing,
            "cleanup_removed": self.cleanup_removed, "cleanup_retained": self.cleanup_retained,
            "cleanup_blocked": self.cleanup_blocked, "cleanup_foreign": self.cleanup_foreign,
            "tokens": self.tokens, "cost_usd": self.cost_usd,
            "completion_rate": self.completion_rate,
            "time_to_clean_seconds": self.time_to_clean_seconds,
            "wall_clock_seconds": self.wall_clock_seconds,
            "active_compute_seconds": self.active_compute_seconds,
            "wait_seconds_by_category": dict(self.wait_seconds_by_category),
            "cost_to_clean": self.cost_to_clean, "fallback_rate": self.fallback_rate,
            "cleanup_reliability": self.cleanup_reliability,
            "attempt_economics": [dict(value) for value in self.attempt_economics],
            "usage_totals": dict(self.usage_totals),
            "usage_total_provenance": dict(self.usage_total_provenance),
            "usage_measurement_coverage": dict(self.usage_measurement_coverage),
            "cost_total_provenance": self.cost_total_provenance,
            "cost_measurement_coverage": dict(self.cost_measurement_coverage),
            "canonical_finding_count": self.canonical_finding_count,
            "finding_contribution_count": self.finding_contribution_count,
            "finding_contributions_by_reviewer": {
                key: dict(value) for key, value in self.finding_contributions_by_reviewer.items()
            },
            "finding_contributions_by_provider": {
                key: dict(value) for key, value in self.finding_contributions_by_provider.items()
            },
            "finding_contributions_by_model": {
                key: dict(value) for key, value in self.finding_contributions_by_model.items()
            },
            "human_intervention_count": self.human_intervention_count,
            "human_interventions_by_reason": dict(self.human_interventions_by_reason),
            "human_intervention_attempts": [
                dict(value) for value in self.human_intervention_attempts
            ],
            "proposals": [dict(value) for value in self.proposals],
            "observation_only": True,
        }


def _number(payload, key, kind):
    if key not in payload:
        return kind(0)
    value = payload[key]
    valid_type = type(value) is int if kind is int else type(value) in {int, float}
    if not valid_type or value < 0 or (type(value) is float and not math.isfinite(value)):
        raise ValueError("invalid numeric metric: " + key)
    return kind(value)


def _attempt_identity(event: WorkflowEvent) -> Optional[tuple]:
    """Coverage identity; provider/model remain row dimensions, not attempts."""
    payload = event.payload
    attempt = payload.get("attempt")
    if type(attempt) is not int or attempt < 1:
        return None
    node_or_chunk = payload.get("chunk_id") or event.node_id
    if type(node_or_chunk) is not str or not node_or_chunk:
        return None
    return (
        event.run_id, node_or_chunk, attempt,
        payload.get("reviewer"), payload.get("lane"),
    )


def _coverage_assignments(expected, rows, predicate):
    grouped = defaultdict(set)
    for identity in expected:
        grouped[identity[:3]].add(identity)
    normalized_expected = set()
    for identities in grouped.values():
        detailed = {
            identity for identity in identities
            if identity[3] is not None or identity[4] is not None
        }
        normalized_expected.update(detailed or identities)

    def resolved(identity):
        if identity[3] is not None or identity[4] is not None:
            return identity
        candidates = {
            candidate for candidate in normalized_expected
            if candidate[:3] == identity[:3]
        }
        return next(iter(candidates)) if len(candidates) == 1 else identity

    measured_counts = Counter()
    unassigned = 0
    assigned_rows = []
    for identity, payload in rows:
        if not predicate(payload):
            continue
        assigned = resolved(identity)
        if assigned not in normalized_expected:
            unassigned += 1
            continue
        measured_counts[assigned] += 1
        assigned_rows.append((assigned, payload))
    measured = set(measured_counts)
    return {
        "expected": len(normalized_expected),
        "measured": len(measured),
        "estimated": len({
            identity for identity, payload in assigned_rows
            if identity in measured
            and payload.get("usage_estimated") is True
        }),
        "missing": len(normalized_expected - measured),
        "overlap": sum(1 for count in measured_counts.values() if count > 1),
        "unassigned": unassigned,
    }, assigned_rows


def _coverage(expected, rows, predicate) -> dict:
    return _coverage_assignments(expected, rows, predicate)[0]


def _dimension_summary(values) -> dict:
    result = {}
    for key, disposition, agreement in values:
        if type(key) is not str or not key:
            continue
        if key not in result:
            result[key] = {bucket: 0 for bucket in CONTRIBUTION_BUCKETS}
        result[key][disposition] += 1
        result[key][agreement] += 1
    return result


def _scoped_totals(attempt_rows, run_rows, legacy_rows, expected_attempts):
    usage_totals = {}
    usage_provenance = {}
    for field in USAGE_FIELDS:
        run_values = [payload[field] for payload in run_rows if field in payload]
        legacy_values = [payload[field] for payload in legacy_rows if field in payload]
        coverage, assigned_rows = _coverage_assignments(
            expected_attempts, attempt_rows, lambda payload: field in payload,
        )
        attempt_values = [payload[field] for _, payload in assigned_rows]
        if len(run_values) > 1:
            raise ValueError("overlapping authoritative run usage: " + field)
        if run_values:
            usage_totals[field] = sum(run_values)
            usage_provenance[field] = "authoritative_run_total"
        elif legacy_values:
            usage_totals[field] = sum(legacy_values)
            usage_provenance[field] = "legacy_unscoped_run_summary"
        elif (
            coverage["expected"] > 0
            and coverage["missing"] == 0
            and coverage["overlap"] == 0
            and coverage["unassigned"] == 0
            and len(attempt_values) == coverage["expected"]
        ):
            usage_totals[field] = sum(attempt_values)
            usage_provenance[field] = "derived_complete_attempts"
        else:
            usage_totals[field] = None
            usage_provenance[field] = None

    run_costs = [payload["cost_usd"] for payload in run_rows if "cost_usd" in payload]
    legacy_costs = [payload["cost_usd"] for payload in legacy_rows if "cost_usd" in payload]
    cost_coverage, assigned_cost_rows = _coverage_assignments(
        expected_attempts, attempt_rows, lambda payload: "cost_usd" in payload,
    )
    attempt_costs = [payload["cost_usd"] for _, payload in assigned_cost_rows]
    if len(run_costs) > 1:
        raise ValueError("overlapping authoritative run cost")
    if run_costs:
        cost, cost_provenance = sum(run_costs), "authoritative_run_total"
    elif legacy_costs:
        cost, cost_provenance = sum(legacy_costs), "legacy_unscoped_run_summary"
    elif (
        cost_coverage["expected"] > 0
        and cost_coverage["missing"] == 0
        and cost_coverage["overlap"] == 0
        and cost_coverage["unassigned"] == 0
        and len(attempt_costs) == cost_coverage["expected"]
    ):
        cost, cost_provenance = sum(attempt_costs), "derived_complete_attempts"
    else:
        cost, cost_provenance = None, None
    return usage_totals, usage_provenance, cost, cost_provenance


class MetricsAggregator:
    """Aggregate immutable observations; proposals never mutate policy."""

    def aggregate(self, events: Iterable[WorkflowEvent]) -> ReliabilityReport:
        values = tuple(events)
        if any(type(event) is not WorkflowEvent for event in values):
            raise ValueError("invalid metric events")
        if values and (
            any(event.sequence != position for position, event in enumerate(values))
            or any(event.run_id != values[0].run_id for event in values)
        ):
            raise ValueError("non-contiguous metric events")
        dimensions = {name: Counter() for name in (
            "provider", "model", "host", "workflow_class", "isolation_mode",
            "isolation_strategy",
        )}
        decision_profiles = Counter()
        attempts = Counter()
        retry_reasons = Counter()
        findings = Counter()
        convergence = []
        node_times = defaultdict(list)
        explicit_node_durations = Counter()
        nodes_with_explicit_duration = set()
        totals = Counter()
        validation_count = validation_first = fallbacks = completed = terminals = 0
        wait_seconds = Counter()
        expected_attempts = set()
        attempt_rows = []
        economics = []
        run_rows = []
        legacy_rows = []
        contributions = []
        canonical_findings = set()
        interventions = []
        seen_interventions = {}
        for event in values:
            payload = event.payload
            for name, counter in dimensions.items():
                value = payload.get(name)
                if type(value) is str and value:
                    counter[value] += 1
            profile = payload.get("decision_profile")
            if isinstance(profile, Mapping):
                decision_profiles[
                    profile.get("uncertainty", "invalid") + "/"
                    + profile.get("consequence", "invalid")
                ] += 1
            elif payload.get("decision_profile_defaulted") is True:
                decision_profiles["legacy-defaulted"] += 1
            node = event.node_id or "run"
            try:
                node_times[node].append(datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00")))
            except ValueError:
                pass
            if "duration_seconds" in payload:
                nodes_with_explicit_duration.add(node)
                explicit_node_durations[node] += _number(payload, "duration_seconds", float)
            wait_category = payload.get("wait_category")
            if wait_category is not None:
                if wait_category not in WAIT_CATEGORIES:
                    raise ValueError("invalid wait category: " + str(wait_category))
                wait_seconds[wait_category] += _number(payload, "duration_seconds", float)
            attempt = payload.get("attempt")
            if type(attempt) is int and attempt > 0:
                attempts[node] = max(attempts[node], attempt)
            identity = _attempt_identity(event)
            if identity is not None:
                expected_attempts.add(identity)
            reason = payload.get("retry_reason", payload.get("fallback_reason"))
            if type(reason) is str and reason:
                retry_reasons[reason] += 1
            if payload.get("fallback_reason"):
                fallbacks += 1
            if payload.get("stage") == "deterministic_validation":
                validation_count += 1
                validation_first += int(payload.get("first_pass") is True)
            reviewer = payload.get("reviewer")
            if payload.get("stage") == "finding" and type(reviewer) is str:
                findings[reviewer] += 1
            signature = payload.get("convergence_signature", payload.get("prior_findings_signature"))
            if type(signature) is str and signature and signature not in convergence:
                convergence.append(signature)
            for name in (
                "persona_expected", "persona_passed", "persona_recovered", "persona_missing",
                "browser_expected", "browser_passed", "browser_recovered", "browser_missing",
                "cleanup_removed", "cleanup_retained", "cleanup_blocked", "cleanup_foreign",
            ):
                totals[name] += _number(payload, name, int)
            if payload.get("usage_scope") == "attempt" and identity is not None:
                attempt_rows.append((identity, payload))
                row = {"run_id": event.run_id, "node_id": event.node_id}
                row.update({
                    field: payload[field]
                    for field in ATTEMPT_ROW_FIELDS if field in payload
                })
                economics.append(row)
            elif payload.get("usage_scope") == "run":
                run_rows.append(payload)
            elif any(field in payload for field in (*USAGE_FIELDS, "cost_usd")):
                legacy_rows.append(payload)
            if payload.get("stage") == "finding_contribution":
                contributions.append(payload)
                if payload.get("finding_disposition") in {"retained", "merged"}:
                    canonical_findings.add(payload["canonical_finding_id"])
            if payload.get("human_intervention") is True:
                intervention_id = payload.get("human_intervention_id")
                row = {
                    "human_intervention_id": intervention_id,
                    "human_intervention_reason": payload["human_intervention_reason"],
                    "producer_stage": payload.get("stage"),
                    "run_id": event.run_id, "node_id": event.node_id,
                }
                for field in (
                    "chunk_id", "attempt", "missing_case_ids",
                    "recovery_receipt_digests",
                ):
                    if field in payload:
                        row[field] = payload[field]
                if "contract_digest" in payload:
                    row["contract_digest"] = payload["contract_digest"]
                identity = (
                    row["producer_stage"], row["run_id"], row["node_id"],
                    row.get("chunk_id"), row.get("attempt"),
                    row["human_intervention_reason"],
                    tuple(row.get("missing_case_ids", ())),
                    tuple(row.get("recovery_receipt_digests", ())),
                    row.get("contract_digest"),
                )
                prior = seen_interventions.setdefault(intervention_id, identity)
                if prior != identity:
                    raise ValueError("conflicting human intervention identity")
                if prior == identity and not any(
                    item["human_intervention_id"] == intervention_id
                    for item in interventions
                ):
                    interventions.append(row)
            if payload.get("stage") in ("run_summary", "review_terminal"):
                terminals += 1
                completed += int(payload.get("status") in ("succeeded", "clean", "findings"))

        usage_coverage = _coverage(
            expected_attempts, attempt_rows,
            lambda payload: any(field in payload for field in USAGE_FIELDS),
        )
        cost_coverage = _coverage(
            expected_attempts, attempt_rows, lambda payload: "cost_usd" in payload,
        )
        usage_totals, usage_provenance, cost, cost_provenance = _scoped_totals(
            attempt_rows, run_rows, legacy_rows, expected_attempts,
        )
        durations = {
            node: (
                explicit_node_durations[node]
                if node in nodes_with_explicit_duration
                else (max(times) - min(times)).total_seconds() if len(times) > 1 else 0.0
            )
            for node, times in node_times.items()
        }
        cleanup_total = sum(totals[name] for name in (
            "cleanup_removed", "cleanup_retained", "cleanup_blocked",
        ))
        clean_total = totals["cleanup_removed"] + totals["cleanup_retained"]
        event_times = []
        cleanup_times = []
        for event in values:
            try:
                parsed_time = datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
                event_times.append(parsed_time)
            except ValueError:
                continue
            if event.payload.get("stage") in {
                "chunk_cleanup", "repository_cleanup", "terminal_reconciliation",
            }:
                cleanup_times.append(parsed_time)
        clean_seconds = (
            (max(cleanup_times) - min(event_times)).total_seconds()
            if cleanup_times and event_times else None
        )
        wall_clock_seconds = (
            (max(event_times) - min(event_times)).total_seconds()
            if event_times else None
        )
        active_compute_seconds = (
            max(0.0, wall_clock_seconds - sum(wait_seconds.values()))
            if wall_clock_seconds is not None else None
        )
        proposals = ()
        if fallbacks:
            proposals += ({
                "kind": "routing_or_workflow_change", "mode": "proposal_only",
                "human_approval_required": True, "rationale": "observed_fallback",
                "evidence_count": fallbacks,
            },)
        if totals["cleanup_blocked"]:
            proposals += ({
                "kind": "cleanup_change", "mode": "proposal_only",
                "human_approval_required": True, "rationale": "observed_cleanup_block",
                "evidence_count": totals["cleanup_blocked"],
            },)
        by_reviewer = _dimension_summary(
            (payload.get("reviewer"), payload["finding_disposition"], payload["agreement"])
            for payload in contributions
        )
        by_provider = _dimension_summary(
            (
                payload.get("provider", payload.get("implemented_by")),
                payload["finding_disposition"], payload["agreement"],
            )
            for payload in contributions
        )
        by_model = _dimension_summary(
            (payload.get("model"), payload["finding_disposition"], payload["agreement"])
            for payload in contributions
        )
        intervention_reasons = Counter(
            row["human_intervention_reason"] for row in interventions
        )
        return ReliabilityReport(
            len(values), durations, dict(attempts), dict(dimensions["provider"]),
            dict(dimensions["model"]), dict(dimensions["host"]),
            dict(dimensions["workflow_class"]), dict(decision_profiles),
            dict(dimensions["isolation_mode"]),
            dict(dimensions["isolation_strategy"]),
            dict(retry_reasons), tuple(convergence),
            validation_first / validation_count if validation_count else 0.0,
            dict(findings), len(findings), totals["persona_expected"],
            totals["persona_passed"], totals["persona_recovered"],
            totals["persona_missing"], totals["browser_expected"],
            totals["browser_passed"], totals["browser_recovered"],
            totals["browser_missing"], totals["cleanup_removed"],
            totals["cleanup_retained"], totals["cleanup_blocked"],
            totals["cleanup_foreign"], usage_totals["usage_count"], cost,
            completed / terminals if terminals else 0.0,
            clean_seconds, wall_clock_seconds, active_compute_seconds,
            {category: wait_seconds[category] for category in WAIT_CATEGORIES},
            cost / clean_total if cost is not None and clean_total else None,
            fallbacks / len(values) if values else 0.0,
            clean_total / cleanup_total if cleanup_total else 0.0,
            tuple(economics), usage_totals, usage_provenance, usage_coverage,
            cost_provenance, cost_coverage, len(canonical_findings),
            len(contributions), by_reviewer, by_provider, by_model,
            len(interventions), dict(intervention_reasons), tuple(interventions),
            proposals,
        )


# --- Run cost summary ---

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
_REQUIRED_INVOCATION = frozenset({"emitted_at", "first_event_at", "last_event_at"})
_REQUIRED_TOTALS = frozenset({
    "usage_count", "input_usage_count", "output_usage_count",
    "cache_read_usage_count", "cache_write_usage_count",
    "reasoning_usage_count", "cost_usd",
    "usage_provenance", "cost_provenance",
})
_ROW_FIELDS = frozenset({
    "requested_provider", "attempted_provider", "implemented_by",
    "provider", "model", "host", "duration_seconds", "wait_category",
    *USAGE_FIELDS, "cost_usd", "measurement_source", "usage_estimated",
})


def validate_run_cost_summary(summary: Mapping) -> None:
    """Validate a run-cost-summary dict against the schema contract.

    Raises ValueError on any structural violation, including an unknown
    schema version.  This is the fail-closed gate for consumers that read
    a run-cost-summary.json artifact.
    """
    if type(summary) is not dict:
        raise ValueError("run-cost-summary is not an object")
    if summary.get("schema_version") != COST_SUMMARY_SCHEMA_VERSION:
        raise ValueError("unsupported run-cost-summary schema version")
    missing = _REQUIRED_TOP_LEVEL - set(summary)
    if missing:
        raise ValueError("run-cost-summary missing fields: " + ",".join(sorted(missing)))
    identity = summary["run_identity"]
    if type(identity) is not dict:
        raise ValueError("run_identity is not an object")
    if set(identity) != _REQUIRED_RUN_IDENTITY:
        raise ValueError("run_identity fields mismatch")
    if type(identity["run_id"]) is not str or not identity["run_id"]:
        raise ValueError("run_id is invalid")
    if type(identity["dirty_state"]) is not bool:
        raise ValueError("dirty_state is not boolean")
    versions = summary["versions"]
    if type(versions) is not dict or "kernel_version" not in versions:
        raise ValueError("versions missing kernel_version")
    if type(versions["kernel_version"]) is not str or not versions["kernel_version"]:
        raise ValueError("kernel_version is invalid")
    invocation = summary["invocation"]
    if type(invocation) is not dict:
        raise ValueError("invocation is not an object")
    if set(invocation) != _REQUIRED_INVOCATION:
        raise ValueError("invocation fields mismatch")
    if type(summary["phases"]) is not list:
        raise ValueError("phases is not a list")
    for row in summary["phases"]:
        _validate_row(row, "phase")
    if type(summary["lanes"]) is not list:
        raise ValueError("lanes is not a list")
    for row in summary["lanes"]:
        _validate_row(row, "lane")
    totals = summary["totals"]
    if type(totals) is not dict:
        raise ValueError("totals is not an object")
    if set(totals) != _REQUIRED_TOTALS:
        raise ValueError("totals fields mismatch")
    coverage = summary["measurement_coverage"]
    if type(coverage) is not dict or set(coverage) != {"usage", "cost"}:
        raise ValueError("measurement_coverage is invalid")
    for key in ("usage", "cost"):
        section = coverage[key]
        if type(section) is not dict:
            raise ValueError("measurement_coverage.%s is not an object" % key)
        expected = {"expected", "measured", "estimated", "missing", "overlap", "unassigned"}
        if set(section) != expected:
            raise ValueError("measurement_coverage.%s fields mismatch" % key)
    if type(summary["volatile_fields"]) is not list:
        raise ValueError("volatile_fields is not a list")


def _validate_row(row: Mapping, id_field: str) -> None:
    if type(row) is not dict:
        raise ValueError("row is not an object")
    if id_field not in row or type(row[id_field]) is not str or not row[id_field]:
        raise ValueError("row %s is invalid" % id_field)
    if type(row.get("measurement_source")) is not str or not row["measurement_source"]:
        raise ValueError("measurement_source is invalid")
    if type(row.get("usage_estimated")) is not bool:
        raise ValueError("usage_estimated is not boolean")
    for field in _ROW_FIELDS:
        if field not in row:
            raise ValueError("row missing field: " + field)


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
    """Compute a stable SHA-256 digest over non-volatile content."""
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


def build_run_cost_summary(
    events: Iterable[WorkflowEvent], *,
    repository_commit: Optional[str] = None,
    dirty_state: bool = False,
) -> dict:
    """Build a schema-bound run-cost-summary dict from workflow events.

    Reuses MetricsAggregator for all aggregation; adds a thin shaping layer
    that produces per-phase rows (from event stages), per-lane rows (from
    attempt economics), totals with provenance, and measurement coverage.
    Missing-data honesty: phases/lanes without usage telemetry report
    measurement_source "unavailable" and null usage fields, never zeros.
    """
    values = tuple(events)
    report = MetricsAggregator().aggregate(values)

    run_id = values[0].run_id if values else "unknown"
    workflow_class = None
    if report.workflow_classes:
        workflow_class = max(
            report.workflow_classes, key=report.workflow_classes.get,
        )

    # Per-phase rows: aggregate by event stage.
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

    phases = [_phase_row_final(phase_data[stage]) for stage in sorted(phase_data)]

    # Per-lane rows: from attempt economics.
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

    # Totals with provenance.
    usage_provenance = {
        field: report.usage_total_provenance.get(field) for field in USAGE_FIELDS
    }
    totals = {
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

    # Measurement coverage.
    measurement_coverage = {
        "usage": {
            "expected": report.usage_measurement_coverage.get("expected", 0),
            "measured": report.usage_measurement_coverage.get("measured", 0),
            "estimated": report.usage_measurement_coverage.get("estimated", 0),
            "missing": report.usage_measurement_coverage.get("missing", 0),
            "overlap": report.usage_measurement_coverage.get("overlap", 0),
            "unassigned": report.usage_measurement_coverage.get("unassigned", 0),
        },
        "cost": {
            "expected": report.cost_measurement_coverage.get("expected", 0),
            "measured": report.cost_measurement_coverage.get("measured", 0),
            "estimated": report.cost_measurement_coverage.get("estimated", 0),
            "missing": report.cost_measurement_coverage.get("missing", 0),
            "overlap": report.cost_measurement_coverage.get("overlap", 0),
            "unassigned": report.cost_measurement_coverage.get("unassigned", 0),
        },
    }

    emitted_at = datetime.now(timezone.utc).isoformat()
    first_event_at = values[0].occurred_at if values else None
    last_event_at = values[-1].occurred_at if values else None

    summary = {
        "schema_version": COST_SUMMARY_SCHEMA_VERSION,
        "run_identity": {
            "run_id": run_id,
            "workflow_class": workflow_class,
            "repository_commit": repository_commit,
            "dirty_state": dirty_state,
        },
        "versions": {
            "kernel_version": _kernel_version_string(),
        },
        "invocation": {
            "emitted_at": emitted_at,
            "first_event_at": first_event_at,
            "last_event_at": last_event_at,
        },
        "phases": phases,
        "lanes": lanes,
        "totals": totals,
        "measurement_coverage": measurement_coverage,
        "volatile_fields": list(VOLATILE_FIELDS),
        "digest": None,
    }
    summary["digest"] = compute_cost_summary_digest(summary)
    return summary
