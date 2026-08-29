#!/usr/bin/env python3
"""Deterministic catalog, production-run, and benchmark intelligence for Depot.

The command deliberately separates facts from policy:

* ``catalog-refresh`` compares an OpenRouter catalog snapshot with the checked-in
  matrix and can refresh existing exact entries. It never admits a new model or
  changes role routing.
* ``report`` aggregates repository-owned run-cost summaries, workflow metrics,
  and Depot role benchmark results. It reads normalized editorial output only
  to recompute a blinded human-rubric digest and never publishes that content.

Scheduled tasks use this command so daily and weekly runs share one evidence
contract instead of reconstructing ad-hoc jq pipelines.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = (
    REPO_ROOT
    / "plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
)
DEFAULT_RUN_ROOTS = (REPO_ROOT / "plans", REPO_ROOT / ".workflow-kernel" / "runs")
DEFAULT_ROLE_POLICY = (
    REPO_ROOT / "plugins/model-router/skills/model-router/references/role-policy.json"
)
DEFAULT_BENCHMARK_SUITE = (
    REPO_ROOT
    / "plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json"
)


class IntelligenceError(ValueError):
    """Raised when evidence is malformed or unsafe to interpret."""


def load_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink():
        raise IntelligenceError(f"regular JSON file required: {path}")
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise IntelligenceError(f"invalid JSON: {path}: {exc}") from exc


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def matrix_json(data: Any) -> str:
    """Preserve the matrix's reviewed field order instead of churning every key."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content)
    temporary.replace(path)


def parse_observed_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).astimezone()
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise IntelligenceError("--observed-at must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IntelligenceError("--observed-at must include a timezone offset")
    return parsed


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def integer(value: Any) -> int | None:
    parsed = number(value)
    if parsed is None or not parsed.is_integer():
        return None
    return int(parsed)


def per_million(value: Any) -> float | None:
    parsed = number(value)
    return None if parsed is None else round(parsed * 1_000_000, 12)


def modality_lists(catalog_model: dict[str, Any]) -> tuple[list[str], list[str]]:
    architecture = catalog_model.get("architecture")
    if not isinstance(architecture, dict):
        return [], []
    inputs = architecture.get("input_modalities")
    outputs = architecture.get("output_modalities")
    return (
        sorted(item for item in inputs if isinstance(item, str))
        if isinstance(inputs, list)
        else [],
        sorted(item for item in outputs if isinstance(item, str))
        if isinstance(outputs, list)
        else [],
    )


def normalized_pricing(catalog_model: dict[str, Any]) -> dict[str, Any]:
    pricing = catalog_model.get("pricing")
    pricing = pricing if isinstance(pricing, dict) else {}
    result: dict[str, Any] = {
        "input_usd_per_m": per_million(pricing.get("prompt")),
        "output_usd_per_m": per_million(pricing.get("completion")),
        "cache_read_usd_per_m": per_million(pricing.get("input_cache_read")),
        "cache_write_usd_per_m": per_million(pricing.get("input_cache_write")),
        "web_search_usd_per_request": number(pricing.get("web_search")),
    }
    overrides = pricing.get("overrides")
    if isinstance(overrides, list):
        normalized_overrides = []
        for override in overrides:
            if not isinstance(override, dict):
                continue
            normalized_overrides.append(
                {
                    "min_prompt_tokens": integer(override.get("min_prompt_tokens")),
                    "prompt": per_million(override.get("prompt")),
                    "completion": per_million(override.get("completion")),
                    "input_cache_read": per_million(override.get("input_cache_read")),
                    "input_cache_write": per_million(override.get("input_cache_write")),
                }
            )
        result["pricing_overrides"] = normalized_overrides or None
    else:
        result["pricing_overrides"] = None
    return result


def catalog_projection(catalog_model: dict[str, Any]) -> dict[str, Any]:
    parameters = catalog_model.get("supported_parameters")
    parameters = sorted(item for item in parameters if isinstance(item, str)) if isinstance(parameters, list) else []
    inputs, outputs = modality_lists(catalog_model)
    top_provider = catalog_model.get("top_provider")
    top_provider = top_provider if isinstance(top_provider, dict) else {}
    reasoning = catalog_model.get("reasoning")
    reasoning = reasoning if isinstance(reasoning, dict) else None
    projection: dict[str, Any] = {
        "catalog_name": catalog_model.get("name"),
        "canonical_slug": catalog_model.get("canonical_slug"),
        "catalog_status": "available",
        "context_tokens": integer(catalog_model.get("context_length")),
        "top_provider_context_tokens": integer(top_provider.get("context_length")),
        "top_provider_max_completion_tokens": integer(top_provider.get("max_completion_tokens")),
        "top_provider_is_moderated": top_provider.get("is_moderated")
        if isinstance(top_provider.get("is_moderated"), bool)
        else None,
        "per_request_limits": catalog_model.get("per_request_limits"),
        "input_modalities": inputs,
        "output_modalities": outputs,
        "supported_parameters": parameters,
        "supports_tools": "tools" in parameters,
        "supports_reasoning": "reasoning" in parameters or reasoning is not None,
        "supports_reasoning_effort": "reasoning_effort" in parameters,
        "supports_structured_outputs": "structured_outputs" in parameters,
        "reasoning": reasoning,
        "default_parameters": catalog_model.get("default_parameters")
        if isinstance(catalog_model.get("default_parameters"), dict)
        else {},
    }
    projection.update(normalized_pricing(catalog_model))
    return projection


def materially_different(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return not math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-6)
    if isinstance(left, list) and isinstance(right, list):
        if all(isinstance(item, str) for item in left + right):
            return sorted(left) != sorted(right)
        if len(left) != len(right):
            return True
        return any(materially_different(a, b) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        keys = set(left) | set(right)
        return any(
            materially_different(left.get(key), right.get(key)) for key in keys
        )
    return left != right


def eligible_new_candidate(model: dict[str, Any]) -> bool:
    slug = model.get("id")
    projection = catalog_projection(model)
    input_price = projection["input_usd_per_m"]
    output_price = projection["output_usd_per_m"]
    return bool(
        isinstance(slug, str)
        and slug
        and not slug.startswith("~")
        and not slug.startswith("anthropic/")
        and not slug.startswith("openrouter/")
        and ":" not in slug
        and "text" in projection["input_modalities"]
        and projection["supports_tools"]
        and projection["supports_structured_outputs"]
        and input_price is not None
        and output_price is not None
        and input_price > 0
        and output_price > 0
    )


def catalog_refresh(args: argparse.Namespace) -> int:
    catalog_path = Path(args.catalog).resolve()
    matrix_path = Path(args.matrix).resolve()
    catalog = load_json(catalog_path)
    matrix = load_json(matrix_path)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("data"), list):
        raise IntelligenceError("catalog must contain a data array")
    if not isinstance(matrix, dict) or not isinstance(matrix.get("models"), list):
        raise IntelligenceError("matrix must contain a models array")

    observed = parse_observed_at(args.observed_at)
    observed_at = observed.isoformat(timespec="seconds")
    expires_at = (observed + timedelta(minutes=int(matrix.get("freshness_rule_minutes", 15)))).isoformat(timespec="seconds")
    snapshot_date = observed.date().isoformat()
    catalog_digest = sha256_bytes(catalog_path.read_bytes())
    live_models = {
        item["id"]: item
        for item in catalog["data"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    matrix_slugs = {
        item.get("slug")
        for item in matrix["models"]
        if isinstance(item, dict) and isinstance(item.get("slug"), str)
    }
    candidate_cutoff = 0.0
    prior_observed = matrix.get("catalog_observed_at")
    if isinstance(prior_observed, str):
        try:
            candidate_cutoff = parse_observed_at(prior_observed).timestamp()
        except IntelligenceError:
            candidate_cutoff = 0.0
    if args.write and candidate_cutoff and observed.timestamp() <= candidate_cutoff:
        raise IntelligenceError(
            "refusing to write a catalog snapshot that is not newer than the matrix"
        )

    changes: list[dict[str, Any]] = []
    updated_models: list[dict[str, Any]] = []
    for existing in matrix["models"]:
        if not isinstance(existing, dict) or not isinstance(existing.get("slug"), str):
            raise IntelligenceError("every matrix model must have a string slug")
        slug = existing["slug"]
        updated = dict(existing)
        live = live_models.get(slug)
        if live is None:
            if existing.get("catalog_status") != "unavailable":
                changes.append({"slug": slug, "field": "catalog_status", "before": existing.get("catalog_status"), "after": "unavailable"})
                updated["catalog_status"] = "unavailable"
        else:
            for field, after in catalog_projection(live).items():
                before = existing.get(field)
                if materially_different(before, after):
                    changes.append({"slug": slug, "field": field, "before": before, "after": after})
                    updated[field] = after
        updated_models.append(updated)

    new_candidates = sorted(
        (
            {
                "slug": model["id"],
                "canonical_slug": model.get("canonical_slug"),
                "name": model.get("name"),
                "created": integer(model.get("created")),
                "context_tokens": integer(model.get("context_length")),
                "input_usd_per_m": normalized_pricing(model)["input_usd_per_m"],
                "output_usd_per_m": normalized_pricing(model)["output_usd_per_m"],
            }
            for model in live_models.values()
            if model["id"] not in matrix_slugs
            and eligible_new_candidate(model)
            and (number(model.get("created")) or 0) > candidate_cutoff
        ),
        key=lambda item: item["created"] or 0,
        reverse=True,
    )[: args.candidate_limit]

    receipt = {
        "schema_version": 1,
        "observedAt": observed_at,
        "expiresAt": expires_at,
        "catalog_source": matrix.get("catalog_source"),
        "catalog_snapshot_sha256": catalog_digest,
        "models_observed": len(live_models),
        "matrix_models": len(updated_models),
        "material_change_count": len(changes),
        "changes": changes,
        "new_candidates": new_candidates,
        "write_applied": bool(args.write and changes),
    }

    if args.write and changes:
        matrix["snapshot_date"] = snapshot_date
        matrix["catalog_observed_at"] = observed_at
        matrix["catalog_snapshot_sha256"] = catalog_digest
        matrix["catalog_snapshot"] = str(catalog_path)
        for model in updated_models:
            model["snapshot_date"] = snapshot_date
        matrix["models"] = updated_models
        write_atomic(matrix_path, matrix_json(matrix))

    if args.output:
        write_atomic(Path(args.output).resolve(), pretty_json(receipt))
    print(pretty_json(receipt), end="")
    return 0


def find_artifacts(roots: Iterable[Path], name: str) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob(name):
            if path.is_file() and not path.is_symlink():
                found.add(path.resolve())
    return sorted(found)


def safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def median(values: Iterable[float | int | None]) -> float | None:
    clean = [float(item) for item in values if item is not None]
    return statistics.median(clean) if clean else None


def add_numeric(target: dict[str, float], key: str, value: Any) -> None:
    parsed = number(value)
    if parsed is not None:
        target[key] += parsed


def production_rollup(roots: list[Path]) -> dict[str, Any]:
    cost_paths = find_artifacts(roots, "run-cost-summary.json")
    metrics_paths = find_artifacts(roots, "metrics.json")
    by_model: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "attempts": 0,
            "duration_seconds": 0.0,
            "input_tokens": 0.0,
            "output_tokens": 0.0,
            "reasoning_tokens": 0.0,
            "input_bytes": 0.0,
            "measured_cost_usd": 0.0,
            "measured_cost_attempts": 0,
            "estimated_attempts": 0,
            "measurement_sources": Counter(),
        }
    )
    by_lane_model: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "attempts": 0,
            "duration_seconds": 0.0,
            "input_tokens": 0.0,
            "output_tokens": 0.0,
            "reasoning_tokens": 0.0,
            "input_bytes": 0.0,
            "measured_cost_usd": 0.0,
            "measured_cost_attempts": 0,
            "estimated_attempts": 0,
        }
    )
    empty_cost_summaries = 0
    malformed: list[str] = []

    for path in cost_paths:
        try:
            artifact = load_json(path)
            lanes = artifact.get("lanes") if isinstance(artifact, dict) else None
            if not isinstance(lanes, list):
                raise IntelligenceError("lanes array missing")
            if not lanes:
                empty_cost_summaries += 1
            for lane in lanes:
                if not isinstance(lane, dict):
                    continue
                model = lane.get("model")
                model_key = model if isinstance(model, str) and model else "unattributed"
                row = by_model[model_key]
                lane_name = lane.get("lane")
                lane_key = lane_name if isinstance(lane_name, str) and lane_name else "unattributed"
                lane_row = by_lane_model[(lane_key, model_key)]
                for target in (row, lane_row):
                    target["attempts"] += 1
                    add_numeric(target, "duration_seconds", lane.get("duration_seconds"))
                    add_numeric(target, "input_tokens", lane.get("input_usage_count"))
                    add_numeric(target, "output_tokens", lane.get("output_usage_count"))
                    add_numeric(target, "reasoning_tokens", lane.get("reasoning_usage_count"))
                    add_numeric(target, "input_bytes", lane.get("input_bytes"))
                cost = number(lane.get("cost_usd"))
                if cost is not None:
                    for target in (row, lane_row):
                        target["measured_cost_usd"] += cost
                        target["measured_cost_attempts"] += 1
                if lane.get("usage_estimated") is True:
                    for target in (row, lane_row):
                        target["estimated_attempts"] += 1
                source = lane.get("measurement_source")
                row["measurement_sources"][source if isinstance(source, str) else "unknown"] += 1
        except IntelligenceError as exc:
            malformed.append(f"{safe_relative(path)}: {exc}")

    quality_by_model: Counter[str] = Counter()
    quality_by_provider: Counter[str] = Counter()
    completion_rates: list[float] = []
    fallback_rates: list[float] = []
    validation_rates: list[float] = []
    canonical_findings = 0
    retries: Counter[str] = Counter()
    metric_models: Counter[str] = Counter()
    metric_providers: Counter[str] = Counter()
    for path in metrics_paths:
        try:
            artifact = load_json(path)
            if not isinstance(artifact, dict):
                raise IntelligenceError("metrics object required")
            for source, target in (
                (artifact.get("finding_contributions_by_model"), quality_by_model),
                (artifact.get("finding_contributions_by_provider"), quality_by_provider),
                (artifact.get("models"), metric_models),
                (artifact.get("providers"), metric_providers),
                (artifact.get("retry_reasons"), retries),
            ):
                if isinstance(source, dict):
                    for key, value in source.items():
                        parsed = integer(value)
                        if isinstance(key, str) and parsed is not None:
                            target[key] += parsed
            for key, target in (
                ("completion_rate", completion_rates),
                ("fallback_rate", fallback_rates),
                ("validation_first_pass_rate", validation_rates),
            ):
                parsed = number(artifact.get(key))
                if parsed is not None:
                    target.append(parsed)
            parsed_findings = integer(artifact.get("canonical_finding_count"))
            if parsed_findings is not None:
                canonical_findings += parsed_findings
        except IntelligenceError as exc:
            malformed.append(f"{safe_relative(path)}: {exc}")

    normalized_models = []
    for model, row in sorted(by_model.items()):
        normalized = dict(row)
        normalized["model"] = model
        normalized["measurement_sources"] = dict(sorted(row["measurement_sources"].items()))
        normalized["finding_contributions"] = quality_by_model.get(model, 0)
        normalized_models.append(normalized)
    normalized_lanes = [
        {"lane": lane, "model": model, **row}
        for (lane, model), row in sorted(by_lane_model.items())
    ]

    return {
        "cost_summary_artifacts": len(cost_paths),
        "metrics_artifacts": len(metrics_paths),
        "empty_cost_summaries": empty_cost_summaries,
        "malformed_artifacts": malformed,
        "by_model": normalized_models,
        "by_lane_model": normalized_lanes,
        "quality": {
            "finding_contributions_by_model": dict(sorted(quality_by_model.items())),
            "finding_contributions_by_provider": dict(sorted(quality_by_provider.items())),
            "canonical_findings": canonical_findings,
            "median_completion_rate": median(completion_rates),
            "median_fallback_rate": median(fallback_rates),
            "median_validation_first_pass_rate": median(validation_rates),
            "retry_reasons": dict(sorted(retries.items())),
            "model_attempt_counts_from_metrics": dict(sorted(metric_models.items())),
            "provider_attempt_counts_from_metrics": dict(sorted(metric_providers.items())),
        },
        "artifact_paths": {
            "run_cost_summaries": [safe_relative(path) for path in cost_paths],
            "metrics": [safe_relative(path) for path in metrics_paths],
        },
    }


