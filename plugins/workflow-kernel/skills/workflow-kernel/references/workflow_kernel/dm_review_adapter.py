"""Pure translation of authoritative dm-review requests and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Tuple

from ._translation import (
    EXECUTION_MODES, RunSpec, dual_key, required_text, translate_receipts,
)
from .model import HostCapabilities, NodeSpec, WorkflowClass
from .schema import WorkflowEvent


REVIEW_STAGES = frozenset({
    "review_request", "review_dispatch", "finding", "coverage_matrix",
    "convergence", "fix_attempt", "browser_verification",
    "repository_cleanup", "review_terminal",
    "finding_contribution", "attempt_usage", "browser_recovery",
})
REVIEW_MODES = frozenset({"full", "quick", "visual", "loop"})


@dataclass(frozen=True)
class ReviewRequest:
    run_id: str
    required_lanes: Tuple[str, ...]
    mode: str = "full"
    workflow_class: WorkflowClass = WorkflowClass.FEATURE
    execution_mode: str = "generic"
    workflow_class_defaulted: bool = False

    def __post_init__(self) -> None:
        required_text(self.run_id, "run id")
        if not isinstance(self.required_lanes, (list, tuple)) or any(
            type(value) is not str or not value for value in self.required_lanes
        ) or len(self.required_lanes) != len(set(self.required_lanes)):
            raise ValueError("invalid review lanes")
        if self.mode not in REVIEW_MODES:
            raise ValueError("invalid review mode")
        if self.execution_mode not in EXECUTION_MODES:
            raise ValueError("invalid execution mode")
        if type(self.workflow_class_defaulted) is not bool:
            raise ValueError("invalid workflow class provenance")
        try:
            workflow_class = WorkflowClass(self.workflow_class)
        except (TypeError, ValueError):
            raise ValueError("invalid workflow class") from None
        object.__setattr__(self, "required_lanes", tuple(self.required_lanes))
        object.__setattr__(self, "workflow_class", workflow_class)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ReviewRequest":
        if type(value) is not dict:
            raise ValueError("review request must be an object")
        raw_class = dual_key(value, "workflow_class", "workflowClass", default=None)
        # `requested_lanes` is the documented request key (caller intent);
        # `required_lanes` is the internal derived-execution field. The
        # requested (input) -> required (derived) translation happens here.
        raw_lanes = value.get("required_lanes", value.get("requested_lanes", ()))
        if type(raw_lanes) not in {list, tuple}:
            raise ValueError("invalid review lanes")
        raw_defaulted = dual_key(
            value, "workflow_class_defaulted", "workflowClassDefaulted",
            default=None,
        )
        if raw_defaulted is None:
            defaulted = raw_class is None
        else:
            # Preserve explicit provenance on round-trip: a serialized legacy
            # request carrying workflow_class + workflow_class_defaulted=true
            # must forward unchanged. Derive only when neither form exists.
            if type(raw_defaulted) is not bool:
                raise ValueError("invalid workflow class provenance")
            if raw_class is None and raw_defaulted is False:
                raise ValueError("invalid workflow class provenance")
            defaulted = raw_defaulted
        return cls(
            dual_key(value, "run_id", "runId", default=None),
            tuple(raw_lanes),
            value.get("mode", "full"),
            "feature" if raw_class is None else raw_class,
            dual_key(value, "execution_mode", "executionMode", default="generic"),
            defaulted,
        )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id, "required_lanes": list(self.required_lanes),
            "mode": self.mode, "workflow_class": self.workflow_class.value,
            "execution_mode": self.execution_mode,
            "workflow_class_defaulted": self.workflow_class_defaulted,
        }


def translate_review(request: ReviewRequest, profile: HostCapabilities) -> RunSpec:
    if type(request) is not ReviewRequest or type(profile) is not HostCapabilities:
        raise ValueError("invalid review request or host profile")
    lane_nodes = tuple(
        NodeSpec("review-lane-" + lane, ("review-request",))
        for lane in request.required_lanes
    )
    convergence_dependencies = tuple(node.node_id for node in lane_nodes) or ("review-request",)
    review_nodes = (NodeSpec("review-request"),) + lane_nodes + (
        NodeSpec("review-convergence", convergence_dependencies),
    )
    if "visual" in request.required_lanes:
        review_nodes += (NodeSpec("review-browser-verification", ("review-convergence",)),)
        cleanup_dependency = "review-browser-verification"
    else:
        cleanup_dependency = "review-convergence"
    review_nodes += (
        NodeSpec("review-cleanup", (cleanup_dependency,)),
        NodeSpec("review-terminal", ("review-cleanup",)),
    )
    return RunSpec(
        request.run_id, request.workflow_class, request.workflow_class_defaulted,
        request.execution_mode, profile.host_name, review_nodes,
        required_lanes=request.required_lanes,
        review_mode=request.mode,
    )


def translate_review_receipts(
    receipts: Iterable[Mapping[str, object]],
) -> Tuple[WorkflowEvent, ...]:
    return translate_receipts(receipts, REVIEW_STAGES)
