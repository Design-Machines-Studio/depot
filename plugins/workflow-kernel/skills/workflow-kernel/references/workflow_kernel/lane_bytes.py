"""Deterministic per-lane input-bytes accounting.

Claude Code subagent and Codex CLI lanes expose no token capture point at
all -- no hook, wrapper, or receipt surface reports per-lane counts, and
building one is out of depot's control.  The measurement currency for
those rails is deterministic INPUT BYTES: the agent definition, the diff
slice, and the boilerplate a lane is fed are computable by code even when
what the provider meters is not.  This module is that calculator, so
every review lane gets an attempt-scoped row with honest
``usage_estimated: true`` provenance instead of a blank.  The identity
half of the payload comes from :mod:`workflow_kernel._usage_identity`,
shared with ``openrouter_usage``, so
``workflow_kernel.pipeline_adapter.translate_pipeline_receipts`` and
:class:`workflow_kernel.metrics.MetricsAggregator` consume both producers
uniformly.

Honesty rules:

* Bytes are bytes.  They are reported in ``input_bytes``, never in
  ``input_usage_count``.  Those two fields carry different units and the
  aggregator totals them separately; nothing anywhere converts between
  them or compares them.  A reader who sees ``input_bytes`` cannot
  mistake it for a token count, which is the whole reason the field
  exists.
* ``input_bytes`` is a PRESENT integer; a zero-length input contributes
  ``0``, which is a real measurement, not an omission.  Every other
  counter and ``cost_usd`` are OMITTED -- never present with ``None``
  and never synthesized -- because ``metrics._number`` raises on a
  present-null numeric and ``cost_summary`` gates on key presence, so
  absence is the only honest spelling of "not measured".
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

import os
import stat

from ._usage_identity import AttemptContext, ProviderAttribution, build_attempt_identity


MEASUREMENT_SOURCE = "estimated_input_bytes"
_PREFIX = "lane input bytes"


def _byte_count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(_PREFIX + ": invalid " + name)
    return value


def estimate_lane_input_bytes(
    *,
    agent_definition_bytes: int,
    diff_bytes: int,
    boilerplate_bytes: int,
    context: AttemptContext,
    attribution: ProviderAttribution,
) -> dict:
    """Build an attempt-scoped usage payload from deterministic bytes.

    The identity half is built and validated by
    :func:`workflow_kernel._usage_identity.build_attempt_identity` -- the same
    call ``openrouter_usage`` makes, so both producers emit an identical
    identity shape.  The measurement is ``input_bytes``: the byte sum, always
    present as an integer, with ``measurement_source: "estimated_input_bytes"``
    and ``usage_estimated: True``.  Every token counter and ``cost_usd`` are
    ABSENT, never ``None`` and never ``0``.
    """
    _byte_count(agent_definition_bytes, "agent_definition_bytes")
    _byte_count(diff_bytes, "diff_bytes")
    _byte_count(boilerplate_bytes, "boilerplate_bytes")
    payload = build_attempt_identity(_PREFIX, context, attribution)
    payload["measurement_source"] = MEASUREMENT_SOURCE
    payload["usage_estimated"] = True
    payload["input_bytes"] = (
        agent_definition_bytes + diff_bytes + boilerplate_bytes
    )
    return payload


def _stat_size(path, name):
    try:
        info = os.stat(path)
    except OSError as error:
        raise ValueError(
            _PREFIX + ": " + name + " not readable: " + str(path)
            + " (" + (error.strerror or str(error)) + ")"
        ) from None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(
            _PREFIX + ": " + name + " is not a regular file: " + str(path)
        )
    return info.st_size


def measure_lane_inputs(
    agent_definition_path,
    diff_path,
    boilerplate_paths: list,
    *,
    context: AttemptContext,
    attribution: ProviderAttribution,
) -> dict:
    """Stat the lane inputs and return the attempt-scoped payload.

    Sizes come from ``os.stat().st_size`` -- no file content enters the
    process.  Live symlinks are followed (``os.stat`` semantics).
    Missing paths, directories passed where a file is expected, dangling
    symlinks, and permission-denied files raise ``ValueError`` naming
    the path; there is never a silent ``0``.  Repeated boilerplate paths
    count once per occurrence.  ``context`` and ``attribution`` are forwarded
    to :func:`estimate_lane_input_bytes`, which validates them.
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
        context=context,
        attribution=attribution,
    )
