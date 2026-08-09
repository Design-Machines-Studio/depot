"""Observation-only API-equivalent cost imputation for attempt rows."""

from __future__ import annotations

import math
import re


_PRICE_FIELDS = {
    "input_usage_count": "input_usd_per_m",
    "output_usage_count": "output_usd_per_m",
    "cache_read_usage_count": "cache_read_usd_per_m",
}
_SNAPSHOT_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def validate_model_matrix(matrix: dict) -> None:
    """Validate the pricing subset consumed by cost imputation."""
    if type(matrix) is not dict or matrix.get("schema_version") != 1:
        raise ValueError("invalid model matrix")
    snapshot = matrix.get("snapshot_date")
    models = matrix.get("models")
    if (
        type(snapshot) is not str or _SNAPSHOT_DATE.fullmatch(snapshot) is None
        or type(models) is not list or not models
    ):
        raise ValueError("invalid model matrix")
    slugs = set()
    for model in models:
        if type(model) is not dict:
            raise ValueError("invalid model matrix")
        slug = model.get("slug")
        if type(slug) is not str or not slug or slug in slugs:
            raise ValueError("invalid model matrix")
        slugs.add(slug)
        if model.get("snapshot_date") != snapshot:
            raise ValueError("invalid model matrix")
        for field in _PRICE_FIELDS.values():
            price = model.get(field)
            if price is None and field == "cache_read_usd_per_m":
                continue
            if (
                type(price) not in (int, float) or type(price) is bool
                or price < 0 or not math.isfinite(price)
            ):
                raise ValueError("invalid model matrix")
    aliases = matrix.get("native_api_equivalent_aliases", {})
    if type(aliases) is not dict:
        raise ValueError("invalid model matrix")
    for alias, slug in aliases.items():
        if (
            type(alias) is not str or not alias or "/" in alias
            or type(slug) is not str or slug not in slugs
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
        slug = matrix.get("native_api_equivalent_aliases", {}).get(model)
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
    priced_model, normalized_slug = _priced_identity(row, matrix, models)
    if priced_model is None:
        return row

    cost = 0.0
    observed_counter = False
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
    if not observed_counter:
        return row

    snapshot_date = priced_model.get("snapshot_date", matrix.get("snapshot_date"))
    if type(snapshot_date) is not str or not snapshot_date:
        return row
    result = dict(row)
    result["cost_usd"] = cost
    alias_provenance = ""
    if normalized_slug is not None:
        alias_provenance = (
            "+model_alias(" + row["model"] + "->" + normalized_slug + ")"
        )
    result["measurement_source"] = (
        result["measurement_source"] + alias_provenance
        + "+imputed_cost(model-matrix@" + snapshot_date + ")"
    )
    result["usage_estimated"] = True
    return result
