#!/usr/bin/env python3
"""Deterministic catalog, production-run, and benchmark intelligence for Depot.

The command deliberately separates facts from policy:

* ``catalog-refresh`` compares an OpenRouter catalog snapshot with the checked-in
  matrix and can refresh existing exact entries. It never admits a new model or
  changes role routing.
* ``report`` aggregates repository-owned run-cost summaries, workflow metrics,
  and Depot role benchmark results. It never reads prompt/model output content.

Scheduled tasks use this command so daily and weekly runs share one evidence
contract instead of reconstructing ad-hoc jq pipelines.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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


def binding_value(result: dict[str, Any], name: str) -> Any:
    bindings = result.get("evidenceBindings")
    binding = bindings.get(name) if isinstance(bindings, dict) else None
    return binding.get("actual") if isinstance(binding, dict) else None


def result_usage(result: dict[str, Any], receipt: dict[str, Any]) -> dict[str, float | None]:
    usage = result.get("usage")
    usage = usage if isinstance(usage, dict) else receipt.get("usage")
    usage = usage if isinstance(usage, dict) else {}

    def usage_number(*names: str) -> float | None:
        for name in names:
            parsed = number(usage.get(name))
            if parsed is not None:
                return parsed
        return None

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
        "cost_usd": usage_number("cost", "cost_usd"),
    }


def supplied_number(result: dict[str, Any], receipt: dict[str, Any], *names: str) -> float | None:
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    for source in (result, usage, receipt):
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


def failure_category(result: dict[str, Any], compatible: bool, fallback_ok: bool) -> str | None:
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
    if not isinstance(identity, dict) or identity.get("confidence") != "confirmed" or not fallback_ok:
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
    for source, name in ((result, "failureClass"), (receipt, "failureKind")):
        reason = source.get(name)
        if isinstance(reason, str) and reason:
            return reason.replace("\n", " ")[:240]
    return category


def normalized_output_digest(directory: Path, result: dict[str, Any]) -> str | None:
    for name in ("normalizedOutputArtifactSha256", "normalizedOutputDigest"):
        digest = result.get(name)
        if isinstance(digest, str) and digest:
            return digest.removeprefix("sha256:")
    normalized = result.get("normalizedOutput")
    if not isinstance(normalized, dict):
        output_path = directory / "output.json"
        if not output_path.is_file() or output_path.is_symlink():
            return None
        try:
            candidate = json.loads(output_path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        normalized = candidate if isinstance(candidate, dict) else None
    if not isinstance(normalized, dict):
        return None
    artifact = json.dumps(normalized, indent=2, ensure_ascii=False) + "\n"
    return sha256_bytes(artifact.encode())


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
    digest = normalized_output_digest(directory, result)
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
    if not isinstance(receipt_digest, str) or digest is None or receipt_digest.removeprefix("sha256:") != digest:
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
    measured_cost_usd = 0.0
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
            usage = result_usage({}, receipt)
            benchmark = receipt.get("benchmark")
            benchmark = benchmark if isinstance(benchmark, dict) else {}
            case_id = benchmark.get("caseId")
            case = case_by_id.get(case_id) if isinstance(case_id, str) else None
            incomplete.append(
                {
                    "path": str(directory),
                    "requested_candidate": receipt.get("requestedModel"),
                    "transport": receipt.get("transport"),
                    "role": benchmark.get("role") or (case.get("role") if isinstance(case, dict) else None),
                    "case_id": case_id,
                    "duration_seconds": supplied_number({}, receipt, "durationSeconds", "duration_seconds"),
                    **usage,
                    "receipt_outcome": receipt.get("outcome"),
                    "failure_category": "transport" if receipt.get("outcome") == "failed" else "harness",
                    "failure_reason": safe_failure_reason({}, receipt, "incomplete attempt"),
                }
            )
            cost = usage["cost_usd"]
            measured_cost_usd += cost if cost is not None else 0
            continue
        try:
            result = load_json(result_path)
        except IntelligenceError as exc:
            usage = result_usage({}, receipt)
            benchmark = receipt.get("benchmark")
            benchmark = benchmark if isinstance(benchmark, dict) else {}
            incomplete.append(
                {
                    "path": str(directory),
                    "requested_candidate": receipt.get("requestedModel"),
                    "transport": receipt.get("transport"),
                    "role": benchmark.get("role"),
                    "case_id": benchmark.get("caseId"),
                    "duration_seconds": supplied_number({}, receipt, "durationSeconds", "duration_seconds"),
                    **usage,
                    "receipt_outcome": receipt.get("outcome"),
                    "failure_category": "parser",
                    "failure_reason": str(exc),
                }
            )
            continue
        if not isinstance(result, dict):
            incomplete.append({"path": str(directory), "failure_category": "parser", "failure_reason": "result object required"})
            continue
        if result.get("schemaVersion") != 2:
            usage = result_usage(result, receipt)
            historical_v1.append(
                {
                    "path": str(directory),
                    "schema_version": result.get("schemaVersion", 1),
                    "requested_candidate": result.get("requestedModel"),
                    "served_identity": result.get("servedModel"),
                    "transport": result.get("transport"),
                    "case_id": result.get("caseId"),
                    "parsed": result.get("parsed") if isinstance(result.get("parsed"), bool) else None,
                    "quality_score": number(result.get("qualityScore")),
                    "duration_seconds": supplied_number(result, receipt, "durationSeconds", "duration_seconds"),
                    **usage,
                    "receipt_outcome": receipt.get("outcome"),
                    "failure_reason": safe_failure_reason(result, receipt, None),
                    "classification": "historical/incompatible; no model conclusion",
                }
            )
            continue

        case_id = result.get("caseId")
        case = case_by_id.get(case_id) if isinstance(case_id, str) else None
        behavior = result.get("behavioralContract")
        behavior = behavior if isinstance(behavior, dict) else {}
        bindings = result.get("evidenceBindings")
        bindings_ok = isinstance(bindings, dict) and all(
            isinstance(bindings.get(name), dict)
            and bindings[name].get("match") is True
            and bindings[name].get("actual") is not None
            for name in V2_BINDINGS
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
        compatible = bindings_ok and authority_ok
        fallback = result.get("fallback")
        fallback_ok = bool(
            isinstance(fallback, dict)
            and isinstance(fallback.get("used"), bool)
            and isinstance(fallback.get("provenance"), str)
            and fallback.get("provenance")
        )
        category = failure_category(result, compatible, fallback_ok)
        transport_outcome = result.get("transportOutcome")
        transport_outcome = transport_outcome if isinstance(transport_outcome, dict) else {}
        identity_status = result.get("identityStatus")
        identity_status = identity_status if isinstance(identity_status, dict) else {}
        comparable = bool(
            compatible
            and result.get("benchmarkFault") is False
            and transport_outcome.get("status") == "success"
            and identity_status.get("confidence") == "confirmed"
            and fallback_ok
            and isinstance(result.get("requestedIdentity"), str)
            and bool(result.get("requestedIdentity"))
            and isinstance(result.get("servedIdentity"), str)
            and bool(result.get("servedIdentity"))
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
        measured_cost_usd += cost if cost is not None else 0
        human, human_rejection = human_rubric_evidence(directory, result, case)
        attempt = {
            "path": str(directory),
            "requested_candidate": result.get("requestedIdentity"),
            "served_identity": result.get("servedIdentity"),
            "endpoint_provider": result.get("endpointProvider"),
            "billing_mode": result.get("billingMode") or receipt.get("billingMode"),
            "transport": result.get("transport"),
            "role": result.get("role"),
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
        role_attempts = [
            attempt for group in role_groups for attempt in group["attempt_records"]
            if attempt["comparable"]
        ]
        incomplete_for_role = [item for item in incomplete if item.get("role") == role]
        role_operational_retries = sum(
            (Counter(group["operational_retries"]) for group in role_groups), Counter()
        )
        role_operational_retries.update(
            item["failure_category"] for item in incomplete_for_role
            if item.get("failure_category") in OPERATIONAL_FAILURE_CATEGORIES
        )
        case_coverage = []
        for case in role_cases:
            matching = [group for group in role_groups if group["case_id"] == case.get("id")]
            case_coverage.append(
                {
                    "case_id": case.get("id"),
                    "case_revision": case.get("revision"),
                    "prompt_revision": case.get("promptRevision"),
                    "required_capabilities": case.get("requiredCapabilities", []),
                    "applicability": case.get("applicability"),
                    "compatible_groups": len(matching),
                    "comparable_attempts": sum(group["comparable_attempts"] for group in matching),
                    "validated_attempts": sum(group["validated_attempts"] for group in matching),
                    "latest_observed_at": max(
                        (group["latest_observed_at"] for group in matching if group["latest_observed_at"] is not None),
                        default=None,
                    ),
                }
            )
        missing_cases = [item["case_id"] for item in case_coverage if item["comparable_attempts"] == 0]
        first_pass = [group["first_pass_validated"] for group in role_groups if group["first_pass_validated"] is not None]
        valid_groups = [group for group in role_groups if group["attempts_to_valid"] is not None]
        latest = max(
            (group["latest_observed_at"] for group in role_groups if group["latest_observed_at"] is not None),
            default=None,
        )
        role_rows.append(
            {
                "role": role,
                "policy_candidates": len(candidates) if isinstance(candidates, list) else 0,
                "required_cases": len(role_cases),
                "case_coverage": case_coverage,
                "missing_cases": missing_cases,
                "gap": "no comparable current evidence" if not role_attempts else ("incomplete case coverage" if missing_cases else None),
                "confidence": "none" if not role_attempts else ("partial" if missing_cases else "controlled-current"),
                "freshness": {"latest_observed_at": latest, "suite_revision": suite.get("suiteRevision"), "policy_snapshot": policy.get("matrixSnapshot")},
                "best_deterministic_quality": max(
                    (group["best_deterministic_quality"] for group in role_groups if group["best_deterministic_quality"] is not None),
                    default=None,
                ),
                "validated_attempts": sum(group["validated_attempts"] for group in role_groups),
                "comparable_attempts": sum(group["comparable_attempts"] for group in role_groups),
                "first_pass_validated_rate": sum(first_pass) / len(first_pass) if first_pass else None,
                "median_time_to_first_validated_seconds": median(group["time_to_first_validated_seconds"] for group in valid_groups),
                "median_attempts_to_valid": median(group["attempts_to_valid"] for group in valid_groups),
                "median_model_rework_to_valid": median(group["model_rework_to_valid"] for group in valid_groups),
                "median_tokens_to_first_validated": {
                    field: median(group["tokens_to_first_validated"][field] for group in valid_groups)
                    for field in (
                        "prompt_tokens", "completion_tokens", "reasoning_tokens",
                        "cache_read_tokens", "cache_creation_tokens",
                    )
                },
                "median_context_to_first_validated": median(group["context_to_first_validated"] for group in valid_groups),
                "useful_finding_yield": median(group["useful_finding_yield"] for group in role_groups),
                "false_positive_yield": median(group["false_positive_yield"] for group in role_groups),
                "operational_retries": dict(sorted(role_operational_retries.items())),
                "model_failure_counts": dict(sorted(sum((Counter({key: value for key, value in group["failure_counts"].items() if key in MODEL_FAILURE_CATEGORIES}) for group in role_groups), Counter()).items())),
                "instrumentation": {
                    field: telemetry_coverage(role_attempts, field)
                    for field in (
                        "duration_seconds", "prompt_tokens", "completion_tokens", "reasoning_tokens",
                        "cache_read_tokens", "cache_creation_tokens", "context_tokens", "tool_calls",
                        "correction_count", "useful_findings", "false_positives",
                    )
                } | {
                    "attempt_order": {
                        "recorded": sum(group["ordering_available"] for group in role_groups),
                        "groups": len(role_groups),
                        "rate": (sum(group["ordering_available"] for group in role_groups) / len(role_groups)) if role_groups else None,
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
                "retained_attempts": sum(group["attempts"] for group in role_groups) + len(incomplete_for_role),
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
                {"case_id": group["case_id"], "validated_attempts": group["validated_attempts"], "best_deterministic_quality": group["best_deterministic_quality"]}
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
            evaluator_families = {
                (
                    group["suite_revision"], group["suite_digest"],
                    group["scorer_revision"],
                    group["normalizer_revision"], group["normalizer_digest"],
                    group["behavior_revision"], group["behavior_digest"],
                )
                for group in candidate_groups
            }
            competitive = any(
                all(
                    any(
                        group["case_id"] == case_id
                        and group["validated_attempts"] >= 3
                        and (
                            group["suite_revision"], group["suite_digest"],
                            group["scorer_revision"],
                            group["normalizer_revision"], group["normalizer_digest"],
                            group["behavior_revision"], group["behavior_digest"],
                        ) == evaluator_family
                        for group in candidate_groups
                    )
                    for case_id in role_case_ids
                )
                for evaluator_family in evaluator_families
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
                    "controlled_competitive_evidence": bool(role_case_ids and competitive and not failures),
                    "benchmark_faults": benchmark_faults,
                    "benchmark_fault_conclusion": "no model conclusion" if benchmark_faults else None,
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
        "measured_cost_usd": measured_cost_usd,
        "matrix_opportunities": [],
        "routing_conclusion": "no routing change justified",
        "views": {
            "quality": {
                "validated_attempts": sum(role["validated_attempts"] for role in role_rows),
                "comparable_attempts": sum(role["comparable_attempts"] for role in role_rows),
                "roles_with_validated_evidence": [role["role"] for role in role_rows if role["validated_attempts"]],
            },
            "reliability": {
                "model_failure_counts": dict(sorted(sum((Counter(role["model_failure_counts"]) for role in role_rows), Counter()).items())),
                "operational_retry_counts": dict(sorted(sum((Counter(role["operational_retries"]) for role in role_rows), Counter()).items())),
                "historical_v1_attempts": len(historical_v1),
                "incompatible_v2_attempts": len(incompatible_v2),
            },
            "latency": {
                role["role"]: role["instrumentation"]["duration_seconds"] for role in role_rows
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
            "provider_spend": {"measured_cost_usd": measured_cost_usd},
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
        "| Role | Cases | Validated | Best quality | First pass | Time to valid | Attempts/rework | Confidence | Freshness | Gap |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for role in benchmark["roles"]:
        first_pass = "n/a" if role["first_pass_validated_rate"] is None else f"{role['first_pass_validated_rate']:.0%}"
        time_valid = "n/a" if role["median_time_to_first_validated_seconds"] is None else f"{role['median_time_to_first_validated_seconds']:.1f}s"
        attempts = "n/a" if role["median_attempts_to_valid"] is None else f"{role['median_attempts_to_valid']:g}/{role['median_model_rework_to_valid']:g}"
        score = "n/a" if role["best_deterministic_quality"] is None else f"{role['best_deterministic_quality']:g}"
        freshness = role["freshness"]["latest_observed_at"] or "none"
        lines.append(
            f"| {role['role']} | {role['required_cases'] - len(role['missing_cases'])}/{role['required_cases']} | "
            f"{role['validated_attempts']}/{role['comparable_attempts']} | {score} | {first_pass} | {time_valid} | "
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

    lines.extend(["## Controlled model-role evidence", ""])
    evidenced_models = [
        row for row in benchmark["model_role_evidence"]
        if row["strengths"] or row["failures"] or row["benchmark_faults"]
    ]
    if evidenced_models:
        lines.extend(
            [
                "| Role | Requested candidate | Transport | Validated strengths | Attributable failures | Gaps | Benchmark faults | Conclusion |",
                "|---|---|---|---:|---:|---:|---:|---|",
            ]
        )
        for row in evidenced_models:
            lines.append(
                f"| {row['role']} | {row['model']} | {row['transport']} | {len(row['strengths'])} | "
                f"{len(row['failures'])} | {len(row['gaps'])} | {row['benchmark_faults']} | {row['routing_conclusion']} |"
            )
    else:
        lines.append("No attributable current v2 model-role evidence is available.")

    lines.extend(["", "## Controlled reliability and failure attribution", ""])
    if benchmark["groups"]:
        lines.extend(
            [
                "| Candidate | Transport | Role | Case/revision | Validated | First pass | Rework | Operational retries | Endpoint providers |",
                "|---|---|---|---|---:|---:|---:|---|---|",
            ]
        )
        for group in benchmark["groups"]:
            first_pass = "n/a" if group["first_pass_validated"] is None else str(group["first_pass_validated"]).lower()
            rework = "n/a" if group["model_rework_to_valid"] is None else str(group["model_rework_to_valid"])
            lines.append(
                f"| {group['requested_candidate']} | {group['transport']} | {group['role']} | "
                f"{group['case_id']}/{group['case_revision']} | {group['validated_attempts']}/{group['comparable_attempts']} | "
                f"{first_pass} | {rework} | `{json.dumps(group['operational_retries'], sort_keys=True)}` | "
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
            "- A model-role change requires three successful attempts on every applicable local case plus production evidence; incomplete coverage cannot promote a model.",
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
        "repository": str(REPO_ROOT),
        "run_roots": [str(root) for root in roots],
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
