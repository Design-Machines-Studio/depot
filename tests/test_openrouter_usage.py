"""Tests for the OpenRouter receipt usage translator and CLI command."""

import contextlib
import dataclasses
import io
import json
import tempfile
import unittest
from pathlib import Path

from workflow_kernel import cli
from workflow_kernel._usage_identity import AttemptContext
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
FAILED_FIXTURE = FIXTURES / "openrouter-receipt-no-usage.json"
SUCCESS_NO_USAGE_FIXTURE = (
    FIXTURES / "openrouter-receipt-success-no-usage.json"
)

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
CONTEXT = AttemptContext(
    lane="implementation", chunk_id="chunk-a", node_id="chunk-a",
    attempt=1, host="codex", duration_seconds=12.5,
)
# Splatted at every call site, so the carrier swap stays a one-line change.
TRANSLATE_ARGS = {"context": CONTEXT}


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
        self.assertEqual(
            set(payload), BASE_KEYS | USAGE_KEYS | {"identity_provenance"},
        )
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

    def test_failed_receipt_is_tagged_as_failed_and_names_the_reason(self):
        """A failed attempt must not read as an attempt that simply reported
        nothing. OpenRouter can bill a generation that returns HTTP 200 with
        `usage: null`, so a row that hides the failure hides real spend."""
        payload = translate_openrouter_receipt(
            _receipt(FAILED_FIXTURE), **TRANSLATE_ARGS,
        )
        self.assertEqual(
            set(payload),
            BASE_KEYS | {"failure_kind", "identity_provenance"},
        )
        self.assertEqual(
            payload["measurement_source"], "openrouter_receipt_failed",
        )
        self.assertEqual(payload["failure_kind"], "incomplete_stream")
        self.assertEqual(payload["model"], "moonshotai/kimi-k3")
        self.assertEqual(payload["provider"], "not_reported")
        self.assertTrue(all(value is not None for value in payload.values()))

    def test_unmetered_success_is_distinguishable_from_a_failure(self):
        """The two measurement-less cases carry different provenance."""
        payload = translate_openrouter_receipt(
            _receipt(SUCCESS_NO_USAGE_FIXTURE), **TRANSLATE_ARGS,
        )
        self.assertEqual(
            payload["measurement_source"], "openrouter_receipt_no_usage",
        )
        self.assertNotIn("failure_kind", payload)
        self.assertEqual(payload["provider"], "Z.AI")
        self.assertEqual(payload["model"], "z-ai/glm-5.2")

    def test_missing_outcome_is_treated_as_a_failure(self):
        """A receipt that cannot state it succeeded has not demonstrated
        that it did."""
        receipt = _receipt(SUCCESS_NO_USAGE_FIXTURE)
        del receipt["outcome"]
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        self.assertEqual(
            payload["measurement_source"], "openrouter_receipt_failed",
        )
        self.assertEqual(payload["failure_kind"], "unreported")

    def test_failed_receipt_still_reports_counters_it_carries(self):
        """A partial generation that billed tokens must show those tokens."""
        receipt = _receipt(FAILED_FIXTURE)
        receipt["usage"] = {"prompt_tokens": 1200, "cost": 0.5}
        payload = translate_openrouter_receipt(receipt, **TRANSLATE_ARGS)
        self.assertEqual(
            payload["measurement_source"], "openrouter_receipt_failed",
        )
        self.assertEqual(payload["input_usage_count"], 1200)
        self.assertEqual(payload["cost_usd"], 0.5)
        self.assertEqual(payload["failure_kind"], "incomplete_stream")

    def test_identity_provenance_marks_receipt_sourced_fields(self):
        """Provider and model are the only receipt-sourced payload fields, and
        the row says so. Lane, chunk, node, attempt, and host come from the
        caller, so lane attribution cannot be forged by editing a receipt."""
        payload = translate_openrouter_receipt(
            _receipt(SUCCESS_FIXTURE), **TRANSLATE_ARGS,
        )
        self.assertEqual(payload["identity_provenance"], "receipt_asserted")
        self.assertEqual(payload["lane"], CONTEXT.lane)
        self.assertEqual(payload["chunk_id"], CONTEXT.chunk_id)
        self.assertEqual(payload["requested_provider"], "openrouter")

        forged = _receipt(SUCCESS_FIXTURE)
        forged["servingProvider"] = "Totally-Legit-Inc"
        forged["responseModel"] = "vendor/imaginary-model"
        forged["lane"] = "some-other-lane"
        forged["chunk_id"] = "some-other-chunk"
        tampered = translate_openrouter_receipt(forged, **TRANSLATE_ARGS)
        self.assertEqual(tampered["provider"], "Totally-Legit-Inc")
        self.assertEqual(tampered["identity_provenance"], "receipt_asserted")
        self.assertEqual(tampered["lane"], CONTEXT.lane)
        self.assertEqual(tampered["chunk_id"], CONTEXT.chunk_id)

    def test_measurementless_payloads_survive_intake(self):
        for fixture, source in (
            (FAILED_FIXTURE, "openrouter_receipt_failed"),
            (SUCCESS_NO_USAGE_FIXTURE, "openrouter_receipt_no_usage"),
        ):
            with self.subTest(source=source):
                self._assert_survives_intake(fixture, source)

    def _assert_survives_intake(self, fixture, source):
        payload = translate_openrouter_receipt(
            _receipt(fixture), **TRANSLATE_ARGS,
        )
        events = translate_pipeline_receipts([_envelope(payload)])
        summary = build_run_cost_summary(events)
        validate_run_cost_summary(summary)
        (lane,) = summary["lanes"]
        self.assertEqual(lane["measurement_source"], source)
        self.assertIsNone(lane["usage_count"])
        self.assertIsNone(lane["cost_usd"])
        self.assertEqual(
            summary["measurement_coverage"]["usage"]["measured"], 0,
        )

    def test_no_measurement_allowance_is_exactly_two_strings_wide(self):
        """Only the two OpenRouter measurement-less provenance strings may
        carry a scoped row with no counters. Every other source fails closed,
        so absence cannot be laundered through an invented provenance."""
        payload = translate_openrouter_receipt(
            _receipt(FAILED_FIXTURE), **TRANSLATE_ARGS,
        )
        payload.pop("failure_kind")
        payload["measurement_source"] = "provider_receipt"
        with self.assertRaises(ValueError) as caught:
            translate_pipeline_receipts([_envelope(payload)])
        self.assertIn(
            "scoped usage row has no measurement", str(caught.exception),
        )

    def test_failure_kind_is_rejected_on_a_non_failed_row(self):
        payload = translate_openrouter_receipt(
            _receipt(SUCCESS_FIXTURE), **TRANSLATE_ARGS,
        )
        payload["failure_kind"] = "smuggled"
        with self.assertRaises(ValueError) as caught:
            translate_pipeline_receipts([_envelope(payload)])
        self.assertIn(
            "failure kind on a non-failed usage row", str(caught.exception),
        )

    def test_failed_row_without_failure_kind_is_rejected(self):
        payload = translate_openrouter_receipt(
            _receipt(FAILED_FIXTURE), **TRANSLATE_ARGS,
        )
        payload.pop("failure_kind")
        with self.assertRaises(ValueError):
            translate_pipeline_receipts([_envelope(payload)])

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
                        receipt,
                        context=dataclasses.replace(CONTEXT, **override),
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

    def test_kernel_runtime_version_matches_the_plugin_manifest(self):
        """The runtime version is a fourth place the kernel version lives.

        Pinning a literal here meant the suite enforced the stale value: the
        manifests moved to 0.10.0 and this test kept 0.9.0 green. Read the
        manifest instead so the assertion cannot drift away from it.
        """
        import json
        import pathlib
        manifest = json.loads((
            pathlib.Path(__file__).parent.parent
            / "plugins/workflow-kernel/.claude-plugin/plugin.json"
        ).read_text())
        self.assertEqual(_kernel_version_string(), manifest["version"])
        self.assertEqual(
            KERNEL_VERSION,
            tuple(int(part) for part in manifest["version"].split(".")),
        )


