"""Deterministic review recovery. Retained inputs are trusted host evidence.

No execution, model dispatch, historical working-tree inference or ledger lives
here. The closeout producer owns sealing, locking, coverage and retention.
"""

from __future__ import annotations

import re

from .dm_review_adapter import _LANE_FIELDS, required_text
from .verification_contract import digest

# The current dm-review deterministic slots. Judgment IDs cannot opt in by
# changing a receipt's basis or adding a "no judgment" limitation.
HOST_VERIFICATION_LANES = frozenset({"go-build-verifier", "tests/build"})


def public_completion(dispatch, output_ref):
    """Project only facts reported by a coherent published private dispatch."""
    if (type(dispatch) is not dict or dispatch.get("schemaVersion") != 1
            or dispatch.get("publication") != {"output": "published"}
            or dispatch.get("transportStub") is not False
            or re.fullmatch(r"dispatch-[a-f0-9]{24}", dispatch.get("receiptId", "")) is None
            or dispatch.get("participantId") != "reviewer-" + dispatch["receiptId"][9:17]):
        raise ValueError("invalid dispatch")
    requested, served = dispatch.get("requested"), dispatch.get("served")
    attempts = dispatch.get("attempts")
    if type(requested) is not dict or type(served) is not dict or type(attempts) is not list:
        raise ValueError("invalid dispatch")
    successful = [row for row in attempts if type(row) is dict and row.get("outcome") == "served"]
    if len(successful) != 1 or attempts[-1] != successful[0]:
        raise ValueError("contradictory dispatch")
    attempt = successful[0]
    for reported, expected in ((attempt.get("requestedEffort"), requested.get("effort")),
                               (attempt.get("normalizedEffort"), dispatch.get("normalizedEffort"))):
        if reported is not None and expected is not None and reported != expected:
            raise ValueError("contradictory dispatch effort")
    for key in ("model", "provider", "transport"):
        required_text(served.get(key), key)
        if served[key] == "not_reported" or served[key] != successful[0].get(key):
            raise ValueError("contradictory dispatch")
    from ._translation import reviewer_family_from_model
    if served.get("family") != reviewer_family_from_model(served["model"]):
        raise ValueError("contradictory dispatch family")
    transmission = dispatch.get("effortTransmission")
    if transmission is None:
        transmitted, status = None, "unavailable"
    elif type(transmission) is dict:
        transmitted, status = dispatch.get("transmittedEffort"), transmission.get("status")
        if status != successful[0].get("effortStatus") or transmitted != successful[0].get("transmittedEffort"):
            raise ValueError("contradictory dispatch effort")
        if dispatch.get("effectiveEffort") != transmitted:
            raise ValueError("contradictory dispatch effort")
    else:
        raise ValueError("invalid dispatch effort")
    independence = dispatch.get("familyIndependence")
    if (type(independence) is not dict or independence.get("passed") is not True
            or type(independence.get("excludedFamilies")) is not list
            or type(requested.get("humanAuthored")) is not bool
            or independence.get("humanAuthored") != requested["humanAuthored"]
            or type(dispatch.get("fallback")) is not bool):
        raise ValueError("invalid dispatch independence")
    if served["family"] in independence["excludedFamilies"]:
        raise ValueError("contradictory dispatch independence")
    if "required" in independence and "independenceReceiptIds" in requested:
        if (type(requested["independenceReceiptIds"]) is not list
                or type(independence["required"]) is not bool
                or independence["required"] != bool(requested["independenceReceiptIds"] or requested["humanAuthored"])):
            raise ValueError("contradictory dispatch independence")
    if type(requested.get("capabilities")) is not list or not requested["capabilities"]:
        raise ValueError("invalid dispatch capabilities")
    return {
        "role": required_text(requested.get("role"), "role"),
        "capabilities": requested["capabilities"],
        "requestedEffort": required_text(requested.get("effort"), "effort"),
        "normalizedEffort": dispatch.get("normalizedEffort"),
        "effectiveEffort": transmitted, "transmittedEffort": transmitted,
        "effortStatus": status, "participantId": dispatch["participantId"],
        "disposition": "completed", "fallback": dispatch["fallback"],
        "evidenceSource": required_text(dispatch.get("probeSource"), "probe source"),
        "transportStub": False,
        "familyIndependence": {"humanAuthored": requested["humanAuthored"],
                               "excludedFamilyCount": len(independence["excludedFamilies"])},
        "output": output_ref,
    }


def host_references(envelope):
    if (type(envelope) is not dict or set(envelope) != {"schema_version", "lane", "source", "source_snapshots", "commands", "artifacts", "limitations"}
            or envelope["schema_version"] != 1 or type(envelope["commands"]) is not list
            or not envelope["commands"] or len(envelope["commands"]) > 64
            or type(envelope["artifacts"]) is not dict or type(envelope["limitations"]) is not list):
        raise ValueError("invalid host evidence")
    source = envelope["source"]
    if type(source) is not dict or set(source) != {"repository", "head", "paths"}:
        raise ValueError("invalid host source")
    refs = set(envelope["artifacts"])
    if type(envelope["source_snapshots"]) is not dict or not envelope["source_snapshots"]:
        raise ValueError("missing host source evidence")
    refs.update(envelope["source_snapshots"].values())
    for row in envelope["commands"]:
        if type(row) is not dict or set(row) != {"receipt_ref", "plan_ref", "lane_id"}:
            raise ValueError("invalid host command")
        refs.add(row["receipt_ref"])
        if row["plan_ref"] is not None:
            refs.add(row["plan_ref"])
    return refs


