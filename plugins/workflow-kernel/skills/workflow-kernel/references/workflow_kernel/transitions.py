"""Pure legal-transition reducer and event reconstruction."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Iterable, Mapping, Tuple

from .schema import (
    ErrorDetailKey, ErrorMessage, IllegalTransitionError, MissingEvidenceError, NodeState,
    NodeStatus, MAX_EVIDENCE_ITEMS, RunMode, RunState, RunStatus,
    SequenceConflictError, WorkflowEvent,
)


TERMINAL_RUN = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BLOCKED,
                          RunStatus.CANCELLED, RunStatus.INTERRUPTED})
RUN_TERMINAL_TARGETS = {
    "run.succeeded": RunStatus.SUCCEEDED,
    "run.failed": RunStatus.FAILED,
    "run.blocked": RunStatus.BLOCKED,
    "run.cancelled": RunStatus.CANCELLED,
    "run.interrupted": RunStatus.INTERRUPTED,
}
NODE_TARGETS = {
    "node.ready": NodeStatus.READY,
    "node.started": NodeStatus.RUNNING,
    "node.waiting": NodeStatus.WAITING,
    "node.succeeded": NodeStatus.SUCCEEDED,
    "node.failed": NodeStatus.FAILED,
    "node.blocked": NodeStatus.BLOCKED,
    "node.skipped": NodeStatus.SKIPPED,
}
LEGAL_NODE_SOURCES = {
    NodeStatus.READY: {NodeStatus.PENDING},
    NodeStatus.RUNNING: {NodeStatus.READY, NodeStatus.WAITING},
    NodeStatus.WAITING: {NodeStatus.RUNNING},
    NodeStatus.SUCCEEDED: {NodeStatus.RUNNING, NodeStatus.WAITING},
    NodeStatus.FAILED: {NodeStatus.RUNNING, NodeStatus.WAITING},
    NodeStatus.BLOCKED: {NodeStatus.PENDING, NodeStatus.READY, NodeStatus.RUNNING, NodeStatus.WAITING},
    NodeStatus.SKIPPED: {NodeStatus.PENDING, NodeStatus.READY},
}


def _strings(payload: Mapping[str, object], key: str, *, required: bool = False) -> Tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item for item in value):
        raise IllegalTransitionError(ErrorMessage.EVENT_PAYLOAD_STRING_LIST, {ErrorDetailKey.FIELD: key})
    result = tuple(value)
    if required and not result:
        raise MissingEvidenceError(ErrorMessage.TRANSITION_EVIDENCE_REQUIRED, {ErrorDetailKey.FIELD: key})
    return result


def _require(condition: bool, state: RunState, event: WorkflowEvent) -> None:
    if not condition:
        raise IllegalTransitionError(ErrorMessage.ILLEGAL_FOR_STATE, {
            ErrorDetailKey.KIND: event.kind, ErrorDetailKey.RUN_STATUS: state.status.value,
            ErrorDetailKey.NODE_ID: event.node_id,
        })


def _merge_evidence(state: RunState, current: Tuple[str, ...], refs: Tuple[str, ...]) -> Tuple[str, ...]:
    """Merge references only after enforcing the run-wide attachment bound."""
    known = set(current)
    additions = []
    for reference in refs:
        if reference not in known:
            known.add(reference)
            additions.append(reference)
    total = len(state.evidence) + sum(len(node.evidence) for node in state.nodes.values())
    if total + len(additions) > MAX_EVIDENCE_ITEMS:
        raise IllegalTransitionError(ErrorMessage.EVIDENCE_ITEM_LIMIT, {
            ErrorDetailKey.REASON_CODE: "evidence_limit_exceeded",
            ErrorDetailKey.LIMIT_ITEMS: MAX_EVIDENCE_ITEMS,
        })
    return current + tuple(additions)


class TransitionEngine:
    def apply(self, state: RunState, event: WorkflowEvent) -> RunState:
        if event.run_id != state.run_id:
            raise IllegalTransitionError(ErrorMessage.EVENT_RUN_ID_STATE_MISMATCH, {ErrorDetailKey.KIND: event.kind})
        if event.sequence != state.revision:
            raise SequenceConflictError(ErrorMessage.EVENT_SEQUENCE_STATE_MISMATCH, {
                ErrorDetailKey.EVENT_SEQUENCE: event.sequence, ErrorDetailKey.REVISION: state.revision,
            })
        if state.status in TERMINAL_RUN and event.kind not in {"evidence.recorded", "cleanup.reconciled"}:
            raise IllegalTransitionError(ErrorMessage.TERMINAL_RUN_MUTATION, {
                ErrorDetailKey.KIND: event.kind, ErrorDetailKey.STATUS: state.status.value,
            })
        if event.kind.startswith("run."):
            return self._apply_run(state, event)
        if event.kind.startswith("node."):
            return self._apply_node(state, event)
        if event.kind == "evidence.recorded":
            return self._apply_evidence(state, event)
        if event.kind == "cleanup.reconciled":
            return self._apply_cleanup(state, event)
        raise IllegalTransitionError(ErrorMessage.UNKNOWN_EVENT_KIND, {ErrorDetailKey.KIND: event.kind})

    def _advance(self, state: RunState, event: WorkflowEvent, **changes) -> RunState:
        return replace(state, revision=state.revision + 1, updated_at=event.occurred_at, **changes)

    def _apply_run(self, state: RunState, event: WorkflowEvent) -> RunState:
        if event.kind == "run.initialized":
            _require(state.revision == 0 and state.status == RunStatus.PLANNED and event.node_id is None, state, event)
            mode_value = event.payload.get("mode", state.mode.value)
            try:
                mode = RunMode(mode_value)
            except (ValueError, TypeError) as exc:
                raise IllegalTransitionError(ErrorMessage.EVENT_UNKNOWN_RUN_MODE, {ErrorDetailKey.MODE: mode_value}) from exc
            return self._advance(state, event, mode=mode)
        if event.kind == "run.started":
            _require(state.status in {RunStatus.PLANNED, RunStatus.WAITING} and event.node_id is None, state, event)
            return self._advance(state, event, status=RunStatus.RUNNING)
        if event.kind == "run.waiting":
            _require(state.status == RunStatus.RUNNING and event.node_id is None, state, event)
            return self._advance(state, event, status=RunStatus.WAITING)
        if event.kind not in RUN_TERMINAL_TARGETS:
            raise IllegalTransitionError(ErrorMessage.UNKNOWN_EVENT_KIND, {ErrorDetailKey.KIND: event.kind})
        target = RUN_TERMINAL_TARGETS[event.kind]
        allowed = state.status in {RunStatus.RUNNING, RunStatus.WAITING}
        if target in {RunStatus.CANCELLED, RunStatus.INTERRUPTED, RunStatus.BLOCKED}:
            allowed = allowed or state.status == RunStatus.PLANNED
        _require(allowed and event.node_id is None, state, event)
        evidence = state.evidence
        if target == RunStatus.SUCCEEDED:
            refs = _strings(event.payload, "evidence", required=True)
            _require(all(node.status in {NodeStatus.SUCCEEDED, NodeStatus.SKIPPED}
                         for node in state.nodes.values()), state, event)
            evidence = _merge_evidence(state, evidence, refs)
        return self._advance(state, event, status=target, evidence=evidence)

    def _apply_node(self, state: RunState, event: WorkflowEvent) -> RunState:
        nodes = dict(state.nodes)
        if event.kind == "node.added":
            _require(state.status not in TERMINAL_RUN and event.node_id is not None and event.node_id not in nodes, state, event)
            dependencies = _strings(event.payload, "dependencies")
            if event.node_id in dependencies or any(item not in nodes for item in dependencies):
                raise IllegalTransitionError(ErrorMessage.NODE_DEPENDENCY_INVALID, {ErrorDetailKey.NODE_ID: event.node_id})
            nodes[event.node_id] = NodeState(event.node_id, dependencies=dependencies)
            return self._advance(state, event, nodes=MappingProxyType(nodes))
        _require(event.node_id is not None and event.node_id in nodes, state, event)
        if event.kind not in NODE_TARGETS:
            raise IllegalTransitionError(ErrorMessage.UNKNOWN_EVENT_KIND, {ErrorDetailKey.KIND: event.kind})
        node = nodes[event.node_id]
        target = NODE_TARGETS[event.kind]
        _require(node.status in LEGAL_NODE_SOURCES[target], state, event)
        if target == NodeStatus.READY:
            try:
                dependencies_succeeded = all(
                    nodes[item].status == NodeStatus.SUCCEEDED for item in node.dependencies
                )
            except KeyError as exc:
                raise IllegalTransitionError(ErrorMessage.NODE_DEPENDENCY_MISSING, {
                    ErrorDetailKey.REASON_CODE: "missing_dependency",
                }) from exc
            _require(dependencies_succeeded, state, event)
        refs = node.evidence
        if target == NodeStatus.SUCCEEDED:
            refs = _merge_evidence(state, refs, _strings(event.payload, "evidence", required=True))
        nodes[event.node_id] = replace(node, status=target, evidence=refs)
        return self._advance(state, event, nodes=MappingProxyType(nodes))

    def _apply_evidence(self, state: RunState, event: WorkflowEvent) -> RunState:
        refs = _strings(event.payload, "evidence", required=True)
        if event.node_id is None:
            evidence = _merge_evidence(state, state.evidence, refs)
            return self._advance(state, event, evidence=evidence)
        nodes = dict(state.nodes)
        _require(event.node_id in nodes, state, event)
        node = nodes[event.node_id]
        nodes[event.node_id] = replace(node, evidence=_merge_evidence(state, node.evidence, refs))
        return self._advance(state, event, nodes=MappingProxyType(nodes))

    def _apply_cleanup(self, state: RunState, event: WorkflowEvent) -> RunState:
        _require(event.node_id is None and not state.cleanup_reconciled, state, event)
        refs = _strings(event.payload, "evidence", required=True)
        evidence = _merge_evidence(state, state.evidence, refs)
        return self._advance(state, event, evidence=evidence, cleanup_reconciled=True)

    def reconstruct(self, events: Iterable[WorkflowEvent]) -> RunState:
        sequence = tuple(events)
        if not sequence:
            raise IllegalTransitionError(ErrorMessage.EMPTY_RECONSTRUCTION)
        first = sequence[0]
        if first.sequence != 0 or first.kind != "run.initialized":
            raise IllegalTransitionError(ErrorMessage.FIRST_EVENT_INITIALIZE, {
                ErrorDetailKey.KIND: first.kind, ErrorDetailKey.SEQUENCE: first.sequence,
            })
        state = RunState.new(first.run_id, first.occurred_at)
        for event in sequence:
            state = self.apply(state, event)
        return state