class OpenRouterUsageAppendTests(unittest.TestCase):
    """The executable half of the emission boundary."""

    def _run(self, args):
        import sys
        old = sys.argv
        sys.argv = ["workflow_kernel"] + args
        try:
            from workflow_kernel.cli import main
            try:
                return main() or 0
            except SystemExit as exc:
                return exc.code or 0
        finally:
            sys.argv = old

    def _base(self, receipts_path, lane, chunk, fixture=None):
        return [
            "openrouter-usage",
            "--receipt", str(fixture or SUCCESS_FIXTURE),
            "--lane", lane, "--chunk-id", chunk, "--node-id", chunk,
            "--attempt", "1", "--host", "claude", "--duration-seconds", "3.5",
            "--append-to", receipts_path,
            "--run-id", "run-append-1",
            "--occurred-at", "2026-08-07T04:05:06+00:00",
            "--authoritative-receipt", "receipts/lane-" + lane + ".json",
        ]

    def test_append_creates_then_extends_the_receipt_stream(self):
        import os
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        try:
            self.assertEqual(self._run(self._base(receipts_path, "a", "chunk-a")), 0)
            with open(receipts_path) as f:
                first = json.load(f)
            self.assertEqual(len(first), 1)
            self.assertEqual(first[0]["stage"], "attempt_usage")
            self.assertEqual(first[0]["sequence"], 0)
            self.assertEqual(first[0]["run_id"], "run-append-1")
            self.assertEqual(first[0]["lane"], "a")

            self.assertEqual(self._run(self._base(receipts_path, "b", "chunk-b")), 0)
            with open(receipts_path) as f:
                second = json.load(f)
            self.assertEqual([r["sequence"] for r in second], [0, 1])
            self.assertEqual([r["lane"] for r in second], ["a", "b"])
        finally:
            import shutil
            shutil.rmtree(directory, ignore_errors=True)

    def test_appended_stream_feeds_a_populated_cost_summary(self):
        """The point of the boundary: lanes[] is no longer empty."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        try:
            self._run(self._base(receipts_path, "security", "chunk-a"))
            self._run(self._base(
                receipts_path, "docs", "chunk-b", fixture=FAILED_FIXTURE,
            ))
            with open(receipts_path) as f:
                receipts = json.load(f)
            summary = build_run_cost_summary(translate_pipeline_receipts(receipts))
            validate_run_cost_summary(summary)
            self.assertEqual(len(summary["lanes"]), 2)
            sources = {row["lane"]: row["measurement_source"] for row in summary["lanes"]}
            self.assertEqual(sources["security"], "openrouter_api_receipt")
            self.assertEqual(sources["docs"], "openrouter_receipt_failed")
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_append_accepts_a_dm_review_receipt_stream(self):
        """The documented `--append-to` wiring for seven of the eleven consumers.

        The append path validated the updated stream with the pipeline adapter
        alone, so every dm-review stream was rejected with "unknown receipt
        stage" -- the measurement boundary could not be wired for the consumer
        the branch was written for. Every other reader of a receipt stream in
        cli.py already tried both adapters; only this one did not, and the
        existing tests all appended onto fresh pipeline-style streams so
        nothing caught it.
        """
        import json as _json
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        try:
            review_stream = [
                {
                    "run_id": "run-append-1", "sequence": 0,
                    "stage": "review_request", "status": "accepted",
                    "node_id": None, "occurred_at": "2026-08-07T00:00:00Z",
                    "authoritative_receipt": "receipts/review/request.json",
                    "host": "claude", "workflow_class": "feature",
                    "workflow_class_defaulted": True,
                    "requested_lanes": ["security-auditor-codex-signoff"],
                },
                {
                    "run_id": "run-append-1", "sequence": 1,
                    "stage": "review_dispatch", "status": "dispatched",
                    "node_id": "security-auditor-codex-signoff",
                    "occurred_at": "2026-08-07T00:01:00Z",
                    "authoritative_receipt": "receipts/review/dispatch.json",
                    "host": "claude", "requested_executor": "codex",
                    "attempted_executor": "codex", "implemented_by": "codex",
                    "attempt": 1,
                },
            ]
            with open(receipts_path, "w") as f:
                _json.dump(review_stream, f)

            self.assertEqual(
                self._run(self._base(receipts_path, "security", "chunk-a")), 0,
            )
            with open(receipts_path) as f:
                updated = _json.load(f)
            self.assertEqual(len(updated), 3)
            self.assertEqual(updated[-1]["stage"], "attempt_usage")
            self.assertEqual(updated[-1]["sequence"], 2)
            # The pre-existing review receipts are untouched.
            self.assertEqual(updated[0]["stage"], "review_request")
            self.assertEqual(updated[1]["stage"], "review_dispatch")
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_append_rejects_a_timestamp_that_is_not_iso_8601(self):
        """The contract says `--occurred-at <ISO-8601>` and nothing enforced it,
        so any non-empty string became durable evidence verbatim."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        try:
            for stamp in ("yesterday", "2026-08-07", "2026-08-07T06:10:00"):
                with self.subTest(occurred_at=stamp):
                    argv = self._base(receipts_path, "a", "chunk-a")
                    for index, item in enumerate(argv):
                        if item == "--occurred-at":
                            argv[index + 1] = stamp
                    self.assertNotEqual(self._run(argv), 0)
            self.assertFalse(os.path.exists(receipts_path))
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_append_refuses_a_symlinked_receipts_directory(self):
        """The ledger write path had no symlink preflight, while the emission
        command that reads the same directory did. One leftover symlink and the
        evidence ledger -- plus its lock file -- lands outside the run."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp(dir=os.getcwd())
        try:
            outside = os.path.join(directory, "outside")
            os.mkdir(outside)
            os.symlink(outside, os.path.join(directory, "workflow-kernel"))
            receipts_path = os.path.join(
                directory, "workflow-kernel", "authoritative-receipts.json",
            )
            self.assertNotEqual(
                self._run(self._base(receipts_path, "a", "chunk-a")), 0,
            )
            self.assertEqual(os.listdir(outside), [])
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_append_still_rejects_a_stream_neither_adapter_accepts(self):
        """Falling back to the review adapter must not become "accept
        anything". A stream that no adapter can read is still refused."""
        import json as _json
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        try:
            with open(receipts_path, "w") as f:
                _json.dump([{"stage": "not-a-real-stage", "sequence": 0}], f)
            self.assertNotEqual(
                self._run(self._base(receipts_path, "security", "chunk-a")), 0,
            )
            # The refused append left the original stream in place.
            with open(receipts_path) as f:
                self.assertEqual(len(_json.load(f)), 1)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_append_requires_the_envelope_flags(self):
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        try:
            for drop in ("--run-id", "--occurred-at", "--authoritative-receipt"):
                with self.subTest(missing=drop):
                    args = self._base(receipts_path, "a", "chunk-a")
                    index = args.index(drop)
                    del args[index:index + 2]
                    self.assertNotEqual(self._run(args), 0)
                    self.assertFalse(os.path.exists(receipts_path))
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_append_and_output_are_mutually_exclusive(self):
        """Appending is a durable ledger mutation; --output is not.

        If --output failed after a successful append, the command would report
        failure over an already-recorded attempt and a retry would append it
        twice. Refuse the combination rather than document a commit order.
        """
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        output_path = os.path.join(directory, "payload.json")
        try:
            args = self._base(receipts_path, "a", "chunk-a")
            args += ["--output", output_path]
            self.assertNotEqual(self._run(args), 0)
            self.assertFalse(os.path.exists(receipts_path))
            self.assertFalse(os.path.exists(output_path))
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_concurrent_appends_do_not_lose_an_attempt(self):
        """Lane attempts finish concurrently; a lost update loses a
        measurement. The append holds an exclusive lock across load, validate,
        and replace, so sequences stay contiguous and no row is discarded."""
        import os
        import shutil
        import subprocess
        import sys
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        module_root = os.path.join(
            repo_root,
            "plugins/workflow-kernel/skills/workflow-kernel/references",
        )
        env = dict(os.environ, PYTHONPATH=module_root)
        try:
            processes = [
                subprocess.Popen(
                    [sys.executable, "-m", "workflow_kernel"]
                    + self._base(receipts_path, "lane-%d" % index, "chunk-%d" % index),
                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                for index in range(4)
            ]
            for process in processes:
                self.assertEqual(process.wait(timeout=120), 0)
            with open(receipts_path) as f:
                receipts = json.load(f)
            self.assertEqual(len(receipts), 4)
            self.assertEqual(
                [entry["sequence"] for entry in receipts], [0, 1, 2, 3],
            )
            self.assertEqual(
                sorted(entry["lane"] for entry in receipts),
                ["lane-0", "lane-1", "lane-2", "lane-3"],
            )
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_append_rejects_a_non_array_target(self):
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts_path = os.path.join(directory, "authoritative-receipts.json")
        with open(receipts_path, "w") as f:
            f.write('{"not": "an array"}')
        try:
            self.assertNotEqual(
                self._run(self._base(receipts_path, "a", "chunk-a")), 0,
            )
            with open(receipts_path) as f:
                self.assertEqual(json.load(f), {"not": "an array"})
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_cli_rejects_a_receipt_with_no_outcome(self):
        """A schemaVersion-2 receipt that cannot state its outcome is
        malformed. Defaulting either way would either mask real failures or
        invent failures that never happened."""
        import json as _json
        import os
        import tempfile

        receipt = _json.loads(SUCCESS_FIXTURE.read_text())
        del receipt["outcome"]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            _json.dump(receipt, f)
            path = f.name
        try:
            code = self._run([
                "openrouter-usage", "--receipt", path,
                "--lane", "a", "--chunk-id", "c", "--node-id", "c",
                "--attempt", "1", "--host", "claude", "--duration-seconds", "1.0",
            ])
            self.assertNotEqual(code, 0)
        finally:
            os.unlink(path)


class OpenRouterUsageCliTests(unittest.TestCase):
    def test_cli_success_stdout_when_no_output(self):
        code, stdout, _ = _invoke(_cli_args(SUCCESS_FIXTURE))
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["measurement_source"], "openrouter_api_receipt")
        self.assertEqual(payload["provider"], "Modal")
        self.assertEqual(payload["usage_count"], 88239)

    def test_cli_failure_receipt_exits_zero(self):
        code, stdout, _ = _invoke(_cli_args(FAILED_FIXTURE))
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(
            set(payload),
            BASE_KEYS | {"failure_kind", "identity_provenance"},
        )
        self.assertEqual(
            payload["measurement_source"], "openrouter_receipt_failed",
        )
        self.assertEqual(payload["failure_kind"], "incomplete_stream")

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


