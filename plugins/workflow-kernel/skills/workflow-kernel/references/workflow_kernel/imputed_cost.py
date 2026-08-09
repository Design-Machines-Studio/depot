"""Observation-only API-equivalent cost imputation for attempt rows."""

from __future__ import annotations

import math
import re
from datetime import date


_PRICE_FIELDS = {
    "input_usage_count": "input_usd_per_m",
    "output_usage_count": "output_usd_per_m",
    "cache_read_usage_count": "cache_read_usd_per_m",
}
_UNPRICED_COST_COUNTER_FIELDS = (
    "cache_write_usage_count",
    "reasoning_usage_count",
)
_SNAPSHOT_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _valid_snapshot_date(value):
    if type(value) is not str or _SNAPSHOT_DATE.fullmatch(value) is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_priced_models(models, snapshot, forbidden_slugs=()):
    if type(models) is not list:
        raise ValueError("invalid model matrix")
    slugs = set()
    for model in models:
        if type(model) is not dict:
            raise ValueError("invalid model matrix")
        slug = model.get("slug")
        if (
            type(slug) is not str or not slug
            or slug in forbidden_slugs or slug in slugs
            or model.get("snapshot_date") != snapshot
        ):
            raise ValueError("invalid model matrix")
        slugs.add(slug)
        for field in _PRICE_FIELDS.values():
            price = model.get(field)
            if price is None and field == "cache_read_usd_per_m":
                continue
            if (
                type(price) not in (int, float) or type(price) is bool
                or price < 0 or not math.isfinite(price)
            ):
                raise ValueError("invalid model matrix")
    return slugs


def validate_model_matrix(matrix: dict) -> None:
    """Validate the pricing subset consumed by cost imputation."""
    if type(matrix) is not dict or matrix.get("schema_version") != 1:
        raise ValueError("invalid model matrix")
    snapshot = matrix.get("snapshot_date")
    models = matrix.get("models")
    if (
        not _valid_snapshot_date(snapshot)
        or type(models) is not list or not models
    ):
        raise ValueError("invalid model matrix")
    slugs = _validate_priced_models(models, snapshot)
    native = matrix.get("native_api_equivalent_cost")
    if (
        type(native) is not dict or native.get("schema_version") != 1
        or not _valid_snapshot_date(native.get("snapshot_date"))
        or type(native.get("models")) is not list
        or type(native.get("aliases")) is not dict
        or type(native.get("input_bytes_per_token_estimate")) not in (int, float)
        or type(native.get("input_bytes_per_token_estimate")) is bool
        or native["input_bytes_per_token_estimate"] <= 0
        or not math.isfinite(native["input_bytes_per_token_estimate"])
    ):
        raise ValueError("invalid model matrix")
    native_slugs = _validate_priced_models(
        native["models"], native["snapshot_date"], slugs,
    )
    all_slugs = slugs | native_slugs
    for alias, slug in native["aliases"].items():
        if (
            type(alias) is not str or not alias or "/" in alias
            or type(slug) is not str or slug not in all_slugs
        ):
            raise ValueError("invalid model matrix")


def _priced_identity(row: dict, matrix: dict, models: list):
    model = row.get("model")
    direct = next((item for item in models if item.get("slug") == model), None)
    if direct is not None:
        return direct, None
    # Native identities map only through an explicit matrix-owned API-equivalent
    # alias. This does not guess Sol/Fable/Opus prices or infer by prefix.
    if (
        type(model) is str
        and row.get("implemented_by") in {"codex", "claude"}
        and row.get("provider") in {"codex", "openai", "claude", "anthropic"}
    ):
        native = matrix.get("native_api_equivalent_cost")
        aliases = native.get("aliases") if type(native) is dict else None
        slug = aliases.get(model) if type(aliases) is dict else None
        alias = next((item for item in models if item.get("slug") == slug), None)
        if alias is not None:
            return alias, slug
    return None, None


def impute_attempt_cost(row: dict, matrix: dict) -> dict:
    """Return ``row`` enriched with an API-equivalent cost when priceable.

    Present costs are authoritative and are never replaced. Missing counters
    remain missing; only counters actually present on the row participate in
    the calculation. An absent model, unusable price, or row with no priceable
    counters leaves the row unchanged.
    """
    if type(row) is not dict or row.get("cost_usd") is not None:
        return row
    models = matrix.get("models") if type(matrix) is dict else None
    if type(models) is not list:
        return row
    native = matrix.get("native_api_equivalent_cost")
    if type(native) is dict and type(native.get("models")) is list:
        models = [*models, *native["models"]]
    priced_model, normalized_slug = _priced_identity(row, matrix, models)
    if priced_model is None:
        return row

    unpriced_counters = [
        field for field in _UNPRICED_COST_COUNTER_FIELDS
        if row.get(field) is not None
    ]
    if unpriced_counters:
        result = dict(row)
        provenance = []
        measurement_source = result.get("measurement_source")
        if type(measurement_source) is str and measurement_source:
            provenance.append(measurement_source)
        provenance.append(
            "cost_imputation_excluded(unpriced="
            + "+".join(unpriced_counters) + ")"
        )
        result["measurement_source"] = "+".join(provenance)
        return result

    cost = 0.0
    observed_counter = False
    byte_estimate = False
    for counter_field, price_field in _PRICE_FIELDS.items():
        counter = row.get(counter_field)
        if counter is None:
            continue
        price = priced_model.get(price_field)
        if (
            type(counter) is not int or counter < 0
            or type(price) not in (int, float) or type(price) is bool
            or price < 0 or not math.isfinite(price)
        ):
            return row
        observed_counter = True
        cost += counter * float(price) / 1_000_000
    if (
        normalized_slug is not None
        and row.get("input_usage_count") is None
        and row.get("input_bytes") is not None
    ):
        input_bytes = row["input_bytes"]
        ratio = native.get("input_bytes_per_token_estimate") if type(native) is dict else None
        input_price = priced_model.get("input_usd_per_m")
        if (
            type(input_bytes) is int and input_bytes >= 0
            and type(ratio) in (int, float) and type(ratio) is not bool
            and ratio > 0 and math.isfinite(ratio)
            and type(input_price) in (int, float) and type(input_price) is not bool
            and input_price >= 0 and math.isfinite(input_price)
        ):
            cost += (input_bytes / ratio) * float(input_price) / 1_000_000
            observed_counter = True
            byte_estimate = True
    if not observed_counter:
        return row

    snapshot_date = priced_model.get("snapshot_date", matrix.get("snapshot_date"))
    if type(snapshot_date) is not str or not snapshot_date:
        return row
    result = dict(row)
    result["cost_usd"] = cost
    provenance = []
    measurement_source = result.get("measurement_source")
    if type(measurement_source) is str and measurement_source:
        provenance.append(measurement_source)
    if normalized_slug is not None:
        provenance.append(
            "model_alias(" + row["model"] + "->" + normalized_slug + ")"
        )
    if byte_estimate:
        ratio = native["input_bytes_per_token_estimate"]
        provenance.append(
            "estimated_input_tokens(input_bytes/" + str(ratio)
            + "_bytes_per_token)"
        )
    provenance.append(
        "imputed_cost(model-matrix@" + snapshot_date + ")"
    )
    result["measurement_source"] = "+".join(provenance)
    result["usage_estimated"] = True
    return result