def host_completion(envelope, value, load_json, load_bytes, snapshot):
    """Accept actual execution results only over byte-equal declared source."""
    from .verification_contract import byte_digest
    host_references(envelope)
    source = envelope["source"]
    if (value["lane"] not in HOST_VERIFICATION_LANES
            or envelope["lane"] != value["lane"] or value["reviewer"] != "host-verification"
            or value["inspected"]["basis"] != "host_evidence"
            or value["result"]["findings"] or value["source"]["worktree_ref"] is not None
            or source["repository"] != value["source"]["repository"]
            or source["head"] != value["source"]["head"]
            or source["paths"] != value["requested"]["paths"]
            or envelope["limitations"] != value["inspected"]["limitations"]):
        raise ValueError("host scope mismatch")
    target = snapshot(source["head"])
    for ref, expected in envelope["artifacts"].items():
        if byte_digest(load_bytes(ref)) != expected:
            raise ValueError("host artifact altered")
    for command in envelope["commands"]:
        receipt = load_json(command["receipt_ref"])
        if command["plan_ref"] is None:
            fields = {"schemaVersion", "lane", "commandArgv", "exitStatus", "result", "stdoutTail", "stderrTail",
                      "sourceRepository", "sourceHead", "sourcePaths"}
            if type(receipt) is not dict or set(receipt) != fields or receipt["schemaVersion"] != 1:
                raise ValueError("invalid command receipt")
            if (type(receipt["sourcePaths"]) is not list or receipt["lane"] != command["lane_id"] or receipt["sourceRepository"] != source["repository"]
                    or not set(source["paths"]) <= set(receipt["sourcePaths"])):
                raise ValueError("host scope mismatch")
            argv, exit_status, passed, head = receipt["commandArgv"], receipt["exitStatus"], receipt["result"] == "passed", receipt["sourceHead"]
            for field in ("stdoutTail", "stderrTail"):
                if type(receipt[field]) is not str or len(receipt[field].encode()) > 8192:
                    raise ValueError("invalid command output")
        else:
            plan = load_json(command["plan_ref"])
            if (type(plan) is not dict or type(receipt) is not dict
                    or plan.get("artifact_role") != "repository_verification_plan"
                    or receipt.get("artifact_role") != "repository_verification_result"
                    or plan.get("schema_version") != 1 or receipt.get("schema_version") != 1
                    or type(plan.get("request")) is not dict or type(plan.get("lanes")) is not list
                    or type(receipt.get("lanes")) is not list
                    or receipt.get("plan_digest") != digest(plan)
                    or receipt.get("request") != plan.get("request")
                    or plan["request"].get("include_worktree") is not False):
                raise ValueError("contradictory verification result")
            if any(type(row) is not dict for row in [*plan["lanes"], *receipt["lanes"]]):
                raise ValueError("invalid verification rows")
            for field in ("profile_digest", "execution_closure_digest", "repository_scope_digest"):
                if receipt.get(field) != plan.get(field) or not receipt.get(field):
                    raise ValueError("contradictory verification result")
            planned = [row for row in plan["lanes"] if row.get("id") == command["lane_id"]]
            observed = [row for row in receipt["lanes"] if row.get("lane_id") == command["lane_id"]]
            if len(planned) != 1 or len(observed) != 1 or planned[0].get("disposition") != "run":
                raise ValueError("missing execution result")
            planned, observed = planned[0], observed[0]
            argv = planned["argv"]
            if observed.get("command_digest") != digest(argv) or planned.get("command_digest") != digest(argv):
                raise ValueError("altered command")
            if planned.get("input_digest") != observed.get("input_digest") or not observed.get("input_digest"):
                raise ValueError("contradictory command input")
            exit_status, passed, head = observed.get("exit_code"), observed.get("status") == "passed", receipt.get("head_commit")
            if head != plan["request"].get("head_commit") or observed.get("reason") != "command_completed":
                raise ValueError("missing execution result")
        if type(argv) is not list or not argv or any(type(arg) is not str for arg in argv):
            raise ValueError("missing command")
        if type(exit_status) is not int or exit_status != 0 or not passed:
            raise ValueError("host verification failed")
        original = snapshot(head)
        if any(path not in target["files"] or original["files"].get(path) != target["files"][path] for path in source["paths"]):
            raise ValueError("host source changed")
    row = {field: "not_applicable" for field in _LANE_FIELDS}
    row.update(reviewer="host-verification", lane=value["lane"], implemented_by="deterministic-host",
               model="not_reported", implementer_family="unknown", reviewer_family="unknown",
               resolution_reason="host-execution-only", evidence_refs=[value["literal"]["host_receipt_ref"]],
               raw_output_ref="review/pending-output.json", raw_output_digest="sha256:" + "0" * 64, finding_count=0)
    return row
