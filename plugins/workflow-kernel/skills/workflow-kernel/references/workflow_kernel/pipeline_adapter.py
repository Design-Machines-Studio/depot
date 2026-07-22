"""Pure, observation-only adapters for authoritative pipeline artifacts."""

from __future__ import annotations

from collections import deque
import re
from typing import Iterable, Mapping, Optional, Tuple

from ._translation import (
    COMMON_RECEIPT_FIELDS, EXECUTION_MODES, ChunkSpec, RunSpec, dual_key,
    required_text, safe_reference, translate_receipts,
)
from .model import (
    BuilderSessionDecision, HostCapabilities, WorkflowClass, WorkflowContext,
)
from .schema import WorkflowEvent
from .workflows import WorkflowTemplates


__all__ = [
    "COMMON_RECEIPT_FIELDS", "EXECUTION_MODES", "ChunkSpec", "PIPELINE_STAGES",
    "RunSpec", "translate_builder_decision", "translate_manifest",
    "translate_pipeline_receipts",
]

PIPELINE_STAGES = frozenset({
    "progress", "manifest_validation", "dependency_ready", "dispatch",
    "deterministic_validation", "evaluation_gate", "browser_verification",
    "merge_disposition", "chunk_cleanup", "final_dm_review",
    "requirements_cross_check", "terminal_reconciliation", "run_summary",
    "verification_contract_bound", "verification_contract_revised",
    "verification_contract_revision_authorized",
    "attempt_usage", "browser_recovery",
})
_RUN_ID_SEPARATORS = re.compile(r"[^a-z0-9]+")


def _run_identity(value: object) -> str:
    value = required_text(value, "feature")
    normalized = _RUN_ID_SEPARATORS.sub("-", value.lower()).strip("-")
    if not normalized or len(normalized) > 255:
        raise ValueError("invalid feature")
    return normalized


def _chunks(value: object) -> Tuple[ChunkSpec, ...]:
    if not isinstance(value, list):
        raise ValueError("chunks must be a list")
    chunks = []
    identifiers = set()
    for raw in value:
        if type(raw) is not dict:
            raise ValueError("chunk must be an object")
        node_id = required_text(raw.get("id"), "chunk id")
        dependencies = dual_key(raw, "depends_on", "dependsOn", default=[])
        if not isinstance(dependencies, list) or any(
            type(item) is not str or not item for item in dependencies
        ) or len(dependencies) != len(set(dependencies)):
            raise ValueError("invalid chunk dependencies")
        if node_id in identifiers:
            raise ValueError("duplicate chunk id")
        identifiers.add(node_id)
        chunks.append(ChunkSpec(node_id, tuple(dependencies)))
    for chunk in chunks:
        if chunk.node_id in chunk.dependencies or not set(chunk.dependencies) <= identifiers:
            raise ValueError("invalid chunk dependency graph")
    return tuple(chunks)


def _levels(chunks: Tuple[ChunkSpec, ...]) -> Tuple[Tuple[str, ...], ...]:
    by_id = {chunk.node_id: chunk for chunk in chunks}
    indegree = {chunk.node_id: len(chunk.dependencies) for chunk in chunks}
    dependents = {chunk.node_id: [] for chunk in chunks}
    for chunk in chunks:
        for dependency in chunk.dependencies:
            dependents[dependency].append(chunk.node_id)
    ready = deque(sorted(node_id for node_id, count in indegree.items() if count == 0))
    levels = []
    visited = 0
    while ready:
        current = tuple(ready)
        ready.clear()
        levels.append(current)
        visited += len(current)
        next_ready = []
        for node_id in current:
            for dependent in dependents[node_id]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    next_ready.append(dependent)
        ready.extend(sorted(next_ready))
    if visited != len(by_id):
        raise ValueError("chunk dependency cycle")
    return tuple(levels)


def _cached_plan(value: object) -> Optional[Tuple[Tuple[str, ...], ...]]:
    if value is None:
        return None
    if type(value) is dict:
        value = value.get("levels")
        if type(value) is not list:
            raise ValueError("invalid executionPlan")
        result = []
        for expected_level, raw in enumerate(value):
            if type(raw) is not dict or raw.get("level") != expected_level:
                raise ValueError("invalid executionPlan")
            strategy = raw.get("strategy")
            if strategy == "sequential":
                items = raw.get("chunks")
                if type(items) is not list:
                    raise ValueError("invalid executionPlan")
            elif strategy == "parallel":
                groups = raw.get("groups")
                if type(groups) is not dict or any(
                    type(key) is not str or type(group) is not list
                    for key, group in groups.items()
                ):
                    raise ValueError("invalid executionPlan")
                items = [item for key in sorted(groups) for item in groups[key]]
            else:
                raise ValueError("invalid executionPlan")
            if any(type(item) is not str or not item for item in items):
                raise ValueError("invalid executionPlan")
            result.append(tuple(items))
        return tuple(result)
    if type(value) is not list or any(type(level) is not list for level in value):
        raise ValueError("invalid executionPlan")
    result = []
    for level in value:
        if any(type(item) is not str or not item for item in level):
            raise ValueError("invalid executionPlan")
        result.append(tuple(level))
    return tuple(result)


