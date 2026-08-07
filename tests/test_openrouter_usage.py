"""Tests for the OpenRouter receipt usage translator and CLI command."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from workflow_kernel import cli
from workflow_kernel.cost_summary import (
    _kernel_version_string,
    build_run_cost_summary,
    validate_run_cost_summary,
)
from workflow_kernel.openrouter_usage import translate_openrouter_receipt
from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
from workflow_kernel.runtime_resolution import KERNEL_VERSION

FIXTURES = Path(__file__).parent / "fixtures"
SUCCESS_FIXTURE = FIXTURES / "openrouter-receipt-success.json"
NO_USAGE_FIXTURE = FIXTURES / "openrouter-receipt-no-usage.json"

USAGE_KEYS = {
    "usage_count", "input_usage_count", "output_usage_count",
    "cache_read_usage_count", "cache_write_usage_count",
    "reasoning_usage_count", "cost_usd",
}
BASE_KEYS = {
    "usage_scope", "measurement_source", "usage_estimated", "attempt",
    "chunk_id", "node_id", "duration_seconds", "lane",
    "requested_provider", "attempted_provider", "implemented_by",
    "provider", "model", "host",
}
TRANSLATE_ARGS = dict(
    lane="implementation", chunk_id="chunk-a", node_id="chunk-a",
    attempt=1, host="codex", duration_seconds=12.5,
)


def _receipt(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _envelope(payload, sequence=0):
    envelope = {
        "run_id": "openrouter-e2e", "sequence": sequence,
        "stage": "attempt_usage", "status": "observed",
        "occurred_at": "2026-08-07T00:00:00Z",
        "authoritative_receipt": "receipts/openrouter-%d.json" % sequence,
    }
    envelope.update(payload)
    return envelope


def _invoke(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def _cli_args(receipt_path, output=None):
    argv = [
        "openrouter-usage",
        "--receipt", str(receipt_path),
        "--lane", "implementation",
        "--chunk-id", "chunk-a",
        "--node-id", "chunk-a",
        "--attempt", "1",
        "--host", "codex",
        "--duration-seconds", "12.5",
    ]
    if output is not None:
        argv += ["--output", str(output)]
    return argv


class OpenRouterUsageTranslationTests(unittest.TestCase):
    def test_success_fixture_maps_all_counters(self):
        payload = translate_openrouter_receipt(
            _receipt(SUCCESS_FIXTURE), **TRANSLATE_ARGS,
        )
        self.assertEqual(payload["usage_scope"], "attempt")
        self.assertEqual(payload["measurement_source"], "openrouter_api_receipt")
        self.assertIs(payload["usage_estimated"], False)
        self.assertEqual(payload["attempt"], 1)
        self.assertEqual(payload["chunk_id"], "chunk-a")
        self.assertEqual(payload["node_id"], "chunk-a")
        self.assertEqual(payload["duration_seconds"], 12.5)
        self.assertEqual(payload["lane"], "implementation")
        self.assertEqual(payload["requested_provider"], "openrouter")
        self.assertEqual(payload["attempted_provider"], "openrouter")
        self.assertEqual(payload["implemented_by"], "openrouter")
        self.assertEqual(payload["provider"], "Modal")
        self.assertEqual(payload["model"], "moonshotai/kimi-k3")
        self.assertEqual(payload["host"], "codex")
        self.assertEqual(payload["input_usage_count"], 52660)
        self.assertEqual(payload["output_usage_count"], 35579)
        self.assertEqual(payload["usage_count"], 88239)
        self.assertEqual(payload["cache_read_usage_count"], 64)
        self.assertEqual(payload["cache_write_usage_count"], 0)
        self.assertEqual(payload["reasoning_usage_count"], 32395)
        self.assertEqual(payload["cost_usd"], 0.6914922)

    def test_exact_payload_key_set_excludes_receipt_provenance(self):
        payload = translate_openrouter_receipt(
            _receipt(SUCCESS_FIXTURE), **TRANSLATE_ARGS,
        )
        self.assertEqual(set(payload), BASE_KEYS | USAGE_KEYS)
        for leaked in (
            "generation_id", "generationId", "authorization", "routing", "cost",
        ):
            self.assertNotIn(leaked, payload)

    def test_missing_source_keys_are_omitted_never_null(self):
        receipt = _receipt(SUCCESS_FIXTURE)
        del receipt["usage"]["prompt_tokens_details"]
        del receipt["usage"]["completion_tokens_details"]
        del receipt["usage"]["cost"]
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        self.assertEqual(payload["measurement_source"], "openrouter_api_receipt")
        for key in (
            "cache_read_usage_count", "cache_write_usage_count",
            "reasoning_usage_count", "cost_usd",
        ):
            self.assertNotIn(key, payload)
        self.assertTrue(all(value is not None for value in payload.values()))

    def test_omitted_counters_render_null_in_lane_row(self):
        receipt = _receipt(SUCCESS_FIXTURE)
        del receipt["usage"]["prompt_tokens_details"]
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        events = translate_pipeline_receipts([_envelope(payload)])
        summary = build_run_cost_summary(events)
        validate_run_cost_summary(summary)
        (lane,) = summary["lanes"]
        self.assertIsNone(lane["cache_read_usage_count"])
        self.assertIsNone(lane["cache_write_usage_count"])
        self.assertEqual(lane["usage_count"], 88239)

    def test_unknown_usage_spellings_are_omitted_not_zeroed(self):
        receipt = _receipt(SUCCESS_FIXTURE)
        receipt["usage"] = {
            "promptTokens": 100, "totalTokens": 200, "costUsd": 1.5,
        }
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        for key in USAGE_KEYS:
            self.assertNotIn(key, payload)
        self.assertEqual(
            payload["measurement_source"], "openrouter_receipt_no_usage",
        )

    def test_provider_and_model_fallback_chain(self):
        receipt = _receipt(SUCCESS_FIXTURE)
        receipt["servingProvider"] = None
        receipt["responseModel"] = None
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        self.assertEqual(payload["provider"], "not_reported")
        self.assertEqual(payload["model"], "moonshotai/kimi-k3")
        receipt["attemptedModel"] = None
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        self.assertEqual(payload["model"], "moonshotai/kimi-k3")
        receipt["requestedModel"] = None
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        self.assertEqual(payload["model"], "not_reported")

    def test_no_usage_failure_receipt(self):
        payload = translate_openrouter_receipt(
            _receipt(NO_USAGE_FIXTURE), **TRANSLATE_ARGS,
        )
        self.assertEqual(set(payload), BASE_KEYS)
        self.assertEqual(
            payload["measurement_source"], "openrouter_receipt_no_usage",
        )
        self.assertEqual(payload["model"], "moonshotai/kimi-k3")
        self.assertEqual(payload["provider"], "not_reported")
        self.assertTrue(all(value is not None for value in payload.values()))

    def test_no_usage_payload_survives_intake(self):
        payload = translate_openrouter_receipt(
            _receipt(NO_USAGE_FIXTURE), **TRANSLATE_ARGS,
        )
        events = translate_pipeline_receipts([_envelope(payload)])
        summary = build_run_cost_summary(events)
        validate_run_cost_summary(summary)
        (lane,) = summary["lanes"]
        self.assertEqual(
            lane["measurement_source"], "openrouter_receipt_no_usage",
        )
        self.assertIsNone(lane["usage_count"])
        self.assertIsNone(lane["cost_usd"])
        self.assertEqual(
            summary["measurement_coverage"]["usage"]["measured"], 0,
        )

    def test_no_measurement_allowance_is_one_provenance_string_wide(self):
        payload = translate_openrouter_receipt(
            _receipt(NO_USAGE_FIXTURE), **TRANSLATE_ARGS,
        )
        payload["measurement_source"] = "provider_receipt"
        with self.assertRaises(ValueError) as caught:
            translate_pipeline_receipts([_envelope(payload)])
        self.assertIn(
            "scoped usage row has no measurement", str(caught.exception),
        )

    def test_invalid_counter_values_rejected(self):
        for bad in (-1, 1.5, True, "100"):
            with self.subTest(bad=bad):
                receipt = _receipt(SUCCESS_FIXTURE)
                receipt["usage"]["prompt_tokens"] = bad
                with self.assertRaises(ValueError):
                    translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)

    def test_invalid_cost_values_rejected(self):
        for bad in (-0.5, "0.5", True, float("nan"), float("inf")):
            with self.subTest(bad=bad):
                receipt = _receipt(SUCCESS_FIXTURE)
                receipt["usage"]["cost"] = bad
                with self.assertRaises(ValueError):
                    translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)

    def test_cost_maps_from_usage_cost_only(self):
        receipt = _receipt(SUCCESS_FIXTURE)
        del receipt["usage"]["cost"]
        receipt["cost"] = 999.0
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        self.assertNotIn("cost_usd", payload)
        self.assertEqual(payload["measurement_source"], "openrouter_api_receipt")

    def test_argument_validation(self):
        receipt = _receipt(SUCCESS_FIXTURE)
        for label, override in (
            ("zero attempt", {"attempt": 0}),
            ("bool attempt", {"attempt": True}),
            ("empty chunk_id", {"chunk_id": ""}),
            ("empty node_id", {"node_id": ""}),
            ("empty host", {"host": ""}),
            ("empty lane", {"lane": ""}),
            ("negative duration", {"duration_seconds": -1.0}),
            ("nan duration", {"duration_seconds": float("nan")}),
        ):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    translate_openrouter_receipt(
                        receipt, **{**TRANSLATE_ARGS, **override},
                    )

    def test_end_to_end_attempt_usage_lands_in_run_cost_summary(self):
        payload = translate_openrouter_receipt(
            _receipt(SUCCESS_FIXTURE), **TRANSLATE_ARGS,
        )
        events = translate_pipeline_receipts([_envelope(payload)])
        summary = build_run_cost_summary(events)
        validate_run_cost_summary(summary)
        # Observation-only: the artifact contract stays at schema version 1.
        self.assertEqual(summary["schema_version"], 1)
        (lane,) = summary["lanes"]
        self.assertEqual(lane["measurement_source"], "openrouter_api_receipt")
        self.assertEqual(lane["usage_count"], 88239)
        self.assertEqual(lane["cost_usd"], 0.6914922)
        self.assertEqual(
            summary["measurement_coverage"]["usage"]["measured"], 1,
        )
        self.assertEqual(
            summary["measurement_coverage"]["usage"]["missing"], 0,
        )
        self.assertEqual(
            summary["measurement_coverage"]["cost"]["measured"], 1,
        )

    def test_kernel_version_is_0_9_0(self):
        self.assertEqual(KERNEL_VERSION, (0, 9, 0))
        self.assertEqual(_kernel_version_string(), "0.9.0")


class OpenRouterUsageCliTests(unittest.TestCase):
    def test_cli_success_stdout_when_no_output(self):
        code, stdout, _ = _invoke(_cli_args(SUCCESS_FIXTURE))
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["measurement_source"], "openrouter_api_receipt")
        self.assertEqual(payload["provider"], "Modal")
        self.assertEqual(payload["usage_count"], 88239)

    def test_cli_failure_receipt_exits_zero(self):
        code, stdout, _ = _invoke(_cli_args(NO_USAGE_FIXTURE))
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(set(payload), BASE_KEYS)
        self.assertEqual(
            payload["measurement_source"], "openrouter_receipt_no_usage",
        )

    def test_cli_byte_identical_canonical_output(self):
        code1, first, _ = _invoke(_cli_args(SUCCESS_FIXTURE))
        code2, second, _ = _invoke(_cli_args(SUCCESS_FIXTURE))
        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(
            first,
            json.dumps(
                payload, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ) + "\n",
        )

    def test_cli_rejects_bad_schema_versions_without_writing_output(self):
        mutations = (
            ("missing", lambda r: r.pop("schemaVersion")),
            ("null", lambda r: r.update(schemaVersion=None)),
            ("string", lambda r: r.update(schemaVersion="2")),
            ("one", lambda r: r.update(schemaVersion=1)),
            ("three", lambda r: r.update(schemaVersion=3)),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as directory:
                    receipt_path = Path(directory) / "receipt.json"
                    receipt = _receipt(SUCCESS_FIXTURE)
                    mutate(receipt)
                    receipt_path.write_text(
                        json.dumps(receipt), encoding="utf-8",
                    )
                    output = Path(directory) / "out.json"
                    code, _, stderr = _invoke(_cli_args(receipt_path, output))
                    self.assertNotEqual(code, 0)
                    self.assertFalse(output.exists())
                    self.assertTrue(stderr.strip())

    def test_cli_rejects_invalid_usage_values_without_writing_output(self):
        receipt = _receipt(SUCCESS_FIXTURE)
        receipt["usage"]["prompt_tokens"] = -5
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            output = Path(directory) / "out.json"
            code, _, _ = _invoke(_cli_args(receipt_path, output))
            self.assertNotEqual(code, 0)
            self.assertFalse(output.exists())

    def test_cli_missing_required_flag_exits_nonzero(self):
        full = _cli_args(SUCCESS_FIXTURE)
        for flag in (
            "--receipt", "--lane", "--chunk-id", "--node-id",
            "--attempt", "--host", "--duration-seconds",
        ):
            with self.subTest(flag=flag):
                index = full.index(flag)
                argv = full[:index] + full[index + 2:]
                code, _, _ = _invoke(argv)
                self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
