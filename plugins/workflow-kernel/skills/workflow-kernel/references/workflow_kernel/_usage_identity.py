"""Shared attempt-scoped identity contract for the measurement producers.

``openrouter_usage`` and ``lane_bytes`` are two translators onto one payload
shape.  Both must satisfy the identical identity gate that
:mod:`workflow_kernel._translation` enforces at intake: an attempt-scoped usage
row needs ``node_id``, ``chunk_id``, ``attempt``, ``duration_seconds``,
``lane``, ``requested_provider``, ``attempted_provider``, ``implemented_by``,
``provider``, ``model``, and ``host``, all present and all well-formed.

That gate is defined once here.  Two parallel copies of it, one per producer,
diverge the moment the receipt schema moves -- and the identity block is
precisely what ``_translation`` and :class:`workflow_kernel.metrics.MetricsAggregator`
depend on being uniform across producers.

The producers contribute only their measurement fields and provenance.  This
module contributes nothing but identity, and validates before it builds so a
malformed field never reaches a payload.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


IDENTITY_TEXT_FIELDS = (
    "lane", "chunk_id", "node_id", "host",
    "requested_provider", "attempted_provider", "implemented_by",
    "provider", "model",
)


@dataclass(frozen=True)
class AttemptContext:
    """Where an attempt happened, as asserted by the caller.

    These six travel together through every producer and always have. Passed
    as loose keywords they were a data clump: eleven-plus positional-by-name
    arguments threaded through three functions, easy to reorder, easy to drop
    one from, and guaranteed to grow as the identity contract does.
    """

    lane: str
    chunk_id: str
    node_id: str
    attempt: int
    host: str
    duration_seconds: float


@dataclass(frozen=True)
class ProviderAttribution:
    """Who was asked, who was tried, and who actually did the work.

    Kept separate from :class:`AttemptContext` because the two producers obtain
    it differently: `lane_bytes` is told, while `openrouter_usage` reads it off
    the provider's own receipt. Splitting them keeps caller-asserted identity
    distinguishable from receipt-attributed identity, which is a distinction
    the payload contract already cares about.
    """

    requested_provider: str
    attempted_provider: str
    implemented_by: str
    provider: str
    model: str

    @classmethod
    def openrouter(cls, provider: str, model: str) -> "ProviderAttribution":
        """Attribution for a lane that ran through the OpenRouter rail."""
        return cls(
            requested_provider="openrouter",
            attempted_provider="openrouter",
            implemented_by="openrouter",
            provider=provider,
            model=model,
        )


def required_text(value, name, prefix):
    """Reject anything that is not a non-empty ``str``.

    ``type(value) is not str`` rather than ``isinstance`` so a ``str``
    subclass carrying surprising behavior cannot pass as a plain identity
    string.
    """
    if type(value) is not str or not value:
        raise ValueError(prefix + ": invalid " + name)
    return value


def required_attempt(value, prefix):
    if type(value) is not int or value < 1:
        raise ValueError(prefix + ": invalid attempt")
    return value


def required_duration(value, prefix):
    if type(value) not in (int, float) or value < 0:
        raise ValueError(prefix + ": invalid duration_seconds")
    if type(value) is float and not math.isfinite(value):
        raise ValueError(prefix + ": invalid duration_seconds")
    return value


def build_attempt_identity(
    prefix: str,
    context: AttemptContext,
    attribution: ProviderAttribution,
) -> dict:
    """Validate and return the attempt-scoped identity block.

    ``prefix`` names the calling producer so an error message says which
    translator rejected the input.  Every field is validated before any part of
    the returned dict is constructed.
    """
    if type(context) is not AttemptContext:
        raise ValueError(prefix + ": invalid attempt context")
    if type(attribution) is not ProviderAttribution:
        raise ValueError(prefix + ": invalid provider attribution")
    values = {
        "lane": context.lane,
        "chunk_id": context.chunk_id,
        "node_id": context.node_id,
        "host": context.host,
        "requested_provider": attribution.requested_provider,
        "attempted_provider": attribution.attempted_provider,
        "implemented_by": attribution.implemented_by,
        "provider": attribution.provider,
        "model": attribution.model,
    }
    for name in IDENTITY_TEXT_FIELDS:
        required_text(values[name], name, prefix)
    required_attempt(context.attempt, prefix)
    required_duration(context.duration_seconds, prefix)
    return {
        "usage_scope": "attempt",
        "attempt": context.attempt,
        "chunk_id": context.chunk_id,
        "node_id": context.node_id,
        "duration_seconds": context.duration_seconds,
        "lane": context.lane,
        "requested_provider": attribution.requested_provider,
        "attempted_provider": attribution.attempted_provider,
        "implemented_by": attribution.implemented_by,
        "provider": attribution.provider,
        "model": attribution.model,
        "host": context.host,
    }
