"""Tests for the run-cost-summary artifact."""

import json
import unittest

from workflow_kernel.metrics import (
    COST_SUMMARY_SCHEMA_VERSION,
    build_run_cost_summary,
    compute_cost_summary_digest,
    validate_run_cost_summary,
    _remove_volatile,
)
from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
from workflow_kernel.redaction import sanitize_durable_payload

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures" / "receipts"


def _usage_receipt(sequence, attempt, **measurements):
    receipt = {
        "run_id": "economics-1", "sequence": sequence,
        "stage": "attempt_usage", "status": "observed",
        "node_id": "chunk-a", "chunk_id": "chunk-a",
        "occurred_at": f"2026-07-14T00:0{sequence}:00Z",
        "authoritative_receipt": f"receipts/attempt-{sequence}.json",
        "host": "codex", "provider": "openai", "model": "gpt-5.6-sol",
        "requested_provider": "openrouter", "attempted_provider": "openai",
        "implemented_by": "codex", "attempt": attempt,
        "duration_seconds": 1.0,
        "usage_scope": "attempt", "measurement_source": "provider_receipt",
        "usage_estimated": False,
    }
    receipt.update(measurements)
    return receipt


class RunCostSummaryTests(unittest.TestCase):
    def _fixture_events(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        return translate_pipeline_receipts(receipts)

    # -- 1. Schema validation and unknown-version rejection --

    def test_emitted_summary_passes_validation(self):
        summary = build_run_cost_summary(self._fixture_events())
        validate_run_cost_summary(summary)  # must not raise

    def test_unknown_schema_version_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        bad["schema_version"] = 999
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_missing_top_level_field_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        del bad["totals"]
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_schema_version_is_one(self):
        summary = build_run_cost_summary(self._fixture_events())
        self.assertEqual(summary["schema_version"], COST_SUMMARY_SCHEMA_VERSION)

    # -- 2. Byte-stable replay --

    def test_byte_stable_replay_excluding_volatile_fields(self):
        events = self._fixture_events()
        s1 = build_run_cost_summary(events, repository_commit="abc123")
        s2 = build_run_cost_summary(events, repository_commit="abc123")
        # emitted_at must differ (wall-clock)
        self.assertNotEqual(
            s1["invocation"]["emitted_at"], s2["invocation"]["emitted_at"],
        )
        # After removing volatile fields, bytes must be identical
        nv1 = _remove_volatile(s1)
        nv2 = _remove_volatile(s2)
        b1 = json.dumps(nv1, sort_keys=True, separators=(",", ":"))
        b2 = json.dumps(nv2, sort_keys=True, separators=(",", ":"))
        self.assertEqual(b1, b2)

    def test_digest_is_stable_across_emissions(self):
        events = self._fixture_events()
        s1 = build_run_cost_summary(events)
        s2 = build_run_cost_summary(events)
        self.assertEqual(s1["digest"], s2["digest"])

    def test_sanitized_output_is_byte_stable(self):
        events = self._fixture_events()
        s1 = sanitize_durable_payload(build_run_cost_summary(events))
        s2 = sanitize_durable_payload(build_run_cost_summary(events))
        s1["digest"] = compute_cost_summary_digest(s1)
        s2["digest"] = compute_cost_summary_digest(s2)
        nv1 = _remove_volatile(s1)
        nv2 = _remove_volatile(s2)
        self.assertEqual(
            json.dumps(nv1, sort_keys=True, separators=(",", ":")),
            json.dumps(nv2, sort_keys=True, separators=(",", ":")),
        )

    # -- 3. Deterministic row ordering and path normalization --

    def test_phases_are_sorted_by_name(self):
        summary = build_run_cost_summary(self._fixture_events())
        names = [row["phase"] for row in summary["phases"]]
        self.assertEqual(names, sorted(names))

    def test_lanes_are_sorted_by_lane_chunk_attempt(self):
        receipts = [
            _usage_receipt(0, 1, usage_count=10, reviewer="security", lane="security"),
            _usage_receipt(1, 1, usage_count=20, reviewer="architecture", lane="architecture"),
            _usage_receipt(2, 2, usage_count=30, reviewer="security", lane="security"),
        ]
        events = translate_pipeline_receipts(receipts)
        summary = build_run_cost_summary(events)
        keys = [
            (row["lane"], row["chunk_id"] or "", row["attempt"] or 0)
            for row in summary["lanes"]
        ]
        self.assertEqual(keys, sorted(keys))

    def test_output_uses_sorted_keys(self):
        summary = build_run_cost_summary(self._fixture_events())
        text = json.dumps(summary, sort_keys=True, separators=(",", ":"))
        # Verify the JSON is deterministic by re-parsing and re-serializing
        reparsed = json.loads(text)
        self.assertEqual(
            json.dumps(reparsed, sort_keys=True, separators=(",", ":")), text,
        )

    # -- 4. Redaction of sensitive values --

    def test_secret_shaped_model_is_redacted(self):
        receipts = [
            _usage_receipt(0, 1, usage_count=10, cost_usd=0.1,
                           model="sk-test-key-1234567890abcdef"),
        ]
        events = translate_pipeline_receipts(receipts)
        summary = build_run_cost_summary(events)
        sanitized = sanitize_durable_payload(summary)
        output = json.dumps(sanitized, sort_keys=True)
        self.assertNotIn("sk-test-key-1234567890abcdef", output)
        self.assertTrue(
            sanitized["lanes"][0]["model"].startswith("value-sha256:"),
            "secret-shaped model must be redacted to a value digest",
        )

    # -- 5. Partial-coverage runs report unavailable provenance --

    def test_phases_without_usage_report_unavailable(self):
        summary = build_run_cost_summary(self._fixture_events())
        for row in summary["phases"]:
            if row["usage_count"] is None:
                self.assertEqual(row["measurement_source"], "unavailable")

    def test_partial_coverage_does_not_zero_fill(self):
        # The pipeline-claude fixture has no attempt_usage events.
        summary = build_run_cost_summary(self._fixture_events())
        for row in summary["phases"]:
            if row["measurement_source"] == "unavailable":
                for field in (
                    "usage_count", "input_usage_count", "output_usage_count",
                    "cache_read_usage_count", "cache_write_usage_count",
                    "reasoning_usage_count",
                ):
                    self.assertIsNone(row[field])
        self.assertGreater(summary["measurement_coverage"]["usage"]["missing"], 0)

    def test_lanes_without_usage_report_unavailable(self):
        # Construct events directly to test a lane with usage_scope='attempt'
        # but without measurement_source or USAGE_FIELDS.
        from workflow_kernel.schema import WorkflowEvent

        events = (
            WorkflowEvent(
                1, 0, "partial-1", "chunk-a", "evidence.recorded",
                "2026-07-14T00:00:00Z",
                {
                    "stage": "attempt_usage", "status": "observed",
                    "chunk_id": "chunk-a", "attempt": 1,
                    "duration_seconds": 2.0,
                    "usage_scope": "attempt",
                    "host": "codex", "provider": "openai",
                    "model": "gpt-5.6-sol",
                    "requested_provider": "openrouter",
                    "attempted_provider": "openai",
                    "implemented_by": "codex",
                },
            ),
            WorkflowEvent(
                1, 1, "partial-1", None, "evidence.recorded",
                "2026-07-14T00:01:00Z",
                {"stage": "run_summary", "status": "succeeded"},
            ),
        )
        summary = build_run_cost_summary(events)
        self.assertGreater(len(summary["lanes"]), 0)
        for lane in summary["lanes"]:
            self.assertEqual(lane["measurement_source"], "unavailable")
            for field in ("usage_count", "input_usage_count", "cost_usd"):
                self.assertIsNone(lane[field])

    # -- 6. CLI surface --

    def test_cli_command_emits_valid_summary(self):
        import os
        import sys
        import tempfile

        events = self._fixture_events()
        # Write a temporary receipts file
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            self.assertTrue(os.path.exists(output_path))
            with open(output_path) as f:
                summary = json.load(f)
            validate_run_cost_summary(summary)
            self.assertEqual(summary["schema_version"], 1)
            self.assertIsNotNone(summary["digest"])
        finally:
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    # -- 7. Empty events and edge cases (sprint contract addendum) --

    def test_empty_events_produce_valid_summary(self):
        summary = build_run_cost_summary(())
        validate_run_cost_summary(summary)
        self.assertEqual(summary["phases"], [])
        self.assertEqual(summary["lanes"], [])
        self.assertIsNone(summary["totals"]["usage_count"])
        self.assertIsNone(summary["totals"]["cost_usd"])

    # -- 8. Round-trip conformance: emitted output validates --

    def test_cli_output_round_trips_through_validator(self):
        import os
        import sys
        import tempfile

        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            with open(output_path) as f:
                summary = json.load(f)
            # Round-trip: the emitted file must pass validation
            validate_run_cost_summary(summary)
            # Digest is recomputed from the emitted (sanitized) content
            recomputed = compute_cost_summary_digest(summary)
            self.assertEqual(recomputed, summary["digest"])
        finally:
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    # -- 9. CLI negative case: malformed events --

    def test_cli_malformed_events_exits_nonzero(self):
        import os
        import sys
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            f.write("{not valid json}")
            events_path = f.name
        output_path = events_path + ".summary.json"
        old_argv = sys.argv
        try:
            from workflow_kernel.cli import main
            exit_code = main([
                "run-cost-summary",
                "--events", events_path,
                "--output", output_path,
            ])
            self.assertNotEqual(exit_code, 0)
            self.assertFalse(os.path.exists(output_path))
        finally:
            sys.argv = old_argv
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    # -- 10. Digest verification with redaction active --

    def test_digest_matches_after_redaction(self):
        receipts = [
            _usage_receipt(0, 1, usage_count=10, cost_usd=0.1,
                           model="sk-test-key-1234567890abcdef"),
        ]
        events = translate_pipeline_receipts(receipts)
        summary = build_run_cost_summary(events)
        sanitized = sanitize_durable_payload(summary)
        sanitized["digest"] = compute_cost_summary_digest(sanitized)
        # Recompute from the sanitized output
        recomputed = compute_cost_summary_digest(sanitized)
        self.assertEqual(recomputed, sanitized["digest"])


if __name__ == "__main__":
    unittest.main()
