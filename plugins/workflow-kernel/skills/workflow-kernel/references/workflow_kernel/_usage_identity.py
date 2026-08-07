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


IDENTITY_TEXT_FIELDS = (
    "lane", "chunk_id", "node_id", "host",
    "requested_provider", "attempted_provider", "implemented_by",
    "provider", "model",
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
    *,
    prefix: str,
    lane: str,
    chunk_id: str,
    node_id: str,
    attempt: int,
    host: str,
    duration_seconds: float,
    requested_provider: str,
    attempted_provider: str,
    implemented_by: str,
    provider: str,
    model: str,
) -> dict:
    """Validate and return the attempt-scoped identity block.

    ``prefix`` names the calling producer so an error message says which
    translator rejected the input.  Every field is validated before any part of
    the returned dict is constructed.
    """
    values = {
        "lane": lane,
        "chunk_id": chunk_id,
        "node_id": node_id,
        "host": host,
        "requested_provider": requested_provider,
        "attempted_provider": attempted_provider,
        "implemented_by": implemented_by,
        "provider": provider,
        "model": model,
    }
    for name in IDENTITY_TEXT_FIELDS:
        required_text(values[name], name, prefix)
    required_attempt(attempt, prefix)
    required_duration(duration_seconds, prefix)
    return {
        "usage_scope": "attempt",
        "attempt": attempt,
        "chunk_id": chunk_id,
        "node_id": node_id,
        "duration_seconds": duration_seconds,
        "lane": lane,
        "requested_provider": requested_provider,
        "attempted_provider": attempted_provider,
        "implemented_by": implemented_by,
        "provider": provider,
        "model": model,
        "host": host,
    }
