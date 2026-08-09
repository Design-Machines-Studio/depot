"""Observation-only API-equivalent cost imputation for attempt rows."""

from __future__ import annotations

import math


_PRICE_FIELDS = {
    "input_usage_count": "input_usd_per_m",
    "output_usage_count": "output_usd_per_m",
    "cache_read_usage_count": "cache_read_usd_per_m",
}


def impute_attempt_cost(row: dict, matrix: dict) -> dict:
    """Return ``row`` enriched with an API-equivalent cost when priceable.

    Present costs are authoritative and are never replaced. Missing counters
    remain missing; only counters actually present on the row participate in
    the calculation. An absent model, unusable price, or row with no priceable
    counters leaves the row unchanged.
    """
    if type(row) is not dict or row.get("cost_usd") is not None:
        return row
    model = row.get("model")
    models = matrix.get("models") if type(matrix) is dict else None
    if type(model) is not str or type(models) is not list:
        return row
    priced_model = next(
        (item for item in models if type(item) is dict and item.get("slug") == model),
        None,
    )
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
    result["measurement_source"] = (
        result["measurement_source"]
        + "+imputed_cost(model-matrix@" + snapshot_date + ")"
    )
    result["usage_estimated"] = True
    return result
