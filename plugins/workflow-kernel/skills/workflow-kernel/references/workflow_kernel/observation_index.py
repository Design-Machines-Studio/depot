"""Strict, deterministic validation for the observation-index-v1 sidecar."""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import math
import re
from typing import Callable, Mapping

from .redaction import normalize_evidence_reference


OBSERVATION_INDEX_SCHEMA_VERSION = 1
OBSERVATION_INDEX_CONTRACT = "observation-index-v1"
MAX_INDEX_BYTES = 262_144
MAX_SOURCES = 64
MAX_PLUGINS = 64
MAX_IDENTITIES = 1_024
MAX_MODELS = 256
MAX_ARTIFACTS = 256
MAX_CANDIDATES = 256
MAX_TEXT = 4_096

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_MEDIA_TYPE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/"
    r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}\Z"
)
_SOURCE_ROLES = frozenset({
    "producer", "lifecycle", "receipts", "attempts", "metrics", "cost",
    "verification", "reconciliation", "provenance", "findings",
    "contributions", "artifact",
})
_UNAVAILABLE_REASONS = frozenset({
    "not_reported", "not_applicable", "unsupported_by_harness",
    "source_missing", "source_stale", "consumer_not_defined",
})
_FRESHNESS = frozenset({"fresh", "stale", "unknown"})
_DISPOSITIONS = frozenset({"accepted", "rejected"})

_TOP_FIELDS = frozenset({
    "schema_version", "contract", "producer", "run", "sources",
    "observations", "emitted_at", "digest",
})
_PRODUCER_FIELDS = frozenset({
    "name", "version", "execution_profile", "source_digest",
})
_SOURCE_FIELDS = frozenset({
    "role", "reference", "digest", "media_type", "size_bytes",
    "source_timestamp", "observed_at", "maximum_age_seconds", "freshness",
    "freshness_reason",
})
_RUN_FIELDS = frozenset({
    "run_id", "session_id", "attempt_ids", "workflow_node_ids", "action_ids",
})
_OBSERVATION_FIELDS = frozenset({
    "plugins", "objective", "budget", "completion_contract", "models",
    "usage", "cost", "verifier", "artifacts", "recovery", "supervision",
    "candidates", "next_action",
})
_USAGE_FIELDS = frozenset({
    "input_tokens", "output_tokens", "cache_read_tokens",
    "cache_write_tokens", "reasoning_tokens", "duration_seconds",
    "model_call_count", "tool_call_count",
})
_PROVENANCE_FIELDS = frozenset({"source_digest", "observed_at"})


