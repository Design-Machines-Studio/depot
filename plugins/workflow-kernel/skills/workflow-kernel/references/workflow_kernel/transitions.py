"""Pure legal-transition reducer and event reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Iterable, Mapping, Tuple

from .redaction import MAX_PAYLOAD_ITEMS, MAX_TOTAL_STRING_BYTES, bounded_iterable
from .schema import (
    ErrorDetailKey, ErrorMessage, IllegalTransitionError, MissingEvidenceError, NodeState,
    NodeStatus, MAX_EVIDENCE_ITEMS, RunMode, RunState, RunStatus,
    SequenceConflictError, UnsafePayloadError, WorkflowEvent,
    _snapshot_run_state, _snapshot_workflow_event, _trusted_run_state_update,
)

MAX_EVENT_ITEMS = 100_000
MAX_RECONSTRUCTION_WORK = 50_100_000


@dataclass
class _StateCounters:
    nodes: int = 0
    edges: int = 0
    evidence: int = 0
    text_bytes: int = 0

    @property
    def items(self) -> int:
        return self.nodes + self.edges + self.evidence

    def require_delta(self, *, nodes=0, edges=0, evidence=0, text_bytes=0) -> None:
        if self.items + nodes + edges + evidence > MAX_PAYLOAD_ITEMS:
            raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE, {
                ErrorDetailKey.LIMIT_ITEMS.value: MAX_PAYLOAD_ITEMS,
            })
        if self.evidence + evidence > MAX_EVIDENCE_ITEMS:
            raise UnsafePayloadError(ErrorMessage.EVIDENCE_ITEM_LIMIT, {
                ErrorDetailKey.LIMIT_ITEMS.value: MAX_EVIDENCE_ITEMS,
            })
        if self.text_bytes + text_bytes > MAX_TOTAL_STRING_BYTES:
            raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE, {
                ErrorDetailKey.LIMIT_BYTES.value: MAX_TOTAL_STRING_BYTES,
            })

    def add(self, *, nodes=0, edges=0, evidence=0, text_bytes=0) -> None:
        self.nodes += nodes
        self.edges += edges
        self.evidence += evidence
        self.text_bytes += text_bytes


class _ReconstructionBudget:
    __slots__ = ("used",)

    def __init__(self):
        self.used = 0

    def charge(self, amount: int) -> None:
        if self.used + amount > MAX_RECONSTRUCTION_WORK:
            raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE, {
                ErrorDetailKey.LIMIT_ITEMS.value: MAX_RECONSTRUCTION_WORK,
                ErrorDetailKey.REASON_CODE.value: "reconstruction_work_limit",
            })
        self.used += amount


def _text_size(values) -> int:
    return sum(len(value.encode("utf-8")) for value in values)


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


def _strings(payload: Mapping[str, object], key: str, *, required: bool = False,
             work=None) -> Tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, (list, tuple)):
        raise IllegalTransitionError(ErrorMessage.EVENT_PAYLOAD_STRING_LIST, {ErrorDetailKey.FIELD.value: key})
    limit = MAX_EVIDENCE_ITEMS if key == "evidence" else MAX_PAYLOAD_ITEMS
    if work is not None:
        work.charge(len(value))
    result = []
    try:
        for item in bounded_iterable(value, max_items=limit):
            if not isinstance(item, str) or not item:
                raise IllegalTransitionError(
                    ErrorMessage.EVENT_PAYLOAD_STRING_LIST, {ErrorDetailKey.FIELD.value: key},
                )
            result.append(item)
    except TypeError:
        raise IllegalTransitionError(ErrorMessage.EVIDENCE_ITEM_LIMIT, {
            ErrorDetailKey.LIMIT_ITEMS.value: limit,
        }) from None
    result = tuple(result)
    if required and not result:
        raise MissingEvidenceError(ErrorMessage.TRANSITION_EVIDENCE_REQUIRED, {ErrorDetailKey.FIELD.value: key})
    return result


def _require(condition: bool, state: RunState, event: WorkflowEvent) -> None:
    if not condition:
        raise IllegalTransitionError(ErrorMessage.ILLEGAL_FOR_STATE, {
            ErrorDetailKey.KIND.value: event.kind, ErrorDetailKey.RUN_STATUS.value: state.status.value,
            ErrorDetailKey.NODE_ID.value: event.node_id,
        })


def _merge_evidence(counters: _StateCounters, current: Tuple[str, ...],
                    refs: Tuple[str, ...], work=None) -> tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Merge references only after enforcing the run-wide attachment bound."""
    if work is not None:
        work.charge(len(current))
    known = set(current)
    additions = []
    if work is not None:
        work.charge(len(refs))
    for reference in refs:
        if reference not in known:
            known.add(reference)
            additions.append(reference)
    additions = tuple(additions)
    if counters.evidence + len(additions) > MAX_EVIDENCE_ITEMS:
        raise IllegalTransitionError(ErrorMessage.EVIDENCE_ITEM_LIMIT, {
            ErrorDetailKey.REASON_CODE.value: "evidence_limit_exceeded",
            ErrorDetailKey.LIMIT_ITEMS.value: MAX_EVIDENCE_ITEMS,
        })
    return current + additions, additions