def result_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    candidates: set[Path] = set()
    for filename in ("result.json", "prompt.txt", "receipt.json", "output.json"):
        for path in root.rglob(filename):
            if path.is_file() and not path.is_symlink():
                candidates.add(path.parent.resolve())
    return sorted(candidates)


V2_BINDINGS = (
    "suiteRevision",
    "suiteDigest",
    "caseRevision",
    "caseDigest",
    "promptRevision",
    "promptDigest",
    "scorerRevision",
    "scorerDigest",
    "normalizerRevision",
    "normalizerDigest",
)
MODEL_FAILURE_CATEGORIES = {"contract", "mandatory", "semantic", "validation"}
OPERATIONAL_FAILURE_CATEGORIES = {"benchmark", "prompt", "parser", "scorer", "harness", "transport", "identity"}
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


def binding_value(result: dict[str, Any], name: str) -> Any:
    bindings = result.get("evidenceBindings")
    binding = bindings.get(name) if isinstance(bindings, dict) else None
    return binding.get("actual") if isinstance(binding, dict) else None


def result_usage(result: dict[str, Any], receipt: dict[str, Any]) -> dict[str, float | None]:
    result_values = result.get("usage")
    result_values = result_values if isinstance(result_values, dict) else {}
    receipt_values = receipt.get("usage")
    receipt_values = receipt_values if isinstance(receipt_values, dict) else {}

    def usage_number(*names: str) -> float | None:
        for source in (result_values, receipt_values):
            for name in names:
                parsed = number(source.get(name))
                if parsed is not None:
                    return parsed
        return None

    cost_usd = usage_number("cost", "cost_usd")
    if cost_usd is None:
        for source in (result, receipt):
            for name in ("providerBilledCostUsd", "billedCostUsd", "costUsd", "cost_usd"):
                cost_usd = number(source.get(name))
                if cost_usd is not None:
                    break
            if cost_usd is not None:
                break
    return {
        "prompt_tokens": usage_number("prompt_tokens", "input_tokens"),
        "completion_tokens": usage_number("completion_tokens", "output_tokens"),
        "reasoning_tokens": usage_number("reasoning_tokens", "reasoning_output_tokens"),
        "cache_read_tokens": usage_number(
            "cache_read_tokens", "cached_input_tokens", "cached_tokens", "cache_read_input_tokens"
        ),
        "cache_creation_tokens": usage_number(
            "cache_creation_tokens", "cache_write_tokens", "cache_creation_input_tokens"
        ),
        "cost_usd": cost_usd,
    }


def supplied_number(result: dict[str, Any], receipt: dict[str, Any], *names: str) -> float | None:
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    receipt_usage = receipt.get("usage") if isinstance(receipt.get("usage"), dict) else {}
    for source in (result, usage, receipt, receipt_usage):
        for name in names:
            parsed = number(source.get(name))
            if parsed is not None:
                return parsed
    return None


def attempt_order(result: dict[str, Any], receipt: dict[str, Any]) -> tuple[str, float] | None:
    for name in ("attemptIndex", "attemptNumber", "attempt_index", "attempt_number"):
        parsed = number(result.get(name))
        if parsed is None:
            parsed = number(receipt.get(name))
        if parsed is not None:
            return ("index", parsed)
    observed = result.get("observedAt") or receipt.get("observedAt")
    if isinstance(observed, str):
        try:
            parsed_at = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed_at.tzinfo is not None and parsed_at.utcoffset() is not None:
            return ("time", parsed_at.timestamp())
    return None


