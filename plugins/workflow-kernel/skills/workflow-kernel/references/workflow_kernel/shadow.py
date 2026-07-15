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
}


@dataclass(frozen=True)
class ReceiptSet:
    events: Tuple[WorkflowEvent, ...]

    @classmethod
    def from_events(cls, events: Iterable[WorkflowEvent]) -> "ReceiptSet":
        values = tuple(events)
        if any(type(event) is not WorkflowEvent for event in values):
            raise ValueError("invalid receipt events")
        for event in values:
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


def _semantic(event: WorkflowEvent) -> tuple:
    payload = event.payload
    return (
        event.node_id, payload.get("stage"), payload.get("status"),
        payload.get("workflow_class"), bool(payload.get("evidence")),
        payload.get("first_pass"), payload.get("persona_expected"),
        payload.get("persona_passed"), payload.get("cleanup_removed"),
        payload.get("cleanup_blocked"),
    )


def _mechanism(event: WorkflowEvent):
    value = event.payload.get("mechanism")
    return KNOWN_MECHANISMS.get(value, value)


class ShadowComparator:
    """Compares facts only; it cannot select nodes, gates, policy, or commands."""

    def compare(self, predicted: RunState, authoritative: ReceiptSet) -> ParityReport:
        if type(predicted) is not RunState or type(authoritative) is not ReceiptSet:
            raise ValueError("invalid parity inputs")
        required = tuple(
            event.payload["authoritative_receipt"] for event in authoritative.events
        )
        present = set(predicted.evidence)
        missing = tuple(reference for reference in required if reference not in present)
        extra = tuple(reference for reference in predicted.evidence if reference not in set(required))
        if missing:
            return ParityReport("kernel_prediction_gap", False, False, missing)
        if extra:
            return ParityReport("unexpected_authoritative_transition", False, False, extra)
        return ParityReport("match", True, True)

    def compare_receipt_sets(self, predicted: ReceiptSet, authoritative: ReceiptSet) -> ParityReport:
        if type(predicted) is not ReceiptSet or type(authoritative) is not ReceiptSet:
            raise ValueError("invalid parity inputs")
        left = tuple(_semantic(event) for event in predicted.events)
        right = tuple(_semantic(event) for event in authoritative.events)
        if left != right:
            return ParityReport("unsafe_to_promote", False, False, ("semantic_transition_difference",))
        left_mechanisms = tuple(_mechanism(event) for event in predicted.events)
        right_mechanisms = tuple(_mechanism(event) for event in authoritative.events)
        raw_left = tuple(event.payload.get("mechanism") for event in predicted.events)
        raw_right = tuple(event.payload.get("mechanism") for event in authoritative.events)
        if raw_left != raw_right and left_mechanisms == right_mechanisms:
            return ParityReport("explained_host_difference", True, False, ("named_mechanism_compatibility",))
        return ParityReport("match", True, True)
