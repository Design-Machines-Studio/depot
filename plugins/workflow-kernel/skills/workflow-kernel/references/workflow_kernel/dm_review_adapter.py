"""Pure translation of authoritative dm-review requests and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Tuple

from .adapters.base import HostCapabilities, WorkflowClass, WorkflowContext
from .pipeline_adapter import RunSpec, _required_text, _translate_receipts
from .schema import WorkflowEvent
from .workflows import WorkflowTemplates


REVIEW_STAGES = frozenset({
    "review_request", "review_dispatch", "finding", "coverage_matrix",
    "convergence", "fix_attempt", "browser_verification",
    "repository_cleanup", "review_terminal",
})
REVIEW_MODES = frozenset({"full", "quick", "visual", "loop"})


@dataclass(frozen=True)
class ReviewRequest:
    run_id: str
    required_lanes: Tuple[str, ...]
    mode: str = "full"
    workflow_class: WorkflowClass = WorkflowClass.FEATURE

    def __post_init__(self) -> None:
        _required_text(self.run_id, "run id")
        if not isinstance(self.required_lanes, (list, tuple)) or any(
            type(value) is not str or not value for value in self.required_lanes
        ) or len(self.required_lanes) != len(set(self.required_lanes)):
            raise ValueError("invalid review lanes")
        if self.mode not in REVIEW_MODES:
            raise ValueError("invalid review mode")
        try:
            workflow_class = WorkflowClass(self.workflow_class)
        except (TypeError, ValueError):
            raise ValueError("invalid workflow class") from None
        object.__setattr__(self, "required_lanes", tuple(self.required_lanes))
        object.__setattr__(self, "workflow_class", workflow_class)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ReviewRequest":
        if not isinstance(value, Mapping):
            raise ValueError("review request must be an object")
        return cls(
            value.get("run_id", value.get("runId")),
            tuple(value.get("required_lanes", value.get("requested_lanes", ()))),
            value.get("mode", "full"),
            value.get("workflow_class", value.get("workflowClass", "feature")),
        )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id, "required_lanes": list(self.required_lanes),
            "mode": self.mode, "workflow_class": self.workflow_class.value,
        }


def translate_review(request: ReviewRequest, profile: HostCapabilities) -> RunSpec:
    if type(request) is not ReviewRequest or type(profile) is not HostCapabilities:
        raise ValueError("invalid review request or host profile")
    nodes = WorkflowTemplates().expand(request.workflow_class, WorkflowContext())
    return RunSpec(
        request.run_id, request.workflow_class, False, "generic",
        profile.host_name, nodes, required_lanes=request.required_lanes,
        review_mode=request.mode,
    )


def translate_review_receipts(
    receipts: Iterable[Mapping[str, object]],
) -> Tuple[WorkflowEvent, ...]:
    return _translate_receipts(receipts, REVIEW_STAGES)
