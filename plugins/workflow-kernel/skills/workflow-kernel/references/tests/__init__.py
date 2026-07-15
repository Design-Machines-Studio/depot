"""Workflow kernel tests."""
import hashlib
import json
import os
import re
import threading
from unittest.mock import patch


def json_document_boundary_corpus(
    canonical, *, json_reason, document_reason, version_reason,
):
    """Return the shared strict-JSON corpus with loader-specific reasons."""
    return {
        "syntax": ("{", json_reason),
        "oversized_integer": (
            canonical.replace(
                '"schema_version": 1',
                '"schema_version": ' + "9" * 5_000,
                1,
            ),
            json_reason,
        ),
        "over_depth": (
            '{"nested":' + "[" * 1_500 + "0" + "]" * 1_500 + "}",
            document_reason,
        ),
        "mismatched_over_depth": ("[" * 17 + "}" * 17, json_reason),
        "underflow": ("]", json_reason),
        "unterminated_string": ('{"value":"open', json_reason),
        "unterminated_escape": ('{"value":"open\\', json_reason),
        "remaining_opener": ("[0", json_reason),
        "malformed_number": (
            canonical.replace('"schema_version": 1', '"schema_version": 01', 1),
            json_reason,
        ),
        "balanced_grammar_error": ("[" * 17 + "0 1" + "]" * 17, json_reason),
        "nan": ("NaN", json_reason),
        "infinity": ("Infinity", json_reason),
        "negative_infinity": ("-Infinity", json_reason),
        "nested_nan": ('{"value":NaN}', json_reason),
        "nested_infinity": ('{"value":Infinity}', json_reason),
        "nested_negative_infinity": ('[0,-Infinity]', json_reason),
        "depth_integer_boundary": (
            "[" * 17 + "9" * 4_096 + "]" * 17,
            document_reason,
        ),
        "depth_negative_integer_boundary": (
            "[" * 17 + "-" + "9" * 4_096 + "]" * 17,
            document_reason,
        ),
        "depth_integer_over_limit": (
            "[" * 17 + "9" * 4_097 + "]" * 17,
            json_reason,
        ),
        "depth_negative_integer_over_limit": (
            "[" * 17 + "-" + "9" * 4_097 + "]" * 17,
            json_reason,
        ),
        "depth_integer_far_over_limit": (
            "[" * 17 + "9" * 5_000 + "]" * 17,
            json_reason,
        ),
        "thousand_digit_version": (
            canonical.replace(
                '"schema_version": 1',
                '"schema_version": ' + "9" * 1_000,
                1,
            ),
            version_reason,
        ),
    }


def ignored_json_boundary_corpus(canonical):
    """Return strict-JSON boundary documents using an otherwise ignored member."""
    def with_value(raw):
        document = canonical.rstrip()
        if not document.endswith("}"):
            raise AssertionError("boundary corpus requires a JSON object")
        return document[:-1] + ',"_ignored_boundary":' + raw + "}"

    return {
        "syntax": ("{", False),
        "ignored_nan": (with_value("NaN"), False),
        "ignored_infinity": (with_value("Infinity"), False),
        "ignored_negative_infinity": (with_value("-Infinity"), False),
        "ignored_over_depth": (
            with_value("[" * 17 + "0" + "]" * 17),
            False,
        ),
        "ignored_integer_boundary": (with_value("9" * 4_096), True),
        "ignored_negative_integer_boundary": (
            with_value("-" + "9" * 4_096),
            True,
        ),
        "ignored_integer_over_limit": (with_value("9" * 4_097), False),
        "ignored_negative_integer_over_limit": (
            with_value("-" + "9" * 4_097),
            False,
        ),
    }


def snapshot_during_validated_mutation(value, snapshot, mutate):
    """Pause one snapshot after its target seal validates, then mutate it."""
    from workflow_kernel import model as kernel_model

    validated = threading.Event()
    release = threading.Event()
    result = []
    failure = []
    original = kernel_model._ORIGIN_SEALS.validate

    def validate(candidate, kind, primitives):
        original(candidate, kind, primitives)
        if candidate is value:
            validated.set()
            release.wait(timeout=2)

    def run():
        try:
            result.append(snapshot(value))
        except BaseException as error:
            failure.append(error)

    with patch.object(kernel_model._ORIGIN_SEALS, "validate", side_effect=validate):
        worker = threading.Thread(target=run)
        worker.start()
        if not validated.wait(timeout=2):
            release.set()
            worker.join(timeout=2)
            raise AssertionError("snapshot never reached origin validation")
        mutate()
        release.set()
        worker.join(timeout=2)
    if worker.is_alive():
        raise AssertionError("snapshot worker did not finish")
    if failure:
        raise failure[0]
    return result[0]


