"""Read-only reliability aggregation over receipt-bound workflow events."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Optional, Tuple

from .schema import WorkflowEvent


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
    cost_to_clean: Optional[float]
    fallback_rate: float
    cleanup_reliability: float
    proposals: Tuple[Mapping[str, object], ...]

    def to_dict(self) -> dict:
        return {
            "event_count": self.event_count,
            "duration_seconds_by_node": dict(self.duration_seconds_by_node),
            "attempts_by_node": dict(self.attempts_by_node),
            "providers": dict(self.providers), "models": dict(self.models),
            "hosts": dict(self.hosts), "workflow_classes": dict(self.workflow_classes),
            "isolation_modes": dict(self.isolation_modes),
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
            "cost_to_clean": self.cost_to_clean, "fallback_rate": self.fallback_rate,
            "cleanup_reliability": self.cleanup_reliability,
            "proposals": [dict(value) for value in self.proposals],
            "observation_only": True,
        }


def _number(payload, key, kind):
    if key not in payload:
        return kind(0)
    value = payload[key]
    if type(value) not in ((int,) if kind is int else (int, float)) or value < 0:
        raise ValueError("invalid numeric metric: " + key)
    return kind(value)


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
        )}
        attempts = Counter()
        retry_reasons = Counter()
        findings = Counter()
        convergence = []
        node_times = defaultdict(list)
        totals = Counter()
        tokens = 0
        cost = 0.0
        saw_tokens = saw_cost = False
        validation_count = validation_first = fallbacks = completed = terminals = 0
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
            attempt = payload.get("attempt")
            if type(attempt) is int and attempt > 0:
                attempts[node] = max(attempts[node], attempt)
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
            if "usage_count" in payload:
                saw_tokens = True
                tokens += _number(payload, "usage_count", int)
            if "cost_usd" in payload:
                saw_cost = True
                cost += _number(payload, "cost_usd", float)
            if payload.get("stage") in ("run_summary", "review_terminal"):
                terminals += 1
                completed += int(payload.get("status") in ("succeeded", "clean", "findings"))
        durations = {
            node: (max(times) - min(times)).total_seconds() if len(times) > 1 else 0.0
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
        return ReliabilityReport(
            len(values), durations, dict(attempts), dict(dimensions["provider"]),
            dict(dimensions["model"]), dict(dimensions["host"]),
            dict(dimensions["workflow_class"]), dict(dimensions["isolation_mode"]),
            dict(retry_reasons), tuple(convergence),
            validation_first / validation_count if validation_count else 0.0,
            dict(findings), len(findings), totals["persona_expected"],
            totals["persona_passed"], totals["persona_recovered"],
            totals["persona_missing"], totals["browser_expected"],
            totals["browser_passed"], totals["browser_recovered"],
            totals["browser_missing"], totals["cleanup_removed"],
            totals["cleanup_retained"], totals["cleanup_blocked"],
            totals["cleanup_foreign"], tokens if saw_tokens else None,
            cost if saw_cost else None,
            completed / terminals if terminals else 0.0,
            clean_seconds,
            cost / clean_total if saw_cost and clean_total else None,
            fallbacks / len(values) if values else 0.0,
            clean_total / cleanup_total if cleanup_total else 0.0,
            proposals,
        )
