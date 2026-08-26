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


def benchmark_rollup(root: Path | None) -> dict[str, Any]:
    if root is None:
        return {"result_root": None, "attempts": 0, "groups": [], "incomplete_attempts": []}
    directories = result_dirs(root)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    incomplete: list[str] = []
    measured_cost_usd = 0.0
    for directory in directories:
        result_path = directory / "result.json"
        if not result_path.is_file():
            incomplete.append(str(directory))
            continue
        try:
            result = load_json(result_path)
        except IntelligenceError:
            incomplete.append(str(directory))
            continue
        if not isinstance(result, dict):
            incomplete.append(str(directory))
            continue
        usage = result.get("usage")
        if isinstance(usage, dict):
            cost = number(usage.get("cost") if "cost" in usage else usage.get("cost_usd"))
            if cost is not None:
                measured_cost_usd += cost
        model = result.get("servedModel") or result.get("requestedModel") or "unknown"
        case_id = result.get("caseId") or "unknown"
        transport = result.get("transport") or result.get("provider") or "unknown"
        grouped[(str(model), str(case_id), str(transport))].append(result)

    groups = []
    for (model, case_id, transport), results in sorted(grouped.items()):
        parsed_successes = [item for item in results if item.get("parsed") is True]
        quality = [number(item.get("qualityScore")) for item in parsed_successes]
        duration = [number(item.get("durationSeconds")) for item in parsed_successes]
        costs = []
        prompt_tokens = []
        completion_tokens = []
        reasoning_tokens = []
        for item in parsed_successes:
            usage = item.get("usage")
            if not isinstance(usage, dict):
                continue
            costs.append(number(usage.get("cost") if "cost" in usage else usage.get("cost_usd")))
            prompt_tokens.append(number(usage.get("prompt_tokens") if "prompt_tokens" in usage else usage.get("input_tokens")))
            completion_tokens.append(number(usage.get("completion_tokens") if "completion_tokens" in usage else usage.get("output_tokens")))
            reasoning_tokens.append(number(usage.get("reasoning_tokens")))
        groups.append(
            {
                "model": model,
                "case_id": case_id,
                "transport": transport,
                "attempts": len(results),
                "parsed_successes": len(parsed_successes),
                "success_rate": len(parsed_successes) / len(results) if results else 0,
                "median_quality_score": median(quality),
                "median_duration_seconds": median(duration),
                "median_cost_usd": median(costs),
                "median_prompt_tokens": median(prompt_tokens),
                "median_completion_tokens": median(completion_tokens),
                "median_reasoning_tokens": median(reasoning_tokens),
            }
        )
    return {
        "result_root": str(root),
        "attempts": sum(group["attempts"] for group in groups) + len(incomplete),
        "groups": groups,
        "incomplete_attempts": incomplete,
        "measured_cost_usd": measured_cost_usd,
    }


def render_report(report: dict[str, Any]) -> str:
    production = report["production"]
    benchmark = report["benchmarks"]
    lines = [
        f"# Depot model intelligence — {report['generated_at'][:10]}",
        "",
        "## Evidence coverage",
        "",
        f"- Run cost summaries: {production['cost_summary_artifacts']}",
        f"- Workflow metrics: {production['metrics_artifacts']}",
        f"- Empty cost summaries: {production['empty_cost_summaries']}",
        f"- Benchmark attempts: {benchmark['attempts']}",
        f"- Incomplete benchmark attempts: {len(benchmark['incomplete_attempts'])}",
    ]
    if production["malformed_artifacts"]:
        lines.append(f"- Malformed artifacts: {len(production['malformed_artifacts'])}")
    lines.extend(["", "## Production economics by model", ""])
    if production["by_model"]:
        lines.extend(
            [
                "| Model | Attempts | Duration | Input tokens | Output tokens | Input bytes | Cost | Finding contributions |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in production["by_model"]:
            lines.append(
                "| {model} | {attempts} | {duration_seconds:.1f}s | {input_tokens:.0f} | {output_tokens:.0f} | {input_bytes:.0f} | ${measured_cost_usd:.4f} | {finding_contributions} |".format(**row)
            )
    else:
        lines.append("No model-attributed lane usage is available.")

    lines.extend(["", "## Production economics by lane and model", ""])
    if production["by_lane_model"]:
        lines.extend(
            [
                "| Lane | Model | Attempts | Duration | Input tokens | Output tokens | Input bytes | Cost |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in production["by_lane_model"]:
            lines.append(
                "| {lane} | {model} | {attempts} | {duration_seconds:.1f}s | {input_tokens:.0f} | {output_tokens:.0f} | {input_bytes:.0f} | ${measured_cost_usd:.4f} |".format(**row)
            )
    else:
        lines.append("No lane/model-attributed usage is available.")

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
            "## Controlled benchmarks",
            "",
        ]
    )
    if benchmark["groups"]:
        lines.extend(
            [
                "| Model | Transport | Case | Success | Median quality | Median duration | Median cost |",
                "|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for group in benchmark["groups"]:
            cost = "n/a" if group["median_cost_usd"] is None else f"${group['median_cost_usd']:.4f}"
            lines.append(
                f"| {group['model']} | {group['transport']} | {group['case_id']} | {group['parsed_successes']}/{group['attempts']} | {group['median_quality_score']} | {group['median_duration_seconds']}s | {cost} |"
            )
    else:
        lines.append("No benchmark results were found.")
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Token counts and deterministic input bytes are different units and are never added together.",
            "- Subscription API-equivalent cost is opportunity-cost evidence, not billed spend.",
            "- A model-role change requires three successful attempts on every applicable local case plus production evidence; incomplete coverage cannot promote a model.",
            "- Exact identity remains in private receipts; this report publishes aggregates only.",
            "",
        ]
    )
    return "\n".join(lines)


def report_command(args: argparse.Namespace) -> int:
    roots = [Path(item).resolve() for item in args.run_root] if args.run_root else list(DEFAULT_RUN_ROOTS)
    benchmark_root = Path(args.benchmark_root).resolve() if args.benchmark_root else None
    report = {
        "schema_version": 1,
        "generated_at": parse_observed_at(args.observed_at).isoformat(timespec="seconds"),
        "repository": str(REPO_ROOT),
        "run_roots": [str(root) for root in roots],
        "production": production_rollup(roots),
        "benchmarks": benchmark_rollup(benchmark_root),
    }
    if args.json_output:
        write_atomic(Path(args.json_output).resolve(), pretty_json(report))
    if args.markdown_output:
        write_atomic(Path(args.markdown_output).resolve(), render_report(report))
    print(pretty_json(report), end="")
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
