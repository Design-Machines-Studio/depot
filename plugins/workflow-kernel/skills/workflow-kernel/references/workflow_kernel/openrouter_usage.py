"""OpenRouter receipt to kernel attempt-usage payload translation.

This module is the measurement backbone's last mile: it translates one
schemaVersion-2 receipt written by ``openrouter-wrapper.sh`` into an
attempt-scoped kernel event payload that
``workflow_kernel.pipeline_adapter.translate_pipeline_receipts`` and
:class:`workflow_kernel.metrics.MetricsAggregator` already consume.

Honesty rules:

* A missing usage counter is OMITTED from the payload -- never present
  with ``None`` and never synthesized as ``0``.  ``metrics._number``
  raises on a present-null numeric and ``cost_summary`` renders absence
  as ``null``, so absence is the only honest spelling of "not reported".
* Counter values that are negative, boolean, float, or string-typed are
  rejected, never propagated.
* A receipt whose usage object yields no measurement at all -- including
  a failure receipt (``usage: null``) -- stays present but honest: it
  maps to the single provenance string ``"openrouter_receipt_no_usage"``
  that ``_translation`` allows to carry a measurement-less scoped row.
* Observation only -- nothing here gates, waives, selects, or alters any
  lane, phase, or review outcome.
"""

from __future__ import annotations

import math


MEASUREMENT_SOURCE = "openrouter_api_receipt"
MEASUREMENT_SOURCE_NO_USAGE = "openrouter_receipt_no_usage"
NOT_REPORTED = "not_reported"

_COUNTER_PATHS = (
    (("prompt_tokens",), "input_usage_count"),
    (("completion_tokens",), "output_usage_count"),
    (("total_tokens",), "usage_count"),
    (("prompt_tokens_details", "cached_tokens"), "cache_read_usage_count"),
    (("prompt_tokens_details", "cache_write_tokens"), "cache_write_usage_count"),
    (("completion_tokens_details", "reasoning_tokens"), "reasoning_usage_count"),
)
_ABSENT = object()


def _required_text(value, name):
    if type(value) is not str or not value:
        raise ValueError("openrouter usage: invalid " + name)
    return value


def _first_text(*values):
    for value in values:
        if type(value) is str and value:
            return value
    return NOT_REPORTED


def _counter(usage, path):
    node = usage
    for part in path:
        if not isinstance(node, dict):
            return _ABSENT
        node = node.get(part)
        if node is None:
            return _ABSENT
    if type(node) is not int or node < 0:
        raise ValueError("invalid openrouter usage counter: " + ".".join(path))
    return node


def _cost(usage):
    value = usage.get("cost")
    if value is None:
        return _ABSENT
    if type(value) not in (int, float) or value < 0:
        raise ValueError("invalid openrouter usage cost")
    if type(value) is float and not math.isfinite(value):
        raise ValueError("invalid openrouter usage cost")
    return value


def translate_openrouter_receipt(
    receipt: dict,
    *,
    lane: str,
    chunk_id: str,
    node_id: str,
    attempt: int,
    host: str,
    duration_seconds: float,
) -> dict:
    """Translate one schemaVersion-2 OpenRouter receipt into a payload.

    The returned dict carries the full attempt-scoped identity and
    provenance that ``_translation`` requires (``node_id``, ``chunk_id``,
    ``attempt``, ``duration_seconds``, ``requested_provider``,
    ``attempted_provider``, ``implemented_by``, ``model``, ``host``).
    Usage counters are copied only when present in the receipt; a missing
    source key means the payload key is ABSENT, never ``None`` and never
    ``0``.  ``generationId``, ``authorization``, and ``routing`` are
    deliberately not propagated -- the receipt file remains the durable
    provenance store.
    """
    if type(receipt) is not dict:
        raise ValueError("openrouter receipt is not an object")
    _required_text(lane, "lane")
    _required_text(chunk_id, "chunk_id")
    _required_text(node_id, "node_id")
    _required_text(host, "host")
    if type(attempt) is not int or attempt < 1:
        raise ValueError("openrouter usage: invalid attempt")
    if type(duration_seconds) not in (int, float) or duration_seconds < 0:
        raise ValueError("openrouter usage: invalid duration_seconds")
    if type(duration_seconds) is float and not math.isfinite(duration_seconds):
        raise ValueError("openrouter usage: invalid duration_seconds")

    usage = receipt.get("usage")
    if usage is not None and type(usage) is not dict:
        raise ValueError("openrouter receipt usage is not an object")

    payload = {
        "usage_scope": "attempt",
        "usage_estimated": False,
        "attempt": attempt,
        "chunk_id": chunk_id,
        "node_id": node_id,
        "duration_seconds": duration_seconds,
        "lane": lane,
        "requested_provider": "openrouter",
        "attempted_provider": "openrouter",
        "implemented_by": "openrouter",
        "provider": _first_text(receipt.get("servingProvider")),
        "model": _first_text(
            receipt.get("responseModel"),
            receipt.get("attemptedModel"),
            receipt.get("requestedModel"),
        ),
        "host": host,
    }
    measurements = {}
    if usage is not None:
        for path, key in _COUNTER_PATHS:
            value = _counter(usage, path)
            if value is not _ABSENT:
                measurements[key] = value
        cost = _cost(usage)
        if cost is not _ABSENT:
            measurements["cost_usd"] = cost
    payload["measurement_source"] = (
        MEASUREMENT_SOURCE if measurements else MEASUREMENT_SOURCE_NO_USAGE
    )
    payload.update(measurements)
    return payload
