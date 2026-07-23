"""Pure translation of authoritative dm-review requests and receipts."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Tuple

from ._translation import (
    EXECUTION_MODES, RunSpec, canonical_finding_identity, dual_key,
    normalize_decision_profile, required_text, safe_reference,
    translate_receipts,
)
from .model import HostCapabilities, NodeSpec, WorkflowClass
from .redaction import contains_high_confidence_secret, normalize_durable_string
from .schema import WorkflowEvent


REVIEW_STAGES = frozenset({
    "review_request", "review_dispatch", "finding", "coverage_matrix",
    "convergence", "fix_attempt", "browser_verification",
    "repository_cleanup", "review_terminal",
    "finding_contribution", "finding_contribution_coverage",
    "attempt_usage", "browser_recovery",
})
REVIEW_MODES = frozenset({"full", "quick", "visual", "loop"})
_CONTRIBUTION_DECISION_FIELDS = frozenset({
    "source_finding_id", "finding_path", "finding_anchor",
    "finding_category", "finding_root_cause", "finding_disposition",
    "agreement", "decision_reason_code", "reviewer", "lane",
    "requested_provider", "attempted_provider", "implemented_by",
    "provider", "model", "source_severity", "evidence_ref", "attempt",
    "occurred_at",
})
_RAW_FINDING_FIELDS = frozenset({
    "source_finding_id", "reviewer", "lane", "source_severity",
    "evidence_ref", "finding_path", "finding_anchor", "finding_category",
    "finding_root_cause",
})
_LANE_FIELDS = frozenset({
    "reviewer", "lane", "requested_provider", "attempted_provider",
    "implemented_by", "provider", "model", "evidence_refs",
    "raw_output_ref", "raw_output_digest", "finding_count",
})
_RAW_LANE_OUTPUT_FIELDS = frozenset({"reviewer", "lane", "findings"})
_DIGEST = "sha256:"


def _document_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return _DIGEST + hashlib.sha256(encoded).hexdigest()


def _require_secret_safe(value: object) -> None:
    if type(value) is str:
        try:
            normalized = normalize_durable_string(value)
        except (TypeError, ValueError):
            raise ValueError("unsafe contribution input") from None
        if normalized != value or contains_high_confidence_secret(value):
            raise ValueError("unsafe contribution input")
        return
    if type(value) is list:
        for item in value:
            _require_secret_safe(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            _require_secret_safe(key)
            _require_secret_safe(item)
        return
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is float and math.isfinite(value):
        return
    raise ValueError("unsafe contribution input")


def require_secret_safe_contribution_inputs(*documents: object) -> None:
    """Reject any durable secret or credential-bearing URI before hashing."""
    for document in documents:
        _require_secret_safe(document)


@dataclass(frozen=True)
class ReviewRequest:
    run_id: str
    required_lanes: Tuple[str, ...]
    mode: str = "full"
    workflow_class: WorkflowClass = WorkflowClass.FEATURE
    execution_mode: str = "generic"
    workflow_class_defaulted: bool = False
    decision_profile: Optional[Mapping[str, str]] = None
    decision_profile_defaulted: bool = True

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
        if type(self.decision_profile_defaulted) is not bool:
            raise ValueError("invalid decision profile provenance")
        if self.decision_profile is None:
            if not self.decision_profile_defaulted:
                raise ValueError("invalid decision profile provenance")
        else:
            profile = normalize_decision_profile(self.decision_profile)
            if self.decision_profile_defaulted:
                raise ValueError("invalid decision profile provenance")
            object.__setattr__(self, "decision_profile", profile)
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
        raw_profile = dual_key(
            value, "decision_profile", "decisionProfile", default=None,
        )
        raw_profile_defaulted = dual_key(
            value, "decision_profile_defaulted", "decisionProfileDefaulted",
            default=None,
        )
        if raw_profile_defaulted is None:
            profile_defaulted = raw_profile is None
        else:
            if type(raw_profile_defaulted) is not bool:
                raise ValueError("invalid decision profile provenance")
            if raw_profile is None and raw_profile_defaulted is False:
                raise ValueError("invalid decision profile provenance")
            profile_defaulted = raw_profile_defaulted
        return cls(
            dual_key(value, "run_id", "runId", default=None),
            tuple(raw_lanes),
            value.get("mode", "full"),
            "feature" if raw_class is None else raw_class,
            dual_key(value, "execution_mode", "executionMode", default="generic"),
            defaulted,
            raw_profile,
            profile_defaulted,
        )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id, "required_lanes": list(self.required_lanes),
            "mode": self.mode, "workflow_class": self.workflow_class.value,
            "execution_mode": self.execution_mode,
            "workflow_class_defaulted": self.workflow_class_defaulted,
            "decision_profile": (
                None if self.decision_profile is None
                else dict(self.decision_profile)
            ),
            "decision_profile_defaulted": self.decision_profile_defaulted,
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
        decision_profile=request.decision_profile,
        decision_profile_defaulted=request.decision_profile_defaulted,
    )


def translate_review_receipts(
    receipts: Iterable[Mapping[str, object]],
) -> Tuple[WorkflowEvent, ...]:
    return translate_receipts(receipts, REVIEW_STAGES)


def export_finding_contributions(
    request: ReviewRequest,
    decisions_document: Mapping[str, object],
    raw_findings_document: Mapping[str, object],
    lane_receipts_document: Mapping[str, object],
    raw_lane_outputs_document: Mapping[str, object],
    existing_receipts: Iterable[Mapping[str, object]],
    input_references: Mapping[str, str],
    sealed_lane_outputs: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Tuple[dict, ...]:
    """Append one validated contribution receipt per raw source finding.

    The exporter owns sequence assignment and canonical identity derivation.
    A caller cannot omit a source decision, choose a digest, or relabel the
    literal execution provenance after synthesis.
    """
    if (
        type(request) is not ReviewRequest or type(decisions_document) is not dict
        or type(raw_findings_document) is not dict
        or type(lane_receipts_document) is not dict
        or type(raw_lane_outputs_document) is not dict
        or type(input_references) is not dict
        or set(input_references) != {
            "decisions", "raw_findings", "lane_receipts", "raw_lane_outputs",
        }
        or (sealed_lane_outputs is not None and type(sealed_lane_outputs) is not dict)
    ):
        raise ValueError("invalid contribution export")
    require_secret_safe_contribution_inputs(*(
        decisions_document, raw_findings_document, lane_receipts_document,
        raw_lane_outputs_document,
    ))
    references = {
        key: safe_reference(value) for key, value in input_references.items()
    }
    document_digests = {
        "decisions": _document_digest(decisions_document),
        "raw_findings": _document_digest(raw_findings_document),
        "lane_receipts": _document_digest(lane_receipts_document),
        "raw_lane_outputs": _document_digest(raw_lane_outputs_document),
    }
    reference_roles = {
        "decisions": "synthesis-decisions",
        "raw_findings": "raw-finding-inventory",
        "lane_receipts": "lane-receipts",
        "raw_lane_outputs": "raw-lane-outputs",
    }
    for key, reference in references.items():
        expected_name = (
            reference_roles[key] + "-sha256-"
            + document_digests[key].removeprefix("sha256:") + ".json"
        )
        if reference != "contribution-inputs/" + expected_name:
            raise ValueError("unsealed contribution input")
    if set(decisions_document) != {
        "schema_version", "artifact_role", "run_id", "source_finding_count",
        "occurred_at", "decisions",
    } or (
        decisions_document["schema_version"] != 1
        or decisions_document["artifact_role"] != "synthesis_decisions"
        or decisions_document["run_id"] != request.run_id
    ):
        raise ValueError("invalid contribution export")
    if set(raw_findings_document) != {
        "schema_version", "artifact_role", "run_id", "findings",
    } or (
        raw_findings_document["schema_version"] != 1
        or raw_findings_document["artifact_role"] != "raw_finding_inventory"
        or raw_findings_document["run_id"] != request.run_id
        or type(raw_findings_document["findings"]) is not list
    ):
        raise ValueError("invalid raw finding inventory")
    if set(lane_receipts_document) != {
        "schema_version", "artifact_role", "run_id", "lanes",
    } or (
        lane_receipts_document["schema_version"] != 1
        or lane_receipts_document["artifact_role"] != "review_lane_receipts"
        or lane_receipts_document["run_id"] != request.run_id
        or type(lane_receipts_document["lanes"]) is not list
    ):
        raise ValueError("invalid review lane receipts")
    if set(raw_lane_outputs_document) != {
        "schema_version", "artifact_role", "run_id", "outputs",
    } or (
        raw_lane_outputs_document["schema_version"] != 1
        or raw_lane_outputs_document["artifact_role"] != "review_lane_raw_outputs"
        or raw_lane_outputs_document["run_id"] != request.run_id
        or type(raw_lane_outputs_document["outputs"]) is not list
    ):
        raise ValueError("invalid raw lane outputs")
    expected = decisions_document["source_finding_count"]
    required_text(decisions_document["occurred_at"], "occurred at")
    decisions = decisions_document["decisions"]
    raw_findings = raw_findings_document["findings"]
    if (
        type(expected) is not int or expected < 0 or type(decisions) is not list
        or len(decisions) != expected or len(raw_findings) != expected
    ):
        raise ValueError("finding contribution cardinality mismatch")
    parsed_outputs = {}
    output_findings = {}
    for output in raw_lane_outputs_document["outputs"]:
        if type(output) is not dict or set(output) != _RAW_LANE_OUTPUT_FIELDS:
            raise ValueError("invalid raw lane output")
        required_text(output["reviewer"], "reviewer")
        required_text(output["lane"], "lane")
        if type(output["findings"]) is not list:
            raise ValueError("invalid raw lane output")
        output = {
            "reviewer": output["reviewer"], "lane": output["lane"],
            "findings": [dict(value) if type(value) is dict else value
                         for value in output["findings"]],
        }
        key = (output["reviewer"], output["lane"])
        if key in parsed_outputs or output["lane"] in {
            value["lane"] for value in parsed_outputs.values()
        }:
            raise ValueError("duplicate raw lane output")
        digest = _document_digest(output)
        reference = (
            "contribution-inputs/raw-lane-output-sha256-"
            + digest.removeprefix("sha256:") + ".json"
        )
        if sealed_lane_outputs is not None:
            sealed = sealed_lane_outputs.get(reference)
            if type(sealed) is not dict or sealed != output:
                raise ValueError("raw lane output seal mismatch")
        parsed_outputs[key] = output
        seen = set()
        for finding in output["findings"]:
            if type(finding) is not dict or set(finding) != _RAW_FINDING_FIELDS:
                raise ValueError("invalid raw lane output finding")
            for field in _RAW_FINDING_FIELDS:
                required_text(finding[field], field.replace("_", " "))
            finding["evidence_ref"] = safe_reference(finding["evidence_ref"])
            if (
                finding["reviewer"] != output["reviewer"]
                or finding["lane"] != output["lane"]
                or finding["source_finding_id"] in seen
            ):
                raise ValueError("invalid raw lane output finding")
            seen.add(finding["source_finding_id"])
            if finding["source_finding_id"] in output_findings:
                raise ValueError("duplicate raw source finding")
            output_findings[finding["source_finding_id"]] = finding
        output["raw_output_digest"] = digest
        output["raw_output_ref"] = reference

    if sealed_lane_outputs is not None and set(sealed_lane_outputs) != {
        output["raw_output_ref"] for output in parsed_outputs.values()
    }:
        raise ValueError("raw lane output seal mismatch")

    lanes = {}
    seen_lane_names = set()
    for lane_receipt in lane_receipts_document["lanes"]:
        if type(lane_receipt) is not dict or set(lane_receipt) != _LANE_FIELDS:
            raise ValueError("invalid review lane receipt")
        for field in _LANE_FIELDS - {
            "evidence_refs", "finding_count", "raw_output_digest",
        }:
            required_text(lane_receipt[field], field.replace("_", " "))
        if (
            type(lane_receipt["finding_count"]) is not int
            or lane_receipt["finding_count"] < 0
            or not isinstance(lane_receipt["raw_output_digest"], str)
            or not lane_receipt["raw_output_digest"].startswith("sha256:")
        ):
            raise ValueError("invalid review lane receipt")
        evidence_refs = lane_receipt["evidence_refs"]
        if (
            type(evidence_refs) is not list or not evidence_refs
            or len(evidence_refs) != len(set(evidence_refs))
        ):
            raise ValueError("invalid review lane receipt")
        normalized_refs = tuple(safe_reference(value) for value in evidence_refs)
        key = (lane_receipt["reviewer"], lane_receipt["lane"])
        if key in lanes or lane_receipt["lane"] in seen_lane_names:
            raise ValueError("duplicate review lane receipt")
        seen_lane_names.add(lane_receipt["lane"])
        output = parsed_outputs.get(key)
        if (
            output is None
            or lane_receipt["raw_output_ref"] != output["raw_output_ref"]
            or lane_receipt["raw_output_digest"] != output["raw_output_digest"]
            or lane_receipt["finding_count"] != len(output["findings"])
        ):
            raise ValueError("review lane raw output mismatch")
        lanes[key] = ({**lane_receipt, "evidence_refs": normalized_refs})
    if (
        len(lanes) != len(request.required_lanes)
        or seen_lane_names != set(request.required_lanes)
        or set(parsed_outputs) != set(lanes)
    ):
        raise ValueError("review lane coverage mismatch")
    raw_by_source = {}
    for raw in raw_findings:
        if type(raw) is not dict or set(raw) != _RAW_FINDING_FIELDS:
            raise ValueError("invalid raw finding inventory")
        for field in _RAW_FINDING_FIELDS:
            required_text(raw[field], field.replace("_", " "))
        raw = dict(raw)
        raw["evidence_ref"] = safe_reference(raw["evidence_ref"])
        source = raw["source_finding_id"]
        if source in raw_by_source:
            raise ValueError("duplicate raw source finding")
        lane = lanes.get((raw["reviewer"], raw["lane"]))
        if lane is None or raw["evidence_ref"] not in lane["evidence_refs"]:
            raise ValueError("raw finding evidence is not lane-bound")
        raw_by_source[source] = raw
    if raw_by_source != output_findings:
        raise ValueError("raw lane output union mismatch")
    try:
        receipts = [dict(value) for value in existing_receipts]
    except Exception:
        raise ValueError("invalid contribution export") from None
    # Existing receipts must already be replayable before appending to them.
    translate_review_receipts(receipts)
    seen_sources = set()
    for decision in decisions:
        if type(decision) is not dict or set(decision) != _CONTRIBUTION_DECISION_FIELDS:
            raise ValueError("invalid contribution decision")
        source_id = decision["source_finding_id"]
        if source_id in seen_sources:
            raise ValueError("finding contribution cardinality mismatch")
        seen_sources.add(source_id)
        raw = raw_by_source.get(source_id)
        if raw is None:
            raise ValueError("decision has no raw source finding")
        lane = lanes.get((raw["reviewer"], raw["lane"]))
        expected_source = {
            **raw,
            **{
                field: lane[field] for field in _LANE_FIELDS
                if field in {
                    "reviewer", "lane", "requested_provider",
                    "attempted_provider", "implemented_by", "provider", "model",
                }
            },
        }
        actual_source = {
            field: decision[field] for field in expected_source
        }
        actual_source["evidence_ref"] = safe_reference(
            actual_source["evidence_ref"]
        )
        if actual_source != expected_source:
            raise ValueError("finding decision source provenance mismatch")
        canonical_id, normalized = canonical_finding_identity(
            decision["finding_path"], decision["finding_anchor"],
            decision["finding_category"], decision["finding_root_cause"],
        )
        receipt = {
            "run_id": request.run_id,
            "sequence": len(receipts),
            "stage": "finding_contribution",
            "status": "recorded",
            "node_id": "review-convergence",
            "authoritative_receipt": references["decisions"],
            "workflow_class": request.workflow_class.value,
            "workflow_class_defaulted": request.workflow_class_defaulted,
            "execution_mode": request.execution_mode,
            "decision_profile_defaulted": request.decision_profile_defaulted,
            "canonical_finding_id": canonical_id,
            **decision,
            **{"finding_" + key: value for key, value in normalized.items()},
        }
        if request.decision_profile is not None:
            receipt["decision_profile"] = dict(request.decision_profile)
        receipts.append(receipt)
    if seen_sources != set(raw_by_source):
        raise ValueError("finding contribution cardinality mismatch")
    digests = {
        "synthesis_decisions_digest": document_digests["decisions"],
        "raw_finding_inventory_digest": document_digests["raw_findings"],
        "lane_receipts_digest": document_digests["lane_receipts"],
        "raw_lane_outputs_digest": document_digests["raw_lane_outputs"],
    }
    coverage = {
        "run_id": request.run_id, "sequence": len(receipts),
        "stage": "finding_contribution_coverage", "status": "complete",
        "node_id": "review-convergence",
        "authoritative_receipt": references["decisions"],
        "workflow_class": request.workflow_class.value,
        "workflow_class_defaulted": request.workflow_class_defaulted,
        "execution_mode": request.execution_mode,
        "decision_profile_defaulted": request.decision_profile_defaulted,
        "raw_finding_count": expected, "decision_count": len(decisions),
        "contribution_count": len(decisions), "coverage_complete": True,
        "synthesis_decisions_ref": references["decisions"],
        "raw_finding_inventory_ref": references["raw_findings"],
        "lane_receipts_ref": references["lane_receipts"],
        "raw_lane_outputs_ref": references["raw_lane_outputs"],
        **digests,
        "occurred_at": decisions_document["occurred_at"],
    }
    if request.decision_profile is not None:
        coverage["decision_profile"] = dict(request.decision_profile)
    receipts.append(coverage)
    # Validate the complete result, including context continuity and exactly
    # one contribution decision for every artifact-scoped source ID.
    translate_review_receipts(receipts)
    return tuple(receipts)


def require_complete_contribution_coverage(
    receipts: Iterable[Mapping[str, object]],
) -> None:
    """Fail closed unless one coverage receipt accounts for every contribution."""
    values = tuple(receipts)
    coverage_positions = [
        index for index, value in enumerate(values)
        if type(value) is dict
        and value.get("stage") == "finding_contribution_coverage"
    ]
    if len(coverage_positions) != 1:
        raise ValueError("missing finding contribution coverage")
    position = coverage_positions[0]
    coverage = values[position]
    contributions = [
        value for value in values[:position]
        if type(value) is dict and value.get("stage") == "finding_contribution"
    ]
    if any(
        type(value) is dict and value.get("stage") == "finding_contribution"
        for value in values[position + 1:]
    ):
        raise ValueError("incomplete finding contribution coverage")
    count = len(contributions)
    if (
        coverage.get("status") != "complete"
        or coverage.get("coverage_complete") is not True
        or coverage.get("raw_finding_count") != count
        or coverage.get("decision_count") != count
        or coverage.get("contribution_count") != count
    ):
        raise ValueError("incomplete finding contribution coverage")


def require_browser_recovery_profile_binding(
    receipts: Iterable[Mapping[str, object]], contract: Mapping[str, object],
    profile: object,
) -> None:
    """Bind every browser recovery proof to the active contract profile."""
    from .behavioral_contract import verification_profile_digest
    from .browser_evidence import BrowserRecoveryReceipt
    from .browser_target import digest_target_route
    from .verification import VerificationProfile

    if type(contract) is not dict or type(profile) is not VerificationProfile:
        raise ValueError("invalid browser recovery contract binding")
    if (
        contract.get("verification_profile_id") != profile.profile_id
        or contract.get("verification_profile_digest")
        != verification_profile_digest(profile.to_dict())
        or type(contract.get("browser_case_ids")) is not list
    ):
        raise ValueError("invalid browser recovery contract binding")
    contract_cases = tuple(contract["browser_case_ids"])
    if len(contract_cases) != len(set(contract_cases)):
        raise ValueError("invalid browser recovery contract binding")
    cases = {case.case_id: case for case in profile.cases}
    required_cases = {case.case_id for case in profile.cases if case.required}
    if set(contract_cases) != required_cases:
        raise ValueError("invalid browser recovery contract binding")
    for receipt in receipts:
        if type(receipt) is not dict or receipt.get("stage") != "browser_recovery":
            continue
        values = receipt.get("recovery_receipts")
        if type(values) is not list or not values:
            raise ValueError("invalid browser recovery contract binding")
        for raw in values:
            recovery = BrowserRecoveryReceipt.from_dict(raw)
            case = cases.get(recovery.case_id)
            if (
                recovery.case_id not in contract_cases or case is None
                or recovery.verification_profile_id != profile.profile_id
                or recovery.configured_engines != profile.configured_engines
                or recovery.target_origin_digest != profile.target_origin_digest
                or recovery.requested_engine != case.browser_engine
                or recovery.viewport != case.viewport
                or recovery.target_route_digest != digest_target_route(case.route)
                or recovery.declared_route_digest != case.declared_route_digest
            ):
                raise ValueError("invalid browser recovery contract binding")