def translate_manifest(manifest: Mapping[str, object], profile: HostCapabilities) -> RunSpec:
    if type(manifest) is not dict or type(profile) is not HostCapabilities:
        raise ValueError("invalid manifest or host profile")
    identity = manifest.get("feature")
    if identity is None:  # bounded legacy compatibility; canonical feature wins.
        identity = dual_key(manifest, "run_id", "runId", default=None)
    run_id = _run_identity(identity)
    raw_class = dual_key(manifest, "workflow_class", "workflowClass", default=None)
    defaulted = raw_class is None
    try:
        workflow_class = WorkflowClass.FEATURE if defaulted else WorkflowClass(raw_class)
    except (TypeError, ValueError):
        raise ValueError("invalid workflowClass") from None
    execution_mode = dual_key(
        manifest, "execution_mode", "executionMode", default="generic",
    )
    if type(execution_mode) is not str or execution_mode not in EXECUTION_MODES:
        raise ValueError("invalid executionMode")
    chunks = _chunks(manifest.get("chunks"))
    levels = _levels(chunks)
    cached = _cached_plan(manifest.get("executionPlan"))
    changed_paths = dual_key(manifest, "changed_paths", "changedPaths", default=[])
    if not isinstance(changed_paths, list):
        raise ValueError("invalid changed paths")
    risk = manifest.get("risk", "low")
    requested_executor = dual_key(
        manifest, "requested_executor", "requestedExecutor", default=None,
    )
    decision_profile = dual_key(
        manifest, "decision_profile", "decisionProfile", default=None,
    )
    decision_profile_defaulted = decision_profile is None
    context = WorkflowContext(
        changed_paths=tuple(changed_paths), requested_executor=requested_executor,
        risk=risk,
    )
    # WorkflowTemplates remains the single safety anchor. Host capability
    # aggregation is intentionally not treated as route authorization here.
    nodes = WorkflowTemplates().expand(workflow_class, context)
    return RunSpec(
        run_id, workflow_class, defaulted, execution_mode, profile.host_name,
        nodes, chunks, levels, cached is not None and cached != levels,
        decision_profile=decision_profile,
        decision_profile_defaulted=decision_profile_defaulted,
    )


def translate_pipeline_receipts(
    receipts: Iterable[Mapping[str, object]],
) -> Tuple[WorkflowEvent, ...]:
    return translate_receipts(
        receipts, PIPELINE_STAGES, isolation_default="per-chunk-worktree",
    )


def translate_builder_decision(
    decision: BuilderSessionDecision, *, authoritative_receipt_reference: str,
    sequence: int, occurred_at: str,
    current_contract_digest: Optional[str] = None,
    claimed_contract_digest: Optional[str] = None,
) -> WorkflowEvent:
    reference = safe_reference(authoritative_receipt_reference)
    if type(decision) is not BuilderSessionDecision:
        raise ValueError("invalid builder decision")
    legacy_contract = (
        current_contract_digest is None and claimed_contract_digest is None
    )
    if not legacy_contract and (
        type(current_contract_digest) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", current_contract_digest) is None
        or type(claimed_contract_digest) is not str
        or claimed_contract_digest != current_contract_digest
    ):
        raise ValueError("verification contract digest mismatch")
    base = decision.to_evidence_event(
        run_id=decision.context.run_id, sequence=sequence,
        node_id=decision.context.node_id, occurred_at=occurred_at,
    )
    values = [reference]
    if decision.result is not None:
        values.extend(decision.result.evidence)
    values.extend(base.payload["evidence"])
    evidence = tuple(dict.fromkeys(values))
    payload = {
        "evidence": list(evidence),
        "authoritative_receipt": reference,
        "stage": "builder_continuity",
        "status": decision.status,
        "verification_contract_bound": not legacy_contract,
        "verification_contract_provenance": (
            "legacy_default_absent" if legacy_contract
            else "authoritative_receipt"
        ),
    }
    if not legacy_contract:
        payload["contract_digest"] = current_contract_digest
    return WorkflowEvent(
        1, sequence, base.run_id, base.node_id, "evidence.recorded",
        occurred_at, payload,
    )