def failure_category(result: dict[str, Any], compatible: bool, identity_ok: bool) -> str | None:
    failure_class = result.get("failureClass")
    failure_class = failure_class if isinstance(failure_class, str) else ""
    if not compatible:
        return "harness"
    if result.get("benchmarkFault") is True:
        if "prompt" in failure_class:
            return "prompt"
        if "parser" in failure_class or "normalizer" in failure_class:
            return "parser"
        if "scorer" in failure_class:
            return "scorer"
        if "harness" in failure_class or "binding" in failure_class:
            return "harness"
        return "benchmark"
    transport = result.get("transportOutcome")
    if not isinstance(transport, dict) or transport.get("status") != "success":
        return "transport"
    identity = result.get("identityStatus")
    if not isinstance(identity, dict) or identity.get("confidence") != "confirmed" or not identity_ok:
        return "identity"
    if result.get("contractPassed") is not True:
        return "contract"
    if result.get("mandatoryPassed") is not True:
        return "mandatory"
    if result.get("semanticPassed") is not True:
        return "semantic"
    if result.get("validationPassed") is not True:
        return "validation"
    return None


def safe_failure_reason(result: dict[str, Any], receipt: dict[str, Any], category: str | None) -> str | None:
    reasons = result.get("failureReasons")
    if isinstance(reasons, list):
        for reason in reasons:
            if isinstance(reason, str) and reason:
                return reason.replace("\n", " ")[:240]
    for source, name in (
        (result, "failureClass"), (result, "failureReason"),
        (receipt, "failureKind"), (receipt, "failureReason"),
    ):
        reason = source.get(name)
        if isinstance(reason, str) and reason:
            return reason.replace("\n", " ")[:240]
    return category


def retained_attempt(
    directory: Path,
    result: dict[str, Any],
    receipt: dict[str, Any],
    case: dict[str, Any] | None,
    category: str,
) -> dict[str, Any]:
    benchmark = receipt.get("benchmark")
    benchmark = benchmark if isinstance(benchmark, dict) else {}
    transport_outcome = result.get("transportOutcome")
    transport_outcome = transport_outcome if isinstance(transport_outcome, dict) else {}

    def text_value(*values: Any) -> str | None:
        return next((value for value in values if isinstance(value, str) and value), None)

    usage = result_usage(result, receipt)
    case_id = text_value(result.get("caseId"), benchmark.get("caseId"))
    authoritative_role = case.get("role") if isinstance(case, dict) else None
    return {
        "path": str(directory),
        "requested_candidate": text_value(
            result.get("requestedIdentity"), result.get("requestedModel"), receipt.get("requestedModel")
        ),
        "served_identity": text_value(
            result.get("servedIdentity"), result.get("servedModel"), receipt.get("responseModel")
        ),
        "endpoint_provider": text_value(
            result.get("endpointProvider"), result.get("provider"), receipt.get("servingProvider")
        ),
        "billing_mode": text_value(result.get("billingMode"), receipt.get("billingMode")),
        "transport": text_value(result.get("transport"), receipt.get("transport")),
        "role": text_value(authoritative_role, result.get("role"), benchmark.get("role")),
        "reported_role": text_value(result.get("role"), benchmark.get("role")),
        "case_id": case_id,
        "observed_at": text_value(result.get("observedAt"), receipt.get("observedAt")),
        "receipt_outcome": text_value(
            result.get("outcome"), receipt.get("outcome"), transport_outcome.get("status")
        ),
        "duration_seconds": supplied_number(result, receipt, "durationSeconds", "duration_seconds"),
        **usage,
        "provider_billed_cost_usd": usage["cost_usd"],
        "context_tokens": supplied_number(
            result, receipt, "contextTokens", "context_tokens", "inputContextTokens"
        ),
        "tool_calls": supplied_number(result, receipt, "toolCalls", "tool_calls", "toolUseCount"),
        "failure_category": category,
        "failure_reason": safe_failure_reason(result, receipt, category),
        "model_conclusion": None,
    }


def closed_identity_proof(result: dict[str, Any], receipt: dict[str, Any]) -> bool:
    identity = result.get("identityStatus")
    identity = identity if isinstance(identity, dict) else {}
    fallback = result.get("fallback")
    fallback = fallback if isinstance(fallback, dict) else {}
    requested = result.get("requestedIdentity")
    served = result.get("servedIdentity")
    transport = result.get("transport")
    native = transport in {"codex-cli", "claude-cli"}
    accepted_provenance = (
        {"response", "modelUsage-unique-max-output-tokens"} if native else {"response"}
    )
    if not (
        isinstance(requested, str)
        and requested
        and isinstance(served, str)
        and served
        and (native or served == requested)
        and identity.get("confidence") == "confirmed"
        and identity.get("provenance") in accepted_provenance
        and fallback.get("used") is False
        and fallback.get("attemptedIdentity") == served
        and fallback.get("attemptedIdentities") == [served]
        and fallback.get("provenance") == "response_model"
    ):
        return False
    optional_receipt_bindings = {
        "requestedModel": requested,
        "responseModel": served,
        "transport": result.get("transport"),
        "fallbackUsed": False,
        "attemptedModel": served,
        "attemptedModels": [served],
        "attemptProvenance": "response_model",
        "responseModelProvenance": identity.get("provenance"),
    }
    return all(
        name not in receipt or receipt.get(name) == expected
        for name, expected in optional_receipt_bindings.items()
    )