def _exact(value: object, fields: frozenset[str], label: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(label + " fields mismatch")
    return value


def _text(value: object, label: str, *, identifier: bool = False) -> str:
    if type(value) is not str or not value or len(value) > MAX_TEXT:
        raise ValueError(label + " is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(label + " contains control characters")
    if identifier and _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(label + " is not a bounded identifier")
    return value


def _digest(value: object, label: str = "digest") -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError(label + " is not canonical sha256")
    return value


def _timestamp(value: object, label: str) -> datetime:
    text = _text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(label + " is invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(label + " must include a timezone")
    return parsed


def _safe_reference(value: object, label: str) -> str:
    reference = _text(value, label)
    try:
        normalized = normalize_evidence_reference(reference)
    except ValueError:
        raise ValueError(label + " is unsafe") from None
    if normalized != reference:
        raise ValueError(label + " must be a run-relative or content reference")
    return reference


def _nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(label + " must be a non-negative integer")
    return value


def _nonnegative_number(value: object, label: str) -> float | int:
    if (
        type(value) not in (int, float) or type(value) is bool
        or value < 0 or not math.isfinite(value)
    ):
        raise ValueError(label + " must be a finite non-negative number")
    return value


def _provenance(value: object, source_digests: frozenset[str], label: str) -> None:
    provenance = _exact(value, _PROVENANCE_FIELDS, label + " provenance")
    if _digest(provenance["source_digest"], label + " source digest") not in source_digests:
        raise ValueError(label + " provenance source is not bound")
    _timestamp(provenance["observed_at"], label + " observed_at")


def _fact(
    value: object,
    source_digests: frozenset[str],
    label: str,
    validate_value: Callable[[object, str], object],
) -> object | None:
    if type(value) is not dict:
        raise ValueError(label + " must be an availability object")
    availability = value.get("availability")
    if availability == "available":
        record = _exact(
            value, frozenset({"availability", "value", "provenance"}), label,
        )
        validate_value(record["value"], label + " value")
        _provenance(record["provenance"], source_digests, label)
        return record["value"]
    if availability == "unavailable":
        record = _exact(
            value, frozenset({"availability", "value", "reason"}), label,
        )
        if record["value"] is not None:
            raise ValueError(label + " unavailable value must be null")
        if record["reason"] not in _UNAVAILABLE_REASONS:
            raise ValueError(label + " unavailable reason is unknown")
        return None
    raise ValueError(label + " availability is unknown")


def _string(value: object, label: str) -> str:
    return _text(value, label)


def _identifier(value: object, label: str) -> str:
    return _text(value, label, identifier=True)


def _identifier_list(value: object, label: str) -> list:
    if type(value) is not list or len(value) > MAX_IDENTITIES:
        raise ValueError(label + " must be a bounded list")
    seen = set()
    for item in value:
        identifier = _identifier(item, label + " item")
        if identifier in seen:
            raise ValueError(label + " contains duplicates")
        seen.add(identifier)
    return value


def _reference(value: object, label: str) -> str:
    return _safe_reference(value, label)


def _source(value: object) -> dict:
    source = _exact(value, _SOURCE_FIELDS, "source")
    if source["role"] not in _SOURCE_ROLES:
        raise ValueError("source role is unknown")
    _safe_reference(source["reference"], "source reference")
    _digest(source["digest"], "source digest")
    if type(source["media_type"]) is not str or _MEDIA_TYPE.fullmatch(source["media_type"]) is None:
        raise ValueError("source media_type is invalid")
    _nonnegative_int(source["size_bytes"], "source size_bytes")
    source_time = _timestamp(source["source_timestamp"], "source timestamp")
    observed_time = _timestamp(source["observed_at"], "source observed_at")
    if source_time > observed_time:
        raise ValueError("source timestamp is after observation")
    maximum_age = source["maximum_age_seconds"]
    if source["freshness"] not in _FRESHNESS:
        raise ValueError("source freshness is unknown")
    reason = source["freshness_reason"]
    if source["freshness"] == "fresh":
        if type(maximum_age) is not int or maximum_age < 0 or reason is not None:
            raise ValueError("fresh source requires a maximum age and no reason")
        if (observed_time - source_time).total_seconds() > maximum_age:
            raise ValueError("fresh source exceeds its declared maximum age")
    elif source["freshness"] == "stale":
        if (
            type(maximum_age) is not int or maximum_age < 0
            or reason != "age_exceeded"
            or (observed_time - source_time).total_seconds() <= maximum_age
        ):
            raise ValueError("stale source contradicts its declared maximum age")
    elif maximum_age is not None or reason not in {"not_reported", "clock_unknown"}:
        raise ValueError("unknown freshness requires no maximum age and a closed reason")
    return source


def _plugin_list(value: object, label: str) -> list:
    if type(value) is not list or len(value) > MAX_PLUGINS:
        raise ValueError(label + " must be a bounded list")
    names = set()
    for item in value:
        plugin = _exact(
            item, frozenset({"name", "version", "digest"}), "plugin",
        )
        name = _identifier(plugin["name"], "plugin name")
        if name in names:
            raise ValueError("plugin names must be unique")
        names.add(name)
        _identifier(plugin["version"], "plugin version")
        _digest(plugin["digest"], "plugin digest")
    return value


def _model_fact(value: object, sources: frozenset[str], label: str) -> object | None:
    return _fact(value, sources, label, _string)


def _model_list(value: object, label: str, sources: frozenset[str]) -> list:
    if type(value) is not list or len(value) > MAX_MODELS:
        raise ValueError(label + " must be a bounded list")
    fields = frozenset({
        "requested_model", "attempted_model", "served_model", "provider",
        "routing_rationale", "fallback_reason",
    })
    for index, item in enumerate(value):
        model = _exact(item, fields, "model observation")
        prefix = f"{label}[{index}]"
        requested = _model_fact(model["requested_model"], sources, prefix + " requested_model")
        attempted = _model_fact(model["attempted_model"], sources, prefix + " attempted_model")
        served = _model_fact(model["served_model"], sources, prefix + " served_model")
        _model_fact(model["provider"], sources, prefix + " provider")
        _model_fact(model["routing_rationale"], sources, prefix + " routing_rationale")
        fallback = _model_fact(model["fallback_reason"], sources, prefix + " fallback_reason")
        if None not in (requested, attempted, served):
            changed = requested != attempted or attempted != served
            if changed and fallback is None:
                raise ValueError("model fallback requires an available reason")
            if not changed and fallback is not None:
                raise ValueError("unchanged model route cannot claim fallback")
    return value


def _artifact_descriptor(value: object, label: str) -> dict:
    artifact = _exact(
        value,
        frozenset({"handle", "reference", "digest", "media_type", "size_bytes", "preview"}),
        label,
    )
    _identifier(artifact["handle"], label + " handle")
    _safe_reference(artifact["reference"], label + " reference")
    _digest(artifact["digest"], label + " digest")
    if type(artifact["media_type"]) is not str or _MEDIA_TYPE.fullmatch(artifact["media_type"]) is None:
        raise ValueError(label + " media_type is invalid")
    _nonnegative_int(artifact["size_bytes"], label + " size_bytes")
    preview = artifact["preview"]
    if type(preview) is not dict:
        raise ValueError(label + " preview must be an availability object")
    if preview.get("availability") == "available":
        _exact(
            preview,
            frozenset({"availability", "reference", "digest", "media_type", "size_bytes"}),
            label + " preview",
        )
        _safe_reference(preview["reference"], label + " preview reference")
        _digest(preview["digest"], label + " preview digest")
        if type(preview["media_type"]) is not str or _MEDIA_TYPE.fullmatch(preview["media_type"]) is None:
            raise ValueError(label + " preview media_type is invalid")
        _nonnegative_int(preview["size_bytes"], label + " preview size_bytes")
    elif preview.get("availability") == "unavailable":
        _exact(preview, frozenset({"availability", "reference", "reason"}), label + " preview")
        if preview["reference"] is not None or preview["reason"] not in _UNAVAILABLE_REASONS:
            raise ValueError(label + " unavailable preview is invalid")
    else:
        raise ValueError(label + " preview availability is unknown")
    return artifact


def _artifact_list(value: object, label: str) -> list:
    if type(value) is not list or len(value) > MAX_ARTIFACTS:
        raise ValueError(label + " must be a bounded list")
    handles = set()
    for index, item in enumerate(value):
        artifact = _artifact_descriptor(item, f"{label}[{index}]")
        if artifact["handle"] in handles:
            raise ValueError(label + " handles must be unique")
        handles.add(artifact["handle"])
    return value


def _verifier(value: object, label: str) -> dict:
    verifier = _exact(value, frozenset({"result", "evidence_references"}), label)
    if verifier["result"] not in {"passed", "failed", "inconclusive"}:
        raise ValueError(label + " result is unknown")
    refs = verifier["evidence_references"]
    if type(refs) is not list or not refs or len(refs) > 64:
        raise ValueError(label + " evidence must be a bounded non-empty list")
    for ref in refs:
        _safe_reference(ref, label + " evidence reference")
    if len(set(refs)) != len(refs):
        raise ValueError(label + " evidence contains duplicates")
    return verifier


def _recovery(value: object, label: str) -> dict:
    record = _exact(value, frozenset({"failure_signature", "recovery_decision"}), label)
    _digest(record["failure_signature"], label + " failure_signature")
    _identifier(record["recovery_decision"], label + " recovery_decision")
    return record


def _supervision(value: object, label: str) -> dict:
    record = _exact(value, frozenset({"stagnation", "intervention"}), label)
    if type(record["stagnation"]) is not bool:
        raise ValueError(label + " stagnation must be boolean")
    _identifier(record["intervention"], label + " intervention")
    return record


def _score(value: object, sources: frozenset[str], label: str) -> None:
    _fact(value, sources, label, _nonnegative_number)


def _candidate_list(value: object, label: str, sources: frozenset[str]) -> list:
    if type(value) is not list or len(value) > MAX_CANDIDATES:
        raise ValueError(label + " must be a bounded list")
    ids = set()
    fields = frozenset({"candidate_id", "parent_ids", "score", "disposition", "provenance"})
    for item in value:
        candidate = _exact(item, fields, "candidate")
        candidate_id = _identifier(candidate["candidate_id"], "candidate id")
        if candidate_id in ids:
            raise ValueError("candidate ids must be unique")
        ids.add(candidate_id)
        _identifier_list(candidate["parent_ids"], "candidate parent_ids")
        _score(candidate["score"], sources, "candidate score")
        if candidate["disposition"] not in _DISPOSITIONS:
            raise ValueError("candidate disposition is unknown")
        _provenance(candidate["provenance"], sources, "candidate")
    return value


def _cost(value: object, sources: frozenset[str]) -> None:
    if type(value) is not dict:
        raise ValueError("cost must be an object")
    status = value.get("status")
    if status == "measured":
        cost = _exact(
            value,
            frozenset({"status", "value_usd", "measurement_reference", "provenance"}),
            "measured cost",
        )
        _nonnegative_number(cost["value_usd"], "measured cost value")
        _safe_reference(cost["measurement_reference"], "measurement reference")
        _provenance(cost["provenance"], sources, "measured cost")
        return
    if status == "imputed":
        cost = _exact(
            value,
            frozenset({
                "status", "value_usd", "matrix_snapshot", "matrix_digest",
                "basis", "provenance",
            }),
            "imputed cost",
        )
        _nonnegative_number(cost["value_usd"], "imputed cost value")
        if type(cost["matrix_snapshot"]) is not str:
            raise ValueError("matrix snapshot is invalid")
        try:
            date.fromisoformat(cost["matrix_snapshot"])
        except ValueError:
            raise ValueError("matrix snapshot is invalid") from None
        _digest(cost["matrix_digest"], "matrix digest")
        _text(cost["basis"], "imputation basis", identifier=True)
        _provenance(cost["provenance"], sources, "imputed cost")
        return
    if status == "unavailable":
        cost = _exact(value, frozenset({"status", "value_usd", "reason"}), "unavailable cost")
        if cost["value_usd"] is not None or cost["reason"] not in _UNAVAILABLE_REASONS:
            raise ValueError("unavailable cost must be null with a closed reason")
        return
    raise ValueError("cost status is unknown")


def canonical_observation_index_bytes(index: Mapping[str, object], *, include_digest: bool = True) -> bytes:
    """Return deterministic UTF-8 JSON bytes for an index mapping."""
    if type(index) is not dict:
        raise ValueError("observation index is not an object")
    value = dict(index)
    if not include_digest:
        value.pop("digest", None)
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def observation_index_digest(index: Mapping[str, object]) -> str:
    """Compute the canonical digest over the document without ``digest``."""
    return "sha256:" + hashlib.sha256(
        canonical_observation_index_bytes(index, include_digest=False)
    ).hexdigest()


def compose_observation_index(document: Mapping[str, object]) -> dict:
    """Copy, digest, and validate one explicitly typed observation document.

    The caller remains responsible for translating its canonical receipts into
    the shared typed shape. This composer never guesses producer identity,
    parses transcripts, or reads referenced artifacts.
    """
    if type(document) is not dict:
        raise ValueError("observation index input is not an object")
    try:
        candidate = json.loads(json.dumps(
            document, ensure_ascii=False, allow_nan=False,
        ))
    except (TypeError, ValueError, RecursionError):
        raise ValueError("observation index input is not bounded JSON") from None
    if candidate.get("digest") is None:
        candidate["digest"] = observation_index_digest(candidate)
    validate_observation_index(candidate)
    return candidate


def validate_observation_index(index: Mapping[str, object]) -> None:
    """Validate one complete observation-index-v1 mapping, failing closed."""
    if type(index) is not dict:
        raise ValueError("observation index is not an object")
    if len(canonical_observation_index_bytes(index)) > MAX_INDEX_BYTES:
        raise ValueError("observation index exceeds byte limit")
    if index.get("schema_version") != OBSERVATION_INDEX_SCHEMA_VERSION:
        raise ValueError("unsupported observation index schema version")
    _exact(index, _TOP_FIELDS, "observation index")
    if index["contract"] != OBSERVATION_INDEX_CONTRACT:
        raise ValueError("observation index contract is unknown")
    emitted_at = _timestamp(index["emitted_at"], "emitted_at")

    raw_sources = index["sources"]
    if type(raw_sources) is not list or not raw_sources or len(raw_sources) > MAX_SOURCES:
        raise ValueError("sources must be a bounded non-empty list")
    sources = [_source(value) for value in raw_sources]
    digests = [source["digest"] for source in sources]
    references = [source["reference"] for source in sources]
    if len(set(digests)) != len(digests) or len(set(references)) != len(references):
        raise ValueError("source bindings are ambiguous")
    source_digests = frozenset(digests)
    producer_sources = [source for source in sources if source["role"] == "producer"]
    if len(producer_sources) != 1:
        raise ValueError("exactly one producer source is required")
    if any(_timestamp(source["observed_at"], "source observed_at") > emitted_at for source in sources):
        raise ValueError("source observation cannot be after index emission")

    producer = _exact(index["producer"], _PRODUCER_FIELDS, "producer")
    _identifier(producer["name"], "producer name")
    _identifier(producer["version"], "producer version")
    _identifier(producer["execution_profile"], "producer execution_profile")
    producer_digest = _digest(producer["source_digest"], "producer source_digest")
    if producer_digest != producer_sources[0]["digest"]:
        raise ValueError("producer identity is not bound to the producer source")

    run = _exact(index["run"], _RUN_FIELDS, "run")
    _identifier(run["run_id"], "run_id")
    _fact(run["session_id"], source_digests, "session_id", _identifier)
    _fact(run["attempt_ids"], source_digests, "attempt_ids", _identifier_list)
    _fact(run["workflow_node_ids"], source_digests, "workflow_node_ids", _identifier_list)
    _fact(run["action_ids"], source_digests, "action_ids", _identifier_list)

    observations = _exact(index["observations"], _OBSERVATION_FIELDS, "observations")
    _fact(observations["plugins"], source_digests, "plugins", _plugin_list)
    _fact(observations["objective"], source_digests, "objective", _string)
    _fact(observations["budget"], source_digests, "budget", _reference)
    _fact(observations["completion_contract"], source_digests, "completion_contract", _reference)
    _fact(
        observations["models"], source_digests, "models",
        lambda value, label: _model_list(value, label, source_digests),
    )
    usage = _exact(observations["usage"], _USAGE_FIELDS, "usage")
    for field in (
        "input_tokens", "output_tokens", "cache_read_tokens",
        "cache_write_tokens", "reasoning_tokens", "model_call_count",
        "tool_call_count",
    ):
        _fact(usage[field], source_digests, "usage " + field, _nonnegative_int)
    _fact(
        usage["duration_seconds"], source_digests, "usage duration_seconds",
        _nonnegative_number,
    )
    _cost(observations["cost"], source_digests)
    _fact(observations["verifier"], source_digests, "verifier", _verifier)
    _fact(observations["artifacts"], source_digests, "artifacts", _artifact_list)
    _fact(observations["recovery"], source_digests, "recovery", _recovery)
    _fact(observations["supervision"], source_digests, "supervision", _supervision)
    _fact(
        observations["candidates"], source_digests, "candidates",
        lambda value, label: _candidate_list(value, label, source_digests),
    )
    _fact(observations["next_action"], source_digests, "next_action", _string)

    _digest(index["digest"], "observation index digest")
    if index["digest"] != observation_index_digest(index):
        raise ValueError("observation index digest mismatch")


__all__ = [
    "MAX_INDEX_BYTES", "OBSERVATION_INDEX_CONTRACT",
    "OBSERVATION_INDEX_SCHEMA_VERSION", "canonical_observation_index_bytes",
    "compose_observation_index", "observation_index_digest",
    "validate_observation_index",
]
