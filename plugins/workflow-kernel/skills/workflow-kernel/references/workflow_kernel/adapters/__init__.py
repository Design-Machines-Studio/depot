"""Workflow kernel host contracts, closed builder outcomes, and safe persistence.

Builder outcomes are closed. Observations project to ``evidence.recorded`` and
are never node lifecycle transitions. ``SessionHandle`` and ``SessionResult``
are immutable provenance receipts for one run/node/attempt, provider, concrete
rail, and capability. Downstream translators must require an authoritative
receipt reference and safely merge result evidence; the observation helper does
not invent a receipt. ``ResumeStateBlob`` raw bytes belong only in protected,
permission-restricted storage with retention/deletion, never ordinary receipts,
events, evidence, artifacts, shadow reports, Airlift payloads, or checkpoints.
Its checksum detects corruption and does not claim authenticity.
"""

from importlib import import_module

from .base import (
    AttemptLedger, BuilderObservation, BuilderOutcome, BuilderSessionDecision,
    FailureReason, GateDecision,
    HostAdapter, HostCapabilities, HostCapability, HostRoute, IsolationDecision, IsolationMode,
    IsolationRequirements, NodeSpec, ResumeStateBlob, ResumeStateContext,
    RetryDecision, SessionHandle, SessionResult, SessionStatus,
    ValidationFeedback, WorkflowClass, WorkflowContext,
)

_LAZY_EXPORTS = {
    "BuilderSessionManager": (".host", "BuilderSessionManager"),
    "FakeHostAdapter": (".host", "FakeHostAdapter"),
    "capabilities_from_harness_profile": (".host", "capabilities_from_harness_profile"),
    "IsolationSelector": (".isolation", "IsolationSelector"),
}


def __getattr__(name: str) -> object:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module = import_module(target[0], __name__)
    value = getattr(module, target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))

__all__ = [
    "AttemptLedger", "BuilderObservation", "BuilderOutcome", "BuilderSessionDecision",
    "BuilderSessionManager",
    "FailureReason", "FakeHostAdapter", "GateDecision", "HostAdapter",
    "HostCapabilities", "HostCapability", "HostRoute", "IsolationDecision", "IsolationMode",
    "IsolationRequirements", "IsolationSelector", "NodeSpec", "RetryDecision",
    "ResumeStateBlob", "ResumeStateContext", "SessionHandle", "SessionResult",
    "SessionStatus", "ValidationFeedback", "WorkflowClass",
    "WorkflowContext", "capabilities_from_harness_profile",
]
