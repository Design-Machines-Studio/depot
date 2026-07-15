"""Semantic shadow comparison with no workflow or cleanup authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from .schema import RunState, WorkflowEvent


KNOWN_MECHANISMS = {
    "claude_native": "agentic_dispatch",
    "codex_companion": "agentic_dispatch",
    "native": "agentic_dispatch",
    "codex_native": "agentic_dispatch",
    "generic_agentic": "agentic_dispatch",
}
KNOWN_AGENTIC_PROVIDERS = frozenset({"anthropic", "openai", "generic"})
KNOWN_HOST_PROFILES = {
    ("claude", "claude_native", "anthropic"),
    ("codex", "codex_companion", "openai"),
    ("generic", "generic_agentic", "generic"),
}


@dataclass(frozen=True)
class ReceiptSet:
    events: Tuple[WorkflowEvent, ...]

    @classmethod
    def from_events(cls, events: Iterable[WorkflowEvent]) -> "ReceiptSet":
        values = tuple(events)
        if any(type(event) is not WorkflowEvent for event in values):
            raise ValueError("invalid receipt events")
        run_id = values[0].run_id if values else None
        for position, event in enumerate(values):
            if event.sequence != position or event.run_id != run_id:
                raise ValueError("non-contiguous receipt set")
            reference = event.payload.get("authoritative_receipt")
            evidence = event.payload.get("evidence", ())
            if type(reference) is not str or reference not in evidence:
                raise ValueError("missing authoritative evidence")
        return cls(values)

    def to_dict(self) -> dict:
        return {"events": [event.to_dict() for event in self.events]}


@dataclass(frozen=True)
class ParityReport:
    reason: str
    semantic_match: bool
    safe_to_promote: bool
    differences: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "reason": self.reason, "semantic_match": self.semantic_match,
            "safe_to_promote": self.safe_to_promote,
            "differences": list(self.differences), "observation_only": True,
        }


def _normalized_reference(value: object) -> object:
    if type(value) is not str:
        return value
    pieces = value.split("/")
    if len(pieces) >= 3 and pieces[0] == "receipts" and pieces[1] in {
        "claude", "codex", "generic",
    }:
        return (pieces[0], "host", *pieces[2:])
    return value


def _routing_fact(event: WorkflowEvent, *, normalize_host: bool = False) -> tuple:
    payload = event.payload
    mechanism = _mechanism(event)
    provider = payload.get("provider")
    host = payload.get("host")
    if normalize_host and mechanism == "agentic_dispatch" and provider in KNOWN_AGENTIC_PROVIDERS:
        provider = "agentic_provider"
    if normalize_host and mechanism == "agentic_dispatch" and host in {"claude", "codex", "generic"}:
        host = "agentic_host"
    return host, mechanism, provider


def _semantic(event: WorkflowEvent, *, normalize_host: bool = False) -> tuple:
    payload = event.payload
    routing = _routing_fact(event, normalize_host=normalize_host)
    return (
        event.run_id, event.sequence, event.node_id, payload.get("stage"),
        payload.get("status"), payload.get("workflow_class"),
        payload.get("workflow_class_defaulted"),
        ("host_execution" if normalize_host else payload.get("execution_mode")), routing,
        (_normalized_reference(payload.get("authoritative_receipt"))
         if normalize_host else payload.get("authoritative_receipt")),
        payload.get("first_pass"), payload.get("persona_expected"),
        payload.get("persona_passed"), payload.get("persona_recovered"),
        payload.get("persona_missing"), payload.get("browser_expected"),
        payload.get("browser_passed"), payload.get("browser_recovered"),
        payload.get("browser_missing"), payload.get("cleanup_removed"),
        payload.get("cleanup_retained"), payload.get("cleanup_blocked"),
        payload.get("cleanup_foreign"), payload.get("cleanup_disposition"),
        payload.get("cleanup_policy"), payload.get("resource_kind"),
        payload.get("resource_name"),
        payload.get("requested_provider"), payload.get("attempted_provider"),
        payload.get("attempt"), payload.get("retry_reason"),
        payload.get("isolation_mode"), payload.get("requested_executor"),
        payload.get("attempted_executor"),
        payload.get("implemented_by"), payload.get("fallback"),
        payload.get("fallback_path"), payload.get("fallback_reason"),
        payload.get("lane"), payload.get("finding_id"),
        payload.get("severity"), payload.get("reviewer"),
        payload.get("requested_lanes"), payload.get("expected_lanes"),
        payload.get("completed_lanes"), payload.get("failed_lanes"),
        payload.get("degraded_lanes"), payload.get("unavailable_lanes"),
        payload.get("topology"), payload.get("topology_node"),
        payload.get("topology_edge"),
        payload.get("finding_count"), payload.get("prior_findings_signature"),
        payload.get("convergence_signature"),
    )


def _mechanism(event: WorkflowEvent):
    value = event.payload.get("mechanism")
    return KNOWN_MECHANISMS.get(value, value)


class ShadowComparator:
    """Compares facts only; it cannot select nodes, gates, policy, or commands."""

    def compare(self, predicted: RunState, authoritative: ReceiptSet) -> ParityReport:
        if type(predicted) is not RunState or type(authoritative) is not ReceiptSet:
            raise ValueError("invalid parity inputs")
        return ParityReport(
            "semantic_receipts_required", False, False,
            ("run_state_evidence_is_not_semantic_parity",),
        )

    def compare_receipt_sets(self, predicted: ReceiptSet, authoritative: ReceiptSet) -> ParityReport:
        if type(predicted) is not ReceiptSet or type(authoritative) is not ReceiptSet:
            raise ValueError("invalid parity inputs")
        if len(predicted.events) < len(authoritative.events):
            return ParityReport(
                "missing_authoritative_evidence", False, False,
                ("missing_receipt_transition",),
            )
        if len(predicted.events) > len(authoritative.events):
            return ParityReport(
                "unexpected_authoritative_transition", False, False,
                ("extra_receipt_transition",),
            )
        left = tuple(_semantic(event) for event in predicted.events)
        right = tuple(_semantic(event) for event in authoritative.events)
        if left == right:
            return ParityReport("match", True, True)
        left_profile = _receipt_host_profile(predicted.events)
        right_profile = _receipt_host_profile(authoritative.events)
        if left_profile is None or right_profile is None or left_profile == right_profile:
            return ParityReport("unsafe_to_promote", False, False, ("semantic_transition_difference",))
        normalized_left = tuple(_semantic(event, normalize_host=True) for event in predicted.events)
        normalized_right = tuple(_semantic(event, normalize_host=True) for event in authoritative.events)
        if normalized_left != normalized_right:
            return ParityReport("unsafe_to_promote", False, False, ("semantic_transition_difference",))
        return ParityReport("explained_host_difference", True, False, ("coherent_named_host_profile",))


def _receipt_host_profile(events: Tuple[WorkflowEvent, ...]):
    hosts = {event.payload.get("host") for event in events}
    mechanisms = {event.payload.get("mechanism") for event in events}
    providers = {
        event.payload.get("provider") for event in events
        if event.payload.get("provider") is not None
    }
    if len(hosts) != 1 or len(mechanisms) != 1 or len(providers) != 1:
        return None
    profile = (next(iter(hosts)), next(iter(mechanisms)), next(iter(providers)))
    return profile if profile in KNOWN_HOST_PROFILES else None