def _json_equal(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            _json_equal(left[name], right[name]) for name in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            _json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def schema_matches(value, schema, root=None):
    """Match the JSON Schema keyword superset shared by policy tests."""
    root = schema if root is None else root
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        if not schema_matches(value, target, root):
            return False
    expected_type = schema.get("type")
    if expected_type is not None:
        names = expected_type if isinstance(expected_type, list) else [expected_type]
        matches = {
            "object": type(value) is dict,
            "array": type(value) is list,
            "string": type(value) is str,
            "integer": type(value) is int,
            "boolean": type(value) is bool,
            "null": value is None,
        }
        if not any(matches.get(name, False) for name in names):
            return False
    if "const" in schema and not _json_equal(value, schema["const"]):
        return False
    if "enum" in schema and not any(
        _json_equal(value, candidate) for candidate in schema["enum"]
    ):
        return False
    if "oneOf" in schema and sum(
        schema_matches(value, candidate, root) for candidate in schema["oneOf"]
    ) != 1:
        return False
    if type(value) is str and len(value) < schema.get("minLength", 0):
        return False
    if type(value) is str and len(value) > schema.get("maxLength", len(value)):
        return False
    if type(value) is str and "pattern" in schema and re.search(
        schema["pattern"], value,
    ) is None:
        return False
    if type(value) is int and value < schema.get("minimum", value):
        return False
    if any(not schema_matches(value, item, root) for item in schema.get("allOf", [])):
        return False
    if "if" in schema and schema_matches(value, schema["if"], root):
        if not schema_matches(value, schema.get("then", {}), root):
            return False
    if type(value) is dict:
        properties = schema.get("properties", {})
        if not set(schema.get("required", [])) <= set(value):
            return False
        additional = schema.get("additionalProperties", True)
        extras = set(value) - set(properties)
        if additional is False and extras:
            return False
        if type(additional) is dict and any(
            not schema_matches(value[name], additional, root) for name in extras
        ):
            return False
        if "propertyNames" in schema and any(
            not schema_matches(name, schema["propertyNames"], root)
            for name in value
        ):
            return False
        if any(
            name in properties and not schema_matches(item, properties[name], root)
            for name, item in value.items()
        ):
            return False
    if type(value) is list:
        if not schema.get("minItems", 0) <= len(value) <= schema.get(
            "maxItems", len(value)
        ):
            return False
        if schema.get("uniqueItems") and len({
            json.dumps(item, sort_keys=True) for item in value
        }) != len(value):
            return False
        prefix = schema.get("prefixItems", [])
        if any(
            not schema_matches(value[index], item_schema, root)
            for index, item_schema in enumerate(prefix[:len(value)])
        ):
            return False
        if "items" in schema and any(
            not schema_matches(item, schema["items"], root)
            for item in value[len(prefix):]
        ):
            return False
        if "contains" in schema and not any(
            schema_matches(item, schema["contains"], root) for item in value
        ):
            return False
    return True


def swap_parent_after_relative_stat(parent, entry_name):
    """Return one stat injector shared by present and missing absence checks."""
    parent = parent.resolve()
    moved = parent.parent / "moved"
    original_stat = os.stat
    swapped = False

    def injected(path, *args, **kwargs):
        nonlocal swapped
        matches = (path == entry_name and kwargs.get("dir_fd") is not None
                   and not swapped)
        try:
            result = original_stat(path, *args, **kwargs)
        except FileNotFoundError:
            if matches:
                swapped = True
                parent.rename(moved)
                parent.mkdir()
            raise
        if matches:
            swapped = True
            parent.rename(moved)
            parent.mkdir()
            (parent / entry_name).touch()
        return result

    return injected


def detail_digest(value):
    return "value-sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def detail_key_digest(value):
    return "key-sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_harness_profile():
    """Return the repo's canonical harness profile for explicit-path tests.

    The runtime never discovers this file implicitly (installed caches have
    no depot ancestor); tests are repository development artifacts, so
    locating the checked-in canonical profile here is legitimate.
    """
    from pathlib import Path

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "plugins" / "pipeline" / "references" / "harness-profile.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("canonical harness-profile.json not found")