def normalized_output_digest(directory: Path, result: dict[str, Any]) -> tuple[str | None, str | None]:
    output_path = directory / "output.json"
    if not output_path.is_file() or output_path.is_symlink():
        return None, "human rubric normalized output artifact unavailable"
    try:
        normalized = json.loads(output_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, "human rubric normalized output artifact unavailable"
    if not isinstance(normalized, dict):
        return None, "human rubric normalized output artifact unavailable"
    artifact = json.dumps(normalized, indent=2, ensure_ascii=False) + "\n"
    recomputed = sha256_bytes(artifact.encode())
    for name in ("normalizedOutputArtifactSha256", "normalizedOutputDigest"):
        if name not in result:
            continue
        declared = result.get(name)
        if not isinstance(declared, str) or DIGEST_PATTERN.fullmatch(declared) is None:
            return None, "declared normalized output digest syntax invalid"
        if declared.removeprefix("sha256:") != recomputed:
            return None, "declared normalized output digest mismatch"
    return recomputed, None


def human_rubric_evidence(
    directory: Path,
    result: dict[str, Any],
    case: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(case, dict) or case.get("humanRubricRequired") is not True:
        return None, None
    path = directory / "human-rubric.json"
    if not path.exists():
        return None, None
    try:
        receipt = load_json(path)
    except IntelligenceError:
        return None, "malformed human rubric receipt"
    allowed = {
        "blindToCandidate", "caseId", "caseRevision", "criterionScores",
        "observedAt", "outputArtifactSha256", "rubricRevision", "schemaVersion", "suiteId",
    }
    rubric = case.get("humanRubric")
    rubric = rubric if isinstance(rubric, dict) else {}
    criteria = rubric.get("criteria")
    criteria = criteria if isinstance(criteria, list) else []
    criterion_ids = sorted(
        item["id"] for item in criteria
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    )
    scores = receipt.get("criterionScores") if isinstance(receipt, dict) else None
    digest, digest_error = normalized_output_digest(directory, result)
    valid_scores = (
        isinstance(scores, dict)
        and sorted(scores) == criterion_ids
        and all(
            not isinstance(value, bool) and isinstance(value, (int, float)) and 1 <= value <= 5
            for value in scores.values()
        )
    )
    if not isinstance(receipt, dict) or set(receipt) != allowed:
        return None, "malformed or identity-bearing human rubric fields"
    if receipt.get("blindToCandidate") is not True:
        return None, "human rubric is not blinded"
    observed_at = receipt.get("observedAt")
    try:
        observed_valid = bool(
            isinstance(observed_at, str)
            and datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
        )
    except ValueError:
        observed_valid = False
    if receipt.get("schemaVersion") != 1 or not observed_valid:
        return None, "malformed human rubric receipt"
    if (
        receipt.get("suiteId") != result.get("suiteId")
        or receipt.get("caseId") != result.get("caseId")
        or receipt.get("caseRevision") != case.get("revision")
        or receipt.get("rubricRevision") != rubric.get("rubricRevision")
    ):
        return None, "human rubric case or rubric mismatch"
    receipt_digest = receipt.get("outputArtifactSha256")
    if digest_error is not None:
        return None, digest_error
    if not isinstance(receipt_digest, str) or DIGEST_PATTERN.fullmatch(receipt_digest) is None:
        return None, "human rubric output digest syntax invalid"
    if digest is None or receipt_digest.removeprefix("sha256:") != digest:
        return None, "human rubric output digest mismatch"
    if not valid_scores:
        return None, "unknown criterion IDs or invalid criterion scores"
    return {
        "rubric_revision": receipt["rubricRevision"],
        "criterion_scores": dict(sorted(scores.items())),
        "mean_score": sum(float(value) for value in scores.values()) / len(scores),
        "observed_at": receipt["observedAt"],
    }, None


def telemetry_coverage(attempts: list[dict[str, Any]], field: str) -> dict[str, Any]:
    total = len(attempts)
    recorded = sum(item.get(field) is not None for item in attempts)
    return {
        "recorded": recorded,
        "attempts": total,
        "rate": recorded / total if total else None,
    }


def sum_through_valid(attempts: list[dict[str, Any]], field: str) -> float | None:
    if not attempts or any(item.get(field) is None for item in attempts):
        return None
    return sum(float(item[field]) for item in attempts)


def group_rollup(key: tuple[Any, ...], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [item for item in attempts if item["comparable"]]
    validated = [item for item in comparable if item["validated"]]
    model_failures = [
        item for item in comparable if item["failure_category"] in MODEL_FAILURE_CATEGORIES
    ]
    comparable_orders = [item["_order"] for item in comparable]
    ordering_available = bool(comparable) and all(order is not None for order in comparable_orders)
    ordering_available = (
        ordering_available
        and len({order[0] for order in comparable_orders}) == 1
        and len(set(comparable_orders)) == len(comparable_orders)
    )
    ordered_comparable = sorted(comparable, key=lambda item: item["_order"]) if ordering_available else []
    all_orders = [item["_order"] for item in attempts]
    operational_ordering = bool(attempts) and all(order is not None for order in all_orders)
    operational_ordering = (
        operational_ordering
        and len({order[0] for order in all_orders}) == 1
        and len(set(all_orders)) == len(all_orders)
    )
    ordered = sorted(attempts, key=lambda item: item["_order"]) if operational_ordering else []
    first_pass: bool | None = None
    first_validated: dict[str, Any] | None = None
    through_valid: list[dict[str, Any]] = []
    operational_before: dict[str, int] | None = None
    if ordered_comparable:
        first_pass = ordered_comparable[0]["validated"]
        first_validated = next((item for item in ordered_comparable if item["validated"]), None)
    if first_validated is not None:
        first_order = first_validated["_order"]
        through_valid = [
            item for item in ordered_comparable if item["_order"] <= first_order
        ]
        if operational_ordering:
            operational_before = dict(sorted(Counter(
                item["failure_category"] for item in ordered
                if item["_order"] < first_order and item["failure_category"] in OPERATIONAL_FAILURE_CATEGORIES
            ).items()))
    model_rework = (
        sum(item["failure_category"] in MODEL_FAILURE_CATEGORIES for item in through_valid)
        if through_valid else None
    )
    compat_names = (
        "requested_candidate", "transport", "role", "case_id", "case_revision",
        "suite_id", "suite_revision", "suite_digest", "case_digest", "prompt_revision",
        "prompt_digest", "scorer_revision", "scorer_digest", "normalizer_revision",
        "normalizer_digest", "behavior_revision", "behavior_digest",
    )
    providers = Counter(
        item["endpoint_provider"] for item in attempts if item["endpoint_provider"] is not None
    )
    served = Counter(
        item["served_identity"] for item in attempts if item["served_identity"] is not None
    )
    billing_modes = Counter(
        item["billing_mode"] for item in attempts if item["billing_mode"] is not None
    )
    human = [item["human_evidence"] for item in attempts if item["human_evidence"] is not None]
    human_rejections = Counter(
        item["human_rejection"] for item in attempts if item["human_rejection"] is not None
    )
    failure_counts = Counter(
        item["failure_category"] for item in attempts if item["failure_category"] is not None
    )
    return {
        **dict(zip(compat_names, key)),
        "attempts": len(attempts),
        "comparable_attempts": len(comparable),
        "validated_attempts": len(validated),
        "validated_rate": len(validated) / len(comparable) if comparable else None,
        "best_deterministic_quality": max(
            (item["quality_score"] for item in comparable if item["quality_score"] is not None),
            default=None,
        ),
        "validator_passes": sum(item["validation_passed"] is True for item in comparable),
        "model_attributable_failures": len(model_failures),
        "first_pass_validated": first_pass,
        "model_rework_to_valid": model_rework,
        "attempts_to_valid": len(through_valid) if through_valid else None,
        "time_to_first_validated_seconds": sum_through_valid(through_valid, "duration_seconds"),
        "median_duration_seconds": median(item["duration_seconds"] for item in comparable),
        "tokens_to_first_validated": {
            field: sum_through_valid(through_valid, field)
            for field in (
                "prompt_tokens", "completion_tokens", "reasoning_tokens",
                "cache_read_tokens", "cache_creation_tokens",
            )
        },
        "context_to_first_validated": sum_through_valid(through_valid, "context_tokens"),
        "ordering_available": ordering_available,
        "operational_ordering_available": operational_ordering,
        "operational_retries": dict(sorted(Counter(
            item["failure_category"] for item in attempts
            if item["failure_category"] in OPERATIONAL_FAILURE_CATEGORIES
        ).items())),
        "operational_retries_before_valid": operational_before,
        "failure_counts": dict(sorted(failure_counts.items())),
        "telemetry_coverage": {
            field: telemetry_coverage(comparable, field)
            for field in (
                "duration_seconds", "prompt_tokens", "completion_tokens", "reasoning_tokens",
                "cache_read_tokens", "cache_creation_tokens", "context_tokens", "tool_calls",
                "correction_count", "useful_findings", "false_positives",
            )
        },
        "useful_finding_yield": median(item["useful_findings"] for item in comparable),
        "false_positive_yield": median(item["false_positives"] for item in comparable),
        "endpoint_providers": dict(sorted(providers.items())),
        "served_identities": dict(sorted(served.items())),
        "billing_modes": dict(sorted(billing_modes.items())),
        "fallback_attempts": sum(item["fallback_used"] is True for item in attempts),
        "latest_observed_at": max(
            (item["observed_at"] for item in attempts if item["observed_at"] is not None),
            default=None,
        ),
        "editorial_human_evidence": (
            {
                "accepted_receipts": len(human),
                "median_mean_score": median(item["mean_score"] for item in human),
            }
            if human else None
        ),
        "editorial_human_rejections": dict(sorted(human_rejections.items())),
        "attempt_records": [
            {name: value for name, value in item.items() if not name.startswith("_")}
            for item in attempts
        ],
    }


EVALUATOR_COHORT_FIELDS = (
    "suite_id", "suite_revision", "suite_digest", "scorer_revision", "scorer_digest",
    "normalizer_revision", "normalizer_digest", "behavior_revision", "behavior_digest",
)
CASE_BINDING_FIELDS = (
    "case_revision", "case_digest", "prompt_revision", "prompt_digest",
)


def evaluator_cohort_key(group: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(group[name] for name in EVALUATOR_COHORT_FIELDS)


def evaluator_cohort_rollup(
    key: tuple[Any, ...],
    groups: list[dict[str, Any]],
    role_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    comparable_attempts = [
        attempt for group in groups for attempt in group["attempt_records"]
        if attempt["comparable"]
    ]
    first_pass = [
        group["first_pass_validated"] for group in groups
        if group["first_pass_validated"] is not None
    ]
    valid_groups = [group for group in groups if group["attempts_to_valid"] is not None]
    case_coverage = []
    case_binding_consistent = True
    for case in role_cases:
        matching = [group for group in groups if group["case_id"] == case.get("id")]
        binding_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for group in matching:
            if group["comparable_attempts"] > 0:
                binding_groups[tuple(group[name] for name in CASE_BINDING_FIELDS)].append(group)
        if len(binding_groups) > 1:
            case_binding_consistent = False
        case_coverage.append(
            {
                "case_id": case.get("id"),
                "case_revision": case.get("revision"),
                "prompt_revision": case.get("promptRevision"),
                "groups": [
                    {
                        "requested_candidate": group["requested_candidate"],
                        "transport": group["transport"],
                        "case_revision": group["case_revision"],
                        "case_digest": group["case_digest"],
                        "prompt_revision": group["prompt_revision"],
                        "prompt_digest": group["prompt_digest"],
                        "comparable_attempts": group["comparable_attempts"],
                        "validated_attempts": group["validated_attempts"],
                    }
                    for group in matching
                ],
                "comparable_attempts": sum(group["comparable_attempts"] for group in matching),
                "validated_attempts": sum(group["validated_attempts"] for group in matching),
                "case_binding_cohorts": [
                    {
                        **dict(zip(CASE_BINDING_FIELDS, binding)),
                        "comparable_attempts": sum(
                            group["comparable_attempts"] for group in binding_matching
                        ),
                        "validated_attempts": sum(
                            group["validated_attempts"] for group in binding_matching
                        ),
                    }
                    for binding, binding_matching in sorted(
                        binding_groups.items(),
                        key=lambda item: tuple(str(part) for part in item[0]),
                    )
                ],
            }
        )
    return {
        **dict(zip(EVALUATOR_COHORT_FIELDS, key)),
        "case_binding_consistent": case_binding_consistent,
        "complete_case_coverage": case_binding_consistent and bool(case_coverage) and all(
            item["comparable_attempts"] > 0 for item in case_coverage
        ),
        "case_coverage": case_coverage,
        "retained_comparable_attempts": len(comparable_attempts),
        "comparable_attempts": len(comparable_attempts) if case_binding_consistent else None,
        "validated_attempts": (
            sum(group["validated_attempts"] for group in groups)
            if case_binding_consistent else None
        ),
        "best_deterministic_quality": max(
            (group["best_deterministic_quality"] for group in groups if group["best_deterministic_quality"] is not None),
            default=None,
        ) if case_binding_consistent else None,
        "first_pass_validated_rate": (
            sum(first_pass) / len(first_pass)
            if case_binding_consistent and first_pass else None
        ),
        "median_duration_seconds": (
            median(attempt["duration_seconds"] for attempt in comparable_attempts)
            if case_binding_consistent else None
        ),
        "median_time_to_first_validated_seconds": median(
            group["time_to_first_validated_seconds"] for group in valid_groups
        ) if case_binding_consistent else None,
        "median_attempts_to_valid": (
            median(group["attempts_to_valid"] for group in valid_groups)
            if case_binding_consistent else None
        ),
        "median_model_rework_to_valid": median(
            group["model_rework_to_valid"] for group in valid_groups
        ) if case_binding_consistent else None,
        "median_tokens_to_first_validated": {
            field: (
                median(group["tokens_to_first_validated"][field] for group in valid_groups)
                if case_binding_consistent else None
            )
            for field in (
                "prompt_tokens", "completion_tokens", "reasoning_tokens",
                "cache_read_tokens", "cache_creation_tokens",
            )
        },
        "median_context_to_first_validated": median(
            group["context_to_first_validated"] for group in valid_groups
        ) if case_binding_consistent else None,
        "useful_finding_yield": (
            median(group["useful_finding_yield"] for group in groups)
            if case_binding_consistent else None
        ),
        "false_positive_yield": (
            median(group["false_positive_yield"] for group in groups)
            if case_binding_consistent else None
        ),
        "model_failure_counts": dict(sorted(sum(
            (
                Counter({
                    name: count for name, count in group["failure_counts"].items()
                    if name in MODEL_FAILURE_CATEGORIES
                })
                for group in groups
            ),
            Counter(),
        ).items())),
        "operational_retries": dict(sorted(sum(
            (Counter(group["operational_retries"]) for group in groups), Counter()
        ).items())),
        "instrumentation": {
            field: (
                telemetry_coverage(comparable_attempts, field)
                if case_binding_consistent
                else {"recorded": None, "attempts": None, "rate": None}
            )
            for field in (
                "duration_seconds", "prompt_tokens", "completion_tokens", "reasoning_tokens",
                "cache_read_tokens", "cache_creation_tokens", "context_tokens", "tool_calls",
                "correction_count", "useful_findings", "false_positives",
            )
        },
    }


def benchmark_rollup(root: Path | None) -> dict[str, Any]:
    policy = load_json(DEFAULT_ROLE_POLICY)
    suite = load_json(DEFAULT_BENCHMARK_SUITE)
    policy_roles = policy.get("roles") if isinstance(policy, dict) else None
    cases = suite.get("cases") if isinstance(suite, dict) else None
    if not isinstance(policy_roles, dict) or not isinstance(cases, list):
        raise IntelligenceError("role policy and v2 benchmark suite authorities are malformed")
    case_by_id = {
        item["id"]: item for item in cases
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    directories = result_dirs(root) if root is not None else []
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    incomplete: list[dict[str, Any]] = []
    historical_v1: list[dict[str, Any]] = []
    incompatible_v2: list[dict[str, Any]] = []
    recorded_costs: list[float] = []
    expected_behavior = suite.get("behavioralContract")
    expected_behavior = expected_behavior if isinstance(expected_behavior, dict) else {}

    for directory in directories:
        receipt_path = directory / "receipt.json"
        try:
            receipt = load_json(receipt_path) if receipt_path.is_file() else {}
        except IntelligenceError:
            receipt = {}
        receipt = receipt if isinstance(receipt, dict) else {}
        result_path = directory / "result.json"
        if not result_path.is_file():
            benchmark = receipt.get("benchmark")
            benchmark = benchmark if isinstance(benchmark, dict) else {}
            case_id = benchmark.get("caseId")
            case = case_by_id.get(case_id) if isinstance(case_id, str) else None
            category = "transport" if receipt.get("outcome") == "failed" else "harness"
            retained = retained_attempt(directory, {}, receipt, case, category)
            incomplete.append(retained)
            if retained["cost_usd"] is not None:
                recorded_costs.append(retained["cost_usd"])
            continue
        try:
            result = load_json(result_path)
        except IntelligenceError:
            benchmark = receipt.get("benchmark")
            benchmark = benchmark if isinstance(benchmark, dict) else {}
            case_id = benchmark.get("caseId")
            case = case_by_id.get(case_id) if isinstance(case_id, str) else None
            retained = retained_attempt(directory, {}, receipt, case, "parser")
            incomplete.append(retained)
            if retained["cost_usd"] is not None:
                recorded_costs.append(retained["cost_usd"])
            continue
        if not isinstance(result, dict):
            benchmark = receipt.get("benchmark")
            benchmark = benchmark if isinstance(benchmark, dict) else {}
            case_id = benchmark.get("caseId")
            case = case_by_id.get(case_id) if isinstance(case_id, str) else None
            retained = retained_attempt(directory, {}, receipt, case, "parser")
            if retained["failure_reason"] == "parser":
                retained["failure_reason"] = "result object required"
            incomplete.append(retained)
            if retained["cost_usd"] is not None:
                recorded_costs.append(retained["cost_usd"])
            continue
        if result.get("schemaVersion") != 2:
            result_case_id = result.get("caseId")
            case = case_by_id.get(result_case_id) if isinstance(result_case_id, str) else None
            retained = retained_attempt(directory, result, receipt, case, "harness")
            historical_v1.append(
                retained | {
                    "schema_version": result.get("schemaVersion", 1),
                    "parsed": result.get("parsed") if isinstance(result.get("parsed"), bool) else None,
                    "quality_score": number(result.get("qualityScore")),
                    "classification": "historical/incompatible; no model conclusion",
                }
            )
            if retained["cost_usd"] is not None:
                recorded_costs.append(retained["cost_usd"])
            continue

        case_id = result.get("caseId")
        case = case_by_id.get(case_id) if isinstance(case_id, str) else None
        behavior = result.get("behavioralContract")
        behavior = behavior if isinstance(behavior, dict) else {}
        bindings = result.get("evidenceBindings")
        suite_bindings = suite.get("bindings")
        suite_bindings = suite_bindings if isinstance(suite_bindings, dict) else {}
        case_bindings_by_id = suite_bindings.get("cases")
        case_bindings_by_id = case_bindings_by_id if isinstance(case_bindings_by_id, dict) else {}
        case_bindings = case_bindings_by_id.get(case_id)
        case_bindings = case_bindings if isinstance(case_bindings, dict) else {}
        binding_authority = {
            "suiteRevision": suite_bindings.get("suiteRevision"),
            "suiteDigest": suite_bindings.get("suiteDigest"),
            "caseRevision": case_bindings.get("caseRevision"),
            "caseDigest": case_bindings.get("caseDigest"),
            "promptRevision": case_bindings.get("promptRevision"),
            "promptDigest": case_bindings.get("promptDigest"),
            "scorerRevision": case_bindings.get("scorerRevision"),
            "scorerDigest": case_bindings.get("scorerDigest"),
            "normalizerRevision": suite_bindings.get("normalizerRevision"),
            "normalizerDigest": suite_bindings.get("normalizerDigest"),
        }
        bindings_ok = isinstance(bindings, dict) and all(
            authority is not None
            and isinstance(bindings.get(name), dict)
            and bindings[name].get("match") is True
            and bindings[name].get("actual") == authority
            and bindings[name].get("declared") == authority
            for name, authority in binding_authority.items()
        )
        authoritative_role = case.get("role") if isinstance(case, dict) else None
        requested_candidate = result.get("requestedIdentity")
        transport = result.get("transport")
        role_candidates = policy_roles.get(authoritative_role)
        role_candidates = role_candidates if isinstance(role_candidates, list) else []
        policy_candidate = next(
            (
                candidate for candidate in role_candidates
                if isinstance(candidate, dict)
                and candidate.get("model") == requested_candidate
                and candidate.get("transport") == transport
            ),
            None,
        )
        required_capabilities = case.get("requiredCapabilities") if isinstance(case, dict) else None
        required_capabilities = required_capabilities if isinstance(required_capabilities, list) else []
        candidate_capabilities = policy_candidate.get("capabilities") if isinstance(policy_candidate, dict) else None
        candidate_capabilities = candidate_capabilities if isinstance(candidate_capabilities, list) else []
        policy_ok = bool(
            isinstance(policy_candidate, dict)
            and result.get("role") == authoritative_role
            and all(
                isinstance(capability, str) and capability in candidate_capabilities
                for capability in required_capabilities
            )
        )
        receipt_benchmark = receipt.get("benchmark")
        receipt_benchmark = receipt_benchmark if isinstance(receipt_benchmark, dict) else {}
        receipt_binding_ok = all(
            name not in receipt or receipt.get(name) == expected
            for name, expected in (
                ("requestedModel", requested_candidate),
                ("transport", transport),
            )
        ) and all(
            name not in receipt_benchmark or receipt_benchmark.get(name) == expected
            for name, expected in (
                ("suiteId", result.get("suiteId")),
                ("caseId", case_id),
                ("role", authoritative_role),
            )
        )
        authority_ok = bool(
            isinstance(case, dict)
            and result.get("suiteId") == suite.get("suiteId")
            and binding_value(result, "suiteRevision") == suite.get("suiteRevision")
            and binding_value(result, "caseRevision") == case.get("revision")
            and binding_value(result, "promptRevision") == case.get("promptRevision")
            and behavior.get("revision") == expected_behavior.get("revision")
            and behavior.get("digest") == expected_behavior.get("digest")
        )
        compatible = bindings_ok and authority_ok and policy_ok and receipt_binding_ok
        fallback = result.get("fallback")
        identity_ok = closed_identity_proof(result, receipt)
        category = failure_category(result, compatible, identity_ok)
        transport_outcome = result.get("transportOutcome")
        transport_outcome = transport_outcome if isinstance(transport_outcome, dict) else {}
        comparable = bool(
            compatible
            and result.get("benchmarkFault") is False
            and transport_outcome.get("status") == "success"
            and identity_ok
        )
        validated = bool(
            comparable
            and result.get("contractPassed") is True
            and result.get("mandatoryPassed") is True
            and result.get("semanticPassed") is True
            and result.get("validationPassed") is True
        )
        usage = result_usage(result, receipt)
        cost = usage["cost_usd"]
        if cost is not None:
            recorded_costs.append(cost)
        human, human_rejection = human_rubric_evidence(directory, result, case)
        attempt = {
            "path": str(directory),
            "requested_candidate": requested_candidate,
            "served_identity": result.get("servedIdentity"),
            "endpoint_provider": result.get("endpointProvider"),
            "billing_mode": result.get("billingMode") or receipt.get("billingMode"),
            "transport": transport,
            "role": authoritative_role,
            "reported_role": result.get("role"),
            "case_id": case_id,
            "case_revision": binding_value(result, "caseRevision"),
            "observed_at": result.get("observedAt") if isinstance(result.get("observedAt"), str) else None,
            "receipt_outcome": receipt.get("outcome") or transport_outcome.get("status"),
            "parsed": result.get("parsed") if isinstance(result.get("parsed"), bool) else None,
            "quality_score": number(result.get("qualityScore")),
            "validation_passed": result.get("validationPassed") if isinstance(result.get("validationPassed"), bool) else None,
            "comparable": comparable,
            "validated": validated,
            "model_conclusion": result.get("modelConclusion") if comparable else None,
            "failure_category": category,
            "failure_class": result.get("failureClass"),
            "failure_reason": safe_failure_reason(result, receipt, category),
            "duration_seconds": supplied_number(result, receipt, "durationSeconds", "duration_seconds"),
            **usage,
            "provider_billed_cost_usd": usage["cost_usd"],
            "context_tokens": supplied_number(result, receipt, "contextTokens", "context_tokens", "inputContextTokens"),
            "tool_calls": supplied_number(result, receipt, "toolCalls", "tool_calls", "toolUseCount"),
            "correction_count": supplied_number(result, receipt, "correctionCount", "correction_count"),
            "useful_findings": supplied_number(result, receipt, "usefulFindings", "usefulFindingCount", "useful_finding_count", "truePositiveCount"),
            "false_positives": supplied_number(result, receipt, "falsePositives", "falsePositiveCount", "false_positive_count"),
            "fallback_used": fallback.get("used") if isinstance(fallback, dict) else None,
            "human_evidence": human,
            "human_rejection": human_rejection,
            "_order": attempt_order(result, receipt),
        }
        key = (
            attempt["requested_candidate"], attempt["transport"], attempt["role"], attempt["case_id"],
            attempt["case_revision"], result.get("suiteId"), binding_value(result, "suiteRevision"),
            binding_value(result, "suiteDigest"), binding_value(result, "caseDigest"),
            binding_value(result, "promptRevision"), binding_value(result, "promptDigest"),
            binding_value(result, "scorerRevision"), binding_value(result, "scorerDigest"),
            binding_value(result, "normalizerRevision"), binding_value(result, "normalizerDigest"),
            behavior.get("revision"), behavior.get("digest"),
        )
        if compatible:
            grouped[key].append(attempt)
        else:
            incompatible_v2.append(
                {name: value for name, value in attempt.items() if not name.startswith("_")}
                | {"classification": "incompatible v2; no model conclusion"}
            )

    groups = [group_rollup(key, attempts) for key, attempts in sorted(grouped.items(), key=lambda item: tuple(str(part) for part in item[0]))]
    role_rows: list[dict[str, Any]] = []
    for role, candidates in policy_roles.items():
        role_cases = [case for case in cases if isinstance(case, dict) and case.get("role") == role]
        role_groups = [group for group in groups if group["role"] == role]
        cohort_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for group in role_groups:
            cohort_groups[evaluator_cohort_key(group)].append(group)
        evaluator_cohorts = [
            evaluator_cohort_rollup(key, matching, role_cases)
            for key, matching in sorted(
                cohort_groups.items(), key=lambda item: tuple(str(part) for part in item[0])
            )
        ]
        metric_cohorts = [
            cohort for cohort in evaluator_cohorts
            if cohort["case_binding_consistent"]
            and cohort["comparable_attempts"] is not None
            and cohort["comparable_attempts"] > 0
        ]
        binding_conflict = any(
            not cohort["case_binding_consistent"]
            and cohort["retained_comparable_attempts"] > 0
            for cohort in evaluator_cohorts
        )
        selected_cohort = metric_cohorts[0] if len(metric_cohorts) == 1 else None
        selected_key = (
            tuple(selected_cohort[name] for name in EVALUATOR_COHORT_FIELDS)
            if selected_cohort is not None else None
        )
        selected_groups = [
            group for group in role_groups
            if selected_key is not None and evaluator_cohort_key(group) == selected_key
        ]
        incomplete_for_role = [item for item in incomplete if item.get("role") == role]
        incompatible_for_role = [item for item in incompatible_v2 if item.get("role") == role]
        role_operational_retries = sum(
            (Counter(group["operational_retries"]) for group in role_groups), Counter()
        )
        role_operational_retries.update(
            item["failure_category"] for item in incomplete_for_role
            if item.get("failure_category") in OPERATIONAL_FAILURE_CATEGORIES
        )
        role_operational_retries.update(
            item["failure_category"] for item in incompatible_for_role
            if item.get("failure_category") in OPERATIONAL_FAILURE_CATEGORIES
        )
        case_coverage = []
        for case in role_cases:
            matching = [group for group in role_groups if group["case_id"] == case.get("id")]
            cohort_coverage = [
                next(
                    item for item in cohort["case_coverage"]
                    if item["case_id"] == case.get("id")
                )
                | {
                    name: cohort[name] for name in EVALUATOR_COHORT_FIELDS
                }
                for cohort in evaluator_cohorts
            ]
            selected_case = next(
                (item for item in cohort_coverage if selected_key is not None and tuple(item[name] for name in EVALUATOR_COHORT_FIELDS) == selected_key),
                None,
            )
            case_coverage.append(
                {
                    "case_id": case.get("id"),
                    "case_revision": case.get("revision"),
                    "prompt_revision": case.get("promptRevision"),
                    "required_capabilities": case.get("requiredCapabilities", []),
                    "applicability": case.get("applicability"),
                    "compatible_groups": len(matching),
                    "comparable_attempts": selected_case["comparable_attempts"] if selected_case is not None else None,
                    "validated_attempts": selected_case["validated_attempts"] if selected_case is not None else None,
                    "evaluator_cohorts": cohort_coverage,
                    "latest_observed_at": max(
                        (group["latest_observed_at"] for group in matching if group["latest_observed_at"] is not None),
                        default=None,
                    ),
                }
            )
        missing_cases = [
            item["case_id"] for item in case_coverage
            if not any(cohort["comparable_attempts"] > 0 for cohort in item["evaluator_cohorts"])
        ]
        latest = max(
            (group["latest_observed_at"] for group in role_groups if group["latest_observed_at"] is not None),
            default=None,
        )
        has_comparable = bool(metric_cohorts)
        instrumentation = (
            selected_cohort["instrumentation"]
            if selected_cohort is not None
            else {
                field: {"recorded": None, "attempts": None, "rate": None}
                for field in (
                    "duration_seconds", "prompt_tokens", "completion_tokens", "reasoning_tokens",
                    "cache_read_tokens", "cache_creation_tokens", "context_tokens", "tool_calls",
                    "correction_count", "useful_findings", "false_positives",
                )
            }
        )
        role_rows.append(
            {
                "role": role,
                "policy_candidates": len(candidates) if isinstance(candidates, list) else 0,
                "required_cases": len(role_cases),
                "case_coverage": case_coverage,
                "evaluator_cohorts": evaluator_cohorts,
                "complete_evaluator_cohorts": sum(
                    cohort["complete_case_coverage"] for cohort in evaluator_cohorts
                ),
                "case_binding_conflict": binding_conflict,
                "missing_cases": missing_cases,
                "gap": "conflicting case/prompt bindings" if binding_conflict else ("no comparable current evidence" if not has_comparable else ("multiple evaluator cohorts" if len(metric_cohorts) > 1 else ("incomplete case coverage" if missing_cases else None))),
                "confidence": "cohort-separated" if binding_conflict else ("none" if not has_comparable else ("cohort-separated" if len(metric_cohorts) > 1 else ("partial" if missing_cases else "controlled-current"))),
                "freshness": {"latest_observed_at": latest, "suite_revision": suite.get("suiteRevision"), "policy_snapshot": policy.get("matrixSnapshot")},
                "best_deterministic_quality": selected_cohort["best_deterministic_quality"] if selected_cohort is not None else None,
                "validated_attempts": selected_cohort["validated_attempts"] if selected_cohort is not None else None,
                "comparable_attempts": selected_cohort["comparable_attempts"] if selected_cohort is not None else None,
                "first_pass_validated_rate": selected_cohort["first_pass_validated_rate"] if selected_cohort is not None else None,
                "median_duration_seconds": selected_cohort["median_duration_seconds"] if selected_cohort is not None else None,
                "median_time_to_first_validated_seconds": selected_cohort["median_time_to_first_validated_seconds"] if selected_cohort is not None else None,
                "median_attempts_to_valid": selected_cohort["median_attempts_to_valid"] if selected_cohort is not None else None,
                "median_model_rework_to_valid": selected_cohort["median_model_rework_to_valid"] if selected_cohort is not None else None,
                "median_tokens_to_first_validated": selected_cohort["median_tokens_to_first_validated"] if selected_cohort is not None else {
                    field: None for field in (
                        "prompt_tokens", "completion_tokens", "reasoning_tokens",
                        "cache_read_tokens", "cache_creation_tokens",
                    )
                },
                "median_context_to_first_validated": selected_cohort["median_context_to_first_validated"] if selected_cohort is not None else None,
                "useful_finding_yield": selected_cohort["useful_finding_yield"] if selected_cohort is not None else None,
                "false_positive_yield": selected_cohort["false_positive_yield"] if selected_cohort is not None else None,
                "operational_retries": dict(sorted(role_operational_retries.items())),
                "model_failure_counts": dict(sorted(sum((Counter({key: value for key, value in group["failure_counts"].items() if key in MODEL_FAILURE_CATEGORIES}) for group in selected_groups), Counter()).items())) if selected_cohort is not None else {},
                "instrumentation": instrumentation | {
                    "attempt_order": {
                        "recorded": sum(group["ordering_available"] for group in selected_groups) if selected_cohort is not None else None,
                        "groups": len(selected_groups) if selected_cohort is not None else None,
                        "rate": (sum(group["ordering_available"] for group in selected_groups) / len(selected_groups)) if selected_groups else None,
                    }
                },
                "editorial_human_evidence": (
                    {
                        "accepted_receipts": sum((group["editorial_human_evidence"] or {}).get("accepted_receipts", 0) for group in role_groups),
                        "median_mean_score": median(
                            (group["editorial_human_evidence"] or {}).get("median_mean_score") for group in role_groups
                        ),
                    }
                    if any(group["editorial_human_evidence"] is not None for group in role_groups) else None
                ),
                "incomplete_attempts": len(incomplete_for_role),
                "incompatible_v2_attempts": len(incompatible_for_role),
                "retained_attempts": sum(group["attempts"] for group in role_groups) + len(incomplete_for_role) + len(incompatible_for_role),
            }
        )

    model_rows: list[dict[str, Any]] = []
    for role, candidates in policy_roles.items():
        role_case_ids = [case["id"] for case in cases if isinstance(case, dict) and case.get("role") == role]
        for candidate in candidates if isinstance(candidates, list) else []:
            if not isinstance(candidate, dict) or not isinstance(candidate.get("model"), str):
                continue
            candidate_groups = [
                group for group in groups
                if group["role"] == role
                and group["requested_candidate"] == candidate["model"]
                and group["transport"] == candidate.get("transport")
            ]
            observed_cases = {group["case_id"] for group in candidate_groups if group["comparable_attempts"]}
            validated_cases = {group["case_id"] for group in candidate_groups if group["validated_attempts"]}
            strengths = [
                {
                    "case_id": group["case_id"], "case_revision": group["case_revision"],
                    "case_digest": group["case_digest"], "prompt_revision": group["prompt_revision"],
                    "prompt_digest": group["prompt_digest"], "scorer_revision": group["scorer_revision"],
                    "scorer_digest": group["scorer_digest"],
                    "validated_attempts": group["validated_attempts"],
                    "best_deterministic_quality": group["best_deterministic_quality"],
                }
                for group in candidate_groups if group["validated_attempts"]
            ]
            failures = [
                {"case_id": group["case_id"], "failure_counts": {key: value for key, value in group["failure_counts"].items() if key in MODEL_FAILURE_CATEGORIES}}
                for group in candidate_groups
                if any(key in MODEL_FAILURE_CATEGORIES for key in group["failure_counts"])
            ]
            benchmark_faults = sum(
                sum(value for key, value in group["failure_counts"].items() if key in {"benchmark", "prompt", "parser", "scorer", "harness"})
                for group in candidate_groups
            )
            candidate_cohorts: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
            for group in candidate_groups:
                candidate_cohorts[evaluator_cohort_key(group)].append(group)
            competitive_cohorts = []
            for cohort_key, cohort_groups_for_candidate in sorted(
                candidate_cohorts.items(), key=lambda item: tuple(str(part) for part in item[0])
            ):
                complete_case_groups: list[dict[str, Any]] = []
                complete = bool(role_case_ids)
                for case_id in role_case_ids:
                    case_groups = [
                        group for group in cohort_groups_for_candidate
                        if group["case_id"] == case_id and group["comparable_attempts"] > 0
                    ]
                    case_bindings = {
                        tuple(group[name] for name in CASE_BINDING_FIELDS)
                        for group in case_groups
                    }
                    eligible = [
                        group for group in case_groups if group["validated_attempts"] >= 3
                    ]
                    if len(case_bindings) != 1 or len(eligible) != 1:
                        complete = False
                    complete_case_groups.extend(eligible)
                cohort_has_model_failures = any(
                    any(key in MODEL_FAILURE_CATEGORIES for key in group["failure_counts"])
                    for group in cohort_groups_for_candidate
                )
                if complete and not cohort_has_model_failures:
                    competitive_cohorts.append(
                        {
                            **dict(zip(EVALUATOR_COHORT_FIELDS, cohort_key)),
                            "case_groups": [
                                {
                                    "case_id": group["case_id"],
                                    "case_revision": group["case_revision"],
                                    "case_digest": group["case_digest"],
                                    "prompt_revision": group["prompt_revision"],
                                    "prompt_digest": group["prompt_digest"],
                                    "scorer_revision": group["scorer_revision"],
                                    "scorer_digest": group["scorer_digest"],
                                    "normalizer_revision": group["normalizer_revision"],
                                    "normalizer_digest": group["normalizer_digest"],
                                    "validated_attempts": group["validated_attempts"],
                                }
                                for group in complete_case_groups
                            ],
                        }
                    )
            model_rows.append(
                {
                    "model": candidate["model"],
                    "role": role,
                    "transport": candidate.get("transport"),
                    "family": candidate.get("family"),
                    "billing": candidate.get("billing"),
                    "capabilities": candidate.get("capabilities", []),
                    "strengths": strengths,
                    "failures": failures,
                    "prohibited_evidence": [],
                    "gaps": sorted(set(role_case_ids) - observed_cases),
                    "validated_case_coverage": len(validated_cases),
                    "controlled_competitive_evidence": bool(competitive_cohorts),
                    "competitive_evidence_cohorts": competitive_cohorts,
                    "benchmark_faults": benchmark_faults,
                    "benchmark_fault_conclusion": "no model conclusion" if benchmark_faults else None,
                    "row_level_conclusion": "no model conclusion" if benchmark_faults else ("attributable model evidence" if strengths or failures else None),
                    "routing_conclusion": "no routing change justified",
                }
            )

    return {
        "result_root": str(root) if root is not None else None,
        "attempts": len(directories),
        "current_v2_attempts": sum(group["attempts"] for group in groups),
        "groups": groups,
        "roles": role_rows,
        "model_role_evidence": model_rows,
        "incomplete_attempts": incomplete,
        "historical_v1": historical_v1,
        "incompatible_v2": incompatible_v2,
        "measured_cost_usd": sum(recorded_costs) if recorded_costs else None,
        "matrix_opportunities": [],
        "routing_conclusion": "no routing change justified",
        "views": {
            "quality": {
                "validated_attempts": (
                    None if any(role["case_binding_conflict"] or (role["comparable_attempts"] is None and len([cohort for cohort in role["evaluator_cohorts"] if cohort["comparable_attempts"]]) > 1) for role in role_rows)
                    else sum((role["validated_attempts"] or 0) for role in role_rows)
                ),
                "comparable_attempts": (
                    None if any(role["case_binding_conflict"] or (role["comparable_attempts"] is None and len([cohort for cohort in role["evaluator_cohorts"] if cohort["comparable_attempts"]]) > 1) for role in role_rows)
                    else sum((role["comparable_attempts"] or 0) for role in role_rows)
                ),
                "roles_with_validated_evidence": [
                    role["role"] for role in role_rows
                    if any(cohort["validated_attempts"] for cohort in role["evaluator_cohorts"])
                ],
                "evaluator_cohorts": {
                    role["role"]: role["evaluator_cohorts"] for role in role_rows
                },
            },
            "reliability": {
                "model_failure_counts": dict(sorted(sum((Counter(role["model_failure_counts"]) for role in role_rows), Counter()).items())),
                "operational_retry_counts": dict(sorted(sum((Counter(role["operational_retries"]) for role in role_rows), Counter()).items())),
                "historical_v1_attempts": len(historical_v1),
                "incompatible_v2_attempts": len(incompatible_v2),
                "retained_attempts": len(directories),
            },
            "latency": {
                role["role"]: {
                    "median_duration_seconds": role["median_duration_seconds"],
                    "coverage": role["instrumentation"]["duration_seconds"],
                    "evaluator_cohorts": [
                        {
                            **{name: cohort[name] for name in EVALUATOR_COHORT_FIELDS},
                            "median_duration_seconds": cohort["median_duration_seconds"],
                            "coverage": cohort["instrumentation"]["duration_seconds"],
                        }
                        for cohort in role["evaluator_cohorts"]
                    ],
                }
                for role in role_rows
            },
            "tokens_context": {
                role["role"]: {
                    field: role["instrumentation"][field]
                    for field in (
                        "prompt_tokens", "completion_tokens", "reasoning_tokens",
                        "cache_read_tokens", "cache_creation_tokens", "context_tokens",
                    )
                }
                for role in role_rows
            },
            "provider_spend": {
                "measured_cost_usd": sum(recorded_costs) if recorded_costs else None,
                "recorded_cost_coverage": {
                    "recorded": len(recorded_costs),
                    "attempts": len(directories),
                    "rate": len(recorded_costs) / len(directories) if directories else None,
                },
            },
            "subscription_marginal_cost": {"value": None, "reason": "reported only when supplied by production evidence"},
            "api_equivalent_cost": {"value": None, "reason": "not inferred or combined with billed spend"},
            "capabilities": {
                role: sorted({capability for candidate in candidates if isinstance(candidate, dict) for capability in candidate.get("capabilities", [])})
                for role, candidates in policy_roles.items() if isinstance(candidates, list)
            },
            "family_diversity": {
                role: sorted({candidate["family"] for candidate in candidates if isinstance(candidate, dict) and isinstance(candidate.get("family"), str)})
                for role, candidates in policy_roles.items() if isinstance(candidates, list)
            },
            "editorial_human": next(
                (role["editorial_human_evidence"] for role in role_rows if role["role"] == "editorial"), None
            ),
        },
    }


def render_report(report: dict[str, Any]) -> str:
    production = report["production"]
    benchmark = report["benchmarks"]
    lines = [
        f"# Depot model intelligence — {report['generated_at'][:10]}",
        "",
        "## Per-role validated quality and efficiency",
        "",
        "| Role | Cases | Validated | Best quality | First pass | Median duration | Time to valid | Attempts/rework | Confidence | Freshness | Gap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for role in benchmark["roles"]:
        first_pass = "n/a" if role["first_pass_validated_rate"] is None else f"{role['first_pass_validated_rate']:.0%}"
        time_valid = "n/a" if role["median_time_to_first_validated_seconds"] is None else f"{role['median_time_to_first_validated_seconds']:.1f}s"
        attempts = "n/a" if role["median_attempts_to_valid"] is None else f"{role['median_attempts_to_valid']:g}/{role['median_model_rework_to_valid']:g}"
        score = "n/a" if role["best_deterministic_quality"] is None else f"{role['best_deterministic_quality']:g}"
        duration = "n/a" if role["median_duration_seconds"] is None else f"{role['median_duration_seconds']:.1f}s"
        validated = "n/a" if role["validated_attempts"] is None else f"{role['validated_attempts']}/{role['comparable_attempts']}"
        freshness = role["freshness"]["latest_observed_at"] or "none"
        lines.append(
            f"| {role['role']} | {role['required_cases'] - len(role['missing_cases'])}/{role['required_cases']} | "
            f"{validated} | {score} | {first_pass} | {duration} | {time_valid} | "
            f"{attempts} | {role['confidence']} | {freshness} | {role['gap'] or 'none'} |"
        )
    lines.extend(
        [
            "",
            "Missing ordering, duration, token, cache, context, tool, correction, and finding telemetry stays null. Independent repeated attempts do not imply an in-session tool call or correction loop.",
            "",
            "## Role case coverage and instrumentation",
            "",
        ]
    )
    for role in benchmark["roles"]:
        instrumentation = {
            key: value["rate"]
            for key, value in role["instrumentation"].items()
            if isinstance(value, dict) and "rate" in value
        }
        lines.extend(
            [
                f"### {role['role']}",
                "",
                f"- Missing cases: {', '.join(role['missing_cases']) or 'none'}",
                f"- Operational retries: `{json.dumps(role['operational_retries'], sort_keys=True)}`",
                f"- Model-attributable failures: `{json.dumps(role['model_failure_counts'], sort_keys=True)}`",
                f"- Instrumentation coverage: `{json.dumps(instrumentation, sort_keys=True)}`",
                f"- Policy snapshot: {role['freshness']['policy_snapshot']}; suite revision: {role['freshness']['suite_revision']}",
                "",
            ]
        )
        if role["evaluator_cohorts"]:
            lines.extend(
                [
                    "| Evaluator cohort scorer | Complete cases | Validated | Best quality | First pass | Median duration | Time to valid |",
                    "|---|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for cohort in role["evaluator_cohorts"]:
                cohort_first_pass = "n/a" if cohort["first_pass_validated_rate"] is None else f"{cohort['first_pass_validated_rate']:.0%}"
                cohort_duration = "n/a" if cohort["median_duration_seconds"] is None else f"{cohort['median_duration_seconds']:.1f}s"
                cohort_time = "n/a" if cohort["median_time_to_first_validated_seconds"] is None else f"{cohort['median_time_to_first_validated_seconds']:.1f}s"
                cohort_quality = "n/a" if cohort["best_deterministic_quality"] is None else f"{cohort['best_deterministic_quality']:g}"
                cohort_validated = (
                    "n/a" if cohort["validated_attempts"] is None
                    else f"{cohort['validated_attempts']}/{cohort['comparable_attempts']}"
                )
                lines.append(
                    f"| {cohort['scorer_revision']}/{cohort['scorer_digest']} | "
                    f"{str(cohort['complete_case_coverage']).lower()} | {cohort_validated} | "
                    f"{cohort_quality} | {cohort_first_pass} | {cohort_duration} | {cohort_time} |"
                )
            lines.append("")

    lines.extend(["## Controlled model-role evidence", ""])
    evidenced_models = [
        row for row in benchmark["model_role_evidence"]
        if row["strengths"] or row["failures"] or row["benchmark_faults"]
    ]
    if evidenced_models:
        lines.extend(
            [
                "| Role | Requested candidate | Transport | Validated strengths | Attributable failures | Gaps | Benchmark faults | Row conclusion | Routing |",
                "|---|---|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for row in evidenced_models:
            lines.append(
                f"| {row['role']} | {row['model']} | {row['transport']} | {len(row['strengths'])} | "
                f"{len(row['failures'])} | {len(row['gaps'])} | {row['benchmark_faults']} | "
                f"{row['row_level_conclusion'] or 'none'} | {row['routing_conclusion']} |"
            )
    else:
        lines.append("No attributable current v2 model-role evidence is available.")

    lines.extend(["", "## Controlled reliability and failure attribution", ""])
    if benchmark["groups"]:
        lines.extend(
            [
                "| Candidate | Transport | Role | Case/revision | Validated | First pass | Rework | Median duration | Operational retries | Endpoint providers |",
                "|---|---|---|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for group in benchmark["groups"]:
            first_pass = "n/a" if group["first_pass_validated"] is None else str(group["first_pass_validated"]).lower()
            rework = "n/a" if group["model_rework_to_valid"] is None else str(group["model_rework_to_valid"])
            duration = "n/a" if group["median_duration_seconds"] is None else f"{group['median_duration_seconds']:.1f}s"
            lines.append(
                f"| {group['requested_candidate']} | {group['transport']} | {group['role']} | "
                f"{group['case_id']}/{group['case_revision']} | {group['validated_attempts']}/{group['comparable_attempts']} | "
                f"{first_pass} | {rework} | {duration} | `{json.dumps(group['operational_retries'], sort_keys=True)}` | "
                f"`{json.dumps(group['endpoint_providers'], sort_keys=True)}` |"
            )
    else:
        lines.append("No compatible v2 controlled groups were found.")
    lines.extend(
        [
            "",
            f"- Incomplete attempts retained: {len(benchmark['incomplete_attempts'])}",
            f"- Incompatible v2 attempts retained: {len(benchmark['incompatible_v2'])}",
            f"- Historical v1 attempts retained: {len(benchmark['historical_v1'])}",
            "- Benchmark, prompt, parser, scorer, and harness faults have `no model conclusion` and do not enter model reliability or demotion evidence.",
            "",
            "## Editorial blinded human evidence",
            "",
        ]
    )
    editorial = next((role for role in benchmark["roles"] if role["role"] == "editorial"), None)
    if editorial is not None and editorial["editorial_human_evidence"] is not None:
        human = editorial["editorial_human_evidence"]
        lines.append(
            f"Accepted blinded digest-matched receipts: {human['accepted_receipts']}; median rubric mean: {human['median_mean_score']}."
        )
    else:
        lines.append("No accepted blinded digest-matched editorial human evidence is available; human quality remains null.")

    quality = production["quality"]
    lines.extend(
        [
            "",
            "## Production quality signals",
            "",
            f"- Canonical findings: {quality['canonical_findings']}",
            f"- Median completion rate: {quality['median_completion_rate']}",
            f"- Median fallback rate: {quality['median_fallback_rate']}",
            f"- Median first-pass validation rate: {quality['median_validation_first_pass_rate']}",
            f"- Retry reasons: `{json.dumps(quality['retry_reasons'], sort_keys=True)}`",
            "",
            "These are workflow signals, not direct causal model-quality scores. Missing model attribution remains missing.",
            "",
            "## Capabilities and family diversity",
            "",
            "Capabilities and model families are policy dimensions. They are not folded into quality, reliability, latency, tokens, or cost.",
            "",
            "## Latency, tokens, context, and tools",
            "",
            "Recorded duration, prompt/completion/reasoning/cache tokens, context, and tool telemetry remain independent axes. Coverage is reported above; missing values are not zero.",
            "",
            "## Provider spend and access economics",
            "",
            f"- Benchmark provider-billed cost: {benchmark['views']['provider_spend']['measured_cost_usd']}",
            f"- Benchmark recorded-cost coverage: `{json.dumps(benchmark['views']['provider_spend']['recorded_cost_coverage'], sort_keys=True)}`",
            "",
        ]
    )
    if production["by_model"]:
        lines.extend(
            [
                "| Model | Attempts | Duration | Input tokens | Output tokens | Input bytes | Provider-billed cost | Finding contributions |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in production["by_model"]:
            lines.append(
                "| {model} | {attempts} | {duration_seconds:.1f}s | {input_tokens:.0f} | {output_tokens:.0f} | {input_bytes:.0f} | ${measured_cost_usd:.4f} | {finding_contributions} |".format(**row)
            )
    else:
        lines.append("No model-attributed lane usage is available.")
    lines.extend(["", "### Production economics by lane and model", ""])
    if production["by_lane_model"]:
        lines.extend(
            [
                "| Lane | Model | Attempts | Duration | Input tokens | Output tokens | Input bytes | Provider-billed cost |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in production["by_lane_model"]:
            lines.append(
                "| {lane} | {model} | {attempts} | {duration_seconds:.1f}s | {input_tokens:.0f} | {output_tokens:.0f} | {input_bytes:.0f} | ${measured_cost_usd:.4f} |".format(**row)
            )
    else:
        lines.append("No lane/model-attributed usage is available.")
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Token counts and deterministic input bytes are different units and are never added together.",
            "- Subscription marginal cost, API-equivalent opportunity cost, and provider-billed spend remain separate views.",
            "- A model-role change requires three comparable, identity-confirmed, no-model-fallback successful attempts on every applicable distinct local case in one digest-compatible cohort plus production evidence; incomplete coverage cannot promote a model.",
            f"- Routing conclusion: {benchmark['routing_conclusion']}.",
            "",
        ]
    )
    return "\n".join(lines)


def report_command(args: argparse.Namespace) -> int:
    roots = [Path(item).resolve() for item in args.run_root] if args.run_root else list(DEFAULT_RUN_ROOTS)
    benchmark_root = Path(args.benchmark_root).resolve() if args.benchmark_root else None
    generated_at = parse_observed_at(args.observed_at).isoformat(timespec="seconds")
    production = production_rollup(roots)
    benchmarks = benchmark_rollup(benchmark_root)

    def repository_path(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    report = {
        "schema_version": 2,
        "generated_at": generated_at,
        "quality_efficiency": {
            "roles": benchmarks["roles"],
            "model_role_evidence": benchmarks["model_role_evidence"],
            "routing_conclusion": benchmarks["routing_conclusion"],
        },
        "benchmarks": benchmarks,
        "production": production,
        "repository": "Design-Machines-Studio/depot",
        "run_roots": [repository_path(root) for root in roots],
    }
    report_json = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_output:
        write_atomic(Path(args.json_output).resolve(), report_json)
    if args.markdown_output:
        write_atomic(Path(args.markdown_output).resolve(), render_report(report))
    print(report_json, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("catalog-refresh", help="compare a live catalog snapshot with the matrix")
    catalog.add_argument("--catalog", required=True)
    catalog.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    catalog.add_argument("--observed-at")
    catalog.add_argument("--candidate-limit", type=int, default=20)
    catalog.add_argument("--output")
    catalog.add_argument("--write", action="store_true", help="refresh existing matrix entries when material changes exist")
    catalog.set_defaults(func=catalog_refresh)

    report = subparsers.add_parser("report", help="aggregate production and benchmark evidence")
    report.add_argument("--run-root", action="append", default=[])
    report.add_argument("--benchmark-root")
    report.add_argument("--observed-at")
    report.add_argument("--json-output")
    report.add_argument("--markdown-output")
    report.set_defaults(func=report_command)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return int(args.func(args))
    except IntelligenceError as exc:
        print(f"model-intelligence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
