"""Pure legal-transition reducer and event reconstruction."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Iterable, Mapping, Tuple

from .schema import (
    IllegalTransitionError, MissingEvidenceError, NodeState, NodeStatus,
    RunMode, RunState, RunStatus, SequenceConflictError, WorkflowEvent,
)


TERMINAL_RUN = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BLOCKED,
                          RunStatus.CANCELLED, RunStatus.INTERRUPTED})
TERMINAL_NODE = frozenset({NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.SKIPPED})


def _strings(payload: Mapping[str, object], key: str, *, required: bool = False) -> Tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item for item in value):
        raise IllegalTransitionError("event payload field must be a string list", {"field": key})
    result = tuple(value)
    if required and not result:
        raise MissingEvidenceError("transition requires evidence", {"field": key})
    return result


def _require(condition: bool, state: RunState, event: WorkflowEvent) -> None:
    if not condition:
        raise IllegalTransitionError("event is illegal for current state", {
            "kind": event.kind, "run_status": state.status.value, "node_id": event.node_id,
        })


class TransitionEngine:
    def apply(self, state: RunState, event: WorkflowEvent) -> RunState:
        if event.run_id != state.run_id:
            raise IllegalTransitionError("event run id does not match state", {"kind": event.kind})
        if event.sequence != state.revision:
            raise SequenceConflictError("event sequence does not match state revision", {
                "event_sequence": event.sequence, "revision": state.revision,
            })
        if state.status in TERMINAL_RUN and event.kind not in {"evidence.recorded", "cleanup.reconciled"}:
            raise IllegalTransitionError("terminal run rejects mutation", {"kind": event.kind, "status": state.status.value})

        nodes = dict(state.nodes)
        status = state.status
        evidence = state.evidence
        cleanup = state.cleanup_reconciled

        if event.kind == "run.initialized":
            _require(state.revision == 0 and state.status == RunStatus.PLANNED and event.node_id is None, state, event)
            mode_value = event.payload.get("mode", state.mode.value)
            try:
                mode = RunMode(mode_value)
            except (ValueError, TypeError) as exc:
                raise IllegalTransitionError("event specifies unknown run mode", {"mode": mode_value}) from exc
            state = replace(state, mode=mode)
        elif event.kind == "run.started":
            _require(status in {RunStatus.PLANNED, RunStatus.WAITING} and event.node_id is None, state, event)
            status = RunStatus.RUNNING
        elif event.kind == "run.waiting":
            _require(status == RunStatus.RUNNING and event.node_id is None, state, event)
            status = RunStatus.WAITING
        elif event.kind.startswith("run."):
            targets = {
                "run.succeeded": RunStatus.SUCCEEDED, "run.failed": RunStatus.FAILED,
                "run.blocked": RunStatus.BLOCKED, "run.cancelled": RunStatus.CANCELLED,
                "run.interrupted": RunStatus.INTERRUPTED,
            }
            if event.kind not in targets:
                raise IllegalTransitionError("unknown event kind", {"kind": event.kind})
            target = targets[event.kind]
            allowed = status in {RunStatus.RUNNING, RunStatus.WAITING}
            if target in {RunStatus.CANCELLED, RunStatus.INTERRUPTED, RunStatus.BLOCKED}:
                allowed = allowed or status == RunStatus.PLANNED
            _require(allowed and event.node_id is None, state, event)
            if target == RunStatus.SUCCEEDED:
                refs = _strings(event.payload, "evidence", required=True)
                _require(all(node.status in {NodeStatus.SUCCEEDED, NodeStatus.SKIPPED} for node in nodes.values()), state, event)
                evidence = tuple(dict.fromkeys(evidence + refs))
            status = target
        elif event.kind == "node.added":
            _require(status not in TERMINAL_RUN and event.node_id is not None and event.node_id not in nodes, state, event)
            dependencies = _strings(event.payload, "dependencies")
            if event.node_id in dependencies or any(item not in nodes for item in dependencies):
                raise IllegalTransitionError("node dependency is invalid", {"node_id": event.node_id})
            nodes[event.node_id] = NodeState(event.node_id, dependencies=dependencies)
        elif event.kind.startswith("node."):
            _require(event.node_id is not None and event.node_id in nodes, state, event)
            node = nodes[event.node_id]
            target_by_kind = {
                "node.ready": NodeStatus.READY, "node.started": NodeStatus.RUNNING,
                "node.waiting": NodeStatus.WAITING, "node.succeeded": NodeStatus.SUCCEEDED,
                "node.failed": NodeStatus.FAILED, "node.blocked": NodeStatus.BLOCKED,
                "node.skipped": NodeStatus.SKIPPED,
            }
            if event.kind not in target_by_kind:
                raise IllegalTransitionError("unknown event kind", {"kind": event.kind})
            target = target_by_kind[event.kind]
            legal = {
                NodeStatus.READY: {NodeStatus.PENDING}, NodeStatus.RUNNING: {NodeStatus.READY, NodeStatus.WAITING},
                NodeStatus.WAITING: {NodeStatus.RUNNING}, NodeStatus.SUCCEEDED: {NodeStatus.RUNNING, NodeStatus.WAITING},
                NodeStatus.FAILED: {NodeStatus.RUNNING, NodeStatus.WAITING}, NodeStatus.BLOCKED: {NodeStatus.PENDING, NodeStatus.READY, NodeStatus.RUNNING, NodeStatus.WAITING},
                NodeStatus.SKIPPED: {NodeStatus.PENDING, NodeStatus.READY},
            }
            _require(node.status in legal[target], state, event)
            if target == NodeStatus.READY:
                _require(all(nodes[item].status == NodeStatus.SUCCEEDED for item in node.dependencies), state, event)
            refs = node.evidence
            if target == NodeStatus.SUCCEEDED:
                refs = tuple(dict.fromkeys(refs + _strings(event.payload, "evidence", required=True)))
            nodes[event.node_id] = replace(node, status=target, evidence=refs)
        elif event.kind == "evidence.recorded":
            refs = _strings(event.payload, "evidence", required=True)
            if event.node_id is None:
                evidence = tuple(dict.fromkeys(evidence + refs))
            else:
                _require(event.node_id in nodes, state, event)
                nodes[event.node_id] = replace(nodes[event.node_id], evidence=tuple(dict.fromkeys(nodes[event.node_id].evidence + refs)))
        elif event.kind == "cleanup.reconciled":
            _require(event.node_id is None and not cleanup, state, event)
            refs = _strings(event.payload, "evidence", required=True)
            evidence = tuple(dict.fromkeys(evidence + refs))
            cleanup = True
        else:
            raise IllegalTransitionError("unknown event kind", {"kind": event.kind})

        return replace(state, revision=state.revision + 1, status=status, updated_at=event.occurred_at,
                       nodes=MappingProxyType(nodes), evidence=evidence, cleanup_reconciled=cleanup)

    def reconstruct(self, events: Iterable[WorkflowEvent]) -> RunState:
        sequence = tuple(events)
        if not sequence:
            raise IllegalTransitionError("cannot reconstruct an empty event ledger")
        first = sequence[0]
        if first.sequence != 0 or first.kind != "run.initialized":
            raise IllegalTransitionError("first event must initialize the run", {"kind": first.kind, "sequence": first.sequence})
        state = RunState.new(first.run_id, first.occurred_at)
        for event in sequence:
            state = self.apply(state, event)
        return state
