"""Read-only reliability aggregation over receipt-bound workflow events."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
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
    payload = event.payload
    attempt = payload.get("attempt")
    if type(attempt) is not int or attempt < 1:
        return None
    node = event.node_id or payload.get("chunk_id")
    if type(node) is not str or not node:
        return None
    return (
        event.run_id, node, payload.get("chunk_id"), attempt,
        payload.get("reviewer"), payload.get("lane"),
        payload.get("requested_provider"), payload.get("attempted_provider"),
        payload.get("implemented_by"), payload.get("provider"), payload.get("model"),
    )


def _coverage(expected, rows, predicate) -> dict:
    measured_counts = Counter(
        identity for identity, payload in rows if predicate(payload)
    )
    measured = set(measured_counts)
    return {
        "expected": len(expected),
        "measured": len(measured),
        "estimated": len({
            identity for identity, payload in rows
            if identity in measured and predicate(payload)
            and payload.get("usage_estimated") is True
        }),
        "missing": len(expected - measured),
        "overlap": sum(1 for count in measured_counts.values() if count > 1),
    }


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


def _scoped_totals(attempt_rows, run_rows, legacy_rows, usage_coverage, cost_coverage):
    usage_totals = {}
    usage_provenance = {}
    for field in USAGE_FIELDS:
        run_values = [payload[field] for payload in run_rows if field in payload]
        legacy_values = [payload[field] for payload in legacy_rows if field in payload]
        attempt_values = [payload[field] for _, payload in attempt_rows if field in payload]
        if len(run_values) > 1:
            raise ValueError("overlapping authoritative run usage: " + field)
        if run_values:
            usage_totals[field] = sum(run_values)
            usage_provenance[field] = "authoritative_run_total"
        elif legacy_values:
            usage_totals[field] = sum(legacy_values)
            usage_provenance[field] = "legacy_unscoped_run_summary"
        elif (
            usage_coverage["expected"] > 0
            and usage_coverage["missing"] == 0
            and usage_coverage["overlap"] == 0
            and len(attempt_values) == usage_coverage["expected"]
        ):
            usage_totals[field] = sum(attempt_values)
            usage_provenance[field] = "derived_complete_attempts"
        else:
            usage_totals[field] = None
            usage_provenance[field] = None

    run_costs = [payload["cost_usd"] for payload in run_rows if "cost_usd" in payload]
    legacy_costs = [payload["cost_usd"] for payload in legacy_rows if "cost_usd" in payload]
    attempt_costs = [payload["cost_usd"] for _, payload in attempt_rows if "cost_usd" in payload]
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
        run_rows = []
        legacy_rows = []
        contributions = []
        canonical_findings = set()
        interventions = []
        seen_interventions = set()
        for event in values:
            payload = event.payload
            for name, counter in dimensions.items():
                value = payload.get(name)
                if type(value) is str and value:
                    counter[value] += 1
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
                if intervention_id not in seen_interventions:
                    seen_interventions.add(intervention_id)
                    row = {
                        "human_intervention_id": intervention_id,
                        "human_intervention_reason": payload["human_intervention_reason"],
                        "run_id": event.run_id, "node_id": event.node_id,
                    }
                    for field in ("chunk_id", "attempt", "missing_case_ids"):
                        if field in payload:
                            row[field] = payload[field]
                    interventions.append(row)
            if payload.get("stage") in ("run_summary", "review_terminal"):
                terminals += 1
                completed += int(payload.get("status") in ("succeeded", "clean", "findings"))

        economics = []
        for _, payload in attempt_rows:
            row = {"run_id": values[0].run_id if values else None}
            node_id = next(
                (event.node_id for event in values if event.payload is payload), None,
            )
            row["node_id"] = node_id
            row.update({field: payload[field] for field in ATTEMPT_ROW_FIELDS if field in payload})
            economics.append(row)
        usage_coverage = _coverage(
            expected_attempts, attempt_rows,
            lambda payload: any(field in payload for field in USAGE_FIELDS),
        )
        cost_coverage = _coverage(
            expected_attempts, attempt_rows, lambda payload: "cost_usd" in payload,
        )
        usage_totals, usage_provenance, cost, cost_provenance = _scoped_totals(
            attempt_rows, run_rows, legacy_rows, usage_coverage, cost_coverage,
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
            dict(dimensions["workflow_class"]), dict(dimensions["isolation_mode"]),
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