class RecordAttemptTests(unittest.TestCase):
    """`record-attempt` is the mechanism that replaced the prose obligation.

    Recording a lane and recording its measurement used to be two calls, the
    second of which lived only in documentation. These tests pin the property
    that made it a mechanism: there is no way to record a lane without also
    recording a usage row for it.
    """

    def _argv(self, receipts, lane, minute, **extra):
        argv = [
            "record-attempt",
            "--receipts", str(receipts),
            "--run-id", "record-attempt-1",
            "--occurred-at", "2026-08-07T09:%02d:00Z" % minute,
            "--authoritative-receipt", "receipts/%s.json" % lane,
            "--stage", "review_dispatch", "--status", "completed",
            "--lane", lane, "--chunk-id", "chunk-a", "--node-id", lane,
            "--attempt", "1", "--host", "claude",
            "--duration-seconds", "5.0",
            "--requested-executor", "codex",
            "--attempted-executor", "openrouter",
            "--implemented-by", "openrouter",
        ]
        for flag, value in extra.items():
            argv += ["--" + flag.replace("_", "-"), str(value)]
        return argv

    def _stream(self, path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def test_every_recorded_lane_carries_a_usage_row(self):
        """The whole point. Three evidence paths, no unpaired lane."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts = os.path.join(directory, "authoritative-receipts.json")
        try:
            code, _, err = _invoke(self._argv(
                receipts, "security", 1,
                openrouter_receipt=SUCCESS_FIXTURE,
            ))
            self.assertEqual(code, 0, err)
            code, _, err = _invoke(self._argv(
                receipts, "docs", 2,
                agent_definition=FIXTURES / "lane-bytes" / "agent-definition.md",
                diff=FIXTURES / "lane-bytes" / "diff.patch",
                provider="anthropic", model="opus",
            ))
            self.assertEqual(code, 0, err)
            # No evidence at all -- the case that used to produce no row.
            code, _, err = _invoke(self._argv(receipts, "architecture", 3))
            self.assertEqual(code, 0, err)

            stream = self._stream(receipts)
            recorded = {
                r["lane"] for r in stream if r["stage"] == "review_dispatch"
            }
            measured = {
                r["lane"] for r in stream if r["stage"] == "attempt_usage"
            }
            self.assertEqual(recorded, {"security", "docs", "architecture"})
            self.assertEqual(recorded - measured, set())
            sources = {
                r["lane"]: r["measurement_source"]
                for r in stream if r["stage"] == "attempt_usage"
            }
            self.assertEqual(sources["security"], "openrouter_api_receipt")
            self.assertEqual(sources["docs"], "estimated_input_bytes")
            self.assertEqual(sources["architecture"], "attempt_unmeasured")
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_unmeasured_lane_still_reaches_the_cost_summary(self):
        """An `attempt_unmeasured` row is a claim, not a gap. It must survive
        translation and appear as a lane the reader can see and question."""
        import os
        import shutil
        import tempfile

        from workflow_kernel.cost_summary import validate_run_cost_summary
        from workflow_kernel.dm_review_adapter import translate_review_receipts

        directory = tempfile.mkdtemp()
        receipts = os.path.join(directory, "authoritative-receipts.json")
        try:
            _invoke(self._argv(receipts, "architecture", 1))
            summary = build_run_cost_summary(
                translate_review_receipts(self._stream(receipts))
            )
            validate_run_cost_summary(summary)
            (lane,) = summary["lanes"]
            self.assertEqual(lane["lane"], "architecture")
            self.assertEqual(lane["measurement_source"], "attempt_unmeasured")
            self.assertIsNone(lane["cost_usd"])
            self.assertIsNone(lane["usage_count"])
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_a_rejected_measurement_appends_neither_receipt(self):
        """Both receipts land or neither does. A lane receipt written beside a
        failed measurement would be the unpaired state this command exists to
        make unrepresentable."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts = os.path.join(directory, "authoritative-receipts.json")
        bad = os.path.join(directory, "not-a-receipt.json")
        with open(bad, "w", encoding="utf-8") as handle:
            handle.write("[]")
        try:
            code, _, _ = _invoke(self._argv(
                receipts, "security", 1, openrouter_receipt=bad,
            ))
            self.assertNotEqual(code, 0)
            self.assertFalse(os.path.exists(receipts))
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_sequences_stay_contiguous_across_paired_appends(self):
        """Two receipts per call still means one contiguous sequence."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        receipts = os.path.join(directory, "authoritative-receipts.json")
        try:
            for index, lane in enumerate(("a", "b", "c"), start=1):
                _invoke(self._argv(receipts, lane, index))
            stream = self._stream(receipts)
            self.assertEqual(
                [r["sequence"] for r in stream], list(range(len(stream))),
            )
            self.assertEqual(len(stream), 6)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_refuses_a_symlinked_receipt_stream(self):
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp(dir=os.getcwd())
        try:
            outside = os.path.join(directory, "outside")
            os.mkdir(outside)
            os.symlink(outside, os.path.join(directory, "workflow-kernel"))
            receipts = os.path.join(
                directory, "workflow-kernel", "authoritative-receipts.json",
            )
            code, _, _ = _invoke(self._argv(receipts, "security", 1))
            self.assertNotEqual(code, 0)
            self.assertEqual(os.listdir(outside), [])
        finally:
            shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
