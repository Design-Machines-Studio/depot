"""OpenRouter receipt to kernel attempt-usage payload translation.

This module is the measurement backbone's last mile: it translates one
schemaVersion-2 receipt written by ``openrouter-wrapper.sh`` into an
attempt-scoped kernel event payload that
``workflow_kernel.pipeline_adapter.translate_pipeline_receipts`` and
:class:`workflow_kernel.metrics.MetricsAggregator` already consume.  The
identity half of the payload is built by
:mod:`workflow_kernel._usage_identity`, shared with ``lane_bytes``, so both
producers emit one uniform shape.

Honesty rules:

* A missing usage counter is OMITTED from the payload -- never present
  with ``None`` and never synthesized as ``0``.  ``metrics._number``
  raises on a present-null numeric and ``cost_summary`` renders absence
  as ``null``, so absence is the only honest spelling of "not reported".
* Counter values that are negative, boolean, float, or string-typed are
  rejected, never propagated.
* A FAILED attempt and an attempt that merely reported no usage are
  different facts and get different provenance.  A receipt whose
  ``outcome`` is not ``"success"`` maps to
  ``"openrouter_receipt_failed"``; a successful receipt that yields no
  measurement maps to ``"openrouter_receipt_no_usage"``.  Both survive
  intake as measurement-less scoped rows, and ``failure_kind`` carries
  the wrapper's reason so a reader can tell an error from an unmetered
  success.  Collapsing the two would hide real spend: OpenRouter can bill
  a generation that returns HTTP 200 with ``usage: null``.
* ``usage_estimated`` is asserted only on a row that carries a
  measurement.  A measurement-less row is neither measured nor
  estimated, so the flag is ``False`` and the provenance string is what
  tells the reader why.
* Provider and model identity arrives from the receipt, which the local
  wrapper writes and nothing signs.  Those fields are recorded together
  with ``identity_provenance``, naming which of them came from the
  receipt rather than from trusted launch context, so a later audit can
  tell attributed identity from asserted identity.  Lane, chunk, node,
  attempt, and host never come from the receipt -- the caller supplies
  them -- so lane attribution cannot be forged by editing a receipt.
* Observation only -- nothing here gates, waives, selects, or alters any
  lane, phase, or review outcome.
"""

from __future__ import annotations

import math

from ._usage_identity import build_attempt_identity


MEASUREMENT_SOURCE = "openrouter_api_receipt"
MEASUREMENT_SOURCE_NO_USAGE = "openrouter_receipt_no_usage"
MEASUREMENT_SOURCE_FAILED = "openrouter_receipt_failed"
NOT_REPORTED = "not_reported"
_PREFIX = "openrouter usage"

_COUNTER_PATHS = (
    (("prompt_tokens",), "input_usage_count"),
    (("completion_tokens",), "output_usage_count"),
    (("total_tokens",), "usage_count"),
    (("prompt_tokens_details", "cached_tokens"), "cache_read_usage_count"),
    (("prompt_tokens_details", "cache_write_tokens"), "cache_write_usage_count"),
    (("completion_tokens_details", "reasoning_tokens"), "reasoning_usage_count"),
)
_ABSENT = object()


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


def _failure_kind(receipt):
    """Return the wrapper's failure reason, or ``None`` for a success.

    ``outcome`` is the wrapper's own verdict. Anything other than the literal
    ``"success"`` -- including a missing or non-string ``outcome`` -- is
    treated as a failure, because a receipt that cannot state it succeeded has
    not demonstrated that it did.
    """
    if receipt.get("outcome") == "success":
        return None
    kind = receipt.get("failureKind")
    if type(kind) is str and kind:
        return kind
    outcome = receipt.get("outcome")
    if type(outcome) is str and outcome:
        return outcome
    return "unreported"


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

    Usage counters are copied only when present in the receipt; a missing
    source key means the payload key is ABSENT, never ``None`` and never
    ``0``.  ``generationId``, ``authorization``, and ``routing`` are
    deliberately not propagated -- the receipt file remains the durable
    provenance store.

    A receipt whose ``outcome`` is not ``"success"`` produces a row tagged
    ``openrouter_receipt_failed`` carrying ``failure_kind``, so a failed
    attempt is never mistaken for an unmetered successful one.  Counters are
    still copied when a failed receipt happens to report them -- a partial
    generation that billed tokens must show those tokens.
    """
    if type(receipt) is not dict:
        raise ValueError("openrouter receipt is not an object")

    usage = receipt.get("usage")
    if usage is not None and type(usage) is not dict:
        raise ValueError("openrouter receipt usage is not an object")

    # Provider and model are the only payload fields sourced from the receipt.
    # Record which ones actually came from it so an audit can separate
    # receipt-attributed identity from caller-asserted identity.
    receipt_provider = _first_text(receipt.get("servingProvider"))
    receipt_model = _first_text(
        receipt.get("responseModel"),
        receipt.get("attemptedModel"),
        receipt.get("requestedModel"),
    )
    payload = build_attempt_identity(
        prefix=_PREFIX,
        lane=lane,
        chunk_id=chunk_id,
        node_id=node_id,
        attempt=attempt,
        host=host,
        duration_seconds=duration_seconds,
        requested_provider="openrouter",
        attempted_provider="openrouter",
        implemented_by="openrouter",
        provider=receipt_provider,
        model=receipt_model,
    )

    measurements = {}
    if usage is not None:
        for path, key in _COUNTER_PATHS:
            value = _counter(usage, path)
            if value is not _ABSENT:
                measurements[key] = value
        cost = _cost(usage)
        if cost is not _ABSENT:
            measurements["cost_usd"] = cost

    failure_kind = _failure_kind(receipt)
    if failure_kind is not None:
        payload["measurement_source"] = MEASUREMENT_SOURCE_FAILED
        payload["failure_kind"] = failure_kind
    elif measurements:
        payload["measurement_source"] = MEASUREMENT_SOURCE
    else:
        payload["measurement_source"] = MEASUREMENT_SOURCE_NO_USAGE
    # A provider receipt is never an estimate: either it reported counters or
    # it reported nothing. The measurement_source string, not this flag, is
    # what tells a reader which of those happened.
    payload["usage_estimated"] = False
    payload["identity_provenance"] = (
        "receipt_asserted"
        if (receipt_provider != NOT_REPORTED or receipt_model != NOT_REPORTED)
        else "not_reported"
    )
    payload.update(measurements)
    return payload