class TransitionEngine:
    def apply(self, state: RunState, event: WorkflowEvent) -> RunState:
        state, accumulated = _snapshot_run_state(state, include_counters=True)
        event = _snapshot_workflow_event(event)
        counters = _StateCounters(*accumulated)
        return self._apply_validated(state, event, counters)

    def _apply_validated(self, state: RunState, event: WorkflowEvent,
                         counters: _StateCounters, work=None) -> RunState:
        if event.run_id != state.run_id:
            raise IllegalTransitionError(ErrorMessage.EVENT_RUN_ID_STATE_MISMATCH, {ErrorDetailKey.KIND.value: event.kind})
        if event.sequence != state.revision:
            raise SequenceConflictError(ErrorMessage.EVENT_SEQUENCE_STATE_MISMATCH, {
                ErrorDetailKey.EVENT_SEQUENCE.value: event.sequence, ErrorDetailKey.REVISION.value: state.revision,
            })
        if state.status in TERMINAL_RUN and event.kind not in {"evidence.recorded", "cleanup.reconciled"}:
            raise IllegalTransitionError(ErrorMessage.TERMINAL_RUN_MUTATION, {
                ErrorDetailKey.KIND.value: event.kind, ErrorDetailKey.STATUS.value: state.status.value,
            })
        if event.kind.startswith("run."):
            return self._apply_run(state, event, counters, work)
        if event.kind.startswith("node."):
            return self._apply_node(state, event, counters, work)
        if event.kind == "evidence.recorded":
            return self._apply_evidence(state, event, counters, work)
        if event.kind == "cleanup.reconciled":
            return self._apply_cleanup(state, event, counters, work)
        raise IllegalTransitionError(ErrorMessage.UNKNOWN_EVENT_KIND, {ErrorDetailKey.KIND.value: event.kind})

    def _advance(self, state: RunState, event: WorkflowEvent,
                 counters: _StateCounters, *, counter_delta=None, **changes) -> RunState:
        delta = counter_delta or {}
        counters.require_delta(**delta)
        result = _trusted_run_state_update(
            state, revision=state.revision + 1, updated_at=event.occurred_at, **changes,
        )
        counters.add(**delta)
        return result

    def _apply_run(self, state: RunState, event: WorkflowEvent,
                   counters: _StateCounters, work) -> RunState:
        if event.kind == "run.initialized":
            _require(state.revision == 0 and state.status == RunStatus.PLANNED and event.node_id is None, state, event)
            mode_value = event.payload.get("mode", state.mode.value)
            try:
                mode = RunMode(mode_value)
            except (ValueError, TypeError):
                raise IllegalTransitionError(ErrorMessage.EVENT_UNKNOWN_RUN_MODE, {ErrorDetailKey.MODE.value: mode_value}) from None
            return self._advance(state, event, counters, mode=mode)
        if event.kind == "run.started":
            _require(state.status in {RunStatus.PLANNED, RunStatus.WAITING} and event.node_id is None, state, event)
            return self._advance(state, event, counters, status=RunStatus.RUNNING)
        if event.kind == "run.waiting":
            _require(state.status == RunStatus.RUNNING and event.node_id is None, state, event)
            return self._advance(state, event, counters, status=RunStatus.WAITING)
        if event.kind not in RUN_TERMINAL_TARGETS:
            raise IllegalTransitionError(ErrorMessage.UNKNOWN_EVENT_KIND, {ErrorDetailKey.KIND.value: event.kind})
        target = RUN_TERMINAL_TARGETS[event.kind]
        allowed = state.status in {RunStatus.RUNNING, RunStatus.WAITING}
        if target in {RunStatus.CANCELLED, RunStatus.INTERRUPTED, RunStatus.BLOCKED}:
            allowed = allowed or state.status == RunStatus.PLANNED
        _require(allowed and event.node_id is None, state, event)
        evidence = state.evidence
        additions = ()
        if target == RunStatus.SUCCEEDED:
            refs = _strings(event.payload, "evidence", required=True, work=work)
            if work is not None:
                work.charge(len(state.nodes))
            _require(all(node.status in {NodeStatus.SUCCEEDED, NodeStatus.SKIPPED}
                         for node in state.nodes.values()), state, event)
            evidence, additions = _merge_evidence(counters, evidence, refs, work)
        return self._advance(
            state, event, counters, status=target, evidence=evidence,
            counter_delta={
                "evidence": len(additions), "text_bytes": _text_size(additions),
            },
        )

    def _apply_node(self, state: RunState, event: WorkflowEvent,
                    counters: _StateCounters, work) -> RunState:
        if work is not None:
            work.charge(len(state.nodes))
        nodes = dict(state.nodes)
        if event.kind == "node.added":
            _require(state.status not in TERMINAL_RUN and event.node_id is not None and event.node_id not in nodes, state, event)
            dependencies = _strings(event.payload, "dependencies", work=work)
            if work is not None:
                work.charge(len(dependencies))
            if event.node_id in dependencies or any(item not in nodes for item in dependencies):
                raise IllegalTransitionError(ErrorMessage.NODE_DEPENDENCY_INVALID, {ErrorDetailKey.NODE_ID.value: event.node_id})
            text_bytes = _text_size((event.node_id, event.node_id, *dependencies))
            nodes[event.node_id] = NodeState(event.node_id, dependencies=dependencies)
            return self._advance(
                state, event, counters, nodes=MappingProxyType(nodes),
                counter_delta={
                    "nodes": 1, "edges": len(dependencies), "text_bytes": text_bytes,
                },
            )
        _require(event.node_id is not None and event.node_id in nodes, state, event)
        if event.kind not in NODE_TARGETS:
            raise IllegalTransitionError(ErrorMessage.UNKNOWN_EVENT_KIND, {ErrorDetailKey.KIND.value: event.kind})
        node = nodes[event.node_id]
        target = NODE_TARGETS[event.kind]
        _require(node.status in LEGAL_NODE_SOURCES[target], state, event)
        if target == NodeStatus.READY:
            if work is not None:
                work.charge(len(node.dependencies))
            try:
                dependencies_succeeded = all(
                    nodes[item].status == NodeStatus.SUCCEEDED for item in node.dependencies
                )
            except KeyError:
                raise IllegalTransitionError(ErrorMessage.NODE_DEPENDENCY_MISSING, {
                    ErrorDetailKey.REASON_CODE.value: "missing_dependency",
                }) from None
            _require(dependencies_succeeded, state, event)
        refs = node.evidence
        additions = ()
        if target == NodeStatus.SUCCEEDED:
            refs, additions = _merge_evidence(
                counters, refs,
                _strings(event.payload, "evidence", required=True, work=work), work,
            )
        nodes[event.node_id] = replace(node, status=target, evidence=refs)
        return self._advance(
            state, event, counters, nodes=MappingProxyType(nodes),
            counter_delta={
                "evidence": len(additions), "text_bytes": _text_size(additions),
            },
        )

    def _apply_evidence(self, state: RunState, event: WorkflowEvent,
                        counters: _StateCounters, work) -> RunState:
        refs = _strings(event.payload, "evidence", required=True, work=work)
        if event.node_id is None:
            evidence, additions = _merge_evidence(
                counters, state.evidence, refs, work,
            )
            return self._advance(
                state, event, counters, evidence=evidence,
                counter_delta={
                    "evidence": len(additions), "text_bytes": _text_size(additions),
                },
            )
        if work is not None:
            work.charge(len(state.nodes))
        nodes = dict(state.nodes)
        _require(event.node_id in nodes, state, event)
        node = nodes[event.node_id]
        merged, additions = _merge_evidence(counters, node.evidence, refs, work)
        nodes[event.node_id] = replace(node, evidence=merged)
        return self._advance(
            state, event, counters, nodes=MappingProxyType(nodes),
            counter_delta={
                "evidence": len(additions), "text_bytes": _text_size(additions),
            },
        )

    def _apply_cleanup(self, state: RunState, event: WorkflowEvent,
                       counters: _StateCounters, work) -> RunState:
        _require(event.node_id is None and not state.cleanup_reconciled, state, event)
        refs = _strings(event.payload, "evidence", required=True, work=work)
        evidence, additions = _merge_evidence(
            counters, state.evidence, refs, work,
        )
        return self._advance(
            state, event, counters, evidence=evidence, cleanup_reconciled=True,
            counter_delta={
                "evidence": len(additions), "text_bytes": _text_size(additions),
            },
        )

    def reconstruct(self, events: Iterable[WorkflowEvent]) -> RunState:
        work = _ReconstructionBudget()
        try:
            sequence = bounded_iterable(events, max_items=MAX_EVENT_ITEMS)
            first = next(sequence)
        except StopIteration:
            raise IllegalTransitionError(ErrorMessage.EMPTY_RECONSTRUCTION)
        except (TypeError, RecursionError):
            raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE, {
                ErrorDetailKey.LIMIT_ITEMS.value: MAX_EVENT_ITEMS,
            }) from None
        first = _snapshot_workflow_event(first)
        work.charge(1)
        if first.sequence != 0 or first.kind != "run.initialized":
            raise IllegalTransitionError(ErrorMessage.FIRST_EVENT_INITIALIZE, {
                ErrorDetailKey.KIND.value: first.kind, ErrorDetailKey.SEQUENCE.value: first.sequence,
            })
        state = RunState.new(first.run_id, first.occurred_at)
        counters = _StateCounters()
        state = self._apply_validated(state, first, counters, work)
        while True:
            try:
                event = next(sequence)
            except StopIteration:
                break
            except (TypeError, RecursionError):
                raise UnsafePayloadError(ErrorMessage.PAYLOAD_NON_JSON_SAFE, {
                    ErrorDetailKey.LIMIT_ITEMS.value: MAX_EVENT_ITEMS,
                }) from None
            work.charge(1)
            state = self._apply_validated(
                state, _snapshot_workflow_event(event), counters, work,
            )
        return state
