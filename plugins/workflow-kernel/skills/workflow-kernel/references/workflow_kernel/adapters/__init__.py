"""Workflow kernel host-boundary adapters.

Boundary code only: host dispatch/resume management, harness capability
aggregation, and isolation selection. The domain value types (workflow
classes, node specs, gate decisions, host capabilities/routes, session
receipts, builder outcomes) live in the core module ``workflow_kernel.model``;
import them from there. Builder outcomes remain closed; observations project
to ``evidence.recorded`` and are never node lifecycle transitions.
"""

from importlib import import_module

_LAZY_EXPORTS = {
    "BuilderSessionManager": (".host", "BuilderSessionManager"),
    "HostAdapter": (".host", "HostAdapter"),
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
    "BuilderSessionManager", "HostAdapter", "IsolationSelector",
    "capabilities_from_harness_profile",
]
