"""Deterministic per-lane input-bytes accounting.

Claude Code subagent and Codex CLI lanes expose no token capture point at
all -- no hook, wrapper, or receipt surface reports per-lane counts, and
building one is out of depot's control.  The measurement currency for
those rails is deterministic INPUT BYTES: the agent definition, the diff
slice, and the boilerplate a lane is fed are computable by code even when
what the provider meters is not.  This module is that calculator, so
every review lane gets an attempt-scoped row with honest
``usage_estimated: true`` provenance instead of a blank.  The payload
shape is identical in kind to ``openrouter_usage`` -- the same identity
fields, the same omit-never-null rule -- so
``workflow_kernel.pipeline_adapter.translate_pipeline_receipts`` and
:class:`workflow_kernel.metrics.MetricsAggregator` consume both producers
uniformly.

Honesty rules:

* Bytes are bytes.  No token multipliers, no unit conversion -- the
  figure is never promoted to a token-equivalent anywhere it surfaces.
* ``input_usage_count`` is a PRESENT integer; a zero-length input
  contributes ``0``, which is a real measurement, not an omission.
  Every other counter and ``cost_usd`` are OMITTED -- never present
  with ``None`` and never synthesized -- because ``metrics._number``
  raises on a present-null numeric and ``cost_summary`` gates on key
  presence, so absence is the only honest spelling of "not measured".
* Byte counts come from ``os.stat().st_size`` only; no file content
  ever enters the process.  Live symlinks are followed (``os.stat``
  semantics); a dangling symlink fails closed.
* File failures fail closed and name the path: a missing path, a
  directory passed where a file is expected, a dangling symlink, or a
  permission-denied file each raise -- there is never a silent ``0``
  and never a zero-filled row.
* Repeated boilerplate paths count once per occurrence; the list is
  deliberately not deduplicated.
* Determinism: same inputs, byte-identical output payload -- no
  timestamps, no randomness.
* Observation only -- nothing here gates, waives, selects, or alters
  any lane, phase, or review outcome.
"""

from __future__ import annotations

import math
import os
import stat


MEASUREMENT_SOURCE = "estimated_input_bytes"


def _required_text(value, name):
    if type(value) is not str or not value:
        raise ValueError("lane input bytes: invalid " + name)
    return value


def _byte_count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError("lane input bytes: invalid " + name)
    return value


def estimate_lane_input_bytes(
    *,
    agent_definition_bytes: int,
    diff_bytes: int,
    boilerplate_bytes: int,
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
    """Build an attempt-scoped usage payload from deterministic bytes.

    The returned dict carries the full attempt-scoped identity and
    provenance that ``_translation`` requires (``node_id``, ``chunk_id``,
    ``attempt``, ``duration_seconds``, ``lane``, ``requested_provider``,
    ``attempted_provider``, ``implemented_by``, ``provider``, ``model``,
    ``host``) -- exactly the shape chunk 01's
    ``openrouter_usage.translate_openrouter_receipt`` emits.  The
    measurement is ``input_usage_count``: the byte sum, always present as
    an integer, with ``measurement_source: "estimated_input_bytes"`` and
    ``usage_estimated: True``.  Every other counter and ``cost_usd`` are
    ABSENT, never ``None`` and never ``0``.
    """
    _byte_count(agent_definition_bytes, "agent_definition_bytes")
    _byte_count(diff_bytes, "diff_bytes")
    _byte_count(boilerplate_bytes, "boilerplate_bytes")
    _required_text(lane, "lane")
    _required_text(chunk_id, "chunk_id")
    _required_text(node_id, "node_id")
    _required_text(host, "host")
    _required_text(requested_provider, "requested_provider")
    _required_text(attempted_provider, "attempted_provider")
    _required_text(implemented_by, "implemented_by")
    _required_text(provider, "provider")
    _required_text(model, "model")
    if type(attempt) is not int or attempt < 1:
        raise ValueError("lane input bytes: invalid attempt")
    if type(duration_seconds) not in (int, float) or duration_seconds < 0:
        raise ValueError("lane input bytes: invalid duration_seconds")
    if type(duration_seconds) is float and not math.isfinite(duration_seconds):
        raise ValueError("lane input bytes: invalid duration_seconds")
    return {
        "usage_scope": "attempt",
        "measurement_source": MEASUREMENT_SOURCE,
        "usage_estimated": True,
        "input_usage_count": (
            agent_definition_bytes + diff_bytes + boilerplate_bytes
        ),
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


def _stat_size(path, name):
    try:
        info = os.stat(path)
    except OSError as error:
        raise ValueError(
            "lane input bytes: " + name + " not readable: " + str(path)
            + " (" + (error.strerror or str(error)) + ")"
        ) from None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(
            "lane input bytes: " + name + " is not a regular file: "
            + str(path)
        )
    return info.st_size


def measure_lane_inputs(
    agent_definition_path,
    diff_path,
    boilerplate_paths: list,
    **identity,
) -> dict:
    """Stat the lane inputs and return the attempt-scoped payload.

    Sizes come from ``os.stat().st_size`` -- no file content enters the
    process.  Live symlinks are followed (``os.stat`` semantics).
    Missing paths, directories passed where a file is expected, dangling
    symlinks, and permission-denied files raise ``ValueError`` naming
    the path; there is never a silent ``0``.  Repeated boilerplate paths
    count once per occurrence.  ``identity`` is forwarded verbatim to
    :func:`estimate_lane_input_bytes`.
    """
    agent_definition_bytes = _stat_size(agent_definition_path, "agent definition")
    diff_bytes = _stat_size(diff_path, "diff")
    boilerplate_bytes = sum(
        _stat_size(path, "boilerplate") for path in boilerplate_paths
    )
    return estimate_lane_input_bytes(
        agent_definition_bytes=agent_definition_bytes,
        diff_bytes=diff_bytes,
        boilerplate_bytes=boilerplate_bytes,
        **identity,
    )
